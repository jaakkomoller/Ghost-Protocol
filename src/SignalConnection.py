import logging, socket, signal, sys, time
from threading import Thread

from PacketManager import *
from Configuration import *
# TODO remove Configuration, sys and signal imports

class SignalServer(Thread):
	
	sock = None
	logger = None
	sender_id = 0
	buf_size = 2000 # TODO This is not nice
	connection_list = [] # List of established connections
	exit_flag = False
	received_packet = None

	# TODO Throw error in case bind fails (Might do it already...)
	def __init__(self, ip = "127.0.0.1", port = 5500):
		Thread.__init__(self)

		# TODO Think trough how the program should exit
        	#signal.signal(signal.SIGINT, self.signal_handler)

        	self.logger = logging.getLogger("Signal server")
        	self.logger.info("Initializing signal server at %s" % (str(time.time())))

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
			print "received message:", data
			self.received_packet.packetize_raw(data)
			self.received_packet.print_packet()

	# destination list should contain (ip, port) tuples
	def init_connections(self, destination_list):
		
		# todo create hello packet
        	#self.packetmanager.create_packet(2, 15, 43962, 52428, 56797, 3150765550, 286331153, 85, 102, None, None)

		for destination in destination_list:
			print 'connecting to ' + destination[0] + ', ' + destination [1]
			#self.sock.sendto("daddaa", (destination[0], int(destination[1])) )
			# todo Create connection and call connect and add to connection list
			#def __init__(self, server, remote_ip, remote_port, remote_session_id, local_session_id, version = 1, seq_no = 1000):
			connection = Connection(self, destination[0], int(destination[1]), 1)
			connection.connect()
			self.connection_list.append(connection)

	def stop(self):
		self.logger.info("server should stop")
		self.exit_flag = True

class Connection:
	
	class State:
		UNCONNECTED = 0
		HELLO_SENT = 1
		HELLO_RECVD = 2
		IDLE = 3

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

	def connect(self):
    		#def create_packet(self, version=1, flags=0, senderID=0, txlocalID=0, txremoteID=0,
                #     sequence=0, ack=0, otype=0, ocode=0, TLVlist=None, rawdata=None):
		# Packet manager should be able to build hello packets (i.e. set remote session id)
		self.packet.create_packet(self.version, 0, self.server.sender_id, self.local_session_id,
			0, self.seq_no, self.ack_no, 1)  
		self.server.sock.sendto(self.packet.build_packet(), (self.remote_ip, self.remote_port) )
		self.state = Connection.State.HELLO_SENT

	


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

	server = SignalServer(port = int(port))

	server.init_connections(peers)
	server.start()
	while server.isAlive():
		try:
			server.join(1)
		except KeyboardInterrupt:
			logger.info('CTRL+C received, killing server...')
			server.stop()
		
#	def init_connections(self, destination_list):
#	def __init__(self, ip = "127.0.0.1", port = 5500):

# TODO Remove this
main()
