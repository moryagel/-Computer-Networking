#!/usr/bin/env python3

import socket
import sys

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


class NimServer:
	def __init__(self, board, port):
		self.initial_board = board
		self.port = port
		self.serving_client = False
		self.game = None
		self.client_conn = None

	# Send packet to client informing about a winner.
	# Return false if send failed
	def send_winner_response(self):
		winner = self.game.get_winner()
		return send_operation(self.client_conn, OP_GAME_DONE, [winner])

	# Send packet indicating whether client's move was illegal or accepted
	# return false if send failed
	def send_move_response(self, validity):
		return send_operation(self.client_conn, OP_MOVE_RESPONSE, [validity])

	# Send packet with new board status
	# Return false if send failed
	def send_board_state_response(self):
		board = self.game.get_board_status()
		return send_operation(self.client_conn, OP_GAME_ACTIVE, board)

	# Send packet with information about the current state of the game
	# return false if send failed
	def execute_game_state_request(self):
		if self.game.done:
			self.send_winner_response()
			return False
		else:
			return self.send_board_state_response()

	# Server moves, send proper response if won
	# return false if updating client failed
	def execute_server_move(self):
		if self.game.done:
			return True
		board = self.game.get_board_status()
		max_heap_index = board.index(max(board))
		self.game.move(max_heap_index, 1)
		return True

	# Execute move request from client send proper response if won
	# return false if updating client failed
	def execute_client_move(self, heap, num):
		move_accepted = self.game.move(heap, num)
		send_res = self.send_move_response(ARG_MOVE_ACCEPTED if move_accepted else ARG_MOVE_ILLEGAL)

		if send_res is False:
			return False
		return True

	def execute_command(self, op, args):
			if op == OP_MOVE:
				return self.execute_client_move(args[0], args[1]) and self.execute_server_move()
			if op == OP_GAME_STATE:
				return self.execute_game_state_request()
			return False

	def start_game(self):
		self.game = Game(self.initial_board)

		while True:
			# receive the packet
			packet_bytes = receive_all(self.client_conn, PACKET_SIZE)
			if packet_bytes == 0:
				break

			# extract the packet information into our packet structure
			op, *args = struct.unpack(PACKET_STRUCT, packet_bytes)

			# execute the received request
			res = self.execute_command(op, args)
			if not res:
				break

	def start(self):
		with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listen_soc:
			listen_soc.bind(('', self.port))
			listen_soc.listen()
			while True:
				(self.client_conn, address) = listen_soc.accept()
				print("Accepted new connection from", address)
				self.start_game()
				self.client_conn.close()
				print("Closed connection with the client")


def check_legal_move(move):
	if len(move) == 0 or len(move) > 2:
		return False
	if move[0] not in LEGAL_MOVES:
		return False
	if not move[1].isdigit():
		return False
	return True


def validate_input(args):
	if len(args) < 3 and len(args) > 4:
		print('Invalid number of arguments')
		exit()

	valid_heaps = len([heap for heap in args[:BOARD_SIZE] if heap.isdigit() and int(heap) >= 1 and int(heap) <= 1000])
	if valid_heaps != BOARD_SIZE:
		print('Heaps sizes should be numbers between 1 to 1000')
		exit()

	if len(args) == 4 and not args[3].isdigit():
		print('Port should be a positive number')
		exit()

	return True

def main():
	args = sys.argv[1:]
	validate_input(args)

	board = list(map(int, args[:BOARD_SIZE]))
	port = int(args[BOARD_SIZE]) if (len(args) == BOARD_SIZE + 1) else SERVER_DEFAULT_PORT
	nim_server = NimServer(board, port)
	nim_server.start()


if __name__ == "__main__":
	main()
