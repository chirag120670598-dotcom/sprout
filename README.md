# Sprout

**A program that levels itself up, and stops when it stops improving.**

Born at level 1 with no idea what a good move looks like. Every six hours it mutates into twenty-odd copies of itself, makes all of them sit the same exam, and keeps a copy only if it measurably plays better. Nobody edits it. You can only watch.

**[chirag120670598-dotcom.github.io/sprout](https://chirag120670598-dotcom.github.io/sprout/)** — the live numbers, read straight out of the file the organism writes.

```
born        0.028   — 2 wins, 70 losses, 72 games
now         see the site — the README does not get to claim numbers it cannot keep current
ceiling     published, not hidden
```

---

## What the idea actually is

You have seen this idea before. A thing that grows by itself, gets smarter with every cycle, and never has to be touched again. Ultron. The paperclip machine. Every "self-improving AI" thread on the internet.

Almost all of it is either a fantasy or a lie, and both fail the same way: **there is no honest way to measure "better".** A system that decides for itself whether it improved is a system that can always claim it did.

So the real problem is not "how do I make something that improves indefinitely". The real problem is: **can you build a thing that genuinely improves itself, where the improvement is a fact instead of a claim — and then be honest about where it stops?**

That is what this repository is.

Sprout is small on purpose. One game, one exam, one program. It is a working, complete, honest answer to the fantasy, at a size where every part of it can be checked by a person in twenty minutes.

---

## What it actually does

**The game.** Connect Four. Seven columns, six rows, four in a line. The rules fit on one page, a wrong move costs nothing, and — critically — a game can be replayed by anyone, so every result is verifiable.

**The brain.** There is no neural network here and pretending otherwise would be dishonest. It is a weighted evaluation of the 69 four-in-a-row windows on the board, read by alpha-beta search. The evaluation is *five numbers*. The search looks at most three moves ahead. That is the whole organism.

**The improvement.** Each generation makes `population` mutated children. Each child is the parent with its weights nudged by random amounts. **Every child sits the identical exam.** The best of them then sits a *second*, three-times-longer exam — the gate — and only that longer score is allowed to become the record. Finally it has to beat the current champion by a margin. A tie is not a win. Most generations are thrown away.

**The gate exists because of a mistake made here first.** The first version shortlisted on 24 games and wrote the winner straight into the record. One mutation scored 0.958 that way; every generation afterwards scored between 0.458 and 0.729 against it. The newcomers were not worse — the *record* was the luckiest of twenty-four noisy samples. That is the winner's curse, and it produces exactly the flattering curve this project is supposed to be the opposite of. Now a score needs 144 games before it can become a record.

**What gets mutated includes the mutation itself.** The mutation width, the population size, the acceptance margin — all of those live in the genome and drift along with the weights. It is not just learning to play; it is learning how to learn. When a long flat stretch sets in, the mutation width is multiplied to search further from home, because being stuck is a property of the method, and the method is what can move.

---

## The exam, and why it is the whole trick

The exam is the reason any of this means anything. It is fixed forever.

| Opponent | What it is | Counts? |
|---|---|---|
| `random` | picks a legal column at random | no — sanity only |
| `first` | always the leftmost empty column | no — sanity only |
| `centre` | always the middle-most empty column | no — sanity only |
| `hand-2` | hand-written weights, two moves ahead | **yes** |
| `hand-3` | the same, one move deeper | **yes** |
| `hand-4` | the same, two moves deeper — **one ply beyond what Sprout may grow to** | **yes** |

Three design decisions do all the work:

**1. The easy opponents are not scored.** Beating a coin flip is not evidence of thinking. Average it in and a newborn looks half-trained. Those three games still run every generation, because losing to one would mean a bug rather than a bad training run — they are a smoke test, not a score.

**2. A perfect score is unreachable by design.** Sprout is capped at three plies of search; `hand-4` looks four ahead. So the organism can never finish the exam and declare itself done. When the line goes flat, that is the ceiling arriving, and it arrives by construction rather than by accident.

**3. The exam never changes.** Same opponents, same seeds, same number of games, same alternating first move. An exam that gets easier over time, or that differs between candidates, measures nothing. A score you can compare across six months is worth more than one that keeps climbing because the test got softer.

Every generation also alternates who moves first. A player that only wins when handed the first move is not better, it is luckier — and a fixed schedule would hide that.

---

## The world ladder — where GitHub actually helps

A program cannot absorb GitHub. Reading repositories does not make anything cleverer, and no amount of access turns five weights into a general mind. That part of the dream is not achievable by any software, so this project does the part that is.

Being measured against something stronger is the one mechanism on this page that produces real improvement. So the organism has a **ladder**: engines that live outside this repository, each pinned to an exact revision, which it plays through a one-line protocol.

```
parent  ->  PLAY 3322      the columns played so far, oldest first
engine  ->  3              the column to play next
```

The split between scout and ladder is deliberate, and it is the whole safety story:

| | |
|---|---|
| **`tools/scout.py`** | A *tool*. Searches GitHub, writes candidates to `board/scout.json`. Run by a person. Found **38** real engine repositories on its first run. |
| **`board/ladder.json`** | A *file a person edits*, by hand, pinned to a commit. Nothing is added automatically. |
| **`sprout world`** | The organism plays whatever is on the ladder — one process per game, a timeout, a closed pipe. |
| **The package** | Contains **no network code whatsoever**. A test fails the build if a single network import appears. |

**World scores never change a level.** If they did, the record would depend on who happened to be on the ladder that month, and the growth curve would be measuring the ladder instead of the organism. So the ladder is reported separately, and it is allowed to go down.

What a person could add, and the organism cannot: any engine that speaks the protocol. An adapter is ten lines. The pinning is not paranoia — a rung that can change underneath a score is not a rung.

---

## The two numbers, and what they are not

**Exam score (0.000 – 1.000).** Results against the three opponents that plan, averaged, with draws counting half. This is strength. It is a game result, not a self-report.

**Aliveness (0 – 100).** Not strength. It asks whether the thing creates problems for a serious opponent: how often a move leaves a threat that has to be answered, and how often a move creates two at once. Measured only against the two strongest fixed opponents, because against a coin flip every player looks quiet. A player can lose while pressing constantly and still score as alive.

The reference points in `sprout/arena.py` were **measured**, not invented — `python3 tools/calibrate.py` plays the fixed opponents against each other and prints the floor and the ceiling. If you edit them by hand, the number becomes decorative.

---

## The rules that keep it honest

These are not aspirations. Each one is checked by something that would fail.

| The claim | What would catch it if it were false |
|---|---|
| The improvement is real | Every generation plays real games against fixed opponents and the ledger records the result — **accepted or rejected** — in `board/ledger.jsonl` |
| Nobody hand-tuned the brain | No weights are written by hand anywhere. `tools/check_site.py` compares `sprout/*.py` against `frozen.sha256` and fails on any edit |
| It cannot look up the answers | There is no network code in the package. A test scans every module and fails the build if `socket`, `urllib`, `http` or `subprocess` ever appears |
| The published numbers are the real ones | `tools/build_site.py` writes the page from `board/state.json`; `tools/check_site.py` fails the build if the two disagree |
| The plateau is not hidden | The flat tail of the growth curve is published, along with the count of rejected generations and the current stall counter |
| The engine is correct | The bitboard win-detector is cross-checked against a naive two-dimensional implementation over 4,000 random boards and 200 complete games |

If the engine is ever changed, `frozen.sha256` is regenerated **in the same commit**, with the reason stated. The audit trail is the commit history, and it is public.

---

## Honest limits

Read this before believing anything on the site.

- **It is not intelligent in the modern sense.** There is no neural network. There are five numbers and a search three plies deep. It is a very good toy and a very honest one, and calling it more than that would be the exact dishonesty this project exists to avoid.
- **It cannot improve at anything except this game.** What improves is a list of five floats. Point it at a different problem and it is thirty lines from useless.
- **It cannot get anything from outside.** No internet, no downloads, no reading up on strategy. It can start an engine a person already put on the ladder, and that is the only door in the building.
- **Having access to all of GitHub would not make it smarter.** This is the important one. Access is not intelligence and it is not learning. A thousand repositories are a thousand things to be measured against, not a thousand ideas it absorbs; the only thing that improves here is a list of five numbers, and it improves by playing, not by reading. Anyone who tells you their program gets smarter by being given more repositories is describing a search engine.
- **It cannot rewrite its own code, change its own exam, or decide that it wants something.** The mutation only ever touches numbers that the engine defines.
- **Improvement is finite, and the ceiling is close.** It is capped at three plies of search against a four-ply opponent. Expect a rapid rise and then a long flat stretch. That is the honest shape of it. A curve that kept going up forever would mean the exam was leaking.
- **The exam is only as good as its opponents.** It can only get good at what the exam asks. If all six opponents were weak, the organism would happily max out at "best of a bad field" and the score would mean nothing. The gauntlet was checked for internal ordering (`hand-2` beats `hand-4` 25% of the time, `hand-3` beats `hand-4` 10%) so the ladder is real.
- **This is a demonstration, not a result.** Nothing here is a finding about machine learning. It is a finding about honesty: how far a thing can get with measurement, mutation, and patience, when nobody is allowed to help it.

---

## Where the fantasy breaks, and what replaces it

The dream is "level 1 to infinite, improving forever on its own".

It does not do that, and nothing does. What it does instead:

- **It genuinely improves itself.** The improvement is a mutation plus a measurement, not a human edit. In the first few generations the exam score moves from 0.028 to well past half marks with nobody touching it.
- **It genuinely stops when it is done.** No system that improves forever has ever existed, because "forever" requires an infinite supply of things you are bad at. Here the supply runs out quickly and the repository shows the exact generation where it did.
- **The ceiling is a fact, not a mystery.** Three plies against four. If you want it higher, that is an engine change — which means a human, a commit, and a reason.

The honest version is smaller than the fantasy. It is also the only version that is true, and it is genuinely satisfying to watch: something that knew nothing, getting better on its own, and then arriving at its limit and saying so.

---

## Run it yourself

```bash
git clone https://github.com/chirag120670598-dotcom/sprout.git
cd sprout

python3 -m sprout status     # where has it got to
python3 -m sprout board      # a game it just played, drawn on the terminal
python3 -m sprout exam       # sit the exam again, opponent by opponent
python3 -m sprout run --iterations 20 --cycles 4 --pause 60
```

No dependencies. Python 3.9 or newer. Nothing to install.

```
sprout/game.py       bitboard rules, and a win test that is checked against a naive one
sprout/organism.py   the genome, the evaluation, the search, the fixed opponents
sprout/arena.py      games, the strength score, the aliveness score
sprout/trainer.py    generations, the exam, the state file, the ledger
sprout/cli.py        run / status / board / exam
board/state.json     written by the organism, not by a person
board/ledger.jsonl   every generation, accepted or rejected
board/live.board     a game it just played
tools/build_site.py  renders the page from the state
tools/check_site.py  fails the build if the page and the state disagree
tools/calibrate.py   measures the aliveness reference points
```

**Fork it and it is yours.** You can change the engine, weaken the exam, make the curve look beautiful — in your fork. That is the difference between a demo and a claim.

### About the read-only thing

GitHub already makes a repository read-only to everyone who does not own it. On top of that, `frozen.sha256` plus `tools/check_site.py` will fail CI if any file under `sprout/` changes without the hashes being regenerated alongside it. That is a guardrail against accidental edits — it is not cryptography, and the owner can always regenerate the hashes. What it guarantees is that such an edit would be **visible in the commit history**, which is the actual promise: no quiet improvements.

---

## Licence

Apache-2.0. Take it, fork it, run your own.
