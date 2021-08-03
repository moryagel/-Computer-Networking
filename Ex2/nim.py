import socket
import struct
import sys
from select import select

from nim_constants import *
from nim_helper import *


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


def print_game_state_response(response):
    game_state = struct.unpack(PACKET_STRUCT, response)
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


def handle_move_response(response):
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


def handle_pre_game_state(response):
    op, *args = struct.unpack(PACKET_STRUCT, response)
    if op == OP_REJECT:
        exit("You are rejected by the server.")
    elif op == OP_WAIT:
        print("Waiting to play against the server.")
        return STATE_PRE_GAME
    elif op == OP_START:
        print("Now you are playing against the server!")
        return STATE_SEND_GAME_STATE_REQ

    exit("Unknown pre-game operation")


def handle_read(recv_buffer, state):
    if state == STATE_PRE_GAME:
        return handle_pre_game_state(recv_buffer)

    elif state == STATE_RECV_GAME_STATE_REQ:
        print_game_state_response(recv_buffer)
        print("Your turn: ", end='', flush=True)
        return STATE_SEND_MOVE

    elif state == STATE_RECV_MOVE:
        handle_move_response(recv_buffer)
        return STATE_SEND_GAME_STATE_REQ

    return state


def start_client(hostname, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as soc:
        try:
            #print("Connecting to port", port, "...")
            soc.connect((hostname, port))
        except ConnectionRefusedError:
            print('Connection Refused')
            exit()

        move = None
        state = STATE_PRE_GAME
        recv_buffer = b''
        total_sent = 0
        while True:
            readables, writeables, _ = select([soc, sys.stdin], [soc], [])

            if soc in readables:
                response = recv(soc, PACKET_SIZE - len(recv_buffer))
                if not response:
                    exit()

                recv_buffer += response
                if len(recv_buffer) < PACKET_SIZE:
                    continue

                state = handle_read(recv_buffer, state)
                recv_buffer = b''

            if sys.stdin in readables:
                message = sys.stdin.readline().strip()
                if message == "Q":
                    exit()

                elif state == STATE_SEND_MOVE and not move:
                    move = parse_move(message)

            if soc in writeables:
                if state == STATE_SEND_MOVE and move:
                    to_send = encode_response(OP_MOVE, move)
                elif state == STATE_SEND_GAME_STATE_REQ:
                    to_send = encode_response(OP_GAME_STATE)
                else:
                    continue

                sent = send(soc, to_send[total_sent:])
                if not sent:
                    exit()

                total_sent += sent
                if total_sent < PACKET_SIZE:
                    continue

                if state == STATE_SEND_MOVE:
                    state = STATE_RECV_MOVE
                    move = None

                elif state == STATE_SEND_GAME_STATE_REQ:
                    state = STATE_RECV_GAME_STATE_REQ

                total_sent = 0


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
