#!/usr/bin/env python3
import socket, struct, threading, sys, base64

mode = sys.argv[1]
infile = sys.argv[3]
outfile = sys.argv[4]

if(mode == "-c"):
	print("-c")
	HOST = sys.argv[2][0 : sys.argv[2].find(':')]
	PORT = int(sys.argv[2][sys.argv[2].find(':') + 1:])
	tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
	dest = (HOST, PORT)
	tcp.connect(dest)
else:
	print("-s")
	HOST = ''
	PORT = int(sys.argv[2])
	tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
	orig = (HOST, PORT)
	tcp.bind(orig)
	tcp.listen(1)
	tcp, address = tcp.accept()

counter = 0
lock = threading.Lock()

def setCounter(val):
	global counter
	lock.acquire()
	try:
		counter = val
	finally:
		lock.release()

def sent(tcp):
	while True:
		c = counter+1
		setCounter(c)
		print(mode, c)
		msg = struct.pack('!i', c)
		tcp.send(msg)
		

def receive(tcp):
	while True:
		msg = tcp.recv(4)
		msg = struct.unpack('!i', msg)[0]
		print("asdddd", msg)
		setCounter(msg)
		print("recv", mode, msg)

threading.Thread(target = receive, args = (tcp, )).start()
threading.Thread(target = sent, args = (tcp, )).start()