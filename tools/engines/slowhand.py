#!/usr/bin/env python3
"""A Connect Four engine that speaks the world protocol.

Deliberately *not* written the way the engine in sprout/ is written: this one
keeps a plain two-dimensional board and does a plain depth-limited search with a
plain heuristic. It shares no representation and no code with the organism, which
is the whole point -- an opponent built out of the same ideas as the student
tests nothing.

    PLAY 3322      -> the columns played so far, oldest first
    3              <- the column to answer with
    QUIT

    python3 tools/engines/slowhand.py --depth 5
"""

from __future__ import annotations

import sys

COLS, ROWS = 7, 6


def new_board():
    return [[0] * ROWS for _ in range(COLS)]


def drop(board, col, player):
    for r in range(ROWS):
        if board[col][r] == 0:
            board[col][r] = player
            return r
    return None


def wins(board, col, row, player):
    for dc, dr in ((1, 0), (0, 1), (1, 1), (1, -1)):
        run = 1
        for sign in (1, -1):
            c, r = col + dc * sign, row + dr * sign
            while 0 <= c < COLS and 0 <= r < ROWS and board[c][r] == player:
                run += 1
                c += dc * sign
                r += dr * sign
        if run >= 4:
            return True
    return False


def legal(board):
    return [c for c in range(COLS) if board[c][ROWS - 1] == 0]


def score_position(board, me):
    def count(player):
        total = 0
        for c in range(COLS):
            for r in range(ROWS):
                if board[c][r] != player:
                    continue
                for dc, dr in ((1, 0), (0, 1), (1, 1), (1, -1)):
                    for i in range(4):
                        cells = [(c + dc * k, r + dr * k) for k in range(i, i + 4)]
                        if not all(0 <= x < COLS and 0 <= y < ROWS for x, y in cells):
                            continue
                        values = [board[x][y] for x, y in cells]
                        if all(v in (0, player) for v in values):
                            mine = sum(1 for v in values if v == player)
                            if mine:
                                total += {1: 1, 2: 8, 3: 60, 4: 1000}[mine]
        return total

    centre = sum(1 for r in range(ROWS) if board[3][r] == me)
    opponent = 2 if me == 1 else 1
    return count(me) - 1.15 * count(opponent) + 4 * centre


def search(board, me, depth, alpha, beta, ply=0):
    opponent = 2 if me == 1 else 1
    moves = legal(board)
    if depth == 0 or not moves:
        return score_position(board, me)
    best = -10**9
    for col in (3, 2, 4, 1, 5, 0, 6):
        if col not in moves:
            continue
        row = drop(board, col, me)
        if wins(board, col, row, me):
            board[col][row] = 0
            return 10**6 - ply
        value = -search(board, opponent, depth - 1, -beta, -alpha, ply + 1)
        board[col][row] = 0
        if value > best:
            best = value
            if best > alpha:
                alpha = best
                if alpha >= beta:
                    break
    return best


def choose(board, me, depth):
    best, best_col = -10**9, None
    opponent = 2 if me == 1 else 1
    for col in (3, 2, 4, 1, 5, 0, 6):
        if board[col][ROWS - 1] != 0:
            continue
        row = drop(board, col, me)
        if wins(board, col, row, me):
            board[col][row] = 0
            return col
        value = -search(board, opponent, depth - 1, -10**9, 10**9, 1)
        board[col][row] = 0
        if value > best:
            best, best_col = value, col
    return best_col


def main(argv):
    depth = 4
    if "--depth" in argv:
        depth = int(argv[argv.index("--depth") + 1])

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line.startswith("QUIT"):
            return 0
        if not line.startswith("PLAY"):
            print(-1, flush=True)
            continue
        parts = line.split()
        history = [int(ch) for ch in parts[1]] if len(parts) > 1 else []
        board = new_board()
        for i, col in enumerate(history):
            drop(board, col, 1 if i % 2 == 0 else 2)
        col = choose(board, 1 if len(history) % 2 == 0 else 2, depth)
        print(col if col is not None else legal(board)[0], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
