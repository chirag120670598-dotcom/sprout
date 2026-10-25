"""The engine that keeps going.

One generation is: take the current organism, make `population` mutated copies,
put every copy through the same fixed exam, keep the best one -- but only if it
beats the current record by a margin. Repeat forever. Stop improving when it
stops improving, which happens on its own and is reported rather than hidden.

Nothing here reads the internet, and nothing writes to the repository's code.
It writes JSON.
"""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path

from .arena import blank_style, merge_style, series, style_score
from .memory import Book
from .game import Board
from .organism import GAUNTLET, STYLE_OPPONENTS, Genome, level_one, mutate, player

# Two exam sizes, for two different jobs.
#
# EXAM_SIZE is the shortlist: cheap enough to run on every child of a generation.
# CONFIRM_SIZE is the gate: three times longer, and only the best child of a
# generation has to sit it. Shortlisting on a small exam and then believing the
# winner is the classic way to publish a number that is really the luckiest of
# twenty-four noisy samples -- the maximum of noise always looks like a signal.
# A candidate only becomes the record if it survives the longer exam.
EXAM_SIZE = 4
CONFIRM_SIZE = 12
EXAM_SEEDS = (104729, 1299709)

# The exam has two halves. Only the serious half is scored. Beating a player
# that flips a coin is not evidence of anything, and averaging it in makes a
# newborn look half-trained.
SCORED = ("hand-2", "hand-3", "hand-4")
SANITY = ("random", "first", "centre")
STALL_LIMIT = 12

STATE_FILE = "state.json"
LEDGER_FILE = "ledger.jsonl"
BOARD_FILE = "live.board"
MEMORY_FILE = "memory.json"

# A single job is allowed this many seconds of total pause. The workflow is a
# chain of jobs, so pacing belongs between runs, not inside one.
MAX_PAUSE_SECONDS = 210


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# -- the exam ----------------------------------------------------------------


def examine(genome: Genome, size: int = EXAM_SIZE, seeds=EXAM_SEEDS) -> dict:
    """A fixed exam, in two halves.

    The scored half is the three opponents that actually plan. The sanity half
    is the three that do not -- a player that loses to a coin flip has a bug,
    not a training problem, and that shows up here immediately.

    The opponents are always the same and the seeds are always the same, so a
    score is comparable across generations and across months. An exam that
    changes between candidates measures nothing.
    """
    me = player(genome)
    scored_w = scored_d = scored_n = 0
    sanity: dict[str, float] = {}

    for name, opponent in GAUNTLET.items():
        w = d = n = 0
        for seed in seeds:
            # The opponent's *name*, never its id -- an id changes between
            # processes, which would make the exam differently hard each run.
            rng = random.Random(f"{seed}:{name}:{genome.depth}:{genome.weights}")
            result = series(me, opponent, size, rng, record_style=False)
            w += result["a"]
            d += result["draws"]
            n += result["games"]
        rate = (w + 0.5 * d) / n if n else 0.0
        if name in SANITY:
            sanity[name] = rate
        else:
            scored_w += w
            scored_d += d
            scored_n += n

    return {
        "score": (scored_w + 0.5 * scored_d) / scored_n if scored_n else 0.0,
        "wins": scored_w,
        "draws": scored_d,
        "losses": scored_n - scored_w - scored_d,
        "games": scored_n,
        "seed": EXAM_SEEDS[0],
        "opponents": list(SCORED),
        "sanity": {k: round(v, 3) for k, v in sanity.items()},
    }


def measure_style(genome: Genome, size: int = EXAM_SIZE, seeds=EXAM_SEEDS) -> float:
    """How alive it looks, scored 0..100, measured against the two strongest
    fixed opponents. Both figures describe the same month's organism."""
    me = player(genome)
    style = blank_style()
    for name in STYLE_OPPONENTS:
        opponent = GAUNTLET[name]
        for seed in seeds:
            rng = random.Random(f"{seed}:{name}:{genome.depth}:{genome.weights}")
            result = series(me, opponent, size, rng, record_style=True)
            merge_style(style, result["style"][0])
    return style_score(style)


# -- state -------------------------------------------------------------------


def new_state(level: int = 1, size: int = EXAM_SIZE,
              confirm_size: int = CONFIRM_SIZE) -> dict:
    genome = level_one()
    # The born record is measured at the same length as every later gate, so
    # the first score and the last are the same kind of number.
    exam = examine(genome, size=confirm_size)
    style = measure_style(genome)
    return {
        "version": 1,
        "name": "sprout",
        "level": level,
        "genome": genome.to_json(),
        "exam": exam,
        "record": exam["score"],
        "style": style,
        "peak": {"exam": exam["score"], "at_level": level},
        "generations": 0,
        "accepted": level - 1,
        "rejected": 0,
        "stall": 0,
        "born": _now(),
        "updated": _now(),
        "history": [{"level": level, "exam": round(exam["score"], 4),
                     "style": style, "generation": 0, "opponents": exam["opponents"]}],
    }


def load_state(board: Path) -> dict | None:
    path = board / STATE_FILE
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A half-written state file must not kill a run that took a month to
        # build. Start over rather than crash.
        return None


def save_state(board: Path, state: dict) -> None:
    board.mkdir(parents=True, exist_ok=True)
    tmp = board / (STATE_FILE + ".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, board / STATE_FILE)


def append_ledger(board: Path, entry: dict) -> None:
    board.mkdir(parents=True, exist_ok=True)
    with open(board / LEDGER_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


def selfplay(genome: Genome, book: Book, games: int, rng: random.Random) -> dict:
    """Play itself, then book the loser's moves.

    The book is used here and on the ladder, and deliberately **not** in the
    exam. A memory that grows between generations would mean the exam changed
    while the candidates did not -- and a score you cannot compare across months
    is not a score. Memory helps it play. The exam alone decides whether it
    levelled up.
    """
    from .game import Board

    me = player(genome, book)
    wins = draws = 0
    booked = 0
    for g in range(games):
        local = random.Random(f"self:{rng.random()}:{g}")
        board = Board()
        while True:
            col = me(board, local)
            board.play(col)
            if board.winner() is not None or board.is_full():
                break
        winner = board.winner()
        if winner is None:
            draws += 1
            continue
        wins += 1
        booked += book.harvest(board.moves, 1 - winner)
    return {"games": games, "wins": wins, "draws": draws, "booked": booked,
            "positions": len(book)}


def render_showcase(genome: Genome, level: int) -> str:
    """One game against the strongest fixed opponent, printed so a reader can
    see what the thing actually does. If it loses, the board says so."""
    opponent = GAUNTLET["hand-3"]
    me = player(genome)
    rng = random.Random(f"showcase:{level}")
    sprout_first = level % 2 == 1
    board = Board()
    while True:
        mover = me if (board.side == 0) == sprout_first else opponent
        col = mover(board, rng)
        board.play(col)
        if board.winner() is not None or board.is_full():
            break
    winner = board.winner()
    if winner is None:
        verdict = "Drawn."
    elif (winner == 0) == sprout_first:
        verdict = f"Sprout won in {board.n} moves."
    else:
        verdict = f"Sprout lost in {board.n} moves."
    side = "o" if sprout_first else "x"
    return (
        f"Sprout ({side}) vs hand-3   ·   level {level}\n"
        f"{board.render()}\n"
        f"{verdict}\n"
    )


# -- one generation ----------------------------------------------------------


def evolve(state: dict, rng: random.Random, size: int = EXAM_SIZE,
           seeds=EXAM_SEEDS, confirm_size: int = CONFIRM_SIZE) -> dict:
    """Run one generation and return a summary. Mutates `state`."""
    parent = Genome.from_json(state["genome"])
    record = state["record"]

    # After a long flat stretch, search further from home. Being stuck is a
    # property of the method, not of the organism, so the method is what moves.
    escaping = state["stall"] >= STALL_LIMIT
    sigma = parent.sigma * 1.6 if escaping else parent.sigma

    best_score, best_child, best_result = -1.0, None, None
    for _ in range(parent.population):
        child = mutate(parent, rng, sigma=sigma)
        result = examine(child, size, seeds)
        if result["score"] > best_score:
            best_score, best_child, best_result = result["score"], child, result

    # The gate. Same seeds, three times the games. Everything that gets written
    # into state.json as a new record was measured here, not on the shortlist.
    best_result = examine(best_child, confirm_size, seeds)
    accepted = best_result["score"] > record + parent.margin
    delta = best_result["score"] - record

    state["generations"] += 1
    if accepted:
        state["genome"] = best_child.to_json()
        state["exam"] = best_result
        state["record"] = best_result["score"]
        state["level"] += 1
        state["accepted"] += 1
        state["stall"] = 0
        # Measured on the long exam, like the record, so the published
        # aliveness figure is not the noisy one from the shortlist.
        state["style"] = measure_style(best_child, confirm_size, seeds)
        if state["record"] > state["peak"]["exam"]:
            state["peak"] = {"exam": state["record"], "at_level": state["level"]}
        state["history"].append({
            "level": state["level"],
            "exam": round(state["record"], 4),
            "style": state["style"],
            "generation": state["generations"],
            "opponents": best_result["opponents"],
        })
    else:
        state["rejected"] += 1
        state["stall"] += 1

    state["updated"] = _now()
    return {
        "generation": state["generations"],
        "level": state["level"],
        "child": best_result["score"],
        "shortlist": best_score,
        "record": record,
        "delta": delta,
        "accepted": accepted,
        "escaping": escaping,
        "child_genome": best_child.to_json() if best_child else None,
    }


def run(repo: Path, iterations: int = 12, cycles: int = 1, pause: float = 0.0,
        quiet: bool = False, reset: bool = False, size: int = EXAM_SIZE,
        confirm_size: int = CONFIRM_SIZE, selfplay_games: int = 4) -> dict:
    """The forever loop, called for a slice of time.

    `iterations` generations per cycle, `cycles` cycles, `pause` seconds between
    them. GitHub Actions gives a job a maximum life, so a truly endless run is a
    sequence of long ones rather than a single immortal process.
    """
    repo = Path(repo)
    board = repo / "board"
    board.mkdir(parents=True, exist_ok=True)

    book = Book.load(board / MEMORY_FILE)
    state = None if reset else load_state(board)
    if state is None:
        state = new_state(size=size, confirm_size=confirm_size)
        save_state(board, state)
        if not quiet:
            print(f"sprout born · level 1 · exam {state['exam']['score']:.3f} "
                  f"({state['exam']['wins']}W {state['exam']['draws']}D {state['exam']['losses']}L)")

    rng = random.Random(f"{state['generations']}:{time.time_ns()}")
    total_pause = pause * max(0, cycles - 1)
    if pause and total_pause > MAX_PAUSE_SECONDS:
        raise SystemExit(
            f"pause x (cycles - 1) = {total_pause}s, over the "
            f"{MAX_PAUSE_SECONDS}s budget for one job; "
            "shorten the pause or run more, shorter jobs instead")

    for cycle in range(cycles):
        accepted_this_cycle = False
        for _ in range(iterations):
            summary = evolve(state, rng, size=size, confirm_size=confirm_size)
            accepted_this_cycle = accepted_this_cycle or summary["accepted"]
            save_state(board, state)
            append_ledger(board, {
                "ts": _now(),
                "generation": summary["generation"],
                "level": summary["level"],
                "child": round(summary["child"], 4),
                "shortlist": round(summary["shortlist"], 4),
                "record": round(summary["record"], 4),
                "delta": round(summary["delta"], 4),
                "accepted": summary["accepted"],
                "escaping": summary["escaping"],
                "depth": state["genome"]["depth"],
                "sigma": state["genome"]["sigma"],
                "population": state["genome"]["population"],
            })
            if not quiet:
                flag = "ACCEPTED -> level %d" % summary["level"] if summary["accepted"] else "rejected"
                print(f"gen {summary['generation']:05d}  "
                      f"child {summary['child']:.3f}  record {summary['record']:.3f}  "
                      f"{summary['delta']:+.3f}  {flag}"
                      + ("   [searching wider]" if summary["escaping"] else ""))

        # Redraw the showcase whenever the level moved during this cycle, not
        # only when the *last* generation did. A level-up on generation 3
        # followed by five rejections used to leave the board stale.
        if accepted_this_cycle:
            genome = Genome.from_json(state["genome"])
            (board / BOARD_FILE).write_text(render_showcase(genome, state["level"]),
                                            encoding="utf-8")

        # A little life between cycles: it plays itself, remembers what went
        # wrong, and that memory is on disk before the next job picks it up.
        if selfplay_games:
            life = selfplay(Genome.from_json(state["genome"]), book, selfplay_games, rng)
            book.save(board / MEMORY_FILE)
            state["memory"] = {"positions": life["positions"],
                               "games": book.data.get("games", 0),
                               "learned": book.data.get("learned", 0)}
            save_state(board, state)
            append_ledger(board, {"ts": _now(), "kind": "memory",
                                  "positions": life["positions"],
                                  "booked": life["booked"], "games": life["games"]})
            if not quiet:
                print(f"  memory  {life['positions']} positions, "
                      f"{life['booked']} moves booked this cycle")

        if cycle + 1 < cycles and pause:
            time.sleep(pause)

    # Re-measure the published aliveness on the long exam before writing the
    # final state. The genome has not changed; only the estimate got better.
    state["style"] = measure_style(Genome.from_json(state["genome"]), size=confirm_size)
    state.setdefault("memory", {"positions": len(book),
                                "games": book.data.get("games", 0),
                                "learned": book.data.get("learned", 0)})
    state["memory"]["positions"] = len(book)
    state["updated"] = _now()
    save_state(board, state)

    if not quiet:
        print(f"level {state['level']} · exam {state['record']:.3f} · "
              f"{state['generations']} generations · "
              f"{state['accepted']} accepted / {state['rejected']} rejected")
    return state
