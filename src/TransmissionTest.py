import time
from Connection import *
from PacketManager import *

test_string = "".join(['*' for i in range(1000)])
stop = False
init_seq = 64000

def main():

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s', datefmt='%d.%m.%y %H:%M:%S', filename='SyncCFT.log', filemode='w')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO) 
    #console.setLevel(logging.DEBUG) 
    formatter = logging.Formatter('%(levelname)s: %(name)s: %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

    if len(sys.argv) != 4:  # the program name and the two arguments
        # stop the program and print an error message
        sys.exit("Args: [server -s, or client -c] [p value] [q value]")
    if sys.argv[1] == "-s":
        print 'Starting server'
        server(float(sys.argv[2]), float(sys.argv[3]))
    else:
        print 'Starting client'
        client(float(sys.argv[2]), float(sys.argv[3]))

class ClientReceiver(Thread):

    def __init__(self, connection):
        Thread.__init__(self)
        self.logger = logging.getLogger("Client receiver")
        self.connection = connection
        self.connection.sock.settimeout(0.5) # So we can exit and wont block forever in recvfrom

    def run(self):
        received_packet = InPacket()
        while stop == False:
            try:
                data, addr = self.connection.sock.recvfrom(2000)
            except:
                continue
            received_packet.packetize_raw(data)
            received_packet.receive_time = time.time()
            #received_packet.print_packet()
            self.connection.receive_packet(received_packet)
        self.connection.stop()
        self.logger.info("receiver thread shutting down")
        
class ClientSender(Thread):

    def __init__(self, connection, sender_id):
        Thread.__init__(self)
        self.logger = logging.getLogger("Client sender")
        self.connection = connection
        self.sender_id = sender_id

    def run(self):
        data = 10
        str_data = "%s%d" % (test_string, data)
        while stop == False:
            packet_to_send = OutPacket()
            packet_to_send.create_packet(version=self.connection.version, flags=[], senderID=self.sender_id,
                txlocalID=self.connection.local_session_id, txremoteID=self.connection.remote_session_id,
                sequence=self.connection.seq_no, ack=self.connection.send_ack_no, otype='UPDATE', ocode='REQUEST')
            packet_to_send.append_entry_to_TLVlist('DATA', str_data)

            if self.connection.send_packet_reliable(packet_to_send) == False:
                #self.logger.info("send failed. sleeping")
                time.sleep(0.1)
            else:
                data = (data + 1) % 100000
                str_data = "%s%d" % (test_string, data)
        self.connection.stop()
        self.logger.info("sender thread shutting down")

def client(p, q):
    sender_id = 2
    global stop
    logger = logging.getLogger("Test client")

    sock = LossySocket(socket.AF_INET, socket.SOCK_DGRAM, q = q, p = p)
    #sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 5000))
    #sock.bind(("10.0.3.2", 5000))

    #connection = Connection(sock = sock, remote_ip = "10.0.3.1", remote_port = 6000,
    connection = Connection(sock = sock, remote_ip = "127.0.0.1", remote_port = 6000,
        local_session_id = 2, remote_session_id = 1,
        version = 1, seq_no = init_seq, send_ack_no = 0, logger_str = "Test Connection to ")
    
    receiver = ClientReceiver(connection)
    receiver.start()
    sender = ClientSender(connection, sender_id)
    sender.start()
    
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info('CTRL+C received, killing connection...')
        stop = True


def server(p, q):
    sender_id = 2
    logger = logging.getLogger("Test server")

    received_packet = InPacket()
    
    sock = LossySocket(socket.AF_INET, socket.SOCK_DGRAM, q = q, p = p)
    #sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #sock.bind(("10.0.3.1", 6000))
    sock.bind(("127.0.0.1", 6000))

    connection = Connection(sock = sock, remote_ip = "127.0.0.1", remote_port = 5000,
        local_session_id = 1, remote_session_id = 2,
        version = 1, seq_no = 1, send_ack_no = init_seq-1, logger_str = "Test Connection to ")
        
    packet_to_send = OutPacket()
    
    exp_data = 10
    t = -1.0
    bits = 0
    try:
        while True:
            data, addr = sock.recvfrom(2000)
            logger.debug("received message")
            received_packet.packetize_raw(data)
            received_packet.receive_time = time.time()
        #received_packet.print_packet()
            if connection.receive_packet(received_packet):
                #print 'testing %d' % exp_data
                d = received_packet.get_TLVlist(tlvtype = 'DATA')[0][1000:]
                received_data = int(d)
                if exp_data != received_data:
                    logger.error("invalid data: %d, expected: %d" % (received_data, exp_data))
                    exit(0)
                exp_data = (exp_data + 1) % 100000
                bits += (len(d) + 1000) *8
                if received_data % 1000 == 0:
                    if t > 0:
                        print 'goodput: %.2f Mbps' % (bits / (time.time() - t) / 1000000)
                    t = time.time()
                    bits = 0

            packet_to_send.create_packet(version=connection.version, flags=[], senderID=sender_id,
                txlocalID=connection.local_session_id, txremoteID=connection.remote_session_id,
                sequence=connection.seq_no, ack=connection.send_ack_no, otype='UPDATE', ocode='REQUEST')

            connection.send_packet_unreliable(packet_to_send)
    except KeyboardInterrupt:
        logger.info('CTRL+C received, killing connection...')
        connection.stop()
        stop = True

main()
