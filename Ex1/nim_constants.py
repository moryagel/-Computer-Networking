#!/usr/bin/env python3

# > Constants

NONE = -1  # used as null argument

SERVER_DEFAULT_HOSTNAME = 'localhost'
SERVER_DEFAULT_PORT = 6444

BOARD_SIZE = 3

PACKET_SIZE = 8         # size of packet structure
PACKET_STRUCT = ">4h"   # packet structure, 4 shorts : 1 for op code, 3 for arguments

ARG_MOVE_ACCEPTED = 1  # move provided by user was accepted
ARG_MOVE_ILLEGAL = 2  # move provided by user is illegal
ARG_SERVER = 1  # used to indicate that the winner was the server
ARG_CLIENT = 2  # used to indicate that the winner was the client

# ------- Operations received from client  -------------

OP_MOVE = 1  # Client requested to make a move
OP_GAME_STATE = 2  # Client requested to get game state

# ------- Operations sent to client  -------------------

OP_GAME_DONE =     3  # Indicating that a game is finished. additional packet info includes winner
OP_GAME_ACTIVE =   4  # Indication that a game is active and waiting for a move. provides boards status info.
OP_MOVE_RESPONSE = 5  # Response for a client move. additional packet info includes if move was accepted or illegal


LEGAL_MOVES = ['A', 'B', 'C']