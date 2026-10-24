"""What it remembers.

A program with no memory makes the same blunder every month and has no way of
noticing. This is a small, explicit, honest one: a book of positions where the
organism has lost before, and the move it made in them.

It is consulted during the search, and a remembered blunder is priced far below
anything the evaluation could otherwise produce -- so it will not play it again
unless every other move loses too. Recording happens after a game is over, when
the outcome is known and the blame can be placed on a specific move rather than
guessed at.

Three honest limits, stated here rather than discovered later:

* It only remembers **exact positions**. A position one move different is a
  different key. That is why the book is small and why it helps less than it
  sounds like it should.
* It learns only from **its own losses**. It cannot tell you *why* a move was
  bad, only that this one was.
* It is a **lookup table, not understanding**. Hand it a position it has never
  seen and it is exactly as naive as it was on day one. This is memory the way a
  notebook is memory, not the way recall is.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

DEFAULT_FILE = "memory.json"
MAX_ENTRIES = 20000
BLUNDER_PENALTY = 3.0e6      # far below a forced loss, far above any evaluation


def key(p0: int, p1: int, side: int) -> str:
    """Two boards that differ only by whose turn it is are not the same
    position, so the side to move is part of the key."""
    raw = f"{p0:014x}:{p1:014x}:{side}".encode("ascii")
    return hashlib.blake2s(raw, digest_size=10).hexdigest()


class Book:
    def __init__(self, data: dict | None = None) -> None:
        self.data = data or {"version": 1, "blunders": {}, "games": 0, "learned": 0}

    # -- persistence -------------------------------------------------------
    @classmethod
    def load(cls, path: str | Path) -> "Book":
        p = Path(path)
        if not p.exists():
            return cls()
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # A half-written book is worth less than a fresh one, and must never
            # be the reason a run dies.
            return cls()
        if not isinstance(data, dict) or "blunders" not in data:
            return cls()
        return cls(data)

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1) + "\n", encoding="utf-8")
        tmp.replace(p)

    # -- recall ------------------------------------------------------------
    def __len__(self) -> int:
        return len(self.data["blunders"])

    def avoids(self, p0: int, p1: int, side: int, col: int) -> bool:
        entry = self.data["blunders"].get(key(p0, p1, side))
        return bool(entry) and col in entry["cols"]

    def penalty(self, p0: int, p1: int, side: int, col: int) -> float:
        return -BLUNDER_PENALTY if self.avoids(p0, p1, side, col) else 0.0

    # -- learning ----------------------------------------------------------
    def record(self, p0: int, p1: int, side: int, col: int) -> None:
        blunders = self.data["blunders"]
        if len(blunders) >= MAX_ENTRIES and key(p0, p1, side) not in blunders:
            return
        entry = blunders.setdefault(key(p0, p1, side), {"cols": [], "n": 0})
        entry["n"] += 1
        if col not in entry["cols"]:
            entry["cols"].append(col)
        self.data["learned"] += 1

    def harvest(self, moves: list[int], loser: int) -> int:
        """Walk a finished game and book every move the loser made.

        Only the ending is blamed -- the move that lost, not the twelve quiet
        ones before it that were also poor. Blaming all of them would fill the
        book with positions that are merely imperfect, and a book full of
        ordinary positions makes a superstitious player.
        """
        from .game import Board

        board = Board()
        recorded = 0
        for i, col in enumerate(moves):
            if board.side == loser:
                self.record(board.p[0], board.p[1], board.side, col)
                recorded += 1
            board.play(col)
        self.data["games"] += 1
        return recorded

    def summary(self) -> str:
        return (f"{len(self)} positions, {self.data.get('games', 0)} games watched, "
                f"{self.data.get('learned', 0)} moves booked")
