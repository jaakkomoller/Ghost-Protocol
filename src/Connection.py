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
	init_rtt = 1.0

	# TODO add timers
	sock = None # Pointer to server socket
	version = 1
	remote_ip = None
	remote_port = 0
	seq_no = 0	# Our seq no
	ack_no = 0	# Last seq we have received in order
	recv_ack_no = 0	# What remote side has acked
	max_local_send_window = 10	# Max local window send in packets
	local_send_window = max_local_send_window	# Local window send in packets
	remote_send_window = 10	# Remote send window in packets
	rtt = 0.0		# RTT in seconds
	local_session_id = 0
	remote_session_id = 0
	state = State.UNCONNECTED
	logger = None
	unack_queue = []	# Queue of sent, but unacked packets
	unack_timer = None
	resends = 0

	# TODO check initializations
	# TODO change server to jsut sock for Connection object
	def __init__(self, sock, remote_ip, remote_port, local_session_id, remote_session_id = 0,
			version = 1, seq_no = random.randint(0, 65534), rtt = init_rtt,
			logger_str = "Connection to", max_local_send_window = 10, remote_send_window = 10):
		self.sock = sock     # Pointer to server socket
		self.version = version
		self.remote_ip = remote_ip
		self.remote_port = remote_port
		self.seq_no = seq_no
		self.sent_ack_no = 0
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
		
		self.logger = logging.getLogger(logger_str + str(self.remote_ip) + ':' + str(self.remote_port))
		self.logger.info("Initializing connection to %s:%i at %s" % (self.remote_ip, self.remote_port, str(time.time())))

	def receive_packet(self, packet):
		self.resends = 0
		if packet.sequence != Connection.max_seq and \
				packet.sequence == (self.ack_no+1 % Connection.max_seq): # Max seq reserved for unreliable transfer.
			# TODO We should not require packets to arrive in order.
			self.ack_no = packet.sequence
		
		# Signal send window
		packet.append_entry_to_TLVlist('CONTROL', 'send_win?%d' % self.local_send_window)

		# Read control data
		for item in packet.get_TLVlist(tlvtype = TLVTYPE['CONTROL']):
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


		self.logger.debug("packets in unack queue before packet: %d" % len(self.unack_queue))
		
		# Remove acked packets from unack queue.
		self.unack_queue[:] = [sent_packet for sent_packet in self.unack_queue if \
			(self.ack_no >= sent_packet.sequence) or \
			(sent_packet.sequence >= Connection.max_seq -1000\
			and 1000 > sent_packet.sequence) ]	
		
		self.local_send_window = self.max_local_send_window - len(self.unack_queue)
		self.logger.debug("packets in unack queue after packet: %d" % len(self.unack_queue))
		oldest = None
		for packet_i in self.unack_queue:
			if (packet_i.ack+1) % Connection.max_seq == self.unack_timer.getPacket().sequence:
				# Packet we are waiting for was not acked.
				return
			if oldest:
				oldest_seq_unwrapped = oldest.sequence
			p_seq_unwrapped = packet_i.sequence
			if oldest and oldest.sequence + Connection.max_seq - packet_i.sequence < 2000:
				self.logger.debug("wrap 1")
				# Iterated packet has wrapped 
				oldest_seq_unwrapped = oldest.sequence + Connection.max_seq
			if oldest and packet_i.sequence + Connection.max_seq - oldest.sequence < 2000:
				self.logger.debug("wrap 2")
				# Oldest has wrapped
				p_seq_unwrapped = packet_i.sequence + Connection.max_seq
			if not oldest or p_seq_unwrapped < oldest_seq_unwrapped:
				# Find the oldest packet in unack_queue
				oldest = packet_i

		# sanity
		if not oldest and len(self.unack_queue) != 0:
			self.logger.error("Error in packet reception: oldest packet not found, but packets still in unack queue")
			sys.exit()

		if oldest:
			# TODO Set timer from the current time
			self.unack_timer.reset_timer(3*self.rtt, oldest) 
		else:
			self.unack_timer.cancel()
			
		
	
	def send_packet_reliable(self, packet):
		if self.local_send_window == 0:
			return False
		
		packet.sequence = self.seq_no

		self.__send_out(packet)

		self.seq_no = (self.seq_no + 1) % (Connection.max_seq)
		if not self.unack_queue:
			self.unack_timer.reset_timer(3*self.rtt, packet)
			self.logger.debug('unack queue is empty')
		else:
			self.logger.debug('unack queue is not empty')
			if self.unack_timer.getState() == 'sleeping cancelled':
				self.logger.warning('Unack timer not running altough packets in unack queue')
		self.unack_queue.append(packet)
		self.local_send_window = self.max_local_send_window - len(self.unack_queue)
		self.logger.debug('Packet sent reliably, packets in queue: %d resend timer state %s, tlvs in packet %d'\
			% (len(self.unack_queue), str(self.unack_timer.getState()), len(packet.TLVs)))
		return True

	def send_packet_unreliable(self, packet):
		packet.sequence = Connection.max_seq

		self.__send_out(packet)

		self.logger.debug('Packet sent unreliably')
	
	def __send_out(self, packet, resend = False):

		packet.ack = self.ack_no
		
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

		self.sock.sendto(packet.build_packet(), (self.remote_ip, self.remote_port) )
	
	def no_ack_timeout(self, packet):
		if not self.unack_queue:
			self.logger.debug('No packets to resend')
			return
		
		self.logger.debug('Resending')
		self.__send_out(packet)
		self.resends += 1
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
			sleeping = 2
			sleeping_cancelled = 3
			killed = 4

		def __init__(self, connection):
			Thread.__init__(self)
			self.__connection = connection
			self.__when_to_wake = 0.0
			self.__zzz = 0.0
			self.__waiting_for_packet = None	# Packet we are waiting to be acked.
			self.__run_permission = thread.allocate_lock()
			self.__state = Connection.NoAckTimer.State.not_started

		def run(self):
			while True:
				self.__state = Connection.NoAckTimer.State.waiting
				self.__run_permission.acquire()

				if self.__state == Connection.NoAckTimer.State.killed:
					# Someone killed us
					return
				
				self.__state = Connection.NoAckTimer.State.sleeping

				time_to_sleep = self.__when_to_wake - time.time()
				if time_to_sleep > 0:
					# Sleep
					time.sleep(time_to_sleep)
				
				if self.__state == Connection.NoAckTimer.State.killed:
					# Someone killed us
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
			self.__waiting_for_packet = packet
			self.setZzz(zzz)
			self.__when_to_wake = time.time() + self.__zzz
			if self.__state == Connection.NoAckTimer.State.not_started:
				# Must have not run yet
				# Lock is initially released
				self.start()
			elif self.__state == Connection.NoAckTimer.State.waiting:
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

	
		def cancel(self):
			if self.__state == Connection.NoAckTimer.State.sleeping:
				self.__state = Connection.NoAckTimer.State.sleeping_cancelled

		def kill(self):
			self.__state = Connection.NoAckTimer.State.killed
			try:
				# Might throw an error if lock is already free..
				self.__run_permission.release()
			except:
				pass

		def getState(self):
			if self.__state == Connection.NoAckTimer.State.not_started:
				return 'not started'
			elif self.__state == Connection.NoAckTimer.State.waiting:
				return 'waiting'
			elif self.__state == Connection.NoAckTimer.State.sleeping:
				return 'sleeping'
			elif self.__state == Connection.NoAckTimer.State.sleeping_cancelled:
				return 'sleeping cancelled'
			elif self.__state == Connection.NoAckTimer.State.killed:
				return 'killed'
			else:
				return 'invalid state'

		def getPacket(self):
			return self.__waiting_for_packet

		def setZzz(self, zzz):
			if zzz > Connection.max_resend_time:
				self.__zzz = Connection.max_resend_time
			else:
				self.__zzz = zzz
				


class LossySocket(object):
	class State:
		loss = 1
		not_lost = 2

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
	
	def calculate_and_print_bw(self, packet_len):
		# Store bw measurement data as (LossySocket, send time, data len) tuple
		LossySocket.bw_measurement_buffer.append((self, time.time(), packet_len))
		bw = 0.0
		packets_sent = 0
		bytes_sent = 0
		for element in LossySocket.bw_measurement_buffer.get():
			if element == None:
				continue
			# We measure per second
			if time.time() - element[1] < 1.0:
				bytes_sent += element[2]
				packets_sent += 1

		oldest = LossySocket.bw_measurement_buffer.get_oldest()
		latest = LossySocket.bw_measurement_buffer.get_latest()

		if oldest != None and latest != None:
			if latest[1] - oldest[1]  < 1.0 and oldest[1] != latest[1]:
				send_time = latest[1] - oldest[1]
			else:
				send_time = 1.0

			self.logger.info("Bandwidth: %f Mbps, %d pps" % (bytes_sent *8 / send_time /1000000, \
				float(packets_sent)/send_time))

	def sendto(self, data, ip_port_tuple):

		if (self.state == LossySocket.State.not_lost and self.p < random.random()) or \
                                (self.state == LossySocket.State.loss and self.q > random.random()):
                        self.socket.sendto(data, ip_port_tuple)
                        self.state = LossySocket.State.not_lost
			self.calculate_and_print_bw(len(data))
                else:
                        self.state = LossySocket.State.loss
