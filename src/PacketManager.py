'''
To do:
* Add variables for dynamic field size -> Not really possible anymore with TLV field
* Build a dictionary with TLVtypes for verification
*** Read TLV from rawdata: DONE ***
'''

import logging, struct

TLVTYPESIZE = 1
TLVLENSIZE = 3
NOTLV = 0

class PacketManager():
    def create_packet(self, version=1, flags=0, exp=0, nextTLV=0, senderID=0, txlocalID=0,
                 txremoteID=0, sequence=0, otype=0, ocode=0, TLVlist=None, rawdata=None):
        
        self.logger = logging.getLogger("PacketManager")
        self.logger.info("PacketManager created")
        
        if rawdata:
            self.packetize_raw(rawdata)
            return
        
        self.version = version              #4 bit
        self.flags = flags                  #4 bit
        self.exp = exp                      #0 bit
        self.nextTLV = 0xFF                 #8 bit
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
            self.append_list_to_TLVlist(TLVlist)
    
    def packetize_raw(self, rawdata):
        tempraw = rawdata
        
        tmpbyte = ord(tempraw[0])
        self.version = tmpbyte >> 4
        self.flags = tmpbyte & 0x0F

        self.nextTLV = ord(tempraw[1])
        
        self.senderID = ord(tempraw[2]) << 8 | ord(tempraw[3])
        self.txlocalID = ord(tempraw[4]) << 8 | ord(tempraw[5])
        self.txremoteID = ord(tempraw[6]) << 8 | ord(tempraw[7])
        self.sequence = ord(tempraw[8]) << 24 | ord(tempraw[9]) << 16 | ord(tempraw[10]) << 8 | ord(tempraw[11])
        
        self.otype = ord(tempraw[12])
        self.ocode = ord(tempraw[13])
        self.checksum = ord(tempraw[14]) << 8 | ord(tempraw[15])
        
        self.print_packet()
        
        if not self.verify_checksum():
            self.logger.debug("[packetize_raw] Checksum failed!! Failed to recover packet header!")
            return False
        if self.nextTLV == 0xFF:
            self.logger.debug("[packetize_raw] No TLVs in this packet!")
            return True
        
        i = 16
        ntype = 0
        while ntype != 0xFF:
            #For the first TLV the type is in the packet header
            if i == 16:
                ctype = self.nextTLV
            else:
                ctype = ntype
            
            ntype = ord(tempraw[i:i+TLVTYPESIZE])
            #print "ntype: %d:%s" % (ntype, chr(ntype))
            i+=TLVTYPESIZE
            
            for j in range(0,TLVLENSIZE):
                temp = tempraw[i]
                if ord(temp) == 0:
                    temp = '0'
                clen = 10**(TLVLENSIZE-j-1) * int(temp)
                i+=1
            #print "clen: %d : %s " % (clen, type(clen))
            cvalue = str(tempraw[i:i+clen])
            i+=clen
            #print "The TLV extracted is", (chr(ctype),clen,cvalue)
            self.append_entry_to_TLVlist(chr(ctype),cvalue)
            
        
     
    def create_TLV_entry(self, TLVtype, TLVvalue):
        if len(TLVvalue)>=10**TLVLENSIZE:
            self.logger.error("Error adding TLV %s:%s:%s" % (TLVtype, str(len(TLVvalue)), TLVvalue))
            return
        
        etype = ord(TLVtype)
        elen = (TLVLENSIZE - len(str(len(TLVvalue)))) * '0' + str(len(TLVvalue))
        evalue = TLVvalue
        return (etype,elen,evalue)
    
    def append_entry_to_TLVlist(self, TLVtype, TLVvalue): #entry coded as (type,value)
        tlventry = self.create_TLV_entry(TLVtype, TLVvalue)
        if tlventry != None:
            self.TLVs.append(tlventry)
        
    def append_list_to_TLVlist(self, infolist): #infolist coded as [(type,value)]
        for item in infolist:
            tlventry = self.create_TLV_entry(item[0], item[1])
            self.TLVs.append(tlventry)

    def calculate_checksum(self):
        tempsum = 0L
        
        subchunk1 = (self.version << 4 | self.flags) << 8 | self.nextTLV
        subchunk2 = int(self.sequence >> 8)
        subchunk3 = int(self.sequence & 0xFF)
        subchunk4 = self.otype << 8 | self.ocode
        #subchunk4 = ord(self.otype) << 8 | ord(self.ocode)
        
        tempsum = subchunk1 + self.senderID + self.txlocalID + self.txremoteID + subchunk2 + subchunk3 + subchunk4
        #print "The tempsum is \n", hex(tempsum)
        tempcarry = tempsum >> 16
        #print "The carry is \n", hex(tempcarry)
        tempsum = tempcarry + (tempsum & 0xFFFF)
        #print "Flipping bits..."
        tempsum = ~tempsum & 0xFFFF
        #print "The checksum is \n", hex(tempsum)
        return tempsum
        
    
    def verify_checksum(self):
        calculated_checksum = self.calculate_checksum()
        
        if calculated_checksum == self.checksum:
            self.logger.debug("Checksum verification successful!!")
            return True
        else:
            self.logger.error("Checksum verification failed!!")
            return False
    
    def build_TLVs(self):
        tempstring = ''
        i=0
        
        if len(self.TLVs) == 0:
            self.logger.debug("There are no TLVs to build")
            return
        
        while i < len(self.TLVs):
            item = self.TLVs[i]
            if i==0:
                self.nextTLV = item[0] #NextTLV field is type of the first TLV
            #Check whether are not at the last element
            if i+1 == len(self.TLVs):
                self.logger.debug("There is no next TLV to build")
                tempstring += struct.pack("!B", 0xFF)
            else:
                #Append type of the next element
                tempstring += struct.pack("!B", self.TLVs[i+1][0])
            for j in item[1]:
                tempstring += struct.pack("!B", ord(j))
            for j in item[2]:
                tempstring += struct.pack("!B", ord(j))
            i+=1
        
        self.bytearrayTLV = tempstring
            
    def build_packet(self): 
        #First build TLV so the field nextType is filled
        self.build_TLVs()
        #Then we can calculate the checksum for the protocol header
        self.checksum = self.calculate_checksum()
        
        byte1 = self.version << 4 | self.flags
        byte2 = self.nextTLV
        
        #Now we can proceed packing the whole structure for network transferring
        packet = struct.pack("!BB",byte1,byte2)+struct.pack("!H",self.senderID)+\
                    struct.pack("!H",self.txlocalID)+struct.pack("!H",self.txremoteID)+\
                    struct.pack("!L",self.sequence)+struct.pack("!BB",self.otype,self.ocode)+\
                    struct.pack("!H",self.checksum)+self.bytearrayTLV
        
        return packet
    
    def print_packet(self):
        print "version: '%s':'%x'" % (self.version,self.version)
        print "flags: '%s':'%x'" % (self.flags,self.flags)
        print "nextTLV: '%s':'%x'" % (self.nextTLV,self.nextTLV)
        print "senderID: '%s':'%x'\n" % (self.senderID,self.senderID)
        print "txlocalID: '%s':'%x'" % (self.txlocalID,self.txlocalID)
        print "txremoteID: '%s':'%x'\n" % (self.txremoteID,self.txremoteID)
        print "sequence: '%s':'%x'\n" % (self.sequence,self.sequence)
        print "otype: '%s':'%x'" % (self.otype,self.otype)
        print "ocode: '%s':'%x'" % (self.ocode,self.ocode)
        print "checksum: '%s':'%x'\n" % (self.checksum,self.checksum)
