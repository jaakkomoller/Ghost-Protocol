import logging, sys, signal, time

from Configuration import *
from FileSystem import *
from PacketManager import *
from Security import *

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s', datefmt='%d.%m.%y %H:%M:%S', filename='SyncCFT.log', filemode='w')
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s: %(name)s: %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

class SyncCFT:
    def __init__(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        self.logger = logging.getLogger("SyncCFT 1.0")
        self.logger.info("Starting SyncCFT 1.0 at %s" % (str(time.time())))
        self.exit_flag = 0

        config = Configuration(sys.argv)

        conf_values = config.load_configuration()
        self.local_password = config.load_password()

        if not conf_values:
            self.logger.error("An error occurred while loading the configuration!")
            return

        (self.port, self.folder, self.p_prob, self.q_prob, self.peers) = conf_values
        #Logging of configuration
        self.logger.info("Listening on UDP port %s" % (str(self.port)))
        self.logger.info("Synchronizing folder %s" % (str(self.folder)))
        self.logger.info("'p' parameter: %s" % (str(self.p_prob)))
        self.logger.info("'q' parameter: %s" % (str(self.q_prob)))

        i=1
        for item in self.peers:
            self.logger.info("Peer %d: %s:%s" % (i,str(item[0]),str(item[1])))
            i+=1

    def start_SyncCFT(self):
        self.packetmanager = PacketManager()
        self.security = Security()
        self.fsystem = FileSystem(self.folder, '.private')

        (self.privateKey,self.publicKey) = self.security.generate_keys(1024)
        self.publicKey_plaintext = self.security.export_key(self.publicKey)

        self.fsystem.start_thread(timeout=1)

        try:
            while not self.exit_flag:
                time.sleep(5)
        except Exception:
            pass

        print self.fsystem.current_dic
        self.fsystem.terminate_thread()

        '''
        print "\n++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
        print "Here comes our new coding!!\n"
        mylist = ['FIL?f1?5?1330560662?5310dab750cabf7e2d1f307554874f9a','RMF?f3?11?1339999999?a73c45107081c08dd4560206b8ef8205']
        print "The difference of the manifests are..."
        print self.fsystem.get_diff_manifest_remote(mylist)
        print "\n++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"

        print self.fsystem.current_dic

        self.fsystem.terminate_thread()


        pwdA= 'passwordA'
        (privateKA,publicKA) = self.security.generate_keys(1024)
        exp_publicKA = self.security.export_key(publicKA)
        hash_A = self.security.calculate_key_hash(exp_publicKA, pwdA)

        #(privateKB,publicKB) = self.security.generate_keys(1024)

        print "Creating the packet..."
        self.packetmanager.create_packet(2, ['SEC'], 0xabcd,0xfeea, 0xfee0, 3150765550, 286331153, "HELLO", "REQUEST", None, None)
        self.packetmanager.append_entry_to_TLVlist('SECURITY', exp_publicKA+'?'+hash_A)
        packet = self.packetmanager.build_packet()

        #self.packetmanager.append_list_to_TLVlist('DATA', ['oneeeeee','twoooooooo','threeeeeeee', 'fourrrrrrr'])
        #self.packetmanager.append_entry_to_TLVlist('DATA', 'data_test')
        #self.packetmanager.append_entry_to_TLVlist('CONTROL', 'control_test')
        #self.packetmanager.append_entry_to_TLVlist('SECURITY', 'security_test')
        #packet = self.packetmanager.build_packet()

        print "This is the packet dump"
        self.packetmanager.hex_packet()

        #raw_data = '\x29\x02\xAB\xCD\xFE\xEA\xFE\xE0\xBB\xCC\xDD\xEE\x11\x11\x11\x11\x01\x01\x4C\xA9\x02\x30\x30\x30\x38\x6F\x6E\x65\x65\x65\x65\x65\x65\x02\x30\x30\x31\x30\x74\x77\x6F\x6F\x6F\x6F\x6F\x6F\x6F\x6F\xFF\x30\x30\x31\x31\x74\x68\x72\x65\x65\x65\x65\x65\x65\x65\x65'
        #raw_packet = self.packetmanager.create_packet(rawdata = raw_data)

        print "\n\n\n"
        print self.packetmanager.get_version()
        print self.packetmanager.get_flags()
        print self.packetmanager.get_senderID()
        print self.packetmanager.get_txlocalID()
        print self.packetmanager.get_txremoteID()
        print self.packetmanager.get_sequence()
        print self.packetmanager.get_ack()
        print self.packetmanager.get_otype()
        print self.packetmanager.get_ocode()
        print "This is the TLV_List"
        print self.packetmanager.get_TLVlist()
        print "This is the get_TLVlist_typevalue"
        print self.packetmanager.get_TLVlist_typevalue()

        print "self.packetmanager.get_TLVlist('SECURITY')"
        print self.packetmanager.get_TLVlist('SECURITY')
        security_payload = self.packetmanager.get_TLVlist('SECURITY')
        recovered_plaintextkey = security_payload[0].split('?')[0]
        recovered_hash = security_payload[0].split('?')[1]

        recovered_key = self.security.import_key(recovered_plaintextkey)
        print recovered_key

        if self.security.calculate_key_hash(recovered_plaintextkey, pwdA) == recovered_hash:
            print "Access granted!"

        '''
        '''
        original_packet = packet[:]

        print "\n\n\n*********************************************************\n\n\n"
        print "The following reprensents a communication between 2 peers"

        password_A= 'ProtocolDesign'
        password_B= 'ProtocolDesig'

        (privateKA,publicKA) = self.security.generate_keys(1024)
        (privateKB,publicKB) = self.security.generate_keys(1024)

        print "Peer-A wants to send"
        self.print_hex(original_packet)

        print "Peer-A encrypts with Public_Key_B"
        encrypted_packet = self.security.encrypt(publicKB, original_packet)
        self.print_hex(encrypted_packet)

        print "Peer-B decrypts with Private_Key_B"
        decrypted_packet = self.security.decrypt(privateKB, encrypted_packet)
        self.print_hex(decrypted_packet)

        if original_packet == decrypted_packet:
            print "Both packets are the same after the crypto!!!"

        #This is the hash sent by A
        exp_publicKA = self.security.export_key(publicKA)
        hash_A = self.security.calculate_key_hash(exp_publicKA, password_A)

        #B calculates the following
        hash_B = self.security.calculate_key_hash(exp_publicKA, password_A)

        if hash_A == hash_B:
            print "Access granted!"
        else:
            print "Wrong password!"
        '''

        return

    def signal_handler(self, signal, frame):
        self.logger.warning("You pressed Ctrl+C")
        print "\nYou pressed Ctrl+C!\n"
        self.exit_flag = 1
        #sys.exit(1)

    def print_hex(self, text):
        l = len(text)
        i = 0
        while i < l:
            print "%04x  " % i,
            for j in range(16):
                if i+j < l:
                    print "%02X" % ord(text[i+j]),
                else:
                    print "  ",
                if j%16 == 7:
                    print "",
            print " ",

            ascii = text[i:i+16]
            r=""
            for i2 in ascii:
                j2 = ord(i2)
                if (j2 < 32) or (j2 >= 127):
                    r=r+"."
                else:
                    r=r+i2
            print r
            i += 16

my_app = SyncCFT()
my_app.start_SyncCFT()

