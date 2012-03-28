import logging, socket, random, select, sys, time, os
from threading import Thread

from PacketManager import *

class DataServer(Thread):

	sock = None
	logger = None
	received_packet = None
	buffer_size = 2048
	port_list = [] # port, socket
	read_list = [] # contains all the sockets for select
	session_list = []

	def __init__(self, ip = "", port = ""):
		Thread.__init__(self)
		self.ip=ip
		self.port=port	

		if not ip: ip = '0.0.0.0'
		if not port: port = random.randint(4500, 4550)

		self.logger = logging.getLogger("Data server started: ip %s, port %s" % (ip,port))

		try:
	      		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			self.sock.bind((ip, port))
			self.sock.setblocking(0) # non-blocking
			self.port_list.append([port,self.sock])
			self.read_list.append(self.sock)

		except socket.error:
			self.logger.alarm("Error with socket")

		self.received_packet = InPacket()


	def run(self):
		
		timeout=2
	
		while True:

            		input = select.select(self.read_list,[],[],timeout)

            		# Data handling or time out
            		for s in input:
				for r in self.read_list:				            
                			if s == [r]:
			           	
	 					try:
							buffer, addr = r.recvfrom(self.buffer_size)

							self.received_packet.packetize_raw(buffer)
							self.received_packet.receive_time = time.time()

							for session in self.session_list:

								if self.received_packet.txremoteID == session.local_session_id and self.received_packet.txlocalID == session.remote_session_id:
									session.handle(self.received_packet)


						except socket.error:
							self.logger.alarm("Error with socket")
			#TODO: time out ?	
			#timeout = timeout+1


	def add_session(self, remote_ip, remote_port, local_session_id, remote_session_id, version, sender_id, file_path, hash, size, is_request):

		data_session = DataSession(remote_ip, remote_port, local_session_id, remote_session_id, version, sender_id, file_path, hash, size, 0) 

		for session in self.session_list:
			
			if session.local_session_id==data_session.local_session_id and session.remote_session_id==data_session.remote_session_id:
				#print("ignore session, it's already there")
				return

                self.session_list.append(data_session)

		if is_request == True:
			to_chunk = data_session.get_chunk_count()
			data_session.data_req(1,to_chunk) # ask for the whole file



	def add_port(self, new_port=""):
                self.new_port=new_port

		# TODO: check if port is already in use                
                if not new_port: new_port = random.randint(4500, 4550)

                self.logger = logging.getLogger("New port added: port %s" % (new_port))

                try:
                        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        self.sock.bind((self.ip, new_port))
                        self.sock.setblocking(0) # non-blocking 
			self.port_list.append([new_port,self.sock])
                        self.read_list.append(self.sock)

                except socket.error:
                        self.logger.alarm("Error with socket")


	def remove_port(self, old_port):
  		self.old_port=old_port
		
		try:
						
			rm = [x[0] for x in self.port_list].index(old_port)
			temp_val=self.port_list.pop(rm)			
			self.read_list.remove(temp_val[1])
			                        
		except:
			pass
	

	def get_port(self):
		from random import choice
		retval=choice(self.port_list)
		return retval[0]



class DataSession():

	socket = None

	#TODO: check these
	seq_no = 0
	ack_no = 0
	chunk_size = 50.0 # just some size to test it

	def __init__(self, remote_ip, remote_port, local_session_id, remote_session_id, version, sender_id, file_path, hash, size, finished): #timeout?
		self.remote_ip = remote_ip
		self.remote_port = remote_port
		self.local_session_id = local_session_id
		self.remote_session_id = remote_session_id
		self.version = version
		self.sender_id = sender_id
		self.file_path = file_path
		self.hash = hash
		self.size = size # in bytes 
		self.finished = finished
		#TODO: add a temp file location

		#TODO: use a server socket
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)



	def handle(self, packet):
		self.packet = packet
		from_chunk = None
		to_chunk = None
		from_ok = 0
		to_ok = 0

		if packet.otype == OPERATION['DATA'] and packet.ocode == CODE['RESPONSE']:
					

			packet.print_packet()
			print("response received")			
	
			tlvlist = packet.get_TLVlist(tlvtype=TLVTYPE['DATA'])
                        print(tlvlist[0])
			
			#TODO: construct the file and manage session. 
			
			#an example of file management
        		#self.allocate_file('/path/to/new_file.temp',self.size)
		
        		# get data (chunks) from tlvs (tlvlist[0]) and find out its id somehow... loop this until all chunks are added
        	        # construct_file('/path/to/new_file.temp',id,chunk)





		elif packet.otype == OPERATION['DATA'] and packet.ocode == CODE['REQUEST']:

		
			packet.print_packet()
			print("request received")

			tlvlist = packet.get_TLVlist(tlvtype=TLVTYPE['DATA'])
						
			if tlvlist[0]== self.filename:
				print("ok")
			else:	
				return


                        tlvlist = packet.get_TLVlist(tlvtype=TLVTYPE['CONTROL'])
                        for tlv in tlvlist:
                                temp = tlv.split('?')[0]
				
				if temp == 'from':
					from_chunk=tlv.split('?')[1]
					print("from chunk")
					print(from_chunk)
					from_ok = 1					

				if temp == 'to':
                                        to_chunk=tlv.split('?')[1]
					print("to chunk")
                                        print(to_chunk)
					to_ok = 1

				if from_ok==1 and to_ok==1:
					self.data_response(int(from_chunk),int(to_chunk))
					from_ok = 0
					to_ok = 0
			

		else:
			pass
	

	
        def data_req(self,from_chunk,to_chunk):

                packet_to_send = OutPacket()
                packet_to_send.create_packet(version=self.version, flags=0, senderID=self.sender_id, txlocalID=self.local_session_id, txremoteID=self.remote_session_id,sequence=self.seq_no, ack=self.ack_no, otype='DATA', ocode='REQUEST')
                packet_to_send.append_entry_to_TLVlist('DATA', self.file_path)
                packet_to_send.append_entry_to_TLVlist('CONTROL', 'from?%d' % from_chunk)
                packet_to_send.append_entry_to_TLVlist('CONTROL', 'to?%d' % to_chunk)
               
		self.socket.sendto(packet_to_send.build_packet(), (self.remote_ip,self.remote_port))


        def data_response(self,from_chunk, to_chunk):

		#TODO: check seq_no etc.

		for x in range(from_chunk, to_chunk+1):

                	packet_to_send = OutPacket()
                	packet_to_send.create_packet(version=self.version, flags=0, senderID=self.sender_id, txlocalID=self.local_session_id, txremoteID=self.remote_session_id,sequence=self.seq_no, ack=self.ack_no, otype='DATA', ocode='RESPONSE')
                	
			chunk=self.get_chunk(x)
			packet_to_send.append_entry_to_TLVlist('DATA', chunk)

			self.socket.sendto(packet_to_send.build_packet(), (self.remote_ip,self.remote_port))




	def get_chunk_count(self):

        	chunks = self.size/self.chunk_size
         	rounded = round(chunks)
 
        	if chunks - rounded > 0:
                	return int(rounded + 1)
        	else:
                	return int(rounded)


	def get_chunk(self,id):

        	try:
                	f = open(self.file_path, "r")
                	f.seek((id-1)*int(self.chunk_size))
                	chunk = f.read(int(self.chunk_size))
                	f.close()
                	return chunk

        	except:
                	pass


	def get_size(self):
        	return os.path.getsize(self.file_path)


	def allocate_file(self,new_file):
        	try:
                	f = open(new_file, "wb")
                	f.write("\0" * self.size)
                	f.close()
        	except:
                	pass


	def construct_file(self,new_file,id,chunk):

        	try:
        		f = open(new_file, "r+")
        		f.seek((id-1)*int(self.chunk_size))
		        f.write(chunk)
        		f.close()

	        except:
        		pass




				
def main():

	data_server = DataServer('0.0.0.0',4500)
	data_server.start()
	#data_server.add_port(4501)
	#data_server.remove_port(4501)

	port=data_server.get_port()
	data_server.add_session('0.0.0.0', 4502,111,222,1,10,'/u/opi/66/kyostit1/temp.txt',234,205,True)


	
main()
