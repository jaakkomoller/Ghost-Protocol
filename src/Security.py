import hashlib, logging
from Crypto.PublicKey import RSA
from Crypto import Cipher


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
    
    def import_key(self, plaintextkey):
        return RSA.importKey(plaintextkey)
    
    def export_key(self, key):
        return key.exportKey()
    
    def encrypt(self, key, data):
        return key.encrypt(data, self.cryptoMode)[0]
    
    def decrypt(self, key, data):
        return key.decrypt(data)
    
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
    