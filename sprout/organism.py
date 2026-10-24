"""The organism: a genome, an evaluation, and a search.

There is no neural network here and pretending otherwise would be silly. This
is a weighted evaluation function over the 69 four-in-a-row windows, read by
alpha-beta search. What makes it an organism rather than a program is that those
weights are not written by anybody -- they are mutated at random and kept only
when they measurably play better. The mutation settings themselves live in the
genome too, so the thing also evolves *how* it evolves.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from . import brain
from .game import CENTER_MASK, ORDER, ROWS, WINDOWS, Board, popcount, won

INF = 1e9
WIN = 1e7

# Weights 0..3 are the value of having 1, 2, 3 or 4 of your pieces in a window
# that the opponent has not touched. Weight 4 is the value of the centre.
WEIGHT_COUNT = 5
WEIGHT_LIMIT = 60.0
MAX_DEPTH = 3

# A hand-written opponent, used by the exam. Roughly "an intern who plays a lot".
GAUNTLET_WEIGHTS = (0.1, 1.2, 14.0, 100.0, 0.7)


@dataclass(frozen=True)
class Genome:
    # `program` is the organism's own evaluation code, written by it. `weights`
    # is the older, fixed-shape brain, kept so checkpoints written before the
    # brain existed still load and still play.
    program: tuple | None = None
    weights: tuple[float, ...] = (0.0,) * 5
    depth: int = 2
    sigma: float = 0.35          # how wildly a child differs from its parent
    population: int = 24         # how many children to try per generation
    margin: float = 0.05         # how far ahead a child must be to take over

    # -- serialisation -----------------------------------------------------
    def to_json(self) -> dict:
        return {
            "program": brain.text(self.program) if self.program is not None else None,
            "weights": [round(w, 6) for w in self.weights],
            "depth": self.depth,
            "sigma": round(self.sigma, 4),
            "population": self.population,
            "margin": round(self.margin, 4),
        }

    @classmethod
    def from_json(cls, data: dict) -> "Genome":
        weights = tuple(float(w) for w in data.get("weights", (0.0,) * WEIGHT_COUNT))
        if len(weights) != WEIGHT_COUNT:
            raise ValueError(f"expected {WEIGHT_COUNT} weights, got {len(weights)}")
        program = brain.from_text(data["program"]) if data.get("program") else None
        return cls(
            program=program,
            weights=weights,
            depth=int(data.get("depth", 2)),
            sigma=float(data.get("sigma", 0.35)),
            population=int(data.get("population", 24)),
            margin=float(data.get("margin", 0.05)),
        )

    def describe(self) -> str:
        if self.program is not None:
            shape = f"program {brain.text(self.program)}"
        else:
            shape = "weights [" + ", ".join(f"{x:+.2f}" for x in self.weights) + "]"
        return (f"depth {self.depth}  {shape}  "
                f"sigma {self.sigma:.2f}  pop {self.population}  margin {self.margin:.2f}")


def level_one() -> Genome:
    """The baby. Every weight zero, so it has no idea what a good position is.

    It is not completely helpless -- even a shallow search notices that a move
    which loses on the spot is a bad move -- but it has no sense of shape,
    no sense of the centre, and no plan.
    """
    return Genome(program=brain.newborn(), weights=(0.0,) * WEIGHT_COUNT, depth=2)


def _clamp(value: float, low: float, high: float) -> float:
    return low if value < low else high if value > high else value


def mutate(parent: Genome, rng: random.Random, sigma: float | None = None) -> Genome:
    """One child. Everything in the genome is fair game, including the settings
    that govern mutation itself."""
    s = parent.sigma if sigma is None else sigma
    if parent.program is not None:
        # Its code is what changes now. The old weights are left alone: mixing
        # two brains would make it impossible to say which one earned a level.
        program = brain.mutate(parent.program, rng)
        weights = parent.weights
    else:
        program = None
        weights = tuple(
            _clamp(w + rng.gauss(0.0, s), -WEIGHT_LIMIT, WEIGHT_LIMIT)
            for w in parent.weights
        )
    depth = parent.depth
    if rng.random() < 0.15:
        depth = int(_clamp(depth + rng.choice((-1, 1)), 1, MAX_DEPTH))
    return Genome(
        program=program,
        weights=weights,
        depth=depth,
        sigma=_clamp(parent.sigma * rng.uniform(0.85, 1.18), 0.05, 1.2),
        population=int(_clamp(parent.population + rng.choice((0, 0, 0, 2, -2)), 6, 32)),
        margin=_clamp(parent.margin + rng.gauss(0.0, 0.012), 0.0, 0.20),
    )


def evaluate(me: int, opp: int, weights: tuple[float, ...],
             program: tuple | None = None) -> float:
    """Score a position from `me`'s point of view.

    Deliberately antisymmetric -- flipping who is `me` flips the sign -- because
    negamax is only correct if the evaluation is. Getting that wrong produces a
    player that looks fine and quietly prefers to lose.
    """
    if program is not None:
        return brain.run(program, brain.features(me, opp))

    score = 0.0
    pc = popcount
    for mask in WINDOWS:
        m = me & mask
        o = opp & mask
        if m and o:
            continue
        if m:
            score += weights[pc(m) - 1]
        if o:
            score -= weights[pc(o) - 1]
    score += weights[4] * (pc(me & CENTER_MASK) - pc(opp & CENTER_MASK))
    return score


def _negamax(me: int, opp: int, heights: list[int], depth: int,
             alpha: float, beta: float, weights: tuple[float, ...], ply: int,
             program: tuple | None = None) -> float:
    if depth <= 0:
        return evaluate(me, opp, weights, program)
    best = -INF
    moved = False
    for c in ORDER:
        if heights[c] >= ROWS:
            continue
        nme = me | (1 << (c * 7 + heights[c]))
        heights[c] += 1
        if won(nme):
            heights[c] -= 1
            return WIN - ply          # sooner wins score higher
        moved = True
        score = -_negamax(opp, nme, heights, depth - 1, -beta, -alpha, weights,
                          ply + 1, program)
        heights[c] -= 1
        if score > best:
            best = score
            if best > alpha:
                alpha = best
                if alpha >= beta:
                    break
    return best if moved else 0.0


def choose(genome: Genome, board: Board, rng: random.Random | None = None,
           book=None) -> int | None:
    """Pick a column. `rng` only breaks ties, so a fixed rng means a fixed game."""
    me = board.p[board.side]
    opp = board.p[1 - board.side]
    heights = list(board.h)
    weights = genome.weights
    program = genome.program
    best_score = -INF
    best: list[int] = []

    for c in ORDER:
        if heights[c] >= ROWS:
            continue
        nme = me | (1 << (c * 7 + heights[c]))
        if won(nme):
            return c                    # always take a win that is right there
        heights[c] += 1
        score = -_negamax(opp, nme, heights, genome.depth - 1, -INF, INF, weights, 1,
                          program)
        heights[c] -= 1
        if book is not None:
            # A remembered blunder is priced far below any evaluation, so it is
            # only avoided when there is something else to play.
            score += book.penalty(me, opp, board.side, c)
        if score > best_score + 1e-9:
            best_score = score
            best = [c]
        elif abs(score - best_score) <= 1e-9:
            best.append(c)

    if not best:
        return None
    if rng is not None and len(best) > 1:
        return rng.choice(best)
    return best[0]


def player(genome: Genome, book=None):
    """Adapt a genome to the (board, rng) -> column interface.

    The rng is passed through even though it only breaks ties. Without it, a
    deterministic player against a deterministic opponent is *one* game -- and
    an exam that reports eight games when only two distinct games exist is not
    measuring anything, it is repeating itself.
    """
    def move(board: Board, rng: random.Random) -> int:
        col = choose(genome, board, rng, book)
        if col is None:
            raise RuntimeError("no legal move")
        return col
    return move


# -- fixed opponents, used by the exam ---------------------------------------


def random_player(board: Board, rng: random.Random) -> int:
    legal = board.legal()
    return rng.choice(legal)


def first_player(board: Board, rng: random.Random) -> int:
    legal = board.legal()
    return legal[-1] if legal else 0


def centre_player(board: Board, rng: random.Random) -> int:
    h = board.h
    for c in ORDER:
        if h[c] < ROWS:
            return c
    return 0


def _gauntlet(depth: int):
    genome = Genome(weights=GAUNTLET_WEIGHTS, depth=depth)
    return player(genome)


GAUNTLET = {
    "random": random_player,
    "first": first_player,
    "centre": centre_player,
    "hand-2": _gauntlet(2),
    "hand-3": _gauntlet(3),
    # One ply deeper than the organism is normally allowed to grow, so a perfect
    # score is not reachable. That is deliberate: an exam you can max out teaches
    # you nothing after the day you max it out.
    "hand-4": _gauntlet(4),
}

# Style is measured only against opposition worth measuring against. Against a
# coin-flip opponent every player looks quiet, and averaging that in would drag
# the number down for reasons that say nothing about the organism.
STYLE_OPPONENTS = ("hand-3", "hand-4")


def with_settings(genome: Genome, **changes) -> Genome:
    return replace(genome, **changes)
