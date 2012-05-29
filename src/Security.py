import hashlib, logging
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES
from Crypto import Cipher
from Crypto import Random

import base64
import os

class Security:
    def __init__(self):
        self.logger = logging.getLogger("Crypto/Security")
        #Select a model: http://en.wikipedia.org/wiki/Block_cipher_modes_of_operation
        self.cryptoMode = Cipher.AES.MODE_CBC
        # the block size for the cipher object; must be 16, 24, or 32 for AES
        self.BLOCK_SIZE = 32
        # the character used for padding--with a block cipher such as AES, the value
        # you encrypt must be a multiple of BLOCK_SIZE in length.  This character is
        # used to ensure that your value is always a multiple of BLOCK_SIZE
        self.PADDING = '{'
    
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
    
    def generate_key_AES(self):
        # one-liner to sufficiently pad the text to be encrypted
        pad = lambda s: s + (self.BLOCK_SIZE - len(s) % self.BLOCK_SIZE) * self.PADDING
        
        # one-liners to encrypt/encode and decrypt/decode a string
        # encrypt with AES, encode with base64
        self.EncodeAES = lambda c, s: base64.b64encode(c.encrypt(pad(s)))
        self.DecodeAES = lambda c, e: c.decrypt(base64.b64decode(e)).rstrip(self.PADDING)
        
        # generate a random secret key
        secret = os.urandom(self.BLOCK_SIZE)
        
        # create a cipher object using the random secret
        cipher = AES.new(secret)
        return cipher
    
    def encrypt_AES(self,cipher,data):
        return self.EncodeAES(cipher, data)
    
    def decrypt_AES(self,cipher,data):
        return self.DecodeAES(cipher, data)
        
    def import_key(self, plaintextkey):
        return RSA.importKey(plaintextkey)
    
    def export_key(self, key):
        return key.exportKey()
    
    def encrypt(self, key, data,chunksize=0, nbytes=0):
        ciphertext = ''
        i = 0
        a = 0
        b = 0
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
        a = 0
        b = 0
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
    