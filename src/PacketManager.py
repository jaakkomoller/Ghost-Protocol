'''
To do:
* Add variables for dynamic field size
* Build a dictionary with TLVtypes for verification
* Read TLV from rawdata

'''

import logging, struct

TLVTYPESIZE = 4
TLVLENSIZE = 3

class PacketManager():
    def __init__(self, version=1, flags=0, exp=0, nextTLV=0, senderID=0, txlocalID=0,
                 txremoteID=0, sequence=0, otype=0, ocode=0, TLVlist=None, rawdata=None):
        
        if rawdata:
            self.packetize_raw(rawdata)
            return
        
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
        self.bytearrayTLV = ''              #variable
        self.TLVs = []                      #variable
        
        if TLVlist is not None:
            self.add_TLV_list()
        
        self.logger = logging.getLogger("PacketManager")
        self.logger.info("PacketManager created")
    
    
    def packetize_raw(self, rawdata):
        #tempraw = rawdata[:]
        tempraw = bytearray(rawdata)
        
        tmpbyte = tempraw[0]
        self.version = tmpbyte >> 4
        self.flags = tmpbyte & 0x0F
        
        tmpbyte = tempraw[1]
        '''
        self.exp = tmpbyte >> (8-(8-TLVTYPESIZE))
        mask = 0xFF >> (8-TLVTYPESIZE)
        self.nextTLV = tmpbyte & mask
        '''
        self.exp = tmpbyte >> 4
        self.nextTLV = tmpbyte & 0x0F
        
        self.senderID = tempraw[2] << 8 | tempraw[3]
        self.txlocalID = tempraw[4] << 8 | tempraw[5]
        self.txremoteID = tempraw[6] << 8 | tempraw[7]
        self.sequence = tempraw[8] << 24 | tempraw[9] << 16 | tempraw[10] << 8 | tempraw[11]
        
        self.otype = tempraw[12]
        self.ocode = tempraw[13]
        self.checksum = tempraw[14] << 8 | tempraw[15]
        
        if not self.verify_checksum():
            self.logger.debug("[packetize_raw] Failed to recover packet header!")
            return False
        if self.nextTLV == 'NULL':
            self.logger.debug("[packetize_raw] No TLVs in this packet!")
            return True
        
        rawtlv = tempraw[16:]
        print "Now we need to process the raw-TLVs:\n", rawtlv
        print "Add the logic to read the TLVs from the code"
        
        
        
     
    def create_TLV_entry(self, TLVtype, TLVvalue):
        if len(TLVtype) <= 0 or len(TLVtype) > TLVTYPESIZE or len(TLVvalue)>=10**TLVLENSIZE:
            self.logger.error("Error adding TLV %s:%s:%s" % (TLVtype, str(len(TLVvalue)), TLVvalue))
            return
        
        etype = (TLVTYPESIZE - len(TLVtype)) * ' ' + TLVtype
        elen = (TLVLENSIZE - len(str(len(TLVvalue)))) * '0' + str(len(TLVvalue))
        evalue = TLVvalue
        #print "This is how the entry looks like"
        #print bytearray(etype+elen+evalue)
        return (bytearray(etype),bytearray(elen),bytearray(evalue))
    
    def append_entry_to_TLVlist(self, entry): #entry coded as (type,value)
        tlventry = self.create_TLV_entry(entry[0], entry[1])
        if tlventry != None:
            self.TLVs.append(tlventry)
        
    def append_list_to_TLVlist(self, infolist): #infolist coded as [(type,value)]
        for item in infolist:
            tlventry = self.create_TLV_entry(item[0], item[1])
            self.TLVs.append(tlventry)

    def calculate_checksum(self):
        tempsum = 0L
        
        subchunk1 = (self.version << 4 | self.flags) << 8 | (self.exp << 4 | self.nextTLV)
        subchunk2 = int(self.sequence >> 8)
        subchunk3 = int(self.sequence & 0xFF)
        subchunk4 = self.otype << 8 | self.ocode
        
        tempsum = subchunk1 + self.senderID + self.txlocalID + self.txremoteID + subchunk2 + subchunk3 + subchunk4
        #print "The tempsum is \n", hex(tempsum)
        tempcarry = tempsum >> 16
        #print "The carry is \n", hex(tempcarry)
        tempsum = tempcarry + (tempsum & 0xFFFF)
        #print "Flipping bits..."
        tempsum = ~tempsum & 0xFFFF
        #print "The checksum is \n", hex(tempsum)
        self.checksum = tempsum
    
    def verify_checksum(self):
        tempsum = 0L
        
        subchunk1 = (self.version << 4 | self.flags) << 8 | (self.exp << 4 | self.nextTLV)
        subchunk2 = int(self.sequence >> 8)
        subchunk3 = int(self.sequence & 0xFF)
        subchunk4 = self.otype << 8 | self.ocode
        
        tempsum = subchunk1 + self.senderID + self.txlocalID + self.txremoteID + subchunk2 + subchunk3 + subchunk4
        tempcarry = tempsum >> 16
        tempsum = tempcarry + (tempsum & 0xFFFF)
        tempsum = ~tempsum & 0xFFFF
        
        if tempsum == self.checksum:
            return True
        else:
            self.logger.error("Checksum verification failed!!")
            return False
    
    def build_TLVs(self):
        temparray = []
        i=0
        
        if len(self.TLVs) == 0:
            self.logger.debug("There are no TLVs to build")
            self.nextTLV = 'NULL'
            return
        
        while i < len(self.TLVs):
            item = self.TLVs[i]
            if i==0:
                self.nextTLV = item[0] #NextTLV type of the first TLV
            
            #Check whether are not at the last element
            if i+1 == len(self.TLVs):
                self.logger.debug("There is no next TLVs to build")
                temparray.append('NULL')
            else:
                #Append type of the next element
                temparray.append(self.TLVs[i+1][0])
            temparray.append(item[1])
            temparray.append(item[2])
            i+=1
        
        for item in temparray:
            self.bytearrayTLV += bytearray(item)
        
        print "This is how the bytearray looks like!"
        print self.bytearrayTLV
            
    def build_packet(self, payload): 
        byte1 = self.version << 4 | self.flags
        byte2 = self.exp << 4 | self.nextTLV
        
        #First build TLV so the field nextType is filled
        self.build_TLVs()
        #Then we can calculate the checksum for the protocol header
        self.calculate_checksum()
        #Now we can proceed packing the whole structure for network transferring
        packet = struct.pack("!BB",byte1,byte2)+struct.pack("!H",self.senderID)+\
                    struct.pack("!H",self.txlocalID)+struct.pack("!H",self.txremoteID)+\
                    struct.pack("!L",self.sequence)+struct.pack("!BB",self.otype,self.ocode)+\
                    struct.pack("!L",self.checksum)+self.bytearrayTLV
        
        return packet
    