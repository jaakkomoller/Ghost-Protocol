import logging, sys, select, signal, string, thread, threading, time

from Configuration import *
from FileSystem import *

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s', datefmt='%d.%m.%y %H:%M:%S', filename='SyncCFT.log', filemode='w')
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
        diff_manifest = []
        self.fsystem = FileSystem(self.folder, '.private')
        
        if self.fsystem.exists_manifest():
            self.logger.info("Found manifest file!")
            starting_manifest = self.fsystem.read_manifest()
        else:
            self.logger.warning("Manifest file not found!")
            starting_manifest = self.fsystem.get_file_list(1)
        
        self.fsystem.print_manifest(starting_manifest)
        #self.fsystem.write_manifest(starting_manifest)
        
        while not self.exit_flag:
            time.sleep(4)
            last_manifest = self.fsystem.get_file_list()
            #print "\n\nThis is the fresh manifest"
            self.fsystem.print_manifest(last_manifest)
            diff_manifest = self.fsystem.diff_manifest(last_manifest, starting_manifest)
            print "\n\nThis is the diff version"
            self.fsystem.print_manifest(diff_manifest)
        
        #self.fsystem.write_manifest(filelist)
        #self.fsystem.inspect_folder(self.folder)
        

    def signal_handler(self, signal, frame):
        self.logger.warning("You pressed Ctrl+C")
        print "\nYou pressed Ctrl+C!\n"
        self.exit_flag = 1
        #sys.exit(1)
        

my_app = SyncCFT()
my_app.start_SyncCFT()

