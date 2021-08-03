import socket
import struct
import sys

from nim_constants import *
from nim_helper import *


def send_operation_receive_response(soc, op, args=[]):
    sent = send_operation(soc, op, args)
    if not sent:
        print('Disconnected from server')
        exit()

    response = receive_all(soc, PACKET_SIZE)
    if not response:
        print('Disconnected from server')
        exit()

    return response

def parse_move(move_str):
    move = move_str.split()
    if (len(move) != 2) or (move[0] not in LEGAL_MOVES) or (not (move[1].isdigit() and int(move[1]) > 0)):
        return [NONE, NONE]

    heap = LEGAL_MOVES.index(move[0])
    num = int(move[1])

    return [heap, num]


def print_board(board):
    print(f'Heap A: {board[0]}')
    print(f'Heap B: {board[1]}')
    print(f'Heap C: {board[2]}')


def print_winner(winner):
    print_board([0, 0, 0])
    if winner is ARG_SERVER:
        print('Server win!')
    elif winner is ARG_CLIENT:
        print('You win!')
    else:
        print('Unknown winner argument received')

def print_game_state(game_state):
    if game_state[0] is OP_GAME_ACTIVE:
        board = game_state[1:]
        print_board(board)
    elif game_state[0] is OP_GAME_DONE:
        winner = game_state[1]
        print_winner(winner)
        exit()
    else:
        print('Unknown game op')
        exit()


# Receive game move input, Send game move to server
def handle_move(soc):
    move_str = input('Your turn: ')

    if move_str == 'Q':
        exit()

    move = parse_move(move_str)
    response = send_operation_receive_response(soc, OP_MOVE, move)

    is_legal = struct.unpack(PACKET_STRUCT, response)
    if is_legal[0] is not OP_MOVE_RESPONSE:
        print('Unknown move response')
        exit()

    if is_legal[1] is ARG_MOVE_ACCEPTED:
        print('Move accepted')
    elif is_legal[1] is ARG_MOVE_ILLEGAL:
        print('Illegal move')
    else:
        print('Unknown move argument received')
        exit()


# Receive game state from server and print accordingly
def handle_game_state(soc):
    response = send_operation_receive_response(soc, OP_GAME_STATE)
    game_state = struct.unpack(PACKET_STRUCT, response)
    print_game_state(game_state)


def start_client(hostname, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as soc:
        try:
            soc.connect((hostname, port))
        except ConnectionRefusedError:
            print('Connection Refused')
            exit()
        while True:
            handle_game_state(soc)
            handle_move(soc)


def main():
    args = sys.argv[1:]

    if len(args) >= 2 and not args[1].isdigit():
        print('Port must be a positive integer!')
        exit()

    hostname = args[0] if len(args) >= 1 else SERVER_DEFAULT_HOSTNAME
    port = int(args[1]) if len(args) >= 2 else SERVER_DEFAULT_PORT
    start_client(hostname, port)


if __name__ == "__main__":
    main()
