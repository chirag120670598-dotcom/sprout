"""Connect Four as bitboards.

Each column is given seven bits, so a shift of one row can never slide across a
column boundary. The seventh bit of every column is never occupied -- that
unused row is what makes the shift-based win test safe: any chain that would
wrap around the board is killed by landing on a permanently empty cell.

That reasoning is exactly the kind of thing that is *probably* right and
occasionally wrong, so tests/test_sprout.py cross-checks this engine against a
naive two-dimensional implementation over thousands of random games. A fast
engine that is wrong is worse than a slow one that is right.
"""

from __future__ import annotations

COLS = 7
ROWS = 6
PLAYABLE = COLS * ROWS

# Try the centre first. Alpha-beta prunes far more when the best move is
# examined early, and in Connect Four the centre is usually the best move.
ORDER = (3, 2, 4, 1, 5, 0, 6)

try:  # Python 3.10+
    _POPCOUNT = int.bit_count

    def popcount(x: int) -> int:
        return x.bit_count()
except AttributeError:  # pragma: no cover - Python 3.9
    def popcount(x: int) -> int:
        return bin(x).count("1")


CENTER_MASK = sum(1 << (c * 7 + r) for c in (2, 3, 4) for r in range(ROWS))

def _build_windows() -> tuple[int, ...]:
    """Every group of four cells that could hold a line: 69 of them."""
    windows: list[int] = []
    for r in range(ROWS):                                    # horizontal
        for c in range(COLS - 3):
            windows.append(sum(1 << ((c + i) * 7 + r) for i in range(4)))
    for c in range(COLS):                                    # vertical
        for r in range(ROWS - 3):
            windows.append(sum(1 << (c * 7 + r + i) for i in range(4)))
    for c in range(COLS - 3):                                # diagonal, rising
        for r in range(ROWS - 3):
            windows.append(sum(1 << ((c + i) * 7 + r + i) for i in range(4)))
    for c in range(COLS - 3):                                # diagonal, falling
        for r in range(3, ROWS):
            windows.append(sum(1 << ((c + i) * 7 + r - i) for i in range(4)))
    return tuple(windows)


WINDOWS: tuple[int, ...] = _build_windows()


def won(pos: int) -> bool:
    """True if `pos` contains four in a line."""
    m = pos & (pos >> 7)
    if m & (m >> 14):
        return True
    m = pos & (pos >> 6)
    if m & (m >> 12):
        return True
    m = pos & (pos >> 8)
    if m & (m >> 16):
        return True
    m = pos & (pos >> 1)
    if m & (m >> 2):
        return True
    return False


class IllegalMove(ValueError):
    pass


class Board:
    """A position. `p[0]` and `p[1]` are the bitboards, `h[col]` the heights."""

    __slots__ = ("p", "h", "side", "n", "last", "moves")

    def __init__(self) -> None:
        self.p = [0, 0]
        self.h = [0] * COLS
        self.side = 0
        self.n = 0
        self.last = -1
        self.moves: list[int] = []   # every column played, oldest first

    # -- state -------------------------------------------------------------
    def legal(self) -> list[int]:
        h = self.h
        return [c for c in ORDER if h[c] < ROWS]

    def is_full(self) -> bool:
        return self.n >= PLAYABLE

    def copy(self) -> "Board":
        b = Board()
        b.p = [self.p[0], self.p[1]]
        b.h = list(self.h)
        b.side = self.side
        b.n = self.n
        b.last = self.last
        b.moves = list(self.moves)
        return b

    # -- moves -------------------------------------------------------------
    def play(self, col: int) -> int:
        if not 0 <= col < COLS or self.h[col] >= ROWS:
            raise IllegalMove(f"column {col} is not playable")
        bit = 1 << (col * 7 + self.h[col])
        self.p[self.side] |= bit
        self.h[col] += 1
        self.n += 1
        self.side ^= 1
        self.last = col
        self.moves.append(col)
        return bit

    def undo(self, col: int) -> None:
        self.side ^= 1
        self.h[col] -= 1
        bit = 1 << (col * 7 + self.h[col])
        self.p[self.side] &= ~bit
        self.n -= 1
        self.last = -1
        if self.moves:
            self.moves.pop()

    # -- result ------------------------------------------------------------
    def winner(self) -> int | None:
        """0 or 1 if that side has four in a line, else None."""
        if won(self.p[0]):
            return 0
        if won(self.p[1]):
            return 1
        return None

    def outcome(self) -> int | None:
        """0, 1, or 2 for a draw, or None while the game is live."""
        w = self.winner()
        if w is not None:
            return w
        return 2 if self.is_full() else None

    def render(self) -> str:
        glyphs = ("o", "x")
        rows = []
        for r in range(ROWS - 1, -1, -1):
            cells = []
            for c in range(COLS):
                bit = 1 << (c * 7 + r)
                cells.append(glyphs[0] if self.p[0] & bit
                             else glyphs[1] if self.p[1] & bit else ".")
            rows.append("  " + " ".join(cells))
        rows.append("  " + " ".join(str(c) for c in range(COLS)))
        return "\n".join(rows)
