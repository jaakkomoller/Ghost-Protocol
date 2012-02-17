import hashlib, os, sys
from stat import *

my_folder = []
root_path = '/home/tester/testdir/'
private_dir = '.private'

def set_private_folder():
    os.chdir(root_path)
    if private_dir in os.listdir(os.getcwd()):
        print "'%s' directory already exists" % (str(private_dir))
    else:
        os.mkdir(private_dir)
        print "'%s' directory created successfully" % (str(private_dir))

def create_manifest():
    del my_folder[:]
    set_private_folder()
    os.chdir(root_path)
    print "Current active directory: %s" % str(os.getcwd())
    walktree(os.getcwd())
    manifest_fd = open(private_dir+'/'+'.manifest','w')
    for i in my_folder:
        to_write = "%s?%s?%s?%s?%s" % (str(i[0]),str(i[1]),str(i[2]),str(i[3]),str(i[4]))
        manifest_fd.write(to_write+'\r\n')
        print "logging: ", to_write
    manifest_fd.close()


def walktree(top):
    for f in os.listdir(top):
        #Skip private folder form synchronization
        if f == private_dir:
            break
        pathname = os.path.join(top, f)
        mode = os.stat(pathname)[ST_MODE]
        if S_ISDIR(mode):
            # It's a directory, get stats and go recursive
            get_statistics(pathname)
            walktree(pathname)
        elif S_ISREG(mode):
            # It's a file, get stats
            get_statistics(pathname)
        else:
            # Unknown file type, print a message
            print 'Skipping %s' % pathname

def get_statistics(filename):
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
        hashfile = get_md5sum_hex(filename)
        filesize =  file_stats[ST_SIZE]
        timestamp = file_stats[ST_MTIME]
    
    fname = filename.lstrip(root_path)
    result = (filetype,fname,filesize,timestamp,hashfile)
    print 'visiting:', result
    my_folder.append(result)
    

def get_md5sum(filename, block_size=2**20):
    fd = open(filename, 'r')
    md5 = hashlib.md5()
    while True:
        data = fd.read(block_size)
        if not data:
            break
        md5.update(data)
    fd.close()
    return md5.digest()

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

