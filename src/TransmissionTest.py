import time
from Connection import *
from PacketManager import *


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
    sock = None
    logger = None

    def __init__(self, connection):
        Thread.__init__(self)
        self.logger = logging.getLogger("Client receiver")
        self.connection = connection

    def run(self):
        received_packet = InPacket()
        while True:
            data, addr = self.connection.sock.recvfrom(2000)
            self.logger.debug("received message")
            received_packet.packetize_raw(data)
            received_packet.receive_time = time.time()
            #received_packet.print_packet()
            self.connection.receive_packet(received_packet)


def client(p, q):
    sender_id = 2
    logger = logging.getLogger("Test client")

    sock = LossySocket(socket.AF_INET, socket.SOCK_DGRAM, q = q, p = p)
    #sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 5000))
    #sock.bind(("10.0.3.2", 5000))

    #connection = Connection(sock = sock, remote_ip = "10.0.3.1", remote_port = 6000,
    connection = Connection(sock = sock, remote_ip = "127.0.0.1", remote_port = 6000,
        local_session_id = 2, remote_session_id = 1,
        version = 1, seq_no = 10000, send_ack_no = 0, logger_str = "Test Connection to ")
    
    receiver = ClientReceiver(connection)
    receiver.start()
    
    data = 10
    while True:
        packet_to_send = OutPacket()
        packet_to_send.create_packet(version=connection.version, flags=[], senderID=sender_id,
            txlocalID=connection.local_session_id, txremoteID=connection.remote_session_id,
            sequence=connection.seq_no, ack=connection.send_ack_no, otype='UPDATE', ocode='REQUEST')
        packet_to_send.append_entry_to_TLVlist('DATA', str(data))

        if connection.send_packet_reliable(packet_to_send) == False:
            logger.info("send failed. sleeping")
            time.sleep(0.1)
        else:
            data = (data + 1) % 100000


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
        version = 1, seq_no = 1, send_ack_no = 9999, logger_str = "Test Connection to ")
        
    packet_to_send = OutPacket()
    
    exp_data = 10

    while True:
        data, addr = sock.recvfrom(2000)
        logger.debug("received message")
        received_packet.packetize_raw(data)
        received_packet.receive_time = time.time()
        #received_packet.print_packet()
        if connection.receive_packet(received_packet):
            received_data = int(received_packet.get_TLVlist(tlvtype = 'DATA')[0])
            if exp_data != received_data:
                logger.error("invalid data: %d, expected: %d" % (received_data, exp_data))
                exit(0)
            exp_data = (exp_data + 1) % 100000

        packet_to_send.create_packet(version=connection.version, flags=[], senderID=sender_id,
            txlocalID=connection.local_session_id, txremoteID=connection.remote_session_id,
            sequence=connection.seq_no, ack=connection.send_ack_no, otype='UPDATE', ocode='REQUEST')

        connection.send_packet_unreliable(packet_to_send)

main()
