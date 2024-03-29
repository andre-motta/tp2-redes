#!/usr/bin/env python3
import socket, struct, threading, sys, base64, time, binascii, os

mode = sys.argv[1]
infile = open(sys.argv[3], 'rb')
outfile = open(sys.argv[4], 'wb')

if(mode == "-c"): #check if it's client
	HOST = sys.argv[2][0 : sys.argv[2].find(':')]
	PORT = int(sys.argv[2][sys.argv[2].find(':') + 1:])
	tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
	dest = (HOST, PORT)
	tcp.connect(dest) #connect
else:
	HOST = ''
	PORT = int(sys.argv[2])
	tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
	orig = (HOST, PORT)
	tcp.bind(orig)
	tcp.listen(1)
	tcp, address = tcp.accept() #accept


idsend = 0 #id of what is being sent now
sendConfirm = 0 # amount of confirms that must be sent
confirmsToSent = []
confirmReceived = 0 #confirm of a given package has been received
lastIdReceived = 1 #last data id received

lockidsend = threading.Lock()
lockconf = threading.Lock()
lockconfToSent = threading.Lock()

def setIdsend(): #lock from id that's going to be sent
	global idsend
	lockidsend.acquire()
	try:
		idsend = (idsend+1)%2
	finally:
		lockidsend.release()

def setConf(val): #lock from received ack
	global confirmReceived
	lockconf.acquire()
	try:
		confirmReceived = val
	finally:
		lockconf.release()

def changeConfToSent(val, add): # lock from list of ack's to send
	global confirmsToSent
	global sendConfirm
	lockconfToSent.acquire()
	try:
		if(val == 0):
			aux = confirmsToSent.pop(0)
			sendConfirm =  sendConfirm - 1
			return aux
		else:
			confirmsToSent.append(add)
			sendConfirm = sendConfirm + 1
			return add
	finally:
		lockconfToSent.release()

def carry_around_add(a, b): #professor's checksum
	c = a + b
	return(c &0xffff)+(c >>16)

def checksumC(msg):
    s = 0
    appended = False
    if len(msg)%2 != 0:
        msg.append(0)
        appended = True
    for i in range(0, len(msg),2):
        w =(msg[i]<<8)+((msg[i+1])) # shift on the msb
        s = carry_around_add(s, w)
    if appended:
        msg.pop()
    return ~s &0xffff

def calcChecksum(frame):
	checksum = checksumC(frame)
	frame[10:11] = bytearray([checksum//256])
	frame[11:12] = bytearray([checksum%256])

	return frame[:]


def createFrame(msg, id, flag): # given the specifications creates a frame
	frame = bytearray([220, 192, 35, 194])
	frame[4:] = frame[:]
	frame[8:] = bytearray([0,0]) if(msg == "") else bytearray([len(msg)//256, len(msg)%256])
	frame[10:] = bytearray([0, 0])
	frame[12:] = bytearray([0]) if(id == 0) else bytearray([1])
	frame[13:] = bytearray([0]) if(flag == 0) else bytearray([128])
	if(msg != ""):
		frame[14:] = msg[:]

	frame = calcChecksum(frame)
	return frame[:]



def sent(tcp, infile):
	lastFrameSent = None
	passedTime = time.clock() - 1.0
	eof = 0 #indicates that the file has ended

	while True:
		if((time.clock() - passedTime) >= 1.0 and confirmReceived == 0): # if hasn't received confirmation and timesout
			if(lastFrameSent is None): # only in the first time
				msg = infile.read(2**16 - 1)
				if(len(msg) != 0): # if there's still something to send shouldn't happen if file isn't empty
					frame = createFrame(msg, idsend, 0)
					frame = binascii.hexlify(bytearray(frame))
					lastFrameSent = frame
					try:
						tcp.send(frame)
					except:
						os._exit(3) # waiting ctrl+c
				if(len(msg) < 2**16 - 1): #if endend file
					eof = 1 #end of file
					infile.close() #close file
			else:
				try:
					tcp.send(lastFrameSent)
				except:
					os._exit(3)
			passedTime = time.clock() # to check retransmission

		elif(confirmReceived == 1 and eof == 0): #if there's still something to send
			msg = infile.read(2**16 - 1)
			if(len(msg) != 0):
				setIdsend() #change id
				setConf(0) # must wait ack
				frame = createFrame(msg, idsend, 0)
				frame = binascii.hexlify(bytearray(frame))
				lastFrameSent = frame
				try:
					tcp.send(frame)
				except:
					os._exit(3)
			if(len(msg) < 2**16 - 1):
				eof = 1
				infile.close()
			passedTime = time.clock()

		if(sendConfirm > 0): #there still some ack to send
			aux = changeConfToSent(0, None)# remove ack to send
			frame = createFrame("", aux, 1) # frame of ack is empty and has flag activated
			frame = binascii.hexlify(bytearray(frame))
			try:
				tcp.send(frame)
			except:
				os._exit(3)

def receiveframe(sync):
	try:
		msg = tcp.recv(12) # receiving header
		while(len(msg) != 12):
			msg = msg + tcp.recv(12 - len(msg))
		msg = struct.unpack('!12s', msg)[0]
	except:
		os._exit(3)
	try:
		msg = base64.b16decode(msg, True)
	except:
		return (msg, False)

	sync[8:] = msg # get header
	length = sync[8]*256 + sync[9]
	try:
		msg = tcp.recv(length*2) # receiving data
		while(len(msg) != 2*length):
			msg =  msg + tcp.recv(length*2 - len(msg)) # concat missing parts
	except:
		os._exit(3)
	msg = struct.unpack('!'+ str(2*length) +'s', msg)[0]

	try:
		msg = base64.b16decode(msg, True)
	except:
		return (sync, False)

	sync[14:] = msg

	backcheck = sync[10:12]
	sync = calcChecksum(sync) # calc checksum
	if (sync[10] == 0 and sync[11] == 0): #checksum valid
		return (sync, backcheck)
	return (sync, False) #checksum invalid


def receive(tcp, outfile):
	lastPackReceived = None # id and checksum from last package received
	ackReceived = 1

	while True:
		try:
			msg = tcp.recv(8) #receiving sync
			while(len(msg) != 8):
				msg = msg + tcp.recv(8 - len(msg))
		except:
			os._exit(3)
		msg = struct.unpack('!8s', msg)[0]
		sync = bytearray([220, 192, 35, 194]) #check sync
		try:
			msg = base64.b16decode(msg, True)
		except:
			continue

		if(sync != msg):
			continue

		try:
			msg = tcp.recv(8)
			while(len(msg) != 8):
				msg = msg + tcp.recv(8 - len(msg))
		except:
			os._exit(3)
		msg = struct.unpack('!8s', msg)[0]
		try:
			msg = base64.b16decode(msg, True)
		except:
			continue

		if(sync == msg):
			sync[4:] = sync[:] # concat sync
			ret, check = receiveframe(sync) # get rest of frame

			if(check != False): # checksum is valid
				if(ret[13] == 128):# if it's ack
					if(ret[12] != ackReceived): # hasn't received this package confirmation yet
						setConf(1)
						ackReceived = ret[12]
				else: # if it's data
					if(lastPackReceived is None): #hasn't receveid a package yet
						changeConfToSent(1, sync[12])
						lastPackReceived = [sync[12], sync[10:12]]
						outfile.write(sync[14:])
						outfile.flush()
					elif(sync[12] == lastPackReceived[0] and sync[10:12] == lastPackReceived[1]): # retransmission
						changeConfToSent(1, sync[12])
					elif(sync[12] != lastPackReceived[0]): # new package
						changeConfToSent(1, sync[12])
						lastPackReceived = [sync[12], sync[10:12]]
						outfile.write(sync[14:])
						outfile.flush()

threading.Thread(target = receive, args = (tcp, outfile, )).start()
threading.Thread(target = sent, args = (tcp, infile, )).start()
