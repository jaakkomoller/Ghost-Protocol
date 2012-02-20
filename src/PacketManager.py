import logging, struct

class PacketManager():
    def __init__(self, version=1, payload_type, sequence, timestamp, ssrc):
        self.version = 0            #4 bit
        self.flags = 0              #4 bit
        self.extension_bit = 0      #1 bit
        self.nofTLV = 0             #7 bit
        self.senderID = 0           #16bit
        self.sessionID = 0          #16bit
        self.checksum = 0           #16bit
        self.sequence = 0           #32bit
        self.MF = 0                 #1 bit
        self.subsequence = 0        #15bit
        self.type = 0               #8 bit
        self.code = 0               #8 bit
        
        self.options = 0            #variable
        self.padding = 0            #variable
        
        self.TLV = []               #variable
        
        self.logger = logging.getLogger("PacketManager")
        self.logger.info("PacketManager created")
        
    def advance_timestamp(self, offset):
        self.timestamp += offset
    
    def increment_sequence(self):
        self.sequence+=1
        
    def build_packet(self, payload): 
        byte1 = 0x80
        byte2 = 0x00
        packet = struct.pack("!BB",byte1,byte2)+struct.pack("!H",self.sequence)+struct.pack("!L",self.timestamp)+struct.pack("!L",self.ssrc)+bytearray(payload)        
        return packet