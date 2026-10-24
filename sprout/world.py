"""The world ladder: opponents that come from outside this repository.

A program cannot absorb GitHub. Reading a repository does not make anything
smarter, and no amount of access turns five weights into a general mind. What a
repository *can* give an organism is something to be measured against -- and
being measured against something stronger is the only mechanism here that has
ever produced a real improvement.

So the ladder is a list of external engines, each one pinned to an exact
revision. `tools/scout.py` finds candidates on GitHub; a human reads one before
it goes on the ladder; `sprout world` plays the current organism against all of
them and reports the score. Nothing is downloaded at runtime and no engine is
ever chosen by the organism itself.

The protocol is deliberately the smallest one that can work:

    parent  ->  PLAY 3322      (the columns played so far, oldest first)
    engine  ->  3              (the column to play next)

A fresh process per game, a timeout, and a closed pipe afterwards. An engine
that hangs, crashes or prints nonsense loses that game and nothing else.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

TIMEOUT = 5.0


class EngineError(RuntimeError):
    pass


@dataclass(frozen=True)
class EngineSpec:
    name: str
    command: list[str]
    source: str          # repository or file the engine came from
    revision: str        # commit sha it was read at, or "bundled"
    added: str           # date it was added, so the ladder has a history

    @classmethod
    def from_json(cls, data: dict) -> "EngineSpec":
        for key in ("name", "command", "source", "revision", "added"):
            if key not in data:
                raise ValueError(f"ladder entry is missing {key!r}")
        if not isinstance(data["command"], list) or not data["command"]:
            raise ValueError("command must be a non-empty list")
        return cls(name=data["name"], command=list(data["command"]),
                   source=data["source"], revision=data["revision"],
                   added=data["added"])

    def to_json(self) -> dict:
        return {"name": self.name, "command": self.command, "source": self.source,
                "revision": self.revision, "added": self.added}

    def resolved(self) -> list[str]:
        """`{python}` is replaced with the interpreter running this code, so a
        ladder written on Linux still works on a Windows runner."""
        return [part.replace("{python}", sys.executable) for part in self.command]


def load_ladder(path: str | Path) -> list[EngineSpec]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return [EngineSpec.from_json(entry) for entry in data.get("engines", [])]


def save_ladder(path: str | Path, specs: list[EngineSpec]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1,
               "note": "Opponents from outside this repository. Pinned on purpose: "
                       "a ladder entry that can change underneath a score is not a rung.",
               "engines": [s.to_json() for s in specs]}
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class ExternalEngine:
    """One rung, spoken to over a pipe."""

    def __init__(self, spec: EngineSpec, timeout: float = TIMEOUT) -> None:
        self.spec = spec
        self.timeout = timeout
        self._proc: subprocess.Popen | None = None

    def _start(self) -> None:
        try:
            self._proc = subprocess.Popen(
                self.spec.resolved(),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, bufsize=1,
            )
        except (OSError, ValueError) as exc:
            raise EngineError(f"{self.spec.name} could not start: {exc}") from exc

    def move(self, history: list[int]) -> int:
        if self._proc is None:
            self._start()
        assert self._proc is not None and self._proc.stdin and self._proc.stdout
        line = "PLAY " + "".join(str(c) for c in history)
        try:
            self._proc.stdin.write(line + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise EngineError(f"{self.spec.name} stopped reading: {exc}") from exc

        started = time.monotonic()
        reply = self._proc.stdout.readline()
        elapsed = time.monotonic() - started
        if not reply:
            raise EngineError(f"{self.spec.name} closed its output")
        if elapsed > self.timeout:
            raise EngineError(f"{self.spec.name} took {elapsed:.1f}s, over the {self.timeout:.0f}s limit")

        text = reply.strip()
        if not text.isdigit():
            raise EngineError(f"{self.spec.name} said {text!r}, which is not a column")
        col = int(text)
        if not 0 <= col <= 6:
            raise EngineError(f"{self.spec.name} chose column {col}, which does not exist")
        return col

    def close(self) -> None:
        if self._proc is None:
            return
        try:
            if self._proc.stdin:
                self._proc.stdin.write("QUIT\n")
                self._proc.stdin.flush()
                self._proc.stdin.close()
            self._proc.wait(timeout=2)
        except Exception:  # noqa: BLE001 - closing must never raise
            pass
        finally:
            proc, self._proc = self._proc, None
            try:
                if proc.poll() is None:
                    proc.kill()
                if proc.stdout:
                    proc.stdout.close()
            except Exception:  # noqa: BLE001
                pass

    def __enter__(self) -> "ExternalEngine":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def duel(genome, spec: EngineSpec, games: int, seed: int = 0,
         timeout: float = TIMEOUT) -> dict:
    """Play the organism against one rung.

    A fresh engine process per game -- an engine that keeps state between games
    would be a different opponent by game five, and comparing scores across a
    set would then mean nothing.
    """
    from .game import Board
    from .organism import player

    mine = player(genome)
    wins = draws = losses = crashes = 0
    for g in range(games):
        rng = random.Random(f"{seed}:{spec.name}:{g}")
        i_move_first = g % 2 == 0
        board = Board()
        engine = ExternalEngine(spec, timeout=timeout)
        # A crash is decided *during* the game and recorded here. Checking the
        # last move against the board afterwards answers a different question --
        # the board has moved on, and the column that was just filled now looks
        # illegal.
        disqualified = False
        try:
            while True:
                mine_to_move = (board.side == 0) == i_move_first
                if mine_to_move:
                    col = mine(board, rng)
                else:
                    try:
                        col = engine.move(board.moves)
                    except EngineError:
                        disqualified = True
                        break
                if col is None or col not in board.legal():
                    disqualified = True
                    break
                board.play(col)
                if board.winner() is not None or board.is_full():
                    break
        finally:
            engine.close()

        if disqualified:
            crashes += 1
        elif board.winner() is None:
            draws += 1
        elif (board.winner() == 0) == i_move_first:
            wins += 1
        else:
            losses += 1

    played = wins + draws + losses
    return {
        "name": spec.name,
        "wins": wins, "draws": draws, "losses": losses, "crashes": crashes,
        "games": games,
        "score": (wins + 0.5 * draws) / played if played else 0.0,
    }


def describe(specs: list[EngineSpec]) -> str:
    if not specs:
        return "the ladder is empty"
    width = max(len(s.name) for s in specs)
    lines = []
    for s in specs:
        lines.append(f"  {s.name:<{width}}  {s.revision[:9]:<9}  added {s.added}  {s.source}")
    return "\n".join(lines)
