import hashlib, logging, os, sys, time
from stat import *

FILETYPE = 0
FILEPATH = 1
FILESIZE = 2
FILETSTAMP = 3
FILEHASH = 4

class FileSystem:
    def __init__(self,path, private_dir):
        self.logger = logging.getLogger("FileSystem")
        self.root_path = path
        self.private_dir = private_dir
        self.manifest_path = self.private_dir+'/'+'.manifest'
        self.set_private_folder()

    def set_private_folder(self):
        try:
            os.chdir(self.root_path)
        except OSError, ex:
            self.logger.error("root folder not found! %s" % (str(ex)))
            sys.exit(1)
            
        if not os.access(self.private_dir, os.F_OK):
            self.logger.warning("creating private directory")
            os.mkdir(self.private_dir)

    def exists_manifest(self):
        if not os.access(self.manifest_path, os.W_OK):
            self.logger.warning("manifest file not found!")
            return False
        return True

    def read_manifest(self):
        tempdic = {}
        fd = open(self.manifest_path,'r')
        lines = fd.readlines()
        fd.close()
        for line in lines:
            temp = line.strip().split('\t')
            entry = (temp[FILETYPE],temp[FILEPATH],temp[FILESIZE],temp[FILETSTAMP],temp[FILEHASH])
            tempdic[(temp[FILETYPE],temp[FILEPATH])] = entry
        return tempdic
        
    def write_manifest(self, infodic):
        fd = open(self.manifest_path,'w')
        for key,value in sorted(infodic.iteritems(), key=lambda (k,v): (v[FILETSTAMP],k), reverse=True):
            towrite = "%s\t%s\t%s\t%s\t%s" % (value[FILETYPE],value[FILEPATH],value[FILESIZE],value[FILETSTAMP],value[FILEHASH])
            fd.write(towrite+'\r\n')
            self.logger.info(towrite)
        fd.close()
    
    def print_manifest(self, infolist):
        for i in infolist:
            print "%s\t%s\t%s\t%s\t%s" % (i[FILETYPE],i[FILEPATH],i[FILESIZE],i[FILETSTAMP],i[FILEHASH])
    
    def print_manifest_dic(self, infodic):
        if len(infodic) != 0:
            for key,value in sorted(infodic.iteritems(), key=lambda (k,v): (v[FILETSTAMP],k), reverse=True):
                print "%s\t%s\t%s\t%s\t%s" % (value[FILETYPE],value[FILEPATH],value[FILESIZE],value[FILETSTAMP],value[FILEHASH])
    
    def get_sorted_list(self, infodic):
        sortedlist = []
        if len(infodic) != 0:
            for key,value in sorted(infodic.iteritems(), key=lambda (k,v): (v[FILETSTAMP],k), reverse=True):
                sortedlist.append((value[FILETYPE],value[FILEPATH],value[FILESIZE],value[FILETSTAMP],value[FILEHASH]))
    
        
    def diff_manifest(self, newfile, oldfile):
        if len(newfile)==0 or len(oldfile)==0:
            return {}
        
        diffdic  = {}
        if newfile != oldfile:
            for newkey, newvalue in newfile.items():
                if oldfile.has_key(newkey):
                    oldvalue = oldfile[newkey]
                    if newvalue[FILETSTAMP]>oldvalue[FILETSTAMP]:
                        self.logger.debug("Updated file '%s'" % (newvalue[FILEPATH]))
                    else:
                        self.logger.debug("No change in file '%s'" % (newvalue[FILEPATH]))
                else:
                    self.logger.debug("New file '%s'" % (newvalue[FILEPATH]))
                    diffdic[('NEW',newkey[0],newkey[1])]=newvalue
            
            for oldkey, oldvalue in oldfile.items():
                if not newfile.has_key(oldkey):
                    self.logger.debug("Ooops file removed '%s'" % (oldvalue[FILEPATH]))
                    print oldvalue
                    if oldkey[FILETYPE]=='DIR':
                        print "Adding to difflist a deleted DIR"
                        tmp = ('RMD',oldvalue[FILEPATH],oldvalue[FILESIZE],str(long(time.time())),oldvalue[FILEHASH])
                        diffdic[('DEL','RMD',oldvalue[FILEPATH])]=tmp
                    elif oldkey[FILETYPE]=='FIL':
                        print "Adding to difflist a deleted FIL"
                        tmp = ('RMF',oldvalue[FILEPATH],oldvalue[FILESIZE],str(long(time.time())),oldvalue[FILEHASH])
                        diffdic[('DEL','RMF',oldvalue[FILEPATH])]=tmp
                    elif oldkey[FILETYPE]=='RMD' or oldkey[FILETYPE]=='RMF':
                        print "Adding to difflist a previously deleted record"
                        diffdic[('CHK',oldvalue[FILETYPE],oldvalue[FILEPATH])]=oldvalue
                    else:
                        self.logger.error("Something nasty happened!")
                    
                
        else:
            print "The manifest is the same"
        return diffdic
   

    def merge_manifest(self, currentdic, diffdic):
        if len(currentdic)==0 or len(diffdic) == 0:
            return
        
        for key,value in diffdic.items():
            #print "Item ", value
            if key[0] == 'DEL':
                self.logger.debug("Adding entry in merger %s : %s" % (value[0],value[1]))
                currentdic[(key[1],key[2])]=[value[0],value[1],value[2],value[3],value[4]]
            elif key[0] == 'CHK':
                #This happens when there is a DEL old record
                if key[1]=='RMD':
                    etype = 'DIR'
                elif key[1]=='RMF':
                    etype = 'FIL'
                if currentdic.has_key((etype,value[1])):
                    #print "New entry over a deleted one has been found!", value[1]
                    pass
                else:
                    #print "Still no new entry over the deleted file! Leaving in dic. ", value[1]
                    currentdic[(key[1],key[2])]=[value[0],value[1],value[2],value[3],value[4]]
                #print "Error in merge %s : %s" % (key,value)
            
    def get_file_list(self, deep=0):
        tempdic = {}
        tempdic2 = {}
        self.inspect_folder(os.getcwd(), tempdic, deep)
        for key,value in sorted(tempdic.iteritems(), key=lambda (k,v): (v[3],k), reverse=True):
            tempdic2[key]=value
        return tempdic2
    
    def inspect_folder(self, top_level, infodic, deep=0):
        for f in os.listdir(top_level):
            if top_level==self.root_path and f == self.private_dir:
                #print "Skipping private folder"
                continue
            
            pathname = os.path.join(top_level, f)
            file_stats = os.stat(pathname)
            mode = file_stats[ST_MODE]
            if S_ISDIR(mode):
                timestamp = str(file_stats[ST_MTIME])
                fname = pathname.split(self.root_path,1)[1][1:]
                infodic[('DIR',fname)]=['DIR',fname,'0',timestamp,'0']
                self.inspect_folder(pathname, infodic, deep)
                
            elif S_ISREG(mode):
                hashfile = '0'
                filesize =  str(file_stats[ST_SIZE])
                timestamp = str(file_stats[ST_MTIME])
                fname = pathname.split(self.root_path,1)[1][1:]
                if deep:
                    hashfile = str(self.get_md5sum_hex(pathname))
                infodic[('FIL',fname)]=['FIL',fname,filesize,timestamp,hashfile]

            else:
                self.logger.error("Not a file or a directory: %s" % (str(pathname)))
    
    def get_md5sum_hex(self, filename, block_size=2**20):
        fd = open(filename, 'r')
        md5 = hashlib.md5()
        while True:
            data = fd.read(block_size)
            if not data:
                break
            md5.update(data)
        fd.close()
        return md5.hexdigest()

    '''
    def get_md5sum(self, filename, block_size=2**20):
        fd = open(filename, 'r')
        md5 = hashlib.md5()
        while True:
            data = fd.read(block_size)
            if not data:
                break
            md5.update(data)
        fd.close()
        return md5.digest()
        
    def get_statistics(self, filename, deep=0):
            filetype = ''
            hashfile = 0
            filesize = 0
            file_stats = os.lstat(filename)
            mode = file_stats[ST_MODE]
            # For directories we only need to retrieve the type and timestamp.
            # If a file inside the directory is modified also affects the directory's timestamp
            if S_ISDIR(mode):
                filetype = 'DIR'
                timestamp = file_stats[ST_MTIME]
            # For files we only need to retrieve all the information
            elif S_ISREG(mode):
                filetype = 'FIL'
                if deep:
                    hashfile = self.get_md5sum_hex(filename)
                filesize =  file_stats[ST_SIZE]
                timestamp = file_stats[ST_MTIME]
            
            fname = filename.lstrip(self.root_path)
            result = (filetype,fname,filesize,timestamp,hashfile)
            
            self.complete_list.append(result)
            return result
    '''