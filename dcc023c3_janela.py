#!/usr/bin/env python3
import socket, struct, threading, sys, base64

mode = sys.argv[1]
infile = open(sys.argv[3], 'r')
outfile = open(sys.argv[4], 'w')

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

def sent(tcp, infile):
	while True:
		st = state
		if(st == 0 or st == 2):
			msg = infile.read(1)
			if(msg != ""):
				setstate(1)
				print(mode, "send", msg, st)
				msg = struct.pack('!1s', msg.encode('ascii', 'ignore'))				
				tcp.send(msg)

		if(st == 2 or st == 3):
			setstate(2)
			print(mode, "send", ";", st)
			msg = struct.pack('!1s', (";").encode('ascii', 'ignore'))			
			tcp.send(msg)

def receive(tcp, outfile):
	while True:
		msg = tcp.recv(1)
		msg = struct.unpack('!1s', msg)[0]
		st = state
		msg = str(msg, 'utf-8')
		if(msg == ";"):
			print(mode, "rcv", msg, st)
			setstate(-1)
		else:
			print(mode, "rcv", msg, st)
			outfile.write(msg)
			outfile.flush()
			setstate(-2)

threading.Thread(target = receive, args = (tcp, outfile, )).start()
threading.Thread(target = sent, args = (tcp, infile, )).start()