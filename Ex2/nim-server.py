#!/usr/bin/env python3

import socket
import sys
import functools

from select import select

from nim_helper import *
from nim_constants import *



class Game:
	def __init__(self, board):
		self.board = board.copy()
		self.done = False
		self.turn = ARG_CLIENT

	# return True iff the game is over (all heaps are 0)
	def is_done(self):
		return sum(self.board) == 0

	# return True iff the move is valid
	def validate_move(self, heap, num):
		if heap >= len(self.board) or heap < 0 or num > self.board[heap] or num < 0:
			return False
		return True

	# execute game move
	def move(self, heap, num):
		assert self.done is False
		self.turn = self.get_next_turn()
		if not self.validate_move(heap, num):
			return False
		self.board[heap] -= num
		self.done = self.is_done()
		return True

	def get_board_status(self):
		return self.board.copy()

	def get_winner(self):
		if self.done:
			return self.get_next_turn()
		return -1

	def get_next_turn(self):
		return ARG_CLIENT if self.turn == ARG_SERVER else ARG_SERVER

# serves a single client connection - handles client requests 
class NimGameHost:

	def __init__(self, board, strategy):
		self.strategy = strategy
		self.game = Game(board)

	# Send packet to client informing about a winner.
	# return encoded winner response 
	def send_winner_response(self):
		winner = self.game.get_winner()
		return encode_response(OP_GAME_DONE, [winner])

	# Send packet indicating whether client's move was illegal or accepted
	# return encoded move response
	def send_move_response(self, validity):
		return encode_response(OP_MOVE_RESPONSE, [validity])

	# Send packet with new board status
	# return encoded board state response
	def send_board_state_response(self):
		board = self.game.get_board_status()
		return encode_response(OP_GAME_ACTIVE, board)

	# Send packet with information about the current state of the game
	# return response for game state request
	def execute_game_state_request(self):
		if self.game.done:
			return self.send_winner_response()
		else:
			return self.send_board_state_response()

	# Server executes its next move
	def execute_server_move(self):
		assert not self.game.is_done()
		board = self.game.get_board_status()
		move, num = self.strategy(board)
		self.game.move(move, num)

	# Execute move request from client and return proper response (valid / illegal move)
	def execute_client_move(self, heap, num):
		move_accepted = self.game.move(heap, num)
		return self.send_move_response(ARG_MOVE_ACCEPTED if move_accepted else ARG_MOVE_ILLEGAL)

	# Handle clients move request and return a response
	def execute_move_request(self, op, args):
		resp = self.execute_client_move(args[0], args[1])
		if not self.game.is_done():
			self.execute_server_move()
		return resp

	# Route client request to appropriate method and return the response
	def execute_command(self, op, args):
			if op == OP_MOVE:
				return self.execute_move_request(op, args)
			if op == OP_GAME_STATE:
				return self.execute_game_state_request()
			assert False

# ------------------------------------------------------------------------------------------------------

class NimServerMultiplexing:
	def __init__(self,
				 board,
				 port,
				 num_players,
				 wait_list_size,
				 strategy):
		self.initial_board = board
		self.port = port
		self.num_players = num_players
		self.wait_list_size = wait_list_size
		self.strategy = strategy       # servers nim playing strategy
		self.active_players = []       # list of sockets playing 
		self.waiting_queue = []        # list of sockets in waiting queue
		self.rejected_players = []     # list of sockets we need to reject 
		self.soc_to_game_host = {}     # map active socket to its running game host
		self.soc_to_msg_recv = {}      # current packet chunk we received in each socket
		self.soc_to_msg_send = {}      # remaining packet chunk to send for every socket

	# remove socket from every list(if exists) and close connection.
	# also start a new game for a waiting socket
	def close_connection(self, client_soc):
		if client_soc in self.active_players:
			self.active_players.remove(client_soc)
			self.soc_to_game_host.pop(client_soc)
			if len(self.waiting_queue) > 0:
				self.client_start(self.waiting_queue.pop(0))

		if client_soc in self.waiting_queue:
			self.waiting_queue.remove(client_soc)

		if client_soc in self.rejected_players:
			self.rejected_players.remove(client_soc)

		if client_soc in self.soc_to_msg_recv:
			self.soc_to_msg_recv.pop(client_soc)

		if client_soc in self.soc_to_msg_send:
			self.soc_to_msg_send.pop(client_soc)
			
		client_soc.close()

	# parse packet into command, execute it and add response to write buffer of socket
	def handle_active_player_packet(self, soc, packet_bytes):		
		op, *args = struct.unpack(PACKET_STRUCT, packet_bytes)
		resp = self.soc_to_game_host[soc].execute_command(op, args)
		self.soc_to_msg_send[soc] += resp

	# handle reads of all readable sockets
	def handle_reads(self, Readable):
		# for every readable socket, we attempt to read the remaining number of bytes to complete a full 4 byte packet
		# if failed, close connection otherwise update remaining number of bytes to read
		# and if a packet was completed, execute it otherwise continue
		for soc in Readable:
			msg = recv(soc, PACKET_SIZE - len(self.soc_to_msg_recv[soc]))
			if len(msg) == 0:
				self.close_connection(soc)
				return

			self.soc_to_msg_recv[soc] += msg
			if len(self.soc_to_msg_recv[soc]) < PACKET_SIZE:
				continue
			
			# handle full packet
			if soc in self.active_players:
				self.handle_active_player_packet(soc, self.soc_to_msg_recv[soc])
				self.soc_to_msg_recv[soc] = self.soc_to_msg_recv[soc][PACKET_SIZE:]

	# handle writes to all writable sockets
	def handle_writes(self, Writable):
		# for every writable socket, we attempt to send the remaining response chunk we have.
		# if failed, close connection otherwise update remaining chunk to send
		for soc in Writable:
			msg = self.soc_to_msg_send[soc]
			if len(msg) == 0:
				continue

			size = send(soc, msg)
			if size == -1:
				self.close_connection(soc)
				return

			# client needs to be rejected and we finished sending the reject message, close the connection
			self.soc_to_msg_send[soc] = msg[size:]
			if len(self.soc_to_msg_send[soc]) == 0 and soc in self.rejected_players:
				self.close_connection(soc)
						

	# Handle a client that can now start a game
	def client_start(self, client_soc):
		print("[debug] socket added to active")
		self.active_players.append(client_soc)
		self.soc_to_game_host[client_soc] = NimGameHost(self.initial_board, self.strategy) 
		self.soc_to_msg_send[client_soc] += encode_response(OP_START)
	
	# Handle a client we need to add to waiting queue
	def client_wait(self, client_soc):
		print("[debug] socket added to waiting")
		self.waiting_queue.append(client_soc) 
		self.soc_to_msg_send[client_soc] += encode_response(OP_WAIT)

	# Handle a client we need to reject
	def client_reject(self, client_soc):
		print("[debug] socket added to reject")
		self.rejected_players.append(client_soc) 
		self.soc_to_msg_send[client_soc] += encode_response(OP_REJECT)

	def handle_new_connection(self, client_soc):
		self.soc_to_msg_recv[client_soc] = b''
		self.soc_to_msg_send[client_soc] = b''		
		if len(self.active_players) < self.num_players:
			self.client_start(client_soc)
		elif len(self.waiting_queue) < self.wait_list_size:
			self.client_wait(client_soc)
		else:
			self.client_reject(client_soc)

	def start(self):
		print("[debug] Server started!")
		with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listen_soc:
			listen_soc.bind(('', self.port))
			listen_soc.listen()
			while True:
				Readable, Writable, _ = select([*self.active_players, *self.waiting_queue, *self.rejected_players, listen_soc], 
											[*self.active_players, *self.waiting_queue, *self.rejected_players], [])
				
				if listen_soc in Readable:
					(client_soc, address) = listen_soc.accept()
					self.handle_new_connection(client_soc)
					Readable.remove(listen_soc)

				self.handle_reads(Readable)

				_, Writable, _ = select([], [*self.active_players, *self.waiting_queue, *self.rejected_players], [], 0)				
				
				self.handle_writes(Writable)	

# ------------------------------------------------------------------------------------------------------


def validate_input(args):
	if len(args) < 5 and len(args) > 8:
		exit('Invalid number of arguments')

	valid_heaps = len([heap for heap in args[:BOARD_SIZE] if heap.isdigit() and int(heap) >= 1 and int(heap) <= 1000])
	if valid_heaps != BOARD_SIZE:
		exit('Heaps sizes should be numbers between 1 to 1000')

	if not args[BOARD_SIZE].isdigit() or int(args[BOARD_SIZE]) < 1:
		exit('Number of simulteneous players should be positive')
	
	if not args[BOARD_SIZE+1].isdigit() or int(args[BOARD_SIZE+1]) < 1:
		exit('Waiting list size should be positive')

	if len(args) == 6 and not args[5].isdigit():
		exit('Port should be a positive number')
	
	flag_list = ['--optimal-strategy', '--multithreading']
	for i in range(6, len(args)):
		if args[i] not in flag_list:
			exit('Invalid flags')
		flag_list.remove(args[i])

	return True

def naive_strategy(board):
	max_heap_index = board.index(max(board))
	return max_heap_index, 1

def optimal_strategy(board):
	nim_sum = functools.reduce(lambda x, y: x ^ y, board)
	for index, heap in enumerate(board):
		target_size = heap ^ nim_sum
		if target_size < heap:
			amount_to_remove = heap - target_size
			return index, amount_to_remove	

def main():
	args = sys.argv[1:]
	validate_input(args)

	board = list(map(int, args[:BOARD_SIZE]))
	port = int(args[BOARD_SIZE+2]) if (len(args) > BOARD_SIZE+2) else SERVER_DEFAULT_PORT
	num_players = int(args[BOARD_SIZE])
	wait_list_size = int(args[BOARD_SIZE+1])
	multithreading = True if ('--multithreading' in args) else False
	strategy = optimal_strategy if ('--optimal-strategy' in args) else naive_strategy
	
	nim_server = None
	if multithreading:
		print('Multithreading is not implemented')
		exit()
	else:
		nim_server = NimServerMultiplexing(board, port, num_players, wait_list_size, strategy)
	
	nim_server.start()
	


if __name__ == "__main__":
	main()
