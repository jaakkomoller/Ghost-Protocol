#Some comment

import logging, struct

class PacketManager():
    def __init__(self, version=1, flags=0, exp=0, nextTLV=0, senderID=0, txlocalID=0,
                 txremoteID=0, sequence=0, otype=0, ocode=0):
        self.version = version              #4 bit
        self.flags = flags                  #4 bit
        self.exp = exp                      #4 bit
        self.nextTLV = nextTLV              #4 bit
        self.senderID = senderID            #16bit
        self.txlocalID = txlocalID          #16bit
        self.txremoteID = txremoteID        #16bit
        self.sequence = sequence            #32bit
        self.otype = otype                  #8 bit
        self.ocode = ocode                  #8 bit
        self.checksum = 0                   #16bit
        
        self.TLVs = []                      #variable
        
        self.logger = logging.getLogger("PacketManager")
        self.logger.info("PacketManager created")
        
    def calculate_checksum(self):
        pass
    
    def verify_checksum(self):
        pass
    
    def build_TLVs(self):
        bytearray(self.TLVs)
        pass
        
    def build_packet(self, payload): 
        byte1 = self.version << 4 | self.flags
        byte2 = self.exp << 4 | self.nextTLV

        packet = struct.pack("!BB",byte1,byte2)+struct.pack("!H",self.senderID)+\
                    struct.pack("!H",self.txlocalID)+struct.pack("!H",self.txremoteID)+\
                    struct.pack("!L",self.sequence)+struct.pack("!BB",self.otype,self.ocode)+\
                    struct.pack("!L",self.checksum)+self.build_TLVs()
        
        return packet