import logging, sys, select, signal, string, thread, threading, time

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
        #print "Starting SyncCFT 1.0\n"
        starting_dic = {}
        current_dic = {}
        previous_dic = {}
        diff_dic = {}
        flag = True
        self.fsystem = FileSystem(self.folder, '.private')
        self.packetmanager = PacketManager()
        
        if self.fsystem.exists_manifest():
            self.logger.info("Found manifest file!")
            starting_dic = self.fsystem.read_manifest()
            
        else:
            self.logger.warning("Manifest file not found!")
            starting_dic = self.fsystem.get_file_list(1)
            
        print "\nStarting manifest"
        self.fsystem.print_manifest_dic(starting_dic)
        current_dic = self.fsystem.get_file_list(1)
        
        
        while not self.exit_flag:
            try:
                raw_input('')
            except:
                continue

            if len(diff_dic) != 0:
                self.fsystem.merge_manifest(current_dic, diff_dic)
            
            if flag:
                diff_dic = self.fsystem.diff_manifest(current_dic, starting_dic)
                previous_dic = current_dic
                flag = False
            
            else:
                current_dic = self.fsystem.get_file_list(1)
                
                diff_dic = self.fsystem.diff_manifest(current_dic, previous_dic)
                print "\nPrinting diff dictionary"
                self.fsystem.print_manifest_dic(diff_dic)
                print('\n')
                
                self.fsystem.merge_manifest(current_dic, diff_dic)

                print "\nPrinting current dictionary"
                self.fsystem.print_manifest_dic(current_dic)
                print('\n')
                previous_dic = current_dic
            
                
        self.fsystem.write_manifest(current_dic)
        
        '''
        print "Creating the packet..."
        self.packetmanager.create_packet(2, 15, 43962, 52428, 56797, 3150765550, 286331153, 85, 102, None, None)
        
        #self.packetmanager.append_entry_to_TLVlist('D', 'FIL?testfile1?000?456')
        self.packetmanager.append_entry_to_TLVlist('DATA', 'test')
        #self.packetmanager.append_entry_to_TLVlist('D', 'test2')
        #self.packetmanager.append_entry_to_TLVlist('D', 'FIL?testfile3?002?456')
        
        packet = self.packetmanager.build_packet()
        
        #self.packetmanager.print_packet()
        self.packetmanager.hex_packet()
        '''
        
        print "Creating new packet from scratch!"
        sraw = '\x2F\x02\xAB\xBA\xCC\xCC\xDD\xDD\xBB\xCC\xDD\xEE\x11\x11\x11\x11\x55\x66\x45\x78\xFF\x30\x30\x34\x74\x65\x73\x74'
        
        self.packetmanager.create_packet(rawdata=sraw)
        #rawpacket = self.packetmanager.build_packet()
        #print "This is the packet returned: len()", len(rawpacket)
        self.packetmanager.hex_packet()
        
        return
        
    def signal_handler(self, signal, frame):
        self.logger.warning("You pressed Ctrl+C")
        print "\nYou pressed Ctrl+C!\n"
        self.exit_flag = 1
        #sys.exit(1)
        

my_app = SyncCFT()
my_app.start_SyncCFT()

