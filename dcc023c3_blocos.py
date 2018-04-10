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

state = 0
#state 0 n tem que mandar confirmação e pode mandar mensagem
#state 1 n tem que mandar confirmação e não pode mandar mensagem
#state 2 tem que mandar confirmação e pode mandar mensagem
#state 3 tem que mandar confirmação e n pode mandar mensagem
lock = threading.Lock()

def setstate(val):
	global state
	lock.acquire()
	try:
		if(val == 1 and state == 0):
			state = 1
		elif(val == 1 and state == 2):
			state = 3
		elif(val == 2 and state == 2):
			state = 0
		elif(val == 2 and state == 3):
			state = 1
		elif(val == -1 and state == 1):
			state = 0
		elif(val == -1 and state == 3):
			state = 2
		elif(val == -2 and state == 0):
			state = 2
		elif(val == -2 and state == 1):
			state = 3
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
	checksum = checksum ^ 0xffff
	frame[10:11] = bytearray([checksum//256])
	frame[11:12] = bytearray([checksum%256])

	return frame[:]


def createFrame(msg, id, flag):
	frame = bytearray([220, 192, 35, 194])
	frame[4:] = frame[:]
	frame[8:] = bytearray([0,0]) if(msg == "") else bytearray([len(msg)//256, len(msg)%256])
	frame[10:] = bytearray([0, 0])
	frame[12:] = bytearray([0]) if(id == 0) else bytearray([1])
	frame[13:] = bytearray([0]) if(flag == 0) else bytearray([128])
	frame[14:] = msg[:]
	print(frame)
	frame = calcChecksum(frame)
	return frame[:]

def sent(tcp, infile):
	while True:
		st = state
		if(st == 0 or st == 2):
			msg = infile.read(2**16 - 1)
			if(msg != ""):
				print(msg)
				frame = createFrame(msg, 0, 0) # we have to keep somewhere the id of the new package
				print(frame)
				frame = base64.b16encode(frame)
				print(frame)
				#keep frame somewhere and have to keep the id of it to confirm
				setstate(1)
				tcp.send(frame)

		if(st == 2 or st == 3):
			frame = createFrame("", 0, 1)
			frame = base64.b16encode(frame)
			msg = struct.pack('!'+len(frame)+'s', )
			tcp.send(msg)

def receiveframe(sync):
	msg = tcp.recv(12) # recebendo resto do cabeçalho
	msg = struct.unpack('!12s', msg)[0]
	msg = base64.b16decode(msg)
	sync[8:] = msg
	length = sync[8]*256 + sync[9]
	print(sync, length)

	msg = tcp.recv(length*2) #recebendo resto do arquivo se tudo estiver certo, na prática(sem forçar erros), estará, na teoria...
	msg = struct.unpack('!'+ str(2*length) +'s', msg)[0]
	msg = base64.b16decode(msg)
	sync[14:] = msg
	print(sync)

	sync = calcChecksum(sync)
	print(sync)

def receive(tcp, outfile):
	while True:
		msg = tcp.recv(16)
		msg = struct.unpack('!16s', msg)[0]
		sync = bytearray([220, 192, 35, 194, 220, 192, 35, 194])
		msg = base64.b16decode(msg)
		if(sync == msg):
			print("begin of package")
			receiveframe(sync)
		'''if(msg == ";"):
			setstate(-1)
		else:
			outfile.write(msg)
			outfile.flush()
			setstate(-2)'''

threading.Thread(target = receive, args = (tcp, outfile, )).start()
threading.Thread(target = sent, args = (tcp, infile, )).start()
