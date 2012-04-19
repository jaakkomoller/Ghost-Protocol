import logging, socket, signal, sys, time, random, thread
from threading import Thread

from PacketManager import *
from Configuration import *
from FileSystem import *
# TODO remove unneeded imports


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
	max_resend_time = 1.0	# Max resend time in secs
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
		self.__setRtt(rtt)
		self.unack_timer = Connection.NoAckTimer(self)
		self.remote_send_time = 0.0
		self.remote_send_time_receive_time = 0.0
		self.unack_queue = RingBuffer(10)	# Queue of sent, but unacked packets
		self.sync = thread.allocate_lock()
		self.resends = 0
		
		self.logger = logging.getLogger(logger_str + str(self.remote_ip) + ':' + str(self.remote_port))
		self.logger.info("Initializing connection to %s:%i at %s" % (self.remote_ip, self.remote_port, str(time.time())))

	def receive_packet(self, packet):
		self.sync.acquire()
		self.resends = 0
		if packet.sequence != Connection.max_seq and \
				packet.sequence == (self.send_ack_no+1 % Connection.max_seq): # Max seq reserved for unreliable transfer.
			# TODO We should not require packets to arrive in order.
			self.send_ack_no = packet.sequence
			ret = True
		else:
			ret = False

		self.recv_ack_no = packet.ack
		
		# Read control data
		for item in packet.get_TLVlist(tlvtype = 'CONTROL'):
			if len(item.split('?')) == 2 and item.split('?')[0] == 'send_win':
				# Send window
				self.remote_send_window = int(item.split('?')[1])
				self.logger.debug("remote send window updated to: %d" % self.remote_send_window)
			if len(item.split('?')) == 2 and item.split('?')[0] == 'send_time':
				# Remote send time
				self.remote_send_time = float(item.split('?')[1])
				self.remote_send_time_receive_time = time.time()
				self.logger.debug("remote send time set to: %f" % self.remote_send_time)
			if len(item.split('?')) == 3 and item.split('?')[0] == 'orig_send_time':
				# Local send time and remote processing time
				self.__setRtt(time.time() - float(item.split('?')[1]) - float(item.split('?')[2]))
				self.logger.debug("rtt set to: %f" % self.rtt)


		self.logger.debug("ack no: %d, packets in unack queue before packet: %d, seq nos: %s" % \
			(self.recv_ack_no, self.unack_queue.getSize(), [unack_packet.sequence for unack_packet in \
			self.unack_queue.get() if unack_packet != None]))
		
		# Remove acked packets from unack queue.
		#self.unack_queue.get()[:] = [sent_packet for sent_packet in self.unack_queue.get() if not\
		#	((self.recv_ack_no >= sent_packet.sequence) or \
		#	(sent_packet.sequence >= Connection.max_seq -1000\
		#	and 1000 > self.ack_no)) ]	
		
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
		return ret
		
	
	def send_packet_reliable(self, packet):
		self.sync.acquire()
		if self.local_send_window == 0:
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
		return True

	def send_packet_unreliable(self, packet):
		self.sync.acquire()
		packet.sequence = Connection.max_seq

		self.__send_out(packet)

		self.logger.debug('Packet sent unreliably')
		self.sync.release()
	
	def __send_out(self, packet, resend = False):

		packet.ack = self.send_ack_no
		
		packet.purge_tlvs(ttype = 'CONTROL')
		
		# Include send time for RTT measurement
		packet.append_entry_to_TLVlist('CONTROL', 'send_time?%f' % time.time())

		# Include send window for window management
		packet.append_entry_to_TLVlist('CONTROL', 'send_win?%d' % self.local_send_window)
		
		# Echo send time for RTT measurement
		if self.remote_send_time != 0.0:
			packet.append_entry_to_TLVlist('CONTROL', 'orig_send_time?%f?%f' % (self.remote_send_time, (time.time() - self.remote_send_time_receive_time)))
			self.remote_send_time = 0.0
			self.remote_send_time_receive_time = 0.0

		packet.send_time = time.time()

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

	def __setRtt(self, rtt):
		if rtt >= 0:
			self.rtt = rtt
		else:
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
			self.__waiting_for_packet = None	# Packet we are waiting to be acked.
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

			self.logger.info("BW: %.2f Mbps, %d pps, ave pkt size: %.2f, resends %d" % \
				(bytes_sent *8 / send_time /1000000, \
				float(packets_sent)/send_time,
				float(bytes_sent) / float(packets_sent),
				resends_in_sec))

	def sendto(self, data, ip_port_tuple, resend = False):

		if (self.state == LossySocket.State.not_lost and self.p < random.random()) or \
                                (self.state == LossySocket.State.loss and self.q > random.random()):
                        self.socket.sendto(data, ip_port_tuple)
                        self.state = LossySocket.State.not_lost
			self.calculate_and_print_bw(len(data), resend)
                else:
                        self.state = LossySocket.State.loss
			


