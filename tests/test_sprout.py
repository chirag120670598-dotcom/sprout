"""Tests for Sprout.

The interesting failure modes here are silent ones. A bitboard that is wrong
one time in ten thousand still plays a plausible game; an evaluation that is not
antisymmetric still wins games, just fewer than it should; a trainer that
compares a candidate against itself still reports levels going up. Each of those
has a test that would notice.
"""

from __future__ import annotations

import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sprout.arena import (blank_style, merge_style, open_threes, play,  # noqa: E402
                          series, style_score)
from sprout.game import COLS, PLAYABLE, ROWS, WINDOWS, Board, IllegalMove, popcount, won  # noqa: E402
from sprout.organism import (GAUNTLET, GAUNTLET_WEIGHTS, MAX_DEPTH, Genome,  # noqa: E402
                             choose, evaluate, level_one, mutate, player)
from sprout.trainer import (EXAM_SIZE, SANITY, SCORED, evolve, examine,  # noqa: E402
                            load_state, measure_style, new_state, render_showcase,
                            save_state)

# Only the 42 playable cells. The seventh row of each column exists in the bit
# layout purely as padding so a shift cannot wrap into the next column.
PLAYABLE_MASK = sum(1 << (c * 7 + r) for c in range(COLS) for r in range(ROWS))

# examine() and measure_style() take size + seeds; evolve() also takes a gate
# length; new_state() does not take seeds at all. Keeping them separate stops a
# test from silently measuring something other than what it claims.
TINY = dict(size=1, seeds=(11,))
TINY2 = dict(size=2, seeds=(11, 23))
EVOLVE_TINY = dict(size=1, seeds=(11,), confirm_size=1)
STATE_TINY = dict(size=1, confirm_size=1)
STRONG = Genome(weights=GAUNTLET_WEIGHTS, depth=3)


# -- an independent, obvious implementation to check the clever one against ----


def naive_grid(board: Board):
    grid = [[None] * ROWS for _ in range(COLS)]
    for c in range(COLS):
        for r in range(ROWS):
            bit = 1 << (c * 7 + r)
            if board.p[0] & bit:
                grid[c][r] = 0
            elif board.p[1] & bit:
                grid[c][r] = 1
    return grid


def naive_line(bits: int) -> bool:
    """Does this single bitboard contain four in a line? Gravity is ignored --
    both implementations read the same cells, so they must agree."""
    grid = [[None] * ROWS for _ in range(COLS)]
    for c in range(COLS):
        for r in range(ROWS):
            if bits & (1 << (c * 7 + r)):
                grid[c][r] = 1
    for c in range(COLS):
        for r in range(ROWS):
            if grid[c][r] is None:
                continue
            for dc, dr in ((1, 0), (0, 1), (1, 1), (1, -1)):
                if all(0 <= c + i * dc < COLS and 0 <= r + i * dr < ROWS
                       and grid[c + i * dc][r + i * dr] for i in range(4)):
                    return True
    return False


def naive_winner(board: Board):
    grid = naive_grid(board)
    for c in range(COLS):
        for r in range(ROWS):
            v = grid[c][r]
            if v is None:
                continue
            for dc, dr in ((1, 0), (0, 1), (1, 1), (1, -1)):
                if all(0 <= c + i * dc < COLS and 0 <= r + i * dr < ROWS
                       and grid[c + i * dc][r + i * dr] == v for i in range(4)):
                    return v
    return None


class TestEngineAgainstNaive(unittest.TestCase):
    """The shift trick in `won` is fast and easy to get subtly wrong. It is
    checked here against the slowest, most obvious implementation available."""

    def test_windows_are_69_groups_of_four(self):
        self.assertEqual(len(WINDOWS), 69)
        for mask in WINDOWS:
            self.assertEqual(popcount(mask), 4)

    def test_random_bitboards_agree(self):
        # Only the 42 playable cells. The seventh row of each column exists in
        # the bit layout as padding so shifts cannot wrap, and a bit there would
        # make a board that cannot occur in a real game.
        rng = random.Random(99)
        for _ in range(4000):
            a = rng.getrandbits(49) & PLAYABLE_MASK
            b = rng.getrandbits(49) & PLAYABLE_MASK & ~a
            self.assertEqual(won(a), naive_line(a), bin(a))
            self.assertEqual(won(b), naive_line(b), bin(b))

    def test_whole_games_agree_move_by_move(self):
        rng = random.Random(7)
        for _ in range(200):
            board = Board()
            while True:
                board.play(rng.choice(board.legal()))
                self.assertEqual(board.winner(), naive_winner(board))
                if board.winner() is not None or board.is_full():
                    break

    def test_vertical_wrap_is_impossible(self):
        """The top three cells of column 0 and the bottom three of column 1 are
        six consecutive bits. On a real board they are not a line; a naive
        shift would call them one."""
        bits = sum(1 << (0 * 7 + r) for r in (3, 4, 5))
        bits |= sum(1 << (1 * 7 + r) for r in (0, 1, 2))
        self.assertFalse(won(bits))
        self.assertFalse(naive_line(bits))

    def test_a_full_column_is_a_win(self):
        self.assertTrue(won(sum(1 << r for r in range(6))))


class TestBoard(unittest.TestCase):

    def test_play_and_undo_restore_the_position(self):
        board = Board()
        snapshot = (list(board.p), list(board.h), board.side, board.n)
        for col in (3, 3, 2, 4):
            board.play(col)
        for col in (4, 2, 3, 3):
            board.undo(col)
        self.assertEqual((board.p, board.h, board.side, board.n), snapshot)

    def test_heights_and_legality(self):
        board = Board()
        for _ in range(ROWS):
            board.play(0)
        self.assertEqual(board.h[0], ROWS)
        self.assertNotIn(0, board.legal())
        with self.assertRaises(IllegalMove):
            board.play(0)

    def test_impossible_column_is_refused(self):
        board = Board()
        for bad in (-1, 7, 100):
            with self.assertRaises(IllegalMove):
                board.play(bad)

    def test_a_full_board_with_no_line_is_a_draw(self):
        board = Board()
        board.n = PLAYABLE          # pretend every cell is taken
        self.assertTrue(board.is_full())
        self.assertIsNone(board.winner())
        self.assertEqual(board.outcome(), 2)

    def test_a_live_game_is_not_an_outcome(self):
        board = Board()
        board.play(3)
        self.assertIsNone(board.outcome())

    def test_an_ordinary_game_reaches_a_decision(self):
        board = Board()
        rng = random.Random(11)
        while board.winner() is None and not board.is_full():
            board.play(rng.choice(board.legal()))
        self.assertIsNotNone(board.winner())

    def test_render_has_the_right_shape(self):
        board = Board()
        board.play(3)
        lines = board.render().strip().splitlines()
        self.assertEqual(len(lines), ROWS + 1)     # six rows plus the column numbers
        self.assertEqual(len(lines[0].split()), COLS)

    def test_copy_is_independent(self):
        board = Board()
        board.play(3)
        clone = board.copy()
        clone.play(3)
        self.assertEqual(board.n, 1)
        self.assertEqual(clone.n, 2)


class TestEvaluation(unittest.TestCase):

    def test_antisymmetry(self):
        """Negamax is only correct if flipping the point of view flips the sign.
        A one-sided evaluation produces a player that quietly prefers to lose."""
        rng = random.Random(3)
        weights = (0.3, 1.5, 12.0, 90.0, 0.6)
        for _ in range(500):
            a = rng.getrandbits(49) & PLAYABLE_MASK
            b = rng.getrandbits(49) & PLAYABLE_MASK & ~a
            self.assertAlmostEqual(evaluate(a, b, weights), -evaluate(b, a, weights), places=6)

    def test_three_beats_two(self):
        weights = (0.3, 1.5, 12.0, 90.0, 0.6)
        board = Board()
        for col in (0, 6, 1, 5, 2):
            board.play(col)
        me = board.p[0]
        opp = board.p[1]
        self.assertGreater(evaluate(me, opp, weights), 0)
        self.assertLess(evaluate(opp, me, weights), 0)

    def test_empty_position_is_zero(self):
        self.assertEqual(evaluate(0, 0, (1.0, 1.0, 1.0, 1.0, 1.0)), 0.0)


class TestPlaying(unittest.TestCase):

    def test_only_legal_moves(self):
        rng = random.Random(5)
        board = Board()
        genome = level_one()
        for _ in range(20):
            col = choose(genome, board)
            self.assertIn(col, board.legal())
            board.play(col)

    def test_takes_a_win_that_is_right_there(self):
        board = Board()
        board.p[0] = sum(1 << (c * 7 + 0) for c in (0, 1, 2))
        board.h = [1, 1, 1, 0, 0, 0, 0]
        board.side = 0
        self.assertEqual(choose(level_one(), board), 3)

    def test_blocks_a_loss_that_is_right_there(self):
        board = Board()
        board.p[1] = sum(1 << (c * 7 + 0) for c in (0, 1, 2))
        board.h = [1, 1, 1, 0, 0, 0, 0]
        board.side = 0
        self.assertEqual(choose(STRONG, board), 3)

    def test_same_seed_same_game(self):
        a = play(player(STRONG), GAUNTLET["random"], random.Random(42), record_style=False)
        b = play(player(STRONG), GAUNTLET["random"], random.Random(42), record_style=False)
        self.assertEqual((a["outcome"], a["plies"]), (b["outcome"], b["plies"]))

    def test_the_strong_player_beats_the_coin_flip(self):
        rng = random.Random(1)
        result = series(player(STRONG), GAUNTLET["random"], 12, rng)
        self.assertGreater(result["score"], 0.9)

    def test_alternating_first_move_removes_the_first_move_gift(self):
        """A player that only wins when it moves first must not score well."""
        same = player(STRONG)
        result = series(same, same, 12, random.Random(2))
        self.assertAlmostEqual(result["score"], 0.5, delta=0.15)


class TestGenome(unittest.TestCase):

    def test_round_trip(self):
        genome = STRONG
        again = Genome.from_json(json.loads(json.dumps(genome.to_json())))
        self.assertEqual(again.weights, genome.weights)
        self.assertEqual(again.depth, genome.depth)

    def test_bad_weight_count_is_refused(self):
        with self.assertRaises(ValueError):
            Genome.from_json({"weights": [1.0, 2.0]})

    def test_mutation_stays_in_bounds(self):
        rng = random.Random(8)
        genome = Genome(weights=(500.0, -500.0, 0.0, 0.0, 0.0), depth=MAX_DEPTH,
                        sigma=5.0, population=99, margin=0.9)
        for _ in range(500):
            genome = mutate(genome, rng)
            self.assertEqual(len(genome.weights), 5)
            self.assertTrue(all(-60.0 <= w <= 60.0 for w in genome.weights))
            self.assertTrue(1 <= genome.depth <= MAX_DEPTH)
            self.assertTrue(0.05 <= genome.sigma <= 1.2)
            self.assertTrue(6 <= genome.population <= 32)
            self.assertTrue(0.0 <= genome.margin <= 0.20)

    def test_a_child_is_not_its_parent(self):
        """Children differ in their *code* now, not in five numbers. Comparing
        the weights here passed for the wrong reason until the brain existed."""
        from sprout import brain
        rng = random.Random(9)
        parent = level_one()
        children = {brain.text(mutate(parent, rng).program) for _ in range(20)}
        self.assertGreater(len(children), 12)

    def test_the_genome_carries_the_program_it_will_run(self):
        child = mutate(level_one(), random.Random(4))
        again = Genome.from_json(json.loads(json.dumps(child.to_json())))
        from sprout import brain
        self.assertEqual(brain.text(again.program), brain.text(child.program))

    def test_description_mentions_everything_that_can_change(self):
        text = STRONG.describe()
        for word in ("depth", "weights", "sigma", "pop", "margin"):
            self.assertIn(word, text)


class TestExam(unittest.TestCase):

    def test_exam_is_deterministic(self):
        first = examine(STRONG, **TINY)
        second = examine(STRONG, **TINY)
        self.assertEqual(first, second)

    def test_newborn_loses_to_the_opponents_that_plan(self):
        """Half marks on day one would mean the exam is half pointless."""
        born = examine(level_one(), **TINY2)
        self.assertLess(born["score"], 0.25)
        for name in SANITY:
            self.assertGreaterEqual(born["sanity"][name], 0.5)

    def test_a_strong_genome_scores_higher_than_a_newborn(self):
        born = examine(level_one(), **TINY2)["score"]
        grown = examine(STRONG, **TINY2)["score"]
        self.assertGreater(grown, born)

    def test_scored_and_sanity_halves_are_disjoint(self):
        self.assertEqual(set(SCORED) | set(SANITY), set(GAUNTLET))
        self.assertFalse(set(SCORED) & set(SANITY))

    def test_score_never_exceeds_one(self):
        result = examine(STRONG, **TINY2)
        self.assertLessEqual(result["score"], 1.0)
        self.assertGreaterEqual(result["score"], 0.0)
        self.assertEqual(result["wins"] + result["draws"] + result["losses"], result["games"])


class TestStyle(unittest.TestCase):

    def test_a_coin_flip_is_not_alive(self):
        style = blank_style()
        result = series(GAUNTLET["random"], GAUNTLET["hand-3"], 8, random.Random(4),
                        record_style=True)
        merge_style(style, result["style"][0])
        self.assertLess(style_score(style), 25)

    def test_a_strong_player_is_alive(self):
        style = blank_style()
        result = series(player(STRONG), GAUNTLET["hand-3"], 8, random.Random(4),
                        record_style=True)
        merge_style(style, result["style"][0])
        self.assertGreater(style_score(style), 60)

    def test_score_is_clamped(self):
        loud = {"plies": 10, "press": 10, "double": 10, "wins": 10, "games": 10}
        self.assertLessEqual(style_score(loud), 100.0)
        silent = blank_style()
        self.assertGreaterEqual(style_score(silent), 0.0)

    def test_open_threes_counts_what_it_says(self):
        board = Board()
        for col in (0, 6, 1, 5, 2):
            board.play(col)
        self.assertGreaterEqual(open_threes(board.p[0], board.p[1]), 1)
        self.assertEqual(open_threes(0, 0), 0)


class TestTrainer(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_state_round_trips_and_survives_corruption(self):
        state = new_state(**STATE_TINY)
        save_state(self.tmp, state)
        self.assertEqual(load_state(self.tmp)["level"], 1)
        (self.tmp / "state.json").write_text("{ truncated", encoding="utf-8")
        self.assertIsNone(load_state(self.tmp))

    def test_missing_state_is_none_not_an_error(self):
        self.assertIsNone(load_state(self.tmp / "nowhere"))

    def test_a_child_must_beat_the_record_by_the_margin(self):
        """The strict comparison is the whole promise: levels only go up on a
        real win, never on noise. An unreachable record must reject everything."""
        state = new_state(**STATE_TINY)
        state["record"] = 1.5          # nothing can beat this
        before = state["level"]
        summary = evolve(state, random.Random(1), **EVOLVE_TINY)
        self.assertFalse(summary["accepted"])
        self.assertEqual(state["level"], before)
        self.assertEqual(state["rejected"], 1)

    def test_a_beatable_record_is_beaten(self):
        rng = random.Random(5)
        state = new_state(**STATE_TINY)
        state["record"] = -1.0
        while state["genome"]["population"] < 9:      # keep the test quick
            state["genome"] = mutate(Genome.from_json(state["genome"]), rng).to_json()
        summary = evolve(state, rng, **EVOLVE_TINY)
        self.assertTrue(summary["accepted"])
        self.assertEqual(state["level"], 2)
        self.assertEqual(state["history"][-1]["level"], 2)

    def test_level_equals_one_plus_accepted(self):
        rng = random.Random(6)
        state = new_state(**STATE_TINY)
        for _ in range(3):
            evolve(state, rng, **EVOLVE_TINY)
        self.assertEqual(state["level"], 1 + state["accepted"])

    def test_history_records_only_accepted_levels(self):
        rng = random.Random(7)
        state = new_state(**STATE_TINY)
        for _ in range(4):
            evolve(state, rng, **EVOLVE_TINY)
        self.assertEqual(len(state["history"]), state["level"])

    def test_stall_counter_and_escape(self):
        state = new_state(**STATE_TINY)
        state["record"] = 1.5
        rng = random.Random(8)
        for _ in range(13):
            evolve(state, rng, **EVOLVE_TINY)
        self.assertEqual(state["stall"], 13)
        summary = evolve(state, rng, **EVOLVE_TINY)
        self.assertTrue(summary["escaping"], "a long stall must widen the search")

    def test_every_generation_is_recorded_with_the_same_opponents(self):
        state = new_state(**STATE_TINY)
        self.assertEqual(state["exam"]["opponents"], list(SCORED))
        self.assertEqual(state["history"][0]["opponents"], list(SCORED))

    def test_showcase_is_a_whole_game(self):
        text = render_showcase(STRONG, 3)
        self.assertIn("level 3", text)
        self.assertTrue(any(word in text for word in ("won", "lost", "Drawn")))

    def test_style_of_a_newborn_is_below_a_grown_one(self):
        self.assertLess(measure_style(level_one(), **TINY2), measure_style(STRONG, **TINY2))


class TestBrain(unittest.TestCase):
    """The organism writes its own evaluation function. The parser, the
    interpreter and the mutation all have to be right, because a brain that
    silently evaluates to nonsense still plays a plausible game -- just a bad
    one, which is much harder to notice."""

    def test_text_round_trips(self):
        from sprout import brain
        source = "(add (mul my3 4.1) (sub centre (mul op2 2.7)))"
        self.assertEqual(brain.text(brain.from_text(source)), source)

    def test_it_refuses_to_be_python(self):
        from sprout import brain
        for hostile in ("__import__('os').system('ls')", "(add __import__ zero)",
                        "(system zero zero)", "((((("):
            with self.assertRaises((ValueError, IndexError)):
                brain.from_text(hostile)

    def test_unknown_names_are_not_leaves(self):
        from sprout import brain
        with self.assertRaises(ValueError):
            brain.leaf("secrets")

    def test_newborn_scores_everything_zero(self):
        from sprout import brain
        self.assertEqual(brain.run(brain.newborn(), [9.0] * 8), 0.0)

    def test_arithmetic_is_arithmetic(self):
        from sprout import brain
        node = brain.from_text("(add (mul 2 3) (sub 10 4))")
        self.assertEqual(brain.run(node, [0.0] * 8), 12.0)

    def test_features_see_what_they_claim(self):
        from sprout import brain
        values = brain.features(0, 0)
        self.assertEqual(len(values), 8)
        self.assertTrue(all(v == 0.0 for v in values[:7]))

    def test_mutation_stays_inside_the_cap(self):
        from sprout import brain
        rng = random.Random(5)
        node = brain.newborn()
        for _ in range(300):
            node = brain.mutate(node, rng)
            self.assertLessEqual(brain.size(node), brain.MAX_SIZE)
            self.assertTrue(brain.leaves_used(node), "a brain must look at something")

    def test_a_brain_and_the_old_weights_agree_on_a_fact(self):
        """Both strategies read the same features, so a brain that prefers
        three-in-a-row can be written the same way the weights expressed it."""
        from sprout import brain
        node = brain.from_text("(sub my3 op3)")
        board = Board()
        for col in (0, 6, 1, 5, 2):
            board.play(col)
        self.assertGreater(brain.run(node, brain.features(board.p[0], board.p[1])), 0)


class TestMemory(unittest.TestCase):

    def test_it_books_the_loser_and_avoids_the_move(self):
        from sprout.memory import Book
        book = Book()
        moves = [3, 3, 2, 4, 1, 5, 0]
        booked = book.harvest(moves, loser=0)
        self.assertGreater(booked, 0)
        self.assertTrue(book.avoids(0, 0, 0, 3))
        self.assertFalse(book.avoids(0, 0, 0, 6))

    def test_a_penalty_only_applies_to_the_remembered_move(self):
        from sprout.memory import Book
        book = Book()
        book.record(1, 2, 0, 3)
        self.assertLess(book.penalty(1, 2, 0, 3), 0)
        self.assertEqual(book.penalty(1, 2, 0, 4), 0.0)
        self.assertEqual(book.penalty(1, 2, 1, 3), 0.0, "the side to move is part of the key")

    def test_it_survives_a_truncated_file(self):
        from sprout.memory import Book
        path = Path(tempfile.mkdtemp()) / "memory.json"
        path.write_text("{ half written", encoding="utf-8")
        self.assertEqual(len(Book.load(path)), 0)

    def test_it_saves_and_reloads(self):
        from sprout.memory import Book
        path = Path(tempfile.mkdtemp()) / "memory.json"
        book = Book()
        book.record(5, 6, 1, 2)
        book.save(path)
        again = Book.load(path)
        self.assertTrue(again.avoids(5, 6, 1, 2))

    def test_it_stops_growing_at_the_cap(self):
        from sprout.memory import MAX_ENTRIES, Book
        book = Book()
        for i in range(MAX_ENTRIES + 20):
            book.record(i, i, 0, 3)
        self.assertLessEqual(len(book), MAX_ENTRIES)


class TestNoNetwork(unittest.TestCase):

    def test_the_package_never_opens_a_connection(self):
        """The organism improves by playing games, not by looking things up.

        It is allowed to *spawn* an engine that a human put on the ladder --
        that is how it meets opponents from outside this repository. It is not
        allowed to fetch one. The distinction is the whole safety story: a
        process it can only start, cannot choose, is a sparring partner; a
        network it can reach is a supply chain.
        """
        offenders = []
        for path in (ROOT / "sprout").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for needle in ("import socket", "import urllib", "import requests",
                           "import http.client", "urlopen", "httpx", "aiohttp"):
                if needle in text:
                    offenders.append(f"{path.name}: {needle}")
        self.assertEqual(offenders, [], offenders)

    def test_only_the_world_module_may_start_a_process(self):
        offenders = [path.name for path in (ROOT / "sprout").glob("*.py")
                     if "subprocess" in path.read_text(encoding="utf-8")
                     and path.name != "world.py"]
        self.assertEqual(offenders, [], "only world.py may spawn an engine")


class TestWorldLadder(unittest.TestCase):

    def spec(self, depth=2):
        from sprout.world import EngineSpec
        # An absolute path: a relative one depends on the working directory a
        # test runner happens to choose, which differs between CI and a laptop.
        script = str(ROOT / "tools" / "engines" / "slowhand.py")
        return EngineSpec(name=f"slowhand-{depth}",
                          command=["{python}", script, "--depth", str(depth)],
                          source="bundled", revision="bundled", added="2026-10-24")

    def test_python_placeholder_is_replaced(self):
        self.assertNotIn("{python}", " ".join(self.spec().resolved()))

    def test_a_bad_ladder_entry_is_refused(self):
        from sprout.world import EngineSpec
        with self.assertRaises(ValueError):
            EngineSpec.from_json({"name": "x", "command": []})

    def test_an_engine_that_does_not_exist_says_so(self):
        from sprout.world import EngineError, EngineSpec, ExternalEngine
        spec = EngineSpec(name="ghost", command=["/nowhere/at/all"],
                          source="none", revision="none", added="2026-10-24")
        with self.assertRaises(EngineError):
            with ExternalEngine(spec) as engine:
                engine.move([])

    def test_a_real_external_engine_answers_legal_moves(self):
        from sprout.world import ExternalEngine
        board = Board()
        with ExternalEngine(self.spec(2), timeout=20) as engine:
            for _ in range(8):
                col = engine.move(board.moves)
                self.assertIn(col, board.legal())
                board.play(col)

    def test_a_duel_is_played_and_scored(self):
        from sprout.world import duel
        result = duel(STRONG, self.spec(2), games=2)
        self.assertEqual(result["crashes"], 0)
        self.assertEqual(result["wins"] + result["draws"] + result["losses"], 2)

    def test_the_shipped_ladder_parses(self):
        from sprout.world import load_ladder
        specs = load_ladder(ROOT / "board" / "ladder.json")
        self.assertGreaterEqual(len(specs), 1)
        for spec in specs:
            self.assertTrue(spec.revision, spec.name)

class TheWorkflowIsAllowedToRun(unittest.TestCase):
    """A workflow that cannot start is the quietest possible bug.

    `keep alive` failed twice, in seven seconds, having never once succeeded:
    the workflow asked for a total pause eight times larger than the trainer
    allows, and the trainer refuses rather than let GitHub kill a job halfway
    through a cycle and lose the checkpoint. Nothing in the code was wrong.
    The numbers in the YAML were. So the numbers are now a test.
    """

    def setUp(self):
        import re
        self.text = (ROOT / ".github" / "workflows" / "keep-alive.yml").read_text()
        self.pause = int(re.search(r"--pause (\d+)", self.text).group(1))
        self.cycles = int(
            re.search(r"CYCLES:.*?\|\|\s*'(\d+)'", self.text).group(1))

    def test_the_pause_fits_the_budget(self):
        from sprout.trainer import MAX_PAUSE_SECONDS
        total = self.pause * max(0, self.cycles - 1)
        self.assertLessEqual(
            total, MAX_PAUSE_SECONDS,
            f"pause {self.pause}s x ({self.cycles} - 1) cycles = {total}s, "
            f"budget is {MAX_PAUSE_SECONDS}s - the job would die before it starts")

    def test_the_workflow_actually_invokes_the_trainer(self):
        self.assertIn("python -m sprout run", self.text)


if __name__ == "__main__":
    unittest.main()
