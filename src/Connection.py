import logging, socket, signal, sys, time, random, thread, struct
from threading import Thread

from PacketManager import *
from Configuration import *
from FileSystem import *
# TODO remove unneeded imports

TXCONTROLTYPE = {'SENDTIME':1, 'OSENDTIME':2, 'SENDWIN':3}
RAWTXCONTROLTYPE = {1:'SENDTIME', 2:'OSENDTIME', 3:'SENDWIN'}

class debugmeta(type):
    send_r_process_time = 0.0
    send_unr_process_time = 0.0
    receive_process_time = 0.0
    measure_process_time = 0.0

    def getTotal(cls):
        return cls.send_r_process_time + cls.send_unr_process_time + \
            cls.receive_process_time + cls.measure_process_time

    def getSendRPer(cls):
        return cls.send_r_process_time / cls.getTotal() * 100.0

    def getSendURPer(cls):
        return cls.send_unr_process_time / cls.getTotal() * 100.0

    def getRecPer(cls):
        return cls.receive_process_time / cls.getTotal() * 100.0

    def getMeaPer(cls):
        return cls.measure_process_time / cls.getTotal() * 100.0

    def __str__(cls):
        return 'sr %.2f %%, sur %.2f %%, r %.2f %%, m %.2f %%' % (cls.getSendRPer(), cls.getSendURPer(),
            cls.getRecPer(), cls.getMeaPer())

    def __repr__(cls):
        return 'Connection.debug, sr %.2f %%, sur %.2f %%, r %.2f %%, m %.2f %%' % \
            (cls.getSendRPer(), cls.getSendURPer(),
            cls.getRecPer(), cls.getMeaPer())

class debug:
    __metaclass__ = debugmeta


# This class is a parent class for all connections, signal or data.
# It provides flow control, security, authentication, and/or congestion control if needed.
class Connection:

    class CongState:
        slow_start = 0
        cong_avoid = 1

    max_seq = int("FFFF", 16)
    max_session_id = int("FF", 16)
    max_user_id = int("FF", 16)
    max_resend_time = 10.0    # Max resend time in secs
    init_rtt = 1.0 # Initial RTT in secs
    rto_mean_rtts = 5 # RTO is a mean of these * rto_times_rtt
    rto_times_rtt = 3 # RT= is rto_mean_rtts * rto_times_rtt
    max_local_send_window = 100
    cong_avoid_drop = 0.8

    # TODO check initializations
    # TODO change server to jsut sock for Connection object
    def __init__(self, sock, remote_ip, remote_port, local_session_id, remote_session_id = 0,
            version = 1, send_ack_no = random.randint(0, max_seq-1),
            seq_no = random.randint(0, max_seq-1),
            rtt = init_rtt, logger_str = "Connection to", local_cong_window = 10, remote_window = 10):
        self.sock = sock     # Pointer to server socket
        self.version = version
        self.remote_ip = remote_ip
        self.remote_port = remote_port
        self.seq_no = seq_no
        self.send_ack_no = send_ack_no
        self.recv_ack_no = 0
        self.local_send_window = self.max_local_send_window
        self.remote_send_window = remote_window
        self.local_session_id = local_session_id
        self.remote_session_id = remote_session_id
        self.remote_send_time = 0.0
        self.remote_send_time_receive_time = 0.0
        self.unack_queue = RingBuffer(self.max_local_send_window)    # Queue of sent, but unacked packets
        self.sync = thread.allocate_lock()
        self.resends = 0

        logger_str += str(self.remote_ip) + ':' + str(self.remote_port)
        self.logger = logging.getLogger(logger_str)
        self.logger.info("Initializing connection to %s:%i at %s" % (self.remote_ip, self.remote_port, str(time.time())))

        self.rtt_buffer = RingBuffer(self.rto_mean_rtts)
        self.__setRtt__(rtt)
        self.rto = self.rtt * self.rto_times_rtt
        self.rtt_mean = rtt
        self.resend_timer = None
        self.resend_timer_lock = thread.allocate_lock() # Synchronization for resend timer handling

        self.resend_send_ack = False

        self.cong_state = Connection.CongState.slow_start
        self.local_cong_window = local_cong_window
        self.last_packet_recv_time = -1 # Last time a packet was received

    def receive_packet_start(self, packet):
        start = time.time()
        self.sync.acquire()
        self.resends = 0

        if not wrapped_is_greater(packet.sequence, self.send_ack_no, self.max_seq) \
                and packet.sequence != Connection.max_seq:
	        self.resend_send_ack = True
#	else:
#		print("resend_send_ack=false")
        if packet.sequence != Connection.max_seq and \
                packet.sequence == wrapped_plus(self.send_ack_no, 1, Connection.max_seq):
                # Max seq reserved for unreliable transfer.
            # TODO We should not require packets to arrive in order.
            self.logger.debug("Expecting %d, got %d" % (wrapped_plus(self.send_ack_no, 1, Connection.max_seq),
                packet.sequence)) #self.logger.debug(
            self.send_ack_no = packet.sequence
            ret = True
        else:
            self.logger.debug("Expecting %d, got %d" % (wrapped_plus(self.send_ack_no, 1, Connection.max_seq),
                packet.sequence))
            ret = False

        if self.cong_state == Connection.CongState.slow_start:
            self.local_cong_win_plus(1)
            self.logger.debug('Slow start: Congestion window increased to %d' % self.local_cong_window)
        elif self.cong_state == Connection.CongState.cong_avoid and self.last_packet_recv_time > 0 and \
                time.time() - self.last_packet_recv_time > self.rtt_mean:
            self.local_cong_win_plus(1)
            self.logger.debug('Cong avoid: Congestion window increased to %d' % self.local_cong_window)
            self.last_packet_recv_time = time.time()
        elif self.last_packet_recv_time < 0:
            self.last_packet_recv_time = time.time()

        #print packet.sequence
        self.recv_ack_no = packet.ack
        
        control_tlvs = packet.get_TLVlist(tlvtype = 'TXCONTROL')
        
        if len(control_tlvs) == 0:
            self.logger.debug("No control tlvs")
            

        # Read control data
        for item in control_tlvs:
            t = struct.unpack('i', item[:4])[0]
            if t == TXCONTROLTYPE['SENDWIN']:
                # Send window
                self.remote_send_window = struct.unpack('ii', item)[1]
                self.logger.debug("remote send window updated to: %d" % self.remote_send_window)
            elif t == TXCONTROLTYPE['SENDTIME']:
                # Remote send time
                self.remote_send_time = struct.unpack('id', item)[1]
                self.remote_send_time_receive_time = time.time()
                self.logger.debug("remote send time set to: %f" % self.remote_send_time)
            elif t == TXCONTROLTYPE['OSENDTIME']:
                # Local send time and remote processing time
                i, loc_s_time, pros_time = struct.unpack('idd', item)
                self.__setRtt__(time.time() - loc_s_time - pros_time)
                self.logger.debug("rtt set to: %f, loc %f, pros %f" % (self.rtt, loc_s_time, pros_time))
            else:
                self.logger.error("Invalid control message: %i" % t)
        

        self.logger.debug("ack no: %d, packets in unack queue before packet: %d, seq nos: %s" % \
            (self.recv_ack_no, self.unack_queue.getSize(), [unack_packet.sequence for unack_packet in \
            self.unack_queue.get() if unack_packet != None]))
        
        # Remove acked packets from unack queue.
        #self.unack_queue.get()[:] = [sent_packet for sent_packet in self.unack_queue.get() if not\
        #    ((self.recv_ack_no >= sent_packet.sequence) or \
        #    (sent_packet.sequence >= Connection.max_seq -1000\
        #    and 1000 > self.ack_no)) ]    
        
        unack_packets = self.unack_queue.get()
        for i in range(len(unack_packets)):
        #for sent_packet in self.unack_queue.get():
            sent_packet = unack_packets[i]
            if sent_packet != None and not self.recv_ack_no_is_smaller(sent_packet.sequence):
                self.logger.debug("removing seq %d" % sent_packet.sequence)
                unack_packets[i] = None

        self.local_send_window = self.max_local_send_window - self.unack_queue.getSize()
        self.logger.debug("packets in unack queue after packet: %d, seq nos: %s" % \
            (self.unack_queue.getSize(), [unack_packet.sequence for unack_packet in \
            self.unack_queue.get() if unack_packet != None]))
        oldest = self.unack_queue.get_oldest()

        # sanity
        if not oldest and self.unack_queue.getSize() != 0:
            self.logger.error("Error in packet reception: oldest packet not found, but packets still in unack queue")
            sys.exit()

        if not oldest:
            self.cancel_resend_timer()
        elif oldest != self.resend_timer.getPacket():
            self.logger.debug("Setting resend timer to %f" % self.rto)
            # TODO Set timer from the current time
            self.reset_resend_timer(self.rto, oldest) 
            
        self.sync.release()
        debug.receive_process_time += time.time() - start
        return ret
        
    def receive_packet_end(self, packet, sender_id):
        if self.resend_send_ack == True:
            # We got new seq but did not ack it
            self.logger.info('Packet processed. Client waiting for ACK, so acking.')
            packet_to_send = OutPacket()
            packet_to_send.create_packet(version=self.version, flags=[], senderID=sender_id,
                txlocalID=self.local_session_id, txremoteID=self.remote_session_id,
                sequence=self.seq_no, ack=self.send_ack_no, otype='UPDATE', ocode='RESPONSE')
            self.send_packet_unreliable(packet_to_send)
    
    def send_packet_reliable(self, packet):
        start = time.time()
        self.sync.acquire()
        if self.local_send_window == 0:
            self.logger.debug('send window full')
            self.sync.release()
            return False
        
        packet.sequence = self.seq_no

        self.__send_out(packet)

        self.seq_no = self.seq_no_plus(1)
        self.logger.debug('seq no set to %d' % self.seq_no)
        if self.unack_queue.getSize() == 0:
            self.reset_resend_timer(self.rto, packet)
            self.logger.debug('unack queue is empty')
        else:
            self.logger.debug('unack queue is not empty')
            #if self.resend_timer.isCancelled():
            #    self.logger.error('resend timer not running altough packets in resend queue, state %s' % self.resend_timer.getState())
            #    exit(0)
        self.logger.debug('%d into send queue' % packet.sequence)
        self.unack_queue.append(packet)
        self.local_send_window = self.max_local_send_window - self.unack_queue.getSize()
        self.logger.debug('Packet sent reliably, packets in queue: %d resend timer state %s, tlvs in packet %d'\
            % (self.unack_queue.getSize(), str(self.resend_timer.getState()), len(packet.TLVs)))
        self.print_resend_timer()
        self.sync.release()
        debug.send_r_process_time += time.time() - start
        return True

    def send_packet_unreliable(self, packet, syn_ack = False):
        start = time.time()
        self.sync.acquire()

        if not syn_ack:
            # ffff marks unreliable packet. Syn_ack should contain seq no though.
            packet.sequence = Connection.max_seq
        else:
            packet.sequence = self.seq_no

        self.__send_out(packet)

        if syn_ack:
            self.seq_no = self.seq_no_plus(1)

        self.logger.debug('Packet sent unreliably')
        self.sync.release()
        debug.send_unr_process_time += time.time() - start
    
    def __send_out(self, packet, resend = False):

        packet.ack = self.send_ack_no
        
        packet.purge_tlvs(ttype = 'TXCONTROL')
        
        # Include send time for RTT measurement
        s_time = time.time()
        #print s_time
        packet.append_entry_to_TLVlist('TXCONTROL', struct.pack('id', TXCONTROLTYPE['SENDTIME'], s_time))

        # Include send window for window management
        packet.append_entry_to_TLVlist('TXCONTROL', struct.pack('ii', TXCONTROLTYPE['SENDWIN'], \
            self.local_send_window))
        
        # Echo send time for RTT measurement
        if self.remote_send_time != 0.0:
            packet.append_entry_to_TLVlist('TXCONTROL', struct.pack('idd', TXCONTROLTYPE['OSENDTIME'], \
                self.remote_send_time, time.time() - self.remote_send_time_receive_time))
            self.remote_send_time = 0.0
            self.remote_send_time_receive_time = 0.0

        self.logger.debug('sending: \n%s' % str(packet))
        
        packet.send_time = time.time()
        self.resend_send_ack = False
#        print(packet)
#       print packet.build_packet()
        self.sock.sendto(packet.build_packet(), (self.remote_ip, self.remote_port), resend, packet.sequence)
    
    def no_ack_timeout(self):
        if not self.unack_queue:
            self.logger.debug('No packets to resend')
            return
        
        for packet in self.unack_queue.get():
            if packet != None:
                self.logger.debug('Resending %d' % packet.sequence)
                self.__send_out(packet, resend = True)
                packet.resends += 1
                self.logger.debug('Resend done, resends %d, tlvs in packet %d' % (self.resends, len(packet.TLVs)))
        self.packet_loss()
        self.resends += 1

    def __setRtt__(self, rtt):
        if rtt >= 0:
            self.rtt_buffer.append(rtt)
            self.rtt = rtt
            self.rtt_mean = sum(self.rtt_buffer.get_no_nones()) / len(self.rtt_buffer.get_no_nones())
            self.rto = self.rto_times_rtt * self.rtt_mean
            self.logger.debug('rto set to %f' % self.rto)
        else:
            self.logger.debug('Invalid RTT: %f. Setting to init RTT.' % rtt)
            self.rtt = Connection.init_rtt
        if self.rtt > 1.0:
            self.logger.debug("RTT set to over 1 second.")

    def packet_loss(self):
        if self.cong_state == Connection.CongState.slow_start:
            self.cong_state = Connection.CongState.cong_avoid
            self.local_cong_window = self.cong_avoid_drop * self.local_cong_window
            self.logger.warning("Slow start: packet loss. cong window: %d" % self.local_cong_window)
        elif self.cong_state == Connection.CongState.cong_avoid:
            self.local_cong_window = self.cong_avoid_drop * self.local_cong_window
            self.logger.warning("Cong avoid: packet loss. cong window: %d" % self.local_cong_window)

    def stop(self):
        self.resend_timer_lock.acquire()
        if self.resend_timer and self.resend_timer.isAlive():
            self.resend_timer.cancel()
        self.resend_timer_lock.release()
            
    def seq_no_plus(self, num):
        # Returns the modulo of the seq no plus num
        return wrapped_plus(self.seq_no, num, self.max_seq)

    def seq_no_minus(self, num):
        # Returns the modulo of the seq no minus num
        return wrapped_minus(self.seq_no, num, self.max_seq)

    def seq_no_is_greater(self, num):
        # Returns the modulo of the seq no minus num
        return wrapped_is_greater(self.seq_no, num, self.max_seq)
        
    def recv_ack_no_is_smaller(self, num):
        # Returns the modulo of the seq no minus num
        return wrapped_is_smaller(self.recv_ack_no, num, self.max_seq)

    def local_cong_win_plus(self, num):
        if self.max_local_send_window >= (self.local_cong_window + num):
            self.local_cong_window += num
        else:
            self.local_cong_window = self.max_local_send_window

    def reset_resend_timer(self, zzz, packet):
        # Creates a new resend timer or resets the existing timer's expire time.
        self.resend_timer_lock.acquire()
        if self.resend_timer != None:
            self.logger.debug('Resetting existing resend timer to %f.' % zzz)
            self.resend_timer.reset(zzz, packet)
        else:
            self.logger.debug('Creating resend timer to %f.' % zzz)
            logger_str = str(self.remote_ip) + ':' + str(self.remote_port)
            self.resend_timer = Connection.ResendTimer(self, logger_str, self.resend_timer_lock, zzz, packet)
            self.resend_timer.start()
        self.resend_timer_lock.release()

    def cancel_resend_timer(self):
        # Cancels the resend timer
        self.resend_timer_lock.acquire()
        if self.resend_timer != None:
            self.resend_timer.cancel()
            self.resend_timer = None
        self.resend_timer_lock.release()

    def print_resend_timer(self):
        # Prints resend timer info
        self.resend_timer_lock.acquire()
        if self.resend_timer != None:
            self.logger.debug(self.resend_timer.str_locked())
        else:
            self.logger.debug('No resend timer.')
        self.resend_timer_lock.release()

    class ResendTimer(Thread):
        ''''Unfortunately there is no class that would offer timer functionality that could work on per thread basis.
        Because of this, we are implementing a class that does what we need. Polling in the master thread would have
        been an alternative, but polling is just too ugly. (Not that this is an especially clean solution either).
        The timer is handled in the functions of the Connection class.'''


        class State:
            # The timer goes to sleep state when started. If the resend time is modified, or the timer is cancelled
            # during the sleel, it will go to reset or cancelled state respectively.
            sleeping = 0
            reset = 1
            cancelled = 2

        def __init__(self, connection, logger_str, sync, zzz, packet):
            Thread.__init__(self)
            self.__connection = connection
            self.__when_to_wake = 0.0
            self.__state = Connection.ResendTimer.State.sleeping

            self.__waiting_for_packet = packet

            self.__sync = sync

            self.logger = logging.getLogger(logger_str + ' resend_timer')
            self.logger.debug("Resend timer created.")

            self.setZzz(zzz)
            self.__when_to_wake = time.time() + self.__zzz

        def run(self):
            # Here be dragons...
            # Sleeps and resends after woken unless cancelled or resetted during sleep.
            # After waking up, doubles the resend timer and sleeps again.
            while True:
                self.__sync.acquire()
                time_to_sleep = self.__when_to_wake - time.time()

                if time_to_sleep < 0:
                   time_to_sleep = 0

                # Sleep
                self.__sync.release()
                time.sleep(time_to_sleep)
                self.__sync.acquire()
            
                if self.__state == Connection.ResendTimer.State.cancelled:
                    # Timer cancelled
                    self.__sync.release()
                    return
                elif self.__state == Connection.ResendTimer.State.reset:
                    # Reset timer and resend
                    self.__state = Connection.ResendTimer.State.sleeping
                    self.__sync.release()
                    continue
                else:
                    # Should resend
                    self.__connection.no_ack_timeout()

                    # Resend again with doubled timeout
                    if self.__connection.resends > 5:
                        self.setZzz(self.__zzz * 2)
                    self.__when_to_wake = time.time() + self.__zzz

                    self.__sync.release()
                    continue
            
    
        def reset(self, zzz, packet):
            # You should hold the lock when coming here.
            self.__waiting_for_packet = packet
            self.setZzz(zzz)
            self.__when_to_wake = time.time() + self.__zzz
            
            self.__state = Connection.ResendTimer.State.reset
    
        def cancel(self):
            # You should hold the lock when coming here.
            self.__state = Connection.ResendTimer.State.cancelled

        def getState(self):
            self.__sync.acquire()
            ret = self.getStateLocked()
            self.__sync.release()
            return ret

        def getStateLocked(self):
            if self.__state == Connection.ResendTimer.State.sleeping:
                return 'sleeping'
            elif self.__state == Connection.ResendTimer.State.cancelled:
                return 'cancelled'
            elif self.__state == Connection.ResendTimer.State.reset:
                return 'reset'
            else:
                self.logger.error("Invalid state.")
                exit()

        def getPacket(self):
            return self.__waiting_for_packet

        def setZzz(self, zzz):
            if zzz > Connection.max_resend_time or zzz <= 0:
                if zzz > Connection.max_resend_time:
                    self.logger.debug("Resend time above max resend time. Setting to max resend time.")
                else:
                    self.logger.debug("Negative resend time provided. Setting to max resend time.")
                self.__zzz = Connection.max_resend_time
            else:
                self.__zzz = zzz


        def __str__(self):
            state = self.getState()
            if state != 'cancelled':
                return 'Resend timer. State: %s, time to wake: %f' % (state, self.__when_to_wake - time.time())
            else:
                return 'Resend timer. State: %s' % state

        def str_locked(self):
            state = self.getStateLocked()
            if state != 'cancelled':
                return 'Resend timer. State: %s, time to wake: %f' % (state, self.__when_to_wake - time.time())
            else:
                return 'Resend timer. State: %s' % state


class RingBuffer:
    def __init__(self, size):
        self.data = [None for i in xrange(size)]

    def append(self, x):
        self.data.pop(0)
        self.data.append(x)

    def get(self):
        return self.data

    def get_no_nones(self):
        return [d for d in self.data if d != None]

    def get_oldest(self):
        for element in self.data:
            if element != None:
                return element
        return None

    def get_latest(self):
        return self.data[len(self.data)-1]
    
    def getSize(self):
        length = 0
        for element in self.data:
            if element != None:
                length += 1
        return length
    
    def set(self, data):
        self.data = data


class LossySocket(object):
    class State:
        loss = 1
        not_lost = 2


    q = 0.0
    p = 0.0
    socket = None
    state = State.not_lost

    bw_measurement_buffer = RingBuffer(100)
    count = 0

    def __init__(self, af_family, protocol, q = 0.0, p = 0.0):
        self.socket = socket.socket(af_family, protocol)
        self.q = q
        self.p = p
        state = LossySocket.State.not_lost

        self.logger = logging.getLogger("LossySocket")
        if p > 1 or q > 1 or p < 0 or q < 0:
            self.logger.error('p and q should be between 0 and 1')
            exit()


    def __getattr__(self, name):
        return getattr(self.socket, name)
    
    def calculate_and_print_bw(self, packet_len, resend):
        # Store bw measurement data as (LossySocket, send time, data len) tuple
        start = time.time()
        LossySocket.bw_measurement_buffer.append((self, time.time(), packet_len, resend))
        bw = 0.0
        packets_sent = 0
        bytes_sent = 0
        resends_in_sec = 0
        for element in LossySocket.bw_measurement_buffer.get():
            if element == None:
                continue
            # We measure per second
            if time.time() - element[1] < 1.0:
                bytes_sent += element[2]
                packets_sent += 1
                if element[3] == True:
                    resends_in_sec += 1

        oldest = LossySocket.bw_measurement_buffer.get_oldest()
        latest = LossySocket.bw_measurement_buffer.get_latest()

        if oldest != None and latest != None:
            if latest[1] - oldest[1]  < 1.0 and oldest[1] != latest[1]:
                send_time = latest[1] - oldest[1]
            else:
                send_time = 1.0
            
            self.count += 1
            if self.count % 1000 == 0:
                self.logger.info("BW: %.2f Mbps, %d pps, ave pkt size: %.2f, resends %d" % \
                    (bytes_sent *8 / send_time /1000000, \
                    float(packets_sent)/send_time,
                    float(bytes_sent) / float(packets_sent),
                    resends_in_sec))
                self.logger.info(str(debug))

        debug.measure_process_time = time.time() - start

    def sendto(self, data, ip_port_tuple, resend = False, seq_no = -1):

        if (self.state == LossySocket.State.not_lost and self.p < random.random()) or \
                                (self.state == LossySocket.State.loss and (1-self.q) > random.random()):
            self.socket.sendto(data, ip_port_tuple)
            self.state = LossySocket.State.not_lost
            self.calculate_and_print_bw(len(data), resend)
            self.logger.debug("data sent %d" % seq_no)
        else:
            self.state = LossySocket.State.loss
            self.logger.debug("simulated loss %d" % seq_no)
            

def wrapped_plus(num1, num2, modulo):
    #print modulo
    return (num1 + num2) % modulo

def wrapped_minus(num1, num2, modulo):
    return (modulo + num1 - num2) % modulo

def wrapped_is_greater(num1, num2, modulo):
    if num1 < 100:
        num1 += modulo
    if num2 < 100:
        num2 += modulo
    return num1 > num2
    
def wrapped_is_smaller(num1, num2, modulo):
    if num1 < 100:
        num1 += modulo
    if num2 < 100:
        num2 += modulo
    return num1 < num2

