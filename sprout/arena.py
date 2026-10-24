"""Games, and the two questions worth asking about one.

*Strength* is who wins. *Style* is whether anything is happening -- a player
that wins by luck still looks asleep, and a player that loses narrowly after
building three open threats does not.

Style deliberately is not a copy of strength. It measures three habits that are
visible from outside, plus how often games reach a conclusion at all. The
reference points in STYLE_REFERENCE are not guesses: tools/calibrate.py plays
the fixed opponents against each other and they were pasted in from that
output, which is why they look arbitrary.
"""

from __future__ import annotations

import random

from .game import WINDOWS, Board, popcount

DRAW = 2


def blank_style() -> dict:
    return {"plies": 0, "press": 0, "double": 0, "wins": 0, "games": 0}


def merge_style(into: dict, other: dict) -> None:
    for key, value in other.items():
        into[key] = into.get(key, 0) + value


def open_threes(me: int, opp: int) -> int:
    """Windows where one side has three and the opponent has nothing.

    These are what make an opponent have to *respond* instead of doing what they
    wanted. A player that never creates one is playing solitaire.
    """
    count = 0
    for mask in WINDOWS:
        if not (opp & mask) and popcount(me & mask) == 3:
            count += 1
    return count


def play(p0, p1, rng: random.Random, record_style: bool = True) -> dict:
    """One game. p0 moves first. Returns the outcome and both players' habits."""
    board = Board()
    styles = [blank_style(), blank_style()]
    while True:
        side = board.side
        move = p0 if side == 0 else p1
        col = move(board, rng)
        board.play(col)

        if record_style:
            s = styles[side]
            s["plies"] += 1
            made = open_threes(board.p[side], board.p[1 - side])
            if made:
                s["press"] += 1
            if made >= 2:
                s["double"] += 1

        winner = board.winner()
        if winner is not None:
            if record_style:
                for s in styles:
                    s["games"] += 1
                styles[winner]["wins"] += 1
            return {"outcome": winner, "plies": board.n, "style": styles}
        if board.is_full():
            if record_style:
                for s in styles:
                    s["games"] += 1
            return {"outcome": DRAW, "plies": board.n, "style": styles}


def series(p_a, p_b, games: int, rng: random.Random, record_style: bool = False) -> dict:
    """Alternate who moves first, so first-move advantage is not a score.

    A player that only wins when handed the first move is not better; it is
    luckier, and a fixed schedule would hide that.
    """
    a_wins = b_wins = draws = 0
    style_a, style_b = blank_style(), blank_style()
    plies = 0
    for i in range(games):
        a_first = i % 2 == 0
        if a_first:
            result = play(p_a, p_b, rng, record_style)
            mine, theirs = 0, 1
        else:
            result = play(p_b, p_a, rng, record_style)
            mine, theirs = 1, 0
        plies += result["plies"]
        if record_style:
            merge_style(style_a, result["style"][mine])
            merge_style(style_b, result["style"][theirs])
        outcome = result["outcome"]
        if outcome == DRAW:
            draws += 1
        elif (outcome == 0) == a_first:
            a_wins += 1
        else:
            b_wins += 1
    return {
        "a": a_wins,
        "b": b_wins,
        "draws": draws,
        "games": games,
        "score": (a_wins + 0.5 * draws) / games if games else 0.0,
        "style": (style_a, style_b),
        "avg_plies": plies / games if games else 0.0,
    }


# -- style ------------------------------------------------------------------
#
# Measured with tools/calibrate.py, which plays every fixed opponent against a
# strong reference player and prints these rates. The numbers below are the
# observed floor (a coin flip) and ceiling (a strong player), rounded. Editing
# them by hand would make the style figure decorative, so they carry provenance.
STYLE_REFERENCE = {
    "press_rate": (0.06, 0.53),     # moves after which the opponent must respond
    "double_rate": (0.00, 0.36),    # moves that create two threats at once
}

STYLE_WEIGHTS = {
    "press_rate": 0.65,
    "double_rate": 0.35,
}


def style_metrics(style: dict) -> dict:
    plies = max(1, style["plies"])
    return {
        "press_rate": style["press"] / plies,
        "double_rate": style["double"] / plies,
    }


def style_score(style: dict) -> float:
    """0..100. Clamped and rounded -- a number that can exceed 100 is a number
    nobody believes.

    Style is not strength. It answers a different question: does this thing
    create problems for its opponent, or is it just filling squares? A player
    can lose while pressing constantly, and that still scores as alive.
    """
    metrics = style_metrics(style)
    total = 0.0
    for key, weight in STYLE_WEIGHTS.items():
        low, high = STYLE_REFERENCE[key]
        scaled = (metrics[key] - low) / (high - low) if high > low else 0.0
        total += weight * (0.0 if scaled < 0 else 1.0 if scaled > 1 else scaled)
    return round(100.0 * total, 1)
