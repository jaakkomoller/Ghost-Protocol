import hashlib, logging, os, string, sys, thread, time
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
        if private_dir.endswith('/'):
            private_dir = private_dir[:-1]
        self.private_dir = private_dir
        print "private_dir: ",private_dir
        self.manifest_path = self.private_dir+'/'+'.manifest'
        self.manifest_path_hash = self.private_dir+'/'+'.manifest_hash'
        print "The manifest_path:", self.manifest_path
        print "The manifest_path_hash:", self.manifest_path_hash
        self.set_private_folder()
        self.exit_flag = False
        self.thread_id = 0
        self.hash_manifest = ''
        self.starting_dic = {}
        self.current_dic = {}
        self.previous_dic = {}
        self.diff_dic = {}

    def start_thread(self, timeout=1):
        self.thread_id = thread.start_new_thread(self.loop,(timeout,))

    def loop(self,timeout):
        try:
            flag = True
            if self.exists_manifest():
                self.logger.info("Found manifest file!")
                self.starting_dic = self.read_manifest()
                self.current_dic = self.get_file_list(1)
            else:
                #self.logger.warning("Manifest file not found!")
                self.starting_dic = self.get_file_list(1)
                self.current_dic = self.starting_dic

            print "\nInitial content of the manifest file"
            self.print_manifest_dic(self.starting_dic)
            #self.current_dic = self.get_file_list(1)

            while not self.exit_flag:
                #print "\n************************************************************************"
                '''
                try:
                    raw_input('')
                except:
                    continue
                '''
                '''
                if len(self.diff_dic) != 0:
                    self.merge_manifest(self.current_dic, self.diff_dic)
                if flag:
                    self.diff_dic = self.diff_manifest(self.current_dic, self.starting_dic)
                    self.previous_dic = self.current_dic
                    flag = False
                else:
                '''
                self.current_dic = self.get_file_list(1)

                self.diff_dic = self.diff_manifest(self.current_dic, self.previous_dic)
                #print "\nPrinting diff dictionary from current to previous"
                #self.print_manifest_dic(self.diff_dic)
                #print('\n')
                self.merge_manifest(self.current_dic, self.diff_dic)
                #print "\nPrinting current dictionary"
                #self.print_manifest_dic(self.current_dic)
                #print('\n')

                self.previous_dic = self.current_dic
                #print "\nThis is the actual manifest file"
                #print self.get_local_manifest()
                #self.print_manifest_dic(self.current_dic)
                #print('\n')

                self.write_manifest(self.current_dic)
                #Update hash manifest
                self.hash_manifest = FileSystem.get_md5sum_hex(self.manifest_path_hash, block_size=2**20)
                print "hash_manifest:", self.hash_manifest
                #Sleep for 1 second and detect changes
                time.sleep(timeout)

        except Exception as e:
            print "Something nasty happened!"
            print e.args

    def terminate_thread(self):
        self.exit_flag = True

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
            self.logger.warning("Manifest file not found!")
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
        fd2 = open(self.manifest_path+'_hash','w')
        for key,value in sorted(infodic.iteritems(), key=lambda (k,v): (v[FILETSTAMP],k), reverse=True):
            towrite = "%s\t%s\t%s\t%s\t%s" % (value[FILETYPE],value[FILEPATH],value[FILESIZE],value[FILETSTAMP],value[FILEHASH])
            fd.write(towrite+'\r\n')
            towrite = "%s\t%s\t%s\t%s" % (value[FILETYPE],value[FILEPATH],value[FILESIZE],value[FILEHASH])
            fd2.write(towrite+'\r\n')
            #self.logger.debug(towrite)
        fd.close()
        fd2.close()

    def print_manifest(self, infolist):
        for i in infolist:
            print "%s\t%s\t%s\t%s\t%s" % (i[FILETYPE],i[FILEPATH],i[FILESIZE],i[FILETSTAMP],i[FILEHASH])

    def print_manifest_dic(self, infodic):
        if len(infodic) != 0:
            for key,value in sorted(infodic.iteritems(), key=lambda (k,v): (v[FILETSTAMP],k), reverse=True):
                print "%s\t%s\t%s\t%s\t%s" % (value[FILETYPE],value[FILEPATH],value[FILESIZE],value[FILETSTAMP],value[FILEHASH])

    def join_entries(self, itemlist, token):
        tmplist = []
        for item in itemlist:
            tmplist.append(string.joinfields(item,token))
        return tmplist

    def get_sorted_list(self, infodic):
        sortedlist = []
        if len(infodic) != 0:
            for key,value in sorted(infodic.iteritems(), key=lambda (k,v): (v[FILETSTAMP],k), reverse=True):
                sortedlist.append([value[FILETYPE],value[FILEPATH],value[FILESIZE],value[FILETSTAMP],value[FILEHASH]])
        return sortedlist

    def get_local_manifest(self):
        current_list = self.get_sorted_list(self.previous_dic)
        return self.join_entries(current_list, '?')

    def get_diff_manifest(self, new_manifest):
        tmpdic = {}

        for item in new_manifest:
            tmpitem = item.split('?')
            tmpdic[(tmpitem[0],tmpitem[1])] = tmpitem

        diffdic = self.diff_manifest(tmpdic, self.previous_dic)
        return self.join_entries(self.get_sorted_list(diffdic), '?')

    def get_diff_manifest_remote(self, remote_manifest):
        tmpdic = {}

        for item in remote_manifest:
            tmpitem = item.split('?')
            tmpdic[(tmpitem[0],tmpitem[1])] = tmpitem

        diffdic = self.diff_manifest_remote(tmpdic, self.previous_dic)
        return self.join_entries(self.get_sorted_list(diffdic), '?')

    def diff_manifest(self, newfile, oldfile):
        if len(newfile)==0 or len(oldfile)==0:
            return {}

        diffdic  = {}
        if newfile != oldfile:
            for newkey, newvalue in newfile.items():
                if oldfile.has_key(newkey):
                    oldvalue = oldfile[newkey]
                    if newvalue[FILETSTAMP]>oldvalue[FILETSTAMP] and newvalue[FILEHASH]!=oldvalue[FILEHASH]:
                        self.logger.debug("Updated file '%s'" % (newvalue[FILEPATH]))
                    else:
                        #self.logger.debug("No change in file '%s'" % (newvalue[FILEPATH]))
                        pass
                else:
                    self.logger.debug("New file '%s'" % (newvalue[FILEPATH]))
                    diffdic[('NEW',newkey[0],newkey[1])]=newvalue

            for oldkey, oldvalue in oldfile.items():
                if not newfile.has_key(oldkey):
                    #self.logger.debug("Ooops file removed '%s'" % (oldvalue[FILEPATH]))
                    #print oldvalue
                    if oldkey[FILETYPE]=='DIR':
                        self.logger.debug("Deleted DIR '%s'" % (str(oldkey[FILEPATH])))
                        tmp = ('RMD',oldvalue[FILEPATH],oldvalue[FILESIZE],str(long(time.time())),oldvalue[FILEHASH])
                        diffdic[('DEL','RMD',oldvalue[FILEPATH])]=tmp
                    elif oldkey[FILETYPE]=='FIL':
                        self.logger.debug("Deleted FIL '%s'" % (str(oldkey[FILEPATH])))
                        tmp = ('RMF',oldvalue[FILEPATH],oldvalue[FILESIZE],str(long(time.time())),oldvalue[FILEHASH])
                        diffdic[('DEL','RMF',oldvalue[FILEPATH])]=tmp
                    elif oldkey[FILETYPE]=='RMD' or oldkey[FILETYPE]=='RMF':
                        #self.logger.debug("Adding to difflist a previously deleted record")
                        diffdic[('CHK',oldvalue[FILETYPE],oldvalue[FILEPATH])]=oldvalue
                    else:
                        self.logger.error("Something nasty happened!")
        else:
            #print "The manifest is the same"
            pass
        return diffdic


    def diff_manifest_remote(self, remotefile, localfile):
        #if len(remotefile)==0 or len(localfile)==0:
        #    return {}
        diffdic  = {}

        if len(localfile)==0:
            return remotefile

        if remotefile != localfile:
            for remotekey, remotevalue in remotefile.items():
                if localfile.has_key(remotekey):
                    localvalue = localfile[remotekey]
                    if remotevalue[FILETSTAMP]>localvalue[FILETSTAMP] and (remotevalue[0]=='RMF' or remotevalue[0]=='RMD'):
                        self.logger.debug("Update local timestamp of a deleted file '%s'" % (remotevalue[FILEPATH]))
                        localvalue[FILETSTAMP] = remotevalue[FILETSTAMP]

                    elif remotevalue[FILETSTAMP]>localvalue[FILETSTAMP] and remotevalue[FILEHASH]!=localvalue[FILEHASH]:
                        self.logger.debug("Updated file '%s'" % (remotevalue[FILEPATH]))
                        diffdic[('NEW',remotekey[0],remotekey[1])]=remotevalue
                    else:
                        #self.logger.debug("No change in file '%s'" % (newvalue[FILEPATH]))
                        pass
                else:
                    self.logger.debug("New entry-file '%s'" % (remotevalue[FILEPATH]))
                    if remotevalue[0]=='RMF' or remotevalue[0]=='RMD':
                        print "Adding a remote RMF/RMD to our local manifest"
                        localfile[remotekey] = remotevalue
                    else:
                        diffdic[('NEW',remotekey[0],remotekey[1])]=remotevalue

        else:
            self.logger.debug("The manifest is the same")
            pass
        return diffdic



    def merge_manifest(self, currentdic, diffdic):
        if len(currentdic)==0 or len(diffdic) == 0:
            return

        for key,value in diffdic.items():
            #print "Item ", value
            if key[0] == 'DEL':
                #self.logger.debug("Adding entry in merger %s : %s" % (value[0],value[1]))
                currentdic[(key[1],key[2])]=[value[0],value[1],value[2],value[3],value[4]]
            elif key[0] == 'CHK':
                #This happens when there is a DEL old record
                if key[1]=='RMD':
                    etype = 'DIR'
                elif key[1]=='RMF':
                    etype = 'FIL'
                if currentdic.has_key((etype,value[1])):
                    #print "New entry over a deleted one has been found! %s:%s" % (str(etype),str(value[1]))
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
                    hashfile = str(FileSystem.get_md5sum_hex(pathname))
                infodic[('FIL',fname)]=['FIL',fname,filesize,timestamp,hashfile]

            else:
                self.logger.error("Not a file or a directory: %s" % (str(pathname)))

    @staticmethod
    def get_md5sum_hex(filename, block_size=2**20):
        fd = open(filename, 'r')
        md5 = hashlib.md5()
        while True:
            data = fd.read(block_size)
            if not data:
                break
            md5.update(data)
        fd.close()
        return md5.hexdigest()

    def get_hash_manifest(self):
        return self.hash_manifest
