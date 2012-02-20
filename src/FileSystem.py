import hashlib, logging, os, sys, time
from stat import *

#folder_content = []
#root_path = '/home/tester/testdir/'
#private_dir = '.private'

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
        templist=[]
        fd = open(self.manifest_path,'r')
        lines = fd.readlines()
        fd.close()
        for line in lines:
            temp = line.strip().split('\t')
            entry = (temp[0],temp[1],temp[2],temp[3],temp[4])
            templist.append(entry)
        return templist
        
    def write_manifest(self, infolist):
        fd = open(self.manifest_path,'w')
        for i in infolist:
            #towrite = "%s?%s?%s?%s?%s" % (str(i[0]),str(i[1]),str(i[2]),str(i[3]),str(i[4]))
            towrite = "%s\t%s\t%s\t%s\t%s" % (str(i[0]),str(i[1]),str(i[2]),str(i[3]),str(i[4]))
            fd.write(towrite+'\r\n')
            self.logger.info(towrite)
        fd.close()
    
    def print_manifest(self, infolist):
        for i in infolist:
            print "%s\t%s\t%s\t%s\t%s" % (str(i[0]),str(i[1]),str(i[2]),str(i[3]),str(i[4]))
    
    def diff_manifest(self, newfile, oldfile):
        difflist=[]
        if newfile != oldfile:
            #print "Additive diff"
            for new_item in newfile:
                #print "\n\nnew_item:", new_item
                found = False
                for old_item in oldfile:
                    #print "old_item:", old_item
                    #Compare type, name and timestamp
                    if new_item[0]==old_item[0] and new_item[1]==old_item[1] and new_item[3]==old_item[3]:
                        found = True
                        break
                if not found:
                    difflist.append(new_item)
                    self.logger.debug("Pos diff: %s" % (str(new_item)))
            
            #print "\n\nNegative diff"
            for old_item in oldfile:
                #print "\n\nold_item:", old_item
                found = False
                for new_item in newfile:
                    #print "new_item:", new_item
                    #Compare type, name and timestamp
                    if new_item[0]==old_item[0] and new_item[1]==old_item[1] and new_item[3]==old_item[3]:
                        found = True
                        break
                if not found:
                    if old_item[0] == 'DIR':
                        etype = 'RMD'
                    if old_item[0] == 'FIL':
                        etype = 'RMF'

                    diffentry = (etype,old_item[1],old_item[2],str(long(time.time())),old_item[4])
                    difflist.append(diffentry)
                    self.logger.debug("Neg diff: %s" % (str(diffentry)))

        else:
            print "The manifest is the same"
        return difflist
                
    def get_file_list(self, deep=0):
        templist = []
        self.inspect_folder(os.getcwd(), templist, deep)
        #Sort the list first by timestamp
        sortedlist = sorted(templist, key=lambda data: data[3], reverse=True)
        return sortedlist
    
    def inspect_folder(self, top_level, infolist, deep=0):
        for f in os.listdir(top_level):
            #print '*** visiting...', f
            if top_level==self.root_path and f == self.private_dir:
                #print "Skipping private folder"
                continue
            
            pathname = os.path.join(top_level, f)
            file_stats = os.stat(pathname)
            mode = file_stats[ST_MODE]
            if S_ISDIR(mode):
                timestamp = str(file_stats[ST_MTIME])
                fname = pathname.split(self.root_path,1)[1][1:]
                infolist.append(('DIR',fname,'0',timestamp,'0'))
                self.inspect_folder(pathname, infolist, deep)
                
            elif S_ISREG(mode):
                hashfile = 0
                filesize =  str(file_stats[ST_SIZE])
                timestamp = str(file_stats[ST_MTIME])
                fname = pathname.split(self.root_path,1)[1][1:]
                if deep:
                    hashfile = str(self.get_md5sum_hex(pathname))
                infolist.append(('FIL',fname,filesize,timestamp,hashfile))

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