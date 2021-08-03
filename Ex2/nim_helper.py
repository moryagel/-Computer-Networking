#!/usr/bin/env python3

import errno
import struct
from nim_constants import *

# > Helper Methods


# send packet, receive bytes sent or -1 upon failure
def send(soc, packet):
	try:
		len = soc.send(packet)
		return len
	except OSError as error:
		if error.errno == errno.EPIPE or error.errno == errno.ECONNRESET:
			print("socket connection broken")
		else:
			print("Connection Problem")
		return -1


# receive size bytes, return msg received or empty message upon failure
def recv(soc, size):
	try:
		msg = soc.recv(size)
		return msg
	except OSError as error:
		if error.errno == errno.ECONNREFUSED:
			print("socket connection refused")
			return b""
		else:
			print("Connection Problem")
			return b""


# seperate creating a response and sending it 
def encode_response(op, args=[]):
	args.extend([NONE]*(3-len(args))) # pad to fit packet structure
	packet_bytes = struct.pack(PACKET_STRUCT, op, *args)
	return packet_bytes
