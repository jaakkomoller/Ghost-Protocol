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
        return 'sr %.2f %, sur %.2f %, r %.2f %, m %.2f %' % (cls.getSendRPer(), cls.getSendURPer(),
            cls.getRecPer(), cls.getMeaPer())

    def __repr__(cls):
        return 'Connection.debug, sr %.2f %, sur %.2f %, r %.2f %, m %.2f %' % \
            (cls.getSendRPer(), cls.getSendURPer(),
            cls.getRecPer(), cls.getMeaPer())

class debug:
    __metaclass__ = debugmeta


# This class is a parent class for all connections, signal or data.
# It provides flow control, security, authentication, and/or congestion control if needed.
class Connection:

    class State:
        UNCONNECTED = 0
        CONNECTED = 1
        HELLO_SENT = 2
        HELLO_RECVD = 3

    # TODO: move session and user id into SignalConnection
    max_seq = int("FFFF", 16)
    max_session_id = int("FF", 16)
    max_user_id = int("FF", 16)
    max_resend_time = 1.0    # Max resend time in secs
    init_rtt = 1.0 # Initial RTT in secs

    # TODO check initializations
    # TODO change server to jsut sock for Connection object
    def __init__(self, sock, remote_ip, remote_port, local_session_id, remote_session_id = 0,
            version = 1, send_ack_no = random.randint(0, 65534), seq_no = random.randint(0, 65534),
            rtt = init_rtt, logger_str = "Connection to", max_local_send_window = 10, remote_send_window = 10):
        self.sock = sock     # Pointer to server socket
        self.version = version
        self.remote_ip = remote_ip
        self.remote_port = remote_port
        self.seq_no = seq_no
        self.send_ack_no = send_ack_no
        self.recv_ack_no = 0
        self.max_local_send_window = max_local_send_window
        self.local_send_window = max_local_send_window
        self.remote_send_window = remote_send_window
        self.local_session_id = local_session_id
        self.remote_session_id = remote_session_id
        self.state = Connection.State.UNCONNECTED
        self.__setRtt__(rtt)
        self.unack_timer = Connection.NoAckTimer(self)
        self.remote_send_time = 0.0
        self.remote_send_time_receive_time = 0.0
        self.unack_queue = RingBuffer(10)    # Queue of sent, but unacked packets
        self.sync = thread.allocate_lock()
        self.resends = 0
        
        self.logger = logging.getLogger(logger_str + str(self.remote_ip) + ':' + str(self.remote_port))
        self.logger.info("Initializing connection to %s:%i at %s" % (self.remote_ip, self.remote_port, str(time.time())))

        self.resend_send_ack = False

    def receive_packet(self, packet):
        start = time.time()
        self.sync.acquire()
        self.resends = 0

        if packet.sequence <= self.send_ack_no:
            self.resend_send_ack = True

        if packet.sequence != Connection.max_seq and \
                packet.sequence == (self.send_ack_no+1 % Connection.max_seq): # Max seq reserved for unreliable transfer.
            # TODO We should not require packets to arrive in order.
            self.send_ack_no = packet.sequence
            ret = True
        else:
            ret = False

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
                self.remote_send_time = struct.unpack('if', item)[1]
                self.remote_send_time_receive_time = time.time()
                self.logger.debug("remote send time set to: %f" % self.remote_send_time)
            elif t == TXCONTROLTYPE['OSENDTIME']:
                # Local send time and remote processing time
                i, loc_s_time, pros_time = struct.unpack('iff', item)
                self.__setRtt__(time.time() - loc_s_time - pros_time)
                self.logger.debug("rtt set to: %f" % self.rtt)
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
            if sent_packet != None and ((self.recv_ack_no >= sent_packet.sequence) or \
                    (sent_packet.sequence >= Connection.max_seq -1000\
                    and 1000 > self.recv_ack_no)):
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

        if oldest:
            # TODO Set timer from the current time
            self.unack_timer.reset_timer(3*self.rtt, oldest) 
        else:
            self.unack_timer.cancel()
            
        self.sync.release()
        debug.receive_process_time += time.time() - start
        return ret
        
    
    def send_packet_reliable(self, packet):
        start = time.time()
        self.sync.acquire()
        if self.local_send_window == 0:
            self.logger.debug('send window full')
            self.sync.release()
            return False
        
        packet.sequence = self.seq_no

        self.__send_out(packet)

        self.seq_no = (self.seq_no + 1) % Connection.max_seq
        if self.unack_queue.getSize() == 0:
            self.unack_timer.reset_timer(3*self.rtt, packet)
            self.logger.debug('unack queue is empty')
        else:
            self.logger.debug('unack queue is not empty')
            if self.unack_timer.isCancelled():
                self.logger.error('Unack timer not running altough packets in unack queue, state %s' % self.unack_timer.getState())
                exit(0)
        self.unack_queue.append(packet)
        self.local_send_window = self.max_local_send_window - self.unack_queue.getSize()
        self.logger.debug('Packet sent reliably, packets in queue: %d resend timer state %s, tlvs in packet %d'\
            % (self.unack_queue.getSize(), str(self.unack_timer.getState()), len(packet.TLVs)))
        self.sync.release()
        debug.send_r_process_time += time.time() - start
        return True

    def send_packet_unreliable(self, packet):
        start = time.time()
        self.sync.acquire()
        packet.sequence = Connection.max_seq

        self.__send_out(packet)

        self.logger.debug('Packet sent unreliably')
        self.sync.release()
        debug.send_unr_process_time += time.time() - start
    
    def __send_out(self, packet, resend = False):

        packet.ack = self.send_ack_no
        
        packet.purge_tlvs(ttype = 'TXCONTROL')
        
        # Include send time for RTT measurement
        packet.append_entry_to_TLVlist('TXCONTROL', struct.pack('if', TXCONTROLTYPE['SENDTIME'], time.time()))

        # Include send window for window management
        packet.append_entry_to_TLVlist('TXCONTROL', struct.pack('ii', TXCONTROLTYPE['SENDWIN'], \
            self.local_send_window))
        
        # Echo send time for RTT measurement
        if self.remote_send_time != 0.0:
            packet.append_entry_to_TLVlist('TXCONTROL', struct.pack('iff', TXCONTROLTYPE['OSENDTIME'], \
                self.remote_send_time, time.time() - self.remote_send_time_receive_time))
            self.remote_send_time = 0.0
            self.remote_send_time_receive_time = 0.0

        packet.send_time = time.time()
        self.resend_send_ack = False

        self.sock.sendto(packet.build_packet(), (self.remote_ip, self.remote_port), resend)
    
    def no_ack_timeout(self, packet):
        if not self.unack_queue:
            self.logger.debug('No packets to resend')
            return
        
        self.logger.debug('Resending')
        self.__send_out(packet, resend = True)
        self.resends += 1
        packet.resends += 1
        self.logger.debug('Resend done, resends %d, tlvs in packet %d' % (self.resends, len(packet.TLVs)))

    def __setRtt__(self, rtt):
        if rtt >= 0:
            self.rtt = rtt
        else:
            self.logger.debug('Invalid RTT: %f' % rtt)
            self.rtt = Connection.init_rtt

    def stop(self):
        if self.unack_timer and self.unack_timer.isAlive():
            self.unack_timer.stop()
            

    class NoAckTimer(Thread):
        class State:
            not_started = 0
            waiting = 1
            waiting_cancelled = 2
            sleeping = 3
            sleeping_cancelled = 4
            killed = 5

        def __init__(self, connection):
            Thread.__init__(self)
            self.__connection = connection
            self.__when_to_wake = 0.0
            self.__zzz = 0.0
            self.__waiting_for_packet = None    # Packet we are waiting to be acked.
            self.__run_permission = thread.allocate_lock()
            self.__sync = thread.allocate_lock()
            self.__state = Connection.NoAckTimer.State.not_started

        def run(self):
            self.__sync.acquire()
            while True:
                if self.__state != Connection.NoAckTimer.State.waiting_cancelled:
                    self.__state = Connection.NoAckTimer.State.waiting
                self.__sync.release()
                self.__run_permission.acquire()
                self.__sync.acquire()

                if self.__state == Connection.NoAckTimer.State.killed:
                    # Someone killed us
                    self.__sync.release()
                    return
                
                self.__state = Connection.NoAckTimer.State.sleeping

                time_to_sleep = self.__when_to_wake - time.time()
                if time_to_sleep > 0:
                    # Sleep
                    self.__sync.release()
                    time.sleep(time_to_sleep)
                    self.__sync.acquire()
                
                if self.__state == Connection.NoAckTimer.State.killed:
                    # Someone killed us
                    self.__sync.release()
                    return

                if self.__state == Connection.NoAckTimer.State.sleeping_cancelled:
                    # Someone reset or cancelled the timer
                    continue

                if self.__state == Connection.NoAckTimer.State.sleeping:
                    # Resend
                    self.__connection.no_ack_timeout(self.__waiting_for_packet)

                    # Resend again with doubled timeout
                    if self.__connection.resends > 5:
                        self.setZzz(self.__zzz * 2)
                    self.__when_to_wake = time.time() + self.__zzz
                    try:
                        # Might throw an error if lock is already free..
                        self.__run_permission.release()
                    except:
                        pass
            
    
        def reset_timer(self, zzz, packet):
            self.__sync.acquire()
            self.__waiting_for_packet = packet
            self.setZzz(zzz)
            self.__when_to_wake = time.time() + self.__zzz
            if self.__state == Connection.NoAckTimer.State.not_started:
                # Must have not run yet
                # Lock is initially released
                self.start()
            elif self.__state == Connection.NoAckTimer.State.waiting or \
                    self.__state == Connection.NoAckTimer.State.waiting_cancelled:
                # Must be waiting for permission to run
                try:
                    # Might throw an error if lock is already free..
                    self.__run_permission.release()
                except:
                    pass
            elif self.__state == Connection.NoAckTimer.State.sleeping or \
                    self.__state == Connection.NoAckTimer.State.sleeping_cancelled:
                # Must be sleeping
                self.state = Connection.NoAckTimer.State.sleeping_cancelled
                try:
                    # Might throw an error if lock is already free..
                    self.__run_permission.release()
                except:
                    pass
            else:
                print 'invalid state'
                sys.exit(0)
            self.__sync.release()

    
        def cancel(self):
            self.__sync.acquire()
            if self.__state == Connection.NoAckTimer.State.sleeping:
                self.__state = Connection.NoAckTimer.State.sleeping_cancelled
            elif self.__state == Connection.NoAckTimer.State.waiting:
                self.__state = Connection.NoAckTimer.State.waiting_cancelled
            self.__sync.release()

        def kill(self):
            self.__sync.acquire()
            self.__state = Connection.NoAckTimer.State.killed
            try:
                # Might throw an error if lock is already free..
                self.__run_permission.release()
            except:
                pass
            self.__sync.release()

        def getState(self):
            self.__sync.acquire()
            if self.__state == Connection.NoAckTimer.State.not_started:
                self.__sync.release()
                return 'not started'
            elif self.__state == Connection.NoAckTimer.State.waiting:
                self.__sync.release()
                return 'waiting'
            elif self.__state == Connection.NoAckTimer.State.waiting_cancelled:
                self.__sync.release()
                return 'waiting cancelled'
            elif self.__state == Connection.NoAckTimer.State.sleeping:
                self.__sync.release()
                return 'sleeping'
            elif self.__state == Connection.NoAckTimer.State.sleeping_cancelled:
                self.__sync.release()
                return 'sleeping cancelled'
            elif self.__state == Connection.NoAckTimer.State.killed:
                self.__sync.release()
                return 'killed'
            else:
                self.__sync.release()
                return 'invalid state'

        def getPacket(self):
            return self.__waiting_for_packet

        def setZzz(self, zzz):
            if zzz > Connection.max_resend_time:
                self.__zzz = Connection.max_resend_time
            else:
                self.__zzz = zzz

        def isCancelled(self):
            self.__sync.acquire()
            ret = self.__state == Connection.NoAckTimer.State.waiting_cancelled or \
                (self.__state == Connection.NoAckTimer.State.sleeping_cancelled and \
                self.__run_permission.locked()) or \
                self.__state == Connection.NoAckTimer.State.killed
            self.__sync.release()
            return ret

class RingBuffer:
    def __init__(self, size):
        self.data = [None for i in xrange(size)]

    def append(self, x):
        self.data.pop(0)
        self.data.append(x)

    def get(self):
        return self.data

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

    def __init__(self, af_family, protocol, q = 1.0, p = 0.0):
        self.socket = socket.socket(af_family, protocol)
        self.q = q
        self.p = p
        state = LossySocket.State.not_lost

        self.logger = logging.getLogger("LossySocket")

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

    def sendto(self, data, ip_port_tuple, resend = False):

        if (self.state == LossySocket.State.not_lost and self.p < random.random()) or \
                                (self.state == LossySocket.State.loss and self.q > random.random()):
            self.socket.sendto(data, ip_port_tuple)
            self.state = LossySocket.State.not_lost
            self.calculate_and_print_bw(len(data), resend)
#            self.logger.debug("data sent")
        else:
            self.state = LossySocket.State.loss
#            self.logger.debug("simulated loss")
            


