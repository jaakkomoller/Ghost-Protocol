import hashlib, logging
from Crypto.PublicKey import RSA
from Crypto import Cipher
from Crypto import Random


class Security:
    def __init__(self):
        self.logger = logging.getLogger("Crypto/Security")
        #Select a model: http://en.wikipedia.org/wiki/Block_cipher_modes_of_operation
        self.cryptoMode = Cipher.AES.MODE_CBC
    
    def set_cryptoMode(self, mode):
        self.cryptoMode = mode
        
    def generate_keys(self, nbits):
        #Generates a set of private/public key
        privateKey = RSA.generate(nbits)
        publicKey = privateKey.publickey()
        return (privateKey, publicKey)
    
    def generate_sharedkey(self):
        iv = Random.new().read(AES.block_size)
        key = Random.new().read(AES.block_size)
        cipher = AES.new(key, AES.MODE_CFB, iv)
        return (iv,key,cipher)
    
    def encrypt_sharedkey(self,iv,cipher,data):
        msg = iv + cipher.encrypt(str(data))
        return msg
    
    def decrypt_sharedkey(self,iv,cipher,data):
        msg = cipher.decrypt(data)[len(iv):]
        
    
    def import_key(self, plaintextkey):
        return RSA.importKey(plaintextkey)
    
    def export_key(self, key):
        return key.exportKey()
    
    def encrypt(self, key, data,chunksize=0, nbytes=0):
        ciphertext = ''
        i = 0
        for i in range(0,len(data)/chunksize):
            a = i*chunksize
            b = a+chunksize
            ciphertext += key.encrypt(data[a:b], self.cryptoMode)[0]
        if b < len(data):
            ciphertext += key.encrypt(data[b:], self.cryptoMode)[0]
        
        return ciphertext[nbytes:]
        #return key.encrypt(data[nbytes:], self.cryptoMode)[0]
    
    def decrypt(self, key, data,chunksize=0, nbytes=0):
        ciphertext = ''
        i = 0
        for i in range(0,len(data)/chunksize):
            a = i*chunksize
            b = a+chunksize
            ciphertext += key.decrypt(data[a:b])
        if b < len(data):
            ciphertext += key.decrypt(data[b:])
        
        return ciphertext[nbytes:]
        #return key.decrypt(data[nbytes:])
    
    #Different values for key and password
    def calculate_key_hash(self, key, pwd):
        md5 = hashlib.md5()
        md5.update(key)
        md5.update(pwd)
        return md5.hexdigest()
    
    #Values is a list of elements to calculate the hash from
    def get_md5sum_hex(self, values):
        md5 = hashlib.md5()
        for item in values:
            md5.update(item)
        return md5.hexdigest()
    