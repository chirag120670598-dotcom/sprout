"""Measure the style reference points. Run this before trusting style_score.

    python3 tools/calibrate.py

It plays every fixed opponent against a strong reference player and prints the
habits it observes. STYLE_REFERENCE in sprout/arena.py was set from this
output, floor to ceiling.
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sprout.arena import blank_style, merge_style, series, style_metrics  # noqa: E402
from sprout.organism import (GAUNTLET, GAUNTLET_WEIGHTS, STYLE_OPPONENTS,  # noqa: E402
                             Genome, level_one, player)

PLAYERS = [
    ("random", GAUNTLET["random"]),
    ("centre", GAUNTLET["centre"]),
    ("level 1 (born)", player(level_one())),
    ("hand-2", player(Genome(weights=GAUNTLET_WEIGHTS, depth=2))),
    ("hand-3", player(Genome(weights=GAUNTLET_WEIGHTS, depth=3))),
    ("hand-4", player(Genome(weights=GAUNTLET_WEIGHTS, depth=4))),
]


def main() -> int:
    references = [GAUNTLET[name] for name in STYLE_OPPONENTS]
    print(f"{'player':<16} {'press':>7} {'double':>7}   (habits per move)\n")
    rows = {}
    for label, candidate in PLAYERS:
        style = blank_style()
        for reference in references:
            for seed in (104729, 1299709):
                rng = random.Random(f"calibrate:{seed}:{label}")
                result = series(candidate, reference, 8, rng, record_style=True)
                merge_style(style, result["style"][0])
        m = style_metrics(style)
        rows[label] = m
        print(f"{label:<16} {m['press_rate']:>7.3f} {m['double_rate']:>7.3f}")

    press = [r["press_rate"] for r in rows.values()]
    double = [r["double_rate"] for r in rows.values()]
    print(f"\nfloor / ceiling observed")
    print(f"  press_rate   {min(press):.3f} .. {max(press):.3f}")
    print(f"  double_rate  {min(double):.3f} .. {max(double):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
