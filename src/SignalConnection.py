import socket
from threading import Thread

from PacketManager import *

class SignalServer(Thread):
	
	sock = None
	logger = None
	sender_id = ""
	buf_size = 2000
	connection_list = [] # List of established connections

	def __init__(self, logger, ip = 127.0.0.1, port = 5500):

		if(logger == None):
			print 'You must specify a logger'
			return

    		self.sock = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
		self.sock.bind((ip, port))

	def run(self):
		
		if(sock == Null):
			return
		while True:
			data, addr = sock.recvfrom(buf_size) # buffer size is 1024 bytes
			print "received message:", data

	def init_connections(self.destination_list):
		
		# todo create hello packet
        	self.packetmanager.create_packet(2, 15, 43962, 52428, 56797, 3150765550, 286331153, 85, 102, None, None)

		for destination in self.destination_list:
			print 'connecting to ' + destination[0] + ', ' + destination [1]
			# todo Create connection and call connect and add to connection list

class Connection:
	
	SignalServer server	# Pointer to server (for shared info, such as Sender ID)
	version = 1
	remote_ip = None
	local_ip = None
	remote_port = 0
	seq_no = 0	# Our seq no
	sent_ack_no = 0	# Last seq we have acked
	recv_ack_no = 0	# What remote side has acked
	local_session_id = ""
	remote_session_id = ""
	state = State.UNCONNECTED
	packet = NULL

	def __init__(self, server, remote_ip, remote_port, remote_session_id, local_session_id, version = 1, seq_no = 1000):
		self.server = server     # Pointer to server (for shared info, such as Sender ID)
        	self.version = version
        	self.remote_ip = remote_ip
        	self.local_ip = local_ip
        	self.remote_port = remote_port
        	self.seq_no = seq_no
        	self.sent_ack_no = sent_ack_no
        	self.recv_ack_no = recv_ack_no
        	self.local_session_id = local_session_id
        	self.remote_session_id = remote_session_id
		self.packet = PacketManager()

	def connect(self):
		self.server.sock.sendto(self.packet.hex_packet(), (self.remote_ip, self_remote_port) )
		self.state = Connection.State.HELLO_SENT


	class State:
		UNCONNECTED = 0
		HELLO_SENT = 1
		HELLO_RECVD = 2
		IDLE = 3
