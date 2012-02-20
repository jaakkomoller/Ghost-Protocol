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
        
        self.TLVs = []               #variable
        
        self.logger = logging.getLogger("PacketManager")
        self.logger.info("PacketManager created")
        
    def calculate_checksum(self):
        pass
    
    def verify_checksum(self):
        pass
        
    def build_packet(self, payload): 

        byte1 = 0x80
        byte2 = 0x00
        byte3 = 0x00
        packet = struct.pack("!BB",byte1,byte2)+struct.pack("!H",self.sequence)+struct.pack("!L",self.timestamp)+struct.pack("!L",self.ssrc)+bytearray(payload)        
        return packet