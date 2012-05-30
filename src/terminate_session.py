import logging, socket, random, select, sys, time
from threading import Thread

from PacketManager import *


if len(sys.argv)!=4:
	sys.exit("Usage: terminate_session.py <local session id> <remote session id> <port>")
	

clisocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

packet_to_send = OutPacket()
packet_to_send.create_packet(version=1, flags=[0], senderID=20, txlocalID=int(sys.argv[1]), txremoteID=int(sys.argv[2]), otype='BYE', ocode='REQUEST')


port=int(sys.argv[3])

clisocket.sendto(packet_to_send.build_packet(), ("127.0.0.1", port))

