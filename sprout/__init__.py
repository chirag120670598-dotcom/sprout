"""Sprout — a program that improves itself, against an exam it cannot cheat.

It is born with no idea what a good position looks like, mutates at random, and
keeps a change only when the change measurably plays better. There is a ceiling,
and the ceiling is reported rather than hidden.
"""

from .arena import series, style_score
from .game import Board
from .organism import Genome, level_one, mutate, player
from .trainer import examine, load_state, render_showcase, run

__version__ = "1.0.0"

__all__ = [
    "Board", "Genome", "level_one", "mutate", "player", "series", "style_score",
    "examine", "run", "load_state", "render_showcase", "__version__",
]
