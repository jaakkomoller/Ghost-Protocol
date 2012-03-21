import logging, socket, signal, sys, time, random
from threading import Thread

from PacketManager import *
from Configuration import *
from FileSystem import *
# TODO remove Configuration, sys and signal imports

class SignalServer(Thread):
	
	sock = None
	logger = None
	sender_id = 0
	buf_size = 2000 # TODO This is not nice
	connection_list = [] # List of established connections
	exit_flag = False
	received_packet = None
	fsystem = None

	# TODO Throw error in case bind fails (Might do it already...)
	def __init__(self, fsystem, ip = "0.0.0.0", port = 5500, sender_id = random.randint(0, 65535)):
		Thread.__init__(self)

		# TODO Think trough how the program should exit
		#signal.signal(signal.SIGINT, self.signal_handler)
		
		self.fsystem = fsystem
		self.sender_id = sender_id

		self.logger = logging.getLogger("Signal server")
		self.logger.info("Initializing signal server id: %d at %s" % (self.sender_id, str(time.time())))

		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock.bind((ip, port))
		self.sock.settimeout(0.5) # So we can exit and wont block forever in recvfrom

		self.received_packet = PacketManager()


	def run(self):
		
		self.logger.info("Server started at %s" % (str(time.time())))
		while self.exit_flag == False:
			try:
				data, addr = self.sock.recvfrom(self.buf_size)
			except socket.error:
				errno, errstr = sys.exc_info()[:2]
				if errno == socket.timeout:
					#self.logger.info("socket timeout")
					continue
				else:
					self.logger.alarm("error with socket")
			self.logger.info("received message")
			self.received_packet.packetize_raw(data)
			self.received_packet.print_packet()
			found = False
			for connection in self.connection_list:
				if self.received_packet.txremoteID == connection.local_session_id:
					connection.handle(self.received_packet)
					found = True
					self.logger.info("packet belongs to existing connection")
					break
			if not found and self.received_packet.otype == OPERATION['HELLO'] and \
					self.received_packet.ocode == CODE['REQUEST'] :
				connection = Connection(self, addr[0], addr[1], 
					self.get_new_session_id(random.randint(0, 65535)), self.received_packet.txlocalID,
					self.received_packet.version, random.randint(0, 65535))
				connection.hello_recv(self.received_packet.sequence)
				self.connection_list.append(connection)
				self.logger.info("hello packet received, new connection established\
(local id %d, remote id %d) and HELLO sent" % (connection.local_session_id, connection.remote_session_id))
				


	# destination list should contain (ip, port) tuples
	def init_connections(self, destination_list):
		
		# todo create hello packet
		#self.packetmanager.create_packet(2, 15, 43962, 52428, 56797, 3150765550, 286331153, 85, 102, None, None)

		for destination in destination_list:
			self.logger.info('connecting to ' + destination[0] + ', ' + destination [1])
			#self.sock.sendto("daddaa", (destination[0], int(destination[1])) )
			connection = Connection(self, destination[0], int(destination[1]),
				self.get_new_session_id(random.randint(0, 65535)))
			connection.connect()
			self.connection_list.append(connection)
	
	# Returns an unigue local session_id. Takes a random number from 0 to 65535 as a parameter.
	def get_new_session_id(self, rand_no):
		for connection in self.connection_list:
			if rand_no == connection.local_session_id:
				return get_new_session_id(random.randint(0, 65535))
		return rand_no

	def stop(self):
		self.logger.info("server should stop")
		self.exit_flag = True

class Connection:
	
	class State:
		UNCONNECTED = 0
		HELLO_SENT = 1
		HELLO_RECVD = 2
		CONNECTED = 3

	# TODO add timers
	server = None # Pointer to SignalServer server (for shared info, such as Sender ID)
	version = 1
	remote_ip = None
	remote_port = 0
	seq_no = 0	# Our seq no
	ack_no = 0	# Last seq we have received in order
	recv_ack_no = 0	# What remote side has acked
	local_session_id = 0
	remote_session_id = 0
	state = State.UNCONNECTED
	packet = None
	logger = None

	# TODO check initializations
	def __init__(self, server, remote_ip, remote_port, local_session_id, remote_session_id = 0,
			version = 1, seq_no = 1000):
		self.server = server     # Pointer to server (for shared info, such as Sender ID)
		self.version = version
		self.remote_ip = remote_ip
		self.remote_port = remote_port
		self.seq_no = seq_no
		self.sent_ack_no = 0
		self.recv_ack_no = 0
		self.local_session_id = local_session_id
		self.remote_session_id = remote_session_id
		self.packet = PacketManager()
		self.state = Connection.State.UNCONNECTED

		self.logger = logging.getLogger("Connection to " + str(self.remote_ip) + ':' + str(self.remote_port))
		self.logger.info("Initializing connection at %s" % (str(time.time())))

	def connect(self):
		#def create_packet(self, version=1, flags=0, senderID=0, txlocalID=0, txremoteID=0,
#     sequence=0, ack=0, otype=0, ocode=0, TLVlist=None, rawdata=None):
		# Packet manager should be able to build hello packets (i.e. set remote session id)
		self.packet.create_packet(version=self.version, flags=0, senderID=self.server.sender_id,
			txlocalID=self.local_session_id, txremoteID=0, sequence=self.seq_no, otype='HELLO',
			ocode='REQUEST')  
		self.send_packet()
		self.state = Connection.State.HELLO_SENT
		# TODO set timers

		# Needs the seq no of the HELLO packet as a parameter.
	def hello_recv(self, seq_no):
		self.ack_no = seq_no
		self.packet.create_packet(version=self.version, flags=0, senderID=self.server.sender_id,
			txlocalID=self.local_session_id, txremoteID=self.remote_session_id, sequence=self.seq_no,
			ack=self.ack_no, otype='HELLO', ocode='RESPONSE')  
		self.send_packet()
		self.state = Connection.State.HELLO_RECVD
		# TODO set timers
	
	def handle(self, packet):
		self.ack_no = packet.sequence # TODO check that everything is received in the between.
		if packet.otype == OPERATION['HELLO'] and packet.ocode == CODE['RESPONSE'] and \
				self.state == Connection.State.HELLO_SENT:
			self.remote_session_id = packet.txlocalID
			self.packet.create_packet(version=self.version, flags=0, senderID=self.server.sender_id,
				txlocalID=self.local_session_id, txremoteID=self.remote_session_id,
				sequence=self.seq_no, ack=self.ack_no, otype='HELLO', ocode='RESPONSE')  
			# TODO set remote sender id and ack no
			self.send_packet()
			self.state = Connection.State.CONNECTED
			self.logger.info('state set to connected')
		elif packet.otype == OPERATION['HELLO'] and packet.ocode == CODE['RESPONSE'] and \
				self.state == Connection.State.HELLO_RECVD:
			self.state = Connection.State.CONNECTED
			self.logger.info('state set to connected')
			self.send_update('REQUEST')
		elif packet.otype == OPERATION['UPDATE'] and \
				self.state == Connection.State.CONNECTED:
			if packet.ocode == CODE['REQUEST']:
				self.logger.info('update request received')
			else:
				self.logger.info('update response received')
			for entry in packet.TLVs:
				if entry[0] == TLVTYPE['DATA']:
					self.logger.info('hash: %s' % entry[2])
					if self.server.fsystem.get_hash_manifest() != entry[2]:
						self.logger.info('hash files differ')
						self.send_list_request()
			if packet.ocode == CODE['REQUEST']:
				self.send_update('RESPONSE')
		elif packet.otype == OPERATION['LIST'] and packet.ocode == CODE['REQUEST'] and \
				self.state == Connection.State.CONNECTED:
			self.send_list_response()
		elif packet.otype == OPERATION['LIST'] and packet.ocode == CODE['RESPONSE'] and \
				self.state == Connection.State.CONNECTED:
			tlvlist = packet.get_TLVlist(tlvtype=TLVTYPE['DATA'])
			manifest = self.server.fsystem.get_diff_manifest(packet.get_TLVlist(tlvtype=TLVTYPE['DATA']))
			self.logger.info('list response received. tlvlist:')
			for entry in tlvlist:
				self.logger.info(entry)
			self.logger.info('diff:')
			for entry in manifest:
				self.logger.info(entry)
				if entry.split('?')[0] == 'FIL':
					self.send_fetch_file(entry.split('?')[1])
		elif packet.otype == OPERATION['PULL'] and packet.ocode == CODE['REQUEST'] and \
				self.state == Connection.State.CONNECTED:
			tlvlist = packet.get_TLVlist(tlvtype=TLVTYPE['DATA'])
			if len(tlvlist) == 0:
				return
			filename = tlvlist[0]

			tlvlist = packet.get_TLVlist(tlvtype=TLVTYPE['CONTROL'])
			remote_port = -1
			remote_tx_id = -1
			for tlv in tlvlist:
				# TODO check lengths
				if tlv.split('?')[0] == 'local_tx_id':
					remote_tx_id = int(tlv.split('?')[1])
				elif tlv.split('?')[0] == 'local_port':
					remote_port = int(tlv.split('?')[1])
			if remote_port >= 0 and remote_tx_id >= 0:
				self.send_fetch_file_response(remote_tx_id, remote_port)
		elif packet.otype == OPERATION['PULL'] and packet.ocode == CODE['RESPONSE'] and \
				self.state == Connection.State.CONNECTED:
			tlvlist = packet.get_TLVlist(tlvtype=TLVTYPE['CONTROL'])
			remote_port = -1
			remote_tx_id = -1
			for tlv in tlvlist:
				# TODO check lengths
				if tlv.split('?')[0] == 'local_tx_id':
					remote_tx_id = int(tlv.split('?')[1])
				elif tlv.split('?')[0] == 'local_port':
					remote_port = int(tlv.split('?')[1])
			# TODO Launch Tomi's code here
			tlv_string = ""
			for tlv in packet.TLVs:
				tlv_string += tlv[2] + ","
			self.logger.info('pull response received, tlvs: %s' % tlv_string)
		else:
			self.logger.info('invalid packet or state')
	
	# ocode is either 'REQUEST' or 'RESPONSE'
	def send_update(self, ocode):
		self.packet.create_packet(version=self.version, flags=0, senderID=self.server.sender_id,
			txlocalID=self.local_session_id, txremoteID=self.remote_session_id,
			sequence=self.seq_no, ack=self.ack_no, otype='UPDATE', ocode=ocode)  
		self.packet.append_entry_to_TLVlist('DATA', self.server.fsystem.get_hash_manifest())
		self.send_packet()
		# TODO set timers
		self.logger.info('update sent, hash %s' % self.server.fsystem.get_hash_manifest())
	
	def send_list_request(self):
		self.packet.create_packet(version=self.version, flags=0, senderID=self.server.sender_id,
			txlocalID=self.local_session_id, txremoteID=self.remote_session_id,
			sequence=self.seq_no, ack=self.ack_no, otype='LIST', ocode='REQUEST')  
		self.send_packet()
		# TODO set timers
		self.logger.info('List request sent')
	
	def send_list_response(self):
		self.packet.create_packet(version=self.version, flags=0, senderID=self.server.sender_id,
			txlocalID=self.local_session_id, txremoteID=self.remote_session_id,
			sequence=self.seq_no, ack=self.ack_no, otype='LIST', ocode='RESPONSE')  
		self.packet.append_list_to_TLVlist('DATA', self.server.fsystem.get_local_manifest())
		self.send_packet()
		# TODO set timers
		self.logger.info('List response sent. local manifest:')
		for entry in self.server.fsystem.get_local_manifest():
			self.logger.debug(entry)

	def send_fetch_file(self, filename):
		# TODO Get port and tx id from Tomi's code
		# TODO Lock the fetched file somehow
		# TODO implement state change with cookie
		local_tx_id = random.randint(0, 65535)
		local_data_port = random.randint(1500, 3000)
		self.packet.create_packet(version=self.version, flags=0, senderID=self.server.sender_id,
			txlocalID=self.local_session_id, txremoteID=self.remote_session_id,
			sequence=self.seq_no, ack=self.ack_no, otype='PULL', ocode='REQUEST')
		self.packet.append_entry_to_TLVlist('DATA', filename)
		self.packet.append_entry_to_TLVlist('CONTROL', 'local_tx_id?%d' % local_tx_id)
		self.packet.append_entry_to_TLVlist('CONTROL', 'local_port?%d' % local_data_port)
		tlv_string = ""
		for tlv in self.packet.TLVs:
			tlv_string += tlv[2] + ","
		self.send_packet()
		# TODO set timers
		self.logger.info('pull request sent, tlvs: %s' % tlv_string)

	def send_fetch_file_response(self, remote_tx_id, remote_data_port):
		# TODO get these from Tomis code.
		# TODO Lock the fetched file somehow
		local_tx_id = random.randint(0, 65535)
		local_data_port = random.randint(1500, 3000)
		self.packet.create_packet(version=self.version, flags=0, senderID=self.server.sender_id,
			txlocalID=self.local_session_id, txremoteID=self.remote_session_id,
			sequence=self.seq_no, ack=self.ack_no, otype='PULL', ocode='RESPONSE')
		self.packet.append_entry_to_TLVlist('CONTROL', 'remote_tx_id?%d' % remote_tx_id)
		self.packet.append_entry_to_TLVlist('CONTROL', 'remote_port?%d' % remote_data_port)
		self.packet.append_entry_to_TLVlist('CONTROL', 'local_tx_id?%d' % local_tx_id)
		self.packet.append_entry_to_TLVlist('CONTROL', 'local_port?%d' % local_data_port)
		tlv_string = ""
		for tlv in self.packet.TLVs:
			tlv_string += tlv[2] + ","
		self.send_packet()
		self.logger.info('pull response sent, tlvs: %s' % tlv_string)

	def send_packet(self):
		self.server.sock.sendto(self.packet.build_packet(), (self.remote_ip, self.remote_port) )
		self.seq_no = self.seq_no + 1
		del self.packet.TLVs[:] # TODO this should be done in packetmanager.
		self.logger.info('Packet sent')
			

# For testing purposes
# TODO Remove this
def main():

	logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s', datefmt='%d.%m.%y %H:%M:%S', filename='SyncCFT.log', filemode='w')
	console = logging.StreamHandler()
	console.setLevel(logging.DEBUG) 
	formatter = logging.Formatter('%(levelname)s: %(name)s: %(message)s')
	console.setFormatter(formatter)
	logging.getLogger('').addHandler(console)

	logger = logging.getLogger("Test main in SignalConnection")

	config = Configuration(sys.argv)
	conf_values = config.load_configuration()
	if not conf_values:
		logger.error("An error occurred while loading the configuration!")
		return

	(port, folder, p_prob, q_prob, peers) = conf_values
	#Logging of configuration 
	logger.info("Listening on UDP port %s" % (str(port)))
	logger.info("'p' parameter: %s" % (str(p_prob)))
	logger.info("'q' parameter: %s" % (str(q_prob)))
	logger.info("Peers to connect:")
	for peer in peers:
		logger.info("%s, %s" % (peer[0], peer[1]))

	fsystem = FileSystem(folder, '.private')
	fsystem.start_thread()
	
	# Sleep a while, so we have an up-to-date manifest TODO Not sure manifest is done.
	time.sleep(2)

	server = SignalServer(fsystem = fsystem, port = int(port), sender_id = random.randint(0, 65535))

	server.init_connections(peers)
	server.start()
	while server.isAlive():
		try:
			server.join(1)
		except KeyboardInterrupt:
			logger.info('CTRL+C received, killing server...')
			server.stop()
		
	fsystem.terminate_thread()
	#	def init_connections(self, destination_list):
	#	def __init__(self, ip = "127.0.0.1", port = 5500):

# TODO Remove this
main()
