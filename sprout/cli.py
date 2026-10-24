"""Command line for Sprout.

    sprout run     --cycles 5 --iterations 12     # the forever loop, a slice of it
    sprout status                                 # where it has got to
    sprout board                                  # what it plays like now
    sprout exam                                   # sit the exam again, no change
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .arena import series, style_score
from .game import Board
from .organism import GAUNTLET, Genome, level_one, player
from .trainer import (EXAM_SEEDS, EXAM_SIZE, SANITY, SCORED, examine, load_state,
                      render_showcase, run)


def _repo() -> Path:
    return Path.cwd()


def cmd_run(args) -> int:
    state = run(_repo(), iterations=args.iterations, cycles=args.cycles,
                pause=args.pause, quiet=args.quiet, reset=args.reset,
                size=args.size, selfplay_games=args.selfplay)
    if args.json:
        print(json.dumps(state, indent=2))
    return 0


def cmd_status(args) -> int:
    state = load_state(_repo() / "board")
    if state is None:
        print("sprout has not been started yet. run: sprout run")
        return 1
    g = Genome.from_json(state["genome"])
    exam = state["exam"]
    if args.json:
        print(json.dumps(state, indent=2))
        return 0
    print(f"Sprout  ·  level {state['level']}")
    print(f"  exam          {state['record']:.3f}   "
          f"({exam['wins']} won, {exam['draws']} drawn, {exam['losses']} lost "
          f"of {exam['games']})")
    print(f"  peak exam     {state['peak']['exam']:.3f}  reached at level {state['peak']['at_level']}")
    print(f"  generations   {state['generations']}")
    print(f"  accepted      {state['accepted']}")
    print(f"  rejected      {state['rejected']}")
    print(f"  stalled       {state['stall']} generation(s) without a breakthrough")
    print(f"  brain         {g.describe()}")
    memory = state.get("memory") or {}
    if memory:
        print(f"  memory        {memory.get('positions', 0)} positions booked, "
              f"{memory.get('games', 0)} games watched")
    print(f"  born          {state['born']}")
    print(f"  updated       {state['updated']}")
    print()
    print("  opponents it is scored against, every generation, unchanged:")
    for name in exam["opponents"]:
        print(f"    - {name}")
    return 0


def cmd_board(args) -> int:
    state = load_state(_repo() / "board")
    if state is None:
        print("sprout has not been started yet. run: sprout run")
        return 1
    genome = Genome.from_json(state["genome"])
    print(render_showcase(genome, state["level"]))
    return 0


def cmd_exam(args) -> int:
    """Sit the exam with the current brain and print every opponent, so a
    reader can see where it is strong and where it is still useless."""
    state = load_state(_repo() / "board")
    genome = Genome.from_json(state["genome"]) if state else level_one()
    me = player(genome)
    import random

    from .arena import blank_style, merge_style
    print(f"exam · level {state['level'] if state else 1} · "
          f"{args.games} games per opponent, alternating first move\n")
    scored_w = scored_d = scored_n = 0
    style = blank_style()
    for name, opponent in GAUNTLET.items():
        w = d = n = 0
        for seed in EXAM_SEEDS:
            rng = random.Random(f"{seed}:{name}:{genome.depth}:{genome.weights}")
            r = series(me, opponent, args.games, rng, record_style=True)
            w += r["a"]; d += r["draws"]; n += r["games"]
            if name not in SANITY:
                merge_style(style, r["style"][0])
        rate = (w + 0.5 * d) / n if n else 0.0
        tag = "counts" if name in SCORED else "sanity"
        print(f"  vs {name:<8} {w:>3}W {d:>3}D {n - w - d:>3}L   score {rate:.3f}   ({tag})")
        if name not in SANITY:
            scored_w += w; scored_d += d; scored_n += n
    overall = (scored_w + 0.5 * scored_d) / scored_n if scored_n else 0.0
    print(f"\n  scored {overall:.3f}   style {style_score(style):.1f}/100")
    return 0


def cmd_world(args) -> int:
    """Play the current organism against every rung on the world ladder.

    These scores are kept separate from the exam on purpose. The exam decides
    whether a mutation is allowed to become a level; the ladder only reports
    where the organism stands against opponents it did not grow up with. Mixing
    the two would mean a rung could change a level, and then the score would
    depend on who happened to be on the ladder that month.
    """
    from .world import describe, duel, load_ladder

    state = load_state(_repo() / "board")
    if state is None:
        print("sprout has not been started yet. run: sprout run")
        return 1
    specs = load_ladder(_repo() / "board" / "ladder.json")
    if not specs:
        print("the ladder is empty. run: python3 tools/scout.py")
        return 1

    genome = Genome.from_json(state["genome"])
    print(describe(specs))
    print()
    rows = []
    for spec in specs:
        result = duel(genome, spec, games=args.games)
        rows.append(result)
        flag = "  (rung failed to answer)" if result["crashes"] else ""
        print(f"  vs {spec.name:<14} {result['wins']:>2}W {result['draws']:>2}D "
              f"{result['losses']:>2}L   score {result['score']:.3f}{flag}")

    played = [r for r in rows if r["wins"] + r["draws"] + r["losses"]]
    if played:
        overall = sum(r["score"] for r in played) / len(played)
        print(f"\n  against the world  {overall:.3f}  (level {state['level']}, "
              f"exam {state['record']:.3f})")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="sprout",
        description="A program that improves itself against a fixed exam, forever.")
    ap.add_argument("--version", action="version", version=f"sprout {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("run", help="evolve for a slice of time")
    p.add_argument("--iterations", type=int, default=12, help="generations per cycle")
    p.add_argument("--cycles", type=int, default=1, help="how many cycles")
    p.add_argument("--pause", type=float, default=0.0, help="seconds between cycles")
    p.add_argument("--size", type=int, default=EXAM_SIZE, help="games per opponent")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--reset", action="store_true", help="start the baby over")
    p.add_argument("--selfplay", type=int, default=4,
                   help="games against itself per cycle, to book mistakes")
    p.add_argument("--json", action="store_true", help="print the final state")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("status", help="where has it got to")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("board", help="print a game it just played")
    p.set_defaults(fn=cmd_board)

    p = sub.add_parser("exam", help="sit the exam opponent by opponent")
    p.add_argument("--games", type=int, default=10)
    p.set_defaults(fn=cmd_exam)

    p = sub.add_parser("world", help="play the engines on the world ladder")
    p.add_argument("--games", type=int, default=4)
    p.set_defaults(fn=cmd_world)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        return 0
