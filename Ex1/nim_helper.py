#!/usr/bin/env python3

import errno
import struct
from nim_constants import *

# > Helper Methods


# send full packet packet on provided socket <soc>. return 0 if function failed
def send_all(soc, packet):
	total_sent = 0
	while total_sent < PACKET_SIZE:
		try:
			bytes_sent = soc.send(packet[total_sent:])
			total_sent = total_sent + bytes_sent
			if bytes_sent == 0:
				return 0
		except OSError as error:
			if error.errno == errno.EPIPE or error.errno == errno.ECONNRESET:
				print("socket connection broken")
			else:
				print("Connection Problem")
			return 0
	return total_sent


# receive full packet on provided socket <soc>. return 0 if function failed
def receive_all(soc, size):
	chunks = []
	bytes_received = 0
	while bytes_received < size:
		try:
			chunk = soc.recv(size - bytes_received)
			if len(chunk) == 0 :
				return 0
		except OSError as error:
			if error.errno == errno.ECONNREFUSED:
				print("socket connection refused")
				return 0
			else:
				print("Connection Problem")
				return 0
		chunks.append(chunk)
		bytes_received = bytes_received + len(chunk)
	return b''.join(chunks)


# sends an operator with up to 3 args, as 4 shorts, through the given connection
def send_operation(conn, op, args):
	args.extend([NONE]*(3-len(args))) # pad to fit packet structure
	packet_bytes = struct.pack(PACKET_STRUCT, op, *args)
	sent = send_all(conn, packet_bytes)
	if sent == 0:
		return False
	return True

