import logging, sys, signal, time

from Configuration import *
from FileSystem import *
from PacketManager import *

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
        
        self.fsystem = FileSystem(self.folder, '.private')
        self.packetmanager = PacketManager()
        
        self.fsystem.start_thread()
        
        while not self.exit_flag:
            time.sleep(5)
        
        mylist = ['FIL?f6?5?1330557437?0ac1b6ca8b53a5dc5c031382b981952f', 'FIL?f8?5?1330556921?5310dab750cabf7e2d1f307554874f9b', 'DIR?d1?0?1330026622?0', 'FIL?f3?6?1329785931?4c850c5b3b2756e67a91bad8e046ddac', 'FIL?f4?2?1329785778?b026324c6904b2a9cb4b88d6d61c81d1', 'FIL?f2?5?1329784733?e5828c564f71fea3a12dde8bd5d27063']
        print "The difference of the manifests are..."
        print self.fsystem.get_diff_manifest(mylist)
        
        self.fsystem.terminate_thread()

        '''
        print "Creating the packet..."
        self.packetmanager.create_packet(2, 15, 0xabcd,0xfeea, 0xfee0, 3150765550, 286331153, "HELLO", "REQUEST", None, None)
        self.packetmanager.append_entry_to_TLVlist('DATA', 'data_test')
        self.packetmanager.append_entry_to_TLVlist('CONTROL', 'control_test')
        self.packetmanager.append_entry_to_TLVlist('SECURITY', 'security_test')
        
        packet = self.packetmanager.build_packet()
        self.packetmanager.hex_packet()

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
        print self.packetmanager.get_TLVlist()
        '''
        
        return
        
    def signal_handler(self, signal, frame):
        self.logger.warning("You pressed Ctrl+C")
        print "\nYou pressed Ctrl+C!\n"
        self.exit_flag = 1
        #sys.exit(1)
        

my_app = SyncCFT()
my_app.start_SyncCFT()

