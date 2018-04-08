#!/usr/bin/env python3
import socket, struct, threading, sys, base64

mode = sys.argv[1]
infile = open(sys.argv[3], 'rb')
outfile = open(sys.argv[4], 'wb')

if(mode == "-c"):
	HOST = sys.argv[2][0 : sys.argv[2].find(':')]
	PORT = int(sys.argv[2][sys.argv[2].find(':') + 1:])
	tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
	dest = (HOST, PORT)
	tcp.connect(dest)
else:
	HOST = ''
	PORT = int(sys.argv[2])
	tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
	orig = (HOST, PORT)
	tcp.bind(orig)
	tcp.listen(1)
	tcp, address = tcp.accept()


SendAck = False;
SendMsgPermission = False;
ReSendMsg = False;
lock = threading.Lock()

def sentMessage():
	global SendMsgPermission
	lock.acquire()
	try:		
		SendMsgPermission = False;
	finally:
		lock.release()

def sentAck():
	global SendAck
	lock.acquire()
	try:
		SendAck = False;
	finally:
		lock.release()

def receivedMessage():
	global SendAck 
	lock.acquire()
	try:		
		SendAck = True;
	finally:
		lock.release()

def receivedAck():
	global SendMsgPermission
	lock.acquire()
	try:

		SendMsgPermission = True;
	finally:
		lock.release()




def calcChecksum(frame):
	checksum = 0
	d = 0
	for b in range(len(frame)//2):
		checksum += frame[b*2]*(256) + frame[b*2 + 1]
		checksum = checksum if(checksum//(2**16) == 0) else checksum%(2**16) +1
	if(len(frame)%2 != 0):
	  checksum += frame[len(frame)-1]*256
	  checksum = checksum if(checksum//(2**16) == 0) else checksum%(2**16) +1

	frame[10:] = bytearray([checksum//256, checksum%256])
	return frame


def createFrame(msg, id, flag):
	frame = bytearray([220, 192, 35, 194])
	frame[4:] = frame[:]
	frame[8:] = bytearray([0,0]) if(msg == "") else bytearray([len(msg)//256, len(msg)%256])
	frame[10:] = bytearray([0, 0])
	frame[12:] = bytearray([0]) if(id == 0) else bytearray([1])
	frame[13:] = bytearray([0]) if(flag == 0) else bytearray([128])
	frame[14:] = msg[:]
	frame = calcChecksum(frame)

def sent(tcp, infile):
	while True:
		global SendAck
		global SendMsgPermission
		if(SendMsgPermission):
			msg = infile.read(2**16 - 1)
			createFrame(msg, id, 0)
			if(msg != ""):
				sentMessage()
				print(mode, "send", msg, st)
				msg = struct.pack('!1s', msg.encode('ascii', 'ignore'))				
				tcp.send(msg)

		if(SendAck):
			sentAck()
			print(mode, "send", ";", st)
			msg = struct.pack('!1s', (";").encode('ascii', 'ignore'))			
			tcp.send(msg)

def receive(tcp, outfile):
	while True:
		msg = tcp.recv(1)
		msg = struct.unpack('!1s', msg)[0]
		msg = str(msg, 'utf-8')
		if(msg == ";"):
			print(mode, "rcv", msg, st)
			receivedAck()
		else:
			print(mode, "rcv", msg, st)
			outfile.write(msg)
			outfile.flush()
			receivedMessage()

threading.Thread(target = receive, args = (tcp, outfile, )).start()
threading.Thread(target = sent, args = (tcp, infile, )).start()