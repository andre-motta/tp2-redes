# !/usr/bin/env python3
import socket, struct, threading, sys, base64, time

mode = sys.argv[1]
infile = open(sys.argv[3], 'rb')
outfile = open(sys.argv[4], 'wb')

if (mode == "-c"):
    HOST = sys.argv[2][0: sys.argv[2].find(':')]
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

idsend = 0  # id of what is being sent now
sendConfirm = 0  # amount of confirms that must be sent
confirmsToSent = []
confirmReceived = 0  # confirm of a given package has been received
lastIdReceived = 1  # last data id received

lockidsend = threading.Lock()
lockconf = threading.Lock()
lockconfToSent = threading.Lock()


def setIdsend():
    global idsend
    lockidsend.acquire()
    try:
        idsend = (idsend + 1) % 2
    finally:
        lockidsend.release()


def setConf(val):
    global confirmReceived
    lockconf.acquire()
    try:
        confirmReceived = val
    finally:
        lockconf.release()


def changeConfToSent(val, add):
    global confirmsToSent
    global sendConfirm
    lockconfToSent.acquire()
    try:
        if (val == 0):
            aux = confirmsToSent.pop(0)
            sendConfirm = sendConfirm - 1
            return aux
        else:
            confirmsToSent.append(add)
            sendConfirm = sendConfirm + 1
            return add
    finally:
        lockconfToSent.release()


def calcChecksum(frame):
    checksum = 0
    d = 0
    for b in range(len(frame) // 2):
        checksum += frame[b * 2] * (256) + frame[b * 2 + 1]
        checksum = checksum if (checksum // (2 ** 16) == 0) else checksum % (2 ** 16) + 1
    if (len(frame) % 2 != 0):
        checksum += frame[len(frame) - 1] * 256
        checksum = checksum if (checksum // (2 ** 16) == 0) else checksum % (2 ** 16) + 1

    checksum = checksum ^ 0xffff
    frame[10:11] = bytearray([checksum // 256])
    frame[11:12] = bytearray([checksum % 256])

    return frame[:]


def createFrame(msg, id, flag):
    frame = bytearray([220, 192, 35, 194])
    frame[4:] = frame[:]
    frame[8:] = bytearray([0, 0]) if (msg == "") else bytearray([len(msg) // 256, len(msg) % 256])
    frame[10:] = bytearray([0, 0])
    frame[12:] = bytearray([0]) if (id == 0) else bytearray([1])
    frame[13:] = bytearray([0]) if (flag == 0) else bytearray([128])
    if (msg != ""):
        frame[14:] = msg[:]

    frame = calcChecksum(frame)
    return frame[:]


def sent(tcp, infile):
    lastFrameSent = None
    passedTime = time.clock() - 1.0
    eof = 0  # indicates that the file has ended

    while True:
        if ((
                time.clock() - passedTime) >= 1.0 and confirmReceived == 0):  # if hasn't received confirmation and timesout
            if (lastFrameSent is None):  # only in the first time
                msg = infile.read(2 ** 16 - 1)
                if (msg != ""):
                    frame = createFrame(msg, idsend, 0)
                    frame = base64.b16encode(frame)
                    lastFrameSent = frame
                    tcp.send(frame)
                if (len(msg) < 2 ** 16 - 1):
                    eof = 1
            else:
                tcp.send(lastFrameSent)
            passedTime = time.clock()

        elif (confirmReceived == 1 and eof == 0):
            msg = infile.read(2 ** 16 - 1)
            if (msg != ""):
                setIdsend()
                setConf(0)
                frame = createFrame(msg, idsend, 0)
                frame = base64.b16encode(frame)
                lastFrameSent = frame
                tcp.send(frame)
            if (len(msg) < 2 ** 16 - 1):
                eof = 1
            passedTime = time.clock()

        if (sendConfirm > 0):
            aux = changeConfToSent(0, None)
            frame = createFrame("", aux, 1)
            frame = base64.b16encode(frame)
            #not sending ack
            #tcp.send(frame)
            #not sending ack

def receiveframe(sync):
    msg = tcp.recv(12)  # recebendo resto do cabeçalho
    msg = struct.unpack('!12s', msg)[0]
    msg = base64.b16decode(msg)
    sync[8:] = msg
    length = sync[8] * 256 + sync[9]

    msg = tcp.recv(length * 2)  # receiving data
    while (len(msg) != 2 * length):
        msg = msg + tcp.recv(length * 2 - len(msg))  # concat missing parts
    msg = struct.unpack('!' + str(2 * length) + 's', msg)[0]
    msg = base64.b16decode(msg)
    sync[14:] = msg

    backcheck = sync[10:12]
    sync = calcChecksum(sync)
    if (sync[10] == 0 and sync[11] == 0):
        return (sync, backcheck)
    return (sync, False)


def receive(tcp, outfile):
    lastPackReceived = None  # id and checksum from last package received
    ackReceived = 1

    while True:
        msg = tcp.recv(8)
        msg = struct.unpack('!8s', msg)[0]
        sync = bytearray([220, 192, 35, 194])
        msg = base64.b16decode(msg)
        if (sync != msg):
            continue

        msg = tcp.recv(8)
        msg = struct.unpack('!8s', msg)[0]
        msg = base64.b16decode(msg)
        if (sync == msg):
            sync[4:] = sync[:]
            ret, check = receiveframe(sync)

            if (check != False):  # checksum is valid
                if (ret[13] == 128):  # if it's ack
                    if (ret[12] != ackReceived):  # hasn't received this package confirmation yet
                        setConf(1)
                        ackReceived = ret[12]
                else:  # if it's data
                    if (lastPackReceived is None):  # hasn't receveid a package yet
                        changeConfToSent(1, sync[12])
                        lastPackReceived = [sync[12], sync[10:12]]
                        outfile.write(sync[14:])
                        outfile.flush()
                    elif (sync[12] == lastPackReceived[0] and sync[10:12] == lastPackReceived[1]):  # retransmission
                        changeConfToSent(1, sync[12])
                    else:  # new package
                        changeConfToSent(1, sync[12])
                        lastPackReceived = [sync[12], sync[10:12]]
                        outfile.write(sync[14:])
                        outfile.flush()


threading.Thread(target=receive, args=(tcp, outfile,)).start()
threading.Thread(target=sent, args=(tcp, infile,)).start()