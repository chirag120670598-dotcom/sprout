"""Render site/index.html from board/state.json.

The page's numbers are not typed by hand. They are read from the same file the
organism writes, and tools/check_site.py fails the build if the published page
and the state ever disagree. A dashboard that can drift from its subject is a
poster, not a dashboard.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

CSS = """
:root{
  --bg:#080b09; --panel:#0f1411; --panel-2:#131a15; --rule:#1e2a22;
  --ink:#e6f0e8; --ink-2:#a9bdb0; --ink-3:#6d8377;
  --alive:#7ee787; --alive-dim:#2ea043; --warn:#d29922; --dead:#8b949e;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;background:var(--bg);color:var(--ink);
  font:400 16.5px/1.65 ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:880px;margin:0 auto;padding:0 24px}
a{color:var(--alive);text-decoration-thickness:1px;text-underline-offset:3px}
a:hover{color:#b3f2b9}
h1,h2,h3{line-height:1.16;letter-spacing:-.02em;margin:0}
h1{font-size:clamp(2.05rem,5.4vw,3.2rem);font-weight:650}
h2{font-size:clamp(1.35rem,3vw,1.72rem);font-weight:630}
h3{font-size:1rem;font-weight:650}
p{margin:.7em 0}
code{font-family:var(--mono);font-size:.87em;background:var(--panel-2);border:1px solid var(--rule);padding:.1em .38em;border-radius:4px;color:#cfe8d3}
pre{margin:0;font-family:var(--mono);font-size:12.5px;line-height:1.6;overflow-x:auto;color:#cfe8d3}

header{border-bottom:1px solid var(--rule);position:sticky;top:0;background:rgba(8,11,9,.9);backdrop-filter:blur(9px);z-index:9}
.nav{display:flex;align-items:center;gap:13px;height:58px}
.brand{display:flex;align-items:center;gap:9px;font-weight:660;letter-spacing:-.02em;color:var(--ink);text-decoration:none}
.nav .sp{flex:1}
.nav a.l{font-size:.88rem;color:var(--ink-2);text-decoration:none;font-weight:520}
.nav a.l:hover{color:var(--ink)}
@media(max-width:640px){.nav a.l.opt{display:none}}

.hero{padding:66px 0 40px}
.pulse{display:inline-flex;align-items:center;gap:9px;font-family:var(--mono);font-size:.76rem;letter-spacing:.1em;text-transform:uppercase;color:var(--alive);border:1px solid #1f3a24;background:#0d1a10;padding:5px 11px;border-radius:999px;margin-bottom:22px}
.dot{width:7px;height:7px;border-radius:50%;background:var(--alive);box-shadow:0 0 0 0 rgba(126,231,135,.6);animation:p 2.4s infinite}
@keyframes p{0%{box-shadow:0 0 0 0 rgba(126,231,135,.5)}70%{box-shadow:0 0 0 9px rgba(126,231,135,0)}100%{box-shadow:0 0 0 0 rgba(126,231,135,0)}}
.lede{font-size:clamp(1.05rem,2.3vw,1.2rem);color:var(--ink-2);max-width:42em;margin-top:20px}

.receipt{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--rule);border:1px solid var(--rule);border-radius:12px;overflow:hidden;margin-top:34px}
@media(max-width:700px){.receipt{grid-template-columns:repeat(2,1fr)}}
.cell{background:var(--panel);padding:18px 18px 16px}
.cell .k{font-family:var(--mono);font-size:.68rem;letter-spacing:.13em;text-transform:uppercase;color:var(--ink-3)}
.cell .v{font-family:var(--mono);font-size:1.72rem;font-weight:600;letter-spacing:-.02em;margin-top:7px;color:var(--ink)}
.cell .u{font-size:.72rem;color:var(--ink-3);font-family:var(--mono);margin-top:3px}
.cell.alive .v{color:var(--alive)}

section{padding:52px 0;border-top:1px solid var(--rule)}
.chartbox{background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:18px 16px 8px;margin-top:22px}
.chartbox .cap{font-size:.8rem;color:var(--ink-3);padding:2px 4px 10px;font-family:var(--mono)}

.two{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:24px}
@media(max-width:760px){.two{grid-template-columns:1fr}}
.box{background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:20px}
.box.yes{border-left:3px solid var(--alive-dim)}
.box.no{border-left:3px solid var(--warn)}
.box h3{margin-bottom:8px}
.box ul{margin:.4em 0 0;padding-left:19px;font-size:.92rem;color:var(--ink-2)}
.box li{margin:.45em 0}
.box strong{color:var(--ink)}

ol.steps{list-style:none;counter-reset:s;padding:0;margin:24px 0 0}
ol.steps li{counter-increment:s;position:relative;padding:0 0 20px 44px;border-left:2px solid var(--rule);margin-left:13px}
ol.steps li:last-child{border-left-color:transparent;padding-bottom:0}
ol.steps li::before{content:counter(s);position:absolute;left:-14px;top:-2px;width:26px;height:26px;border-radius:50%;background:var(--panel-2);border:1px solid var(--rule);color:var(--alive);font-family:var(--mono);font-size:.78rem;display:grid;place-items:center}
ol.steps p{font-size:.93rem;color:var(--ink-2);margin:.25em 0}
.term{background:#050806;border:1px solid var(--rule);border-radius:10px;padding:14px 16px;margin-top:10px}
.term pre{color:#a7c8b0}
.term .g{color:var(--alive)}
.term .w{color:var(--warn)}

details{border-bottom:1px solid var(--rule);padding:15px 0}
details:first-of-type{border-top:1px solid var(--rule);margin-top:24px}
summary{cursor:pointer;font-weight:600;font-size:.96rem;list-style:none;display:flex;justify-content:space-between;gap:16px}
summary::-webkit-details-marker{display:none}
summary::after{content:"+";font-family:var(--mono);color:var(--ink-3)}
details[open] summary::after{content:"\\2013"}
details p{font-size:.93rem;color:var(--ink-2);max-width:54em}

footer{padding:38px 0 62px;border-top:1px solid var(--rule);font-size:.86rem;color:var(--ink-3)}
footer .row{display:flex;flex-wrap:wrap;gap:8px 20px;align-items:center}
footer a{color:var(--ink-2)}
.badge{font-family:var(--mono);font-size:.72rem;letter-spacing:.09em;text-transform:uppercase;color:var(--warn);border:1px solid #3a2f16;background:#1a1409;padding:4px 9px;border-radius:6px}
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sprout — a program that levels itself up, and stops when it stops</title>
<meta name="description" content="Born at level 1 knowing nothing. Mutates at random, sits the same exam every generation, keeps a change only when it measurably plays better. You can only watch.">
<meta name="theme-color" content="#080b09">
<meta property="og:title" content="Sprout — a program that levels itself up">
<meta property="og:description" content="Born at level 1 knowing nothing. It improves itself against an exam it cannot cheat, and the ceiling is published, not hidden.">
<meta property="og:type" content="website">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%23080b09'/%3E%3Cpath d='M16 26V14M16 14c0-5 3-8 8-8 0 5-3 8-8 8zM16 18c0-5-3-8-8-8 0 5 3 8 8 8z' fill='none' stroke='%237ee787' stroke-width='2' stroke-linecap='round'/%3E%3C/svg%3E">
<style>__CSS__</style>
</head>
<body>

<header>
  <div class="wrap nav">
    <a class="brand" href="#top">
      <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="8" fill="#0f1411"/><path d="M16 26V14M16 14c0-5 3-8 8-8 0 5-3 8-8 8zM16 18c0-5-3-8-8-8 0 5 3 8 8 8z" fill="none" stroke="#7ee787" stroke-width="2" stroke-linecap="round"/></svg>
      Sprout
    </a>
    <span class="sp"></span>
    <a class="l opt" href="#chart">Growth</a>
    <a class="l opt" href="#how">How</a>
    <a class="l opt" href="#limits">Ceiling</a>
    <a class="l" href="https://github.com/chirag120670598-dotcom/sprout">GitHub</a>
  </div>
</header>

<main id="top">

<div class="wrap hero">
  <span class="pulse"><span class="dot"></span> alive · generation __GENERATIONS__</span>
  <h1>It was born at level 1 knowing nothing.<br>It is levelling itself up.<br>You can only watch.</h1>
  <p class="lede">
    Sprout is one program, one exam, and no hand-written strategy. Every six hours
    it makes __POPULATION__ mutated copies of itself, puts all of them through the
    same fixed test, and keeps a copy only if it measurably plays better. Nobody
    edits it. Nobody tells it what a good move is. The numbers below are read
    straight out of the file it writes.
  </p>

  <div class="receipt" id="receipt"
       data-level="__LEVEL__" data-exam="__EXAM__" data-style="__STYLE__"
       data-generations="__GENERATIONS__" data-accepted="__ACCEPTED__"
       data-rejected="__REJECTED__" data-peak="__PEAK__" data-stall="__STALL__">
    <div class="cell alive"><div class="k">Level</div><div class="v">__LEVEL__</div><div class="u">+__ACCEPTED__ since birth</div></div>
    <div class="cell alive"><div class="k">Exam score</div><div class="v">__EXAM__</div><div class="u">born at __BORN__</div></div>
    <div class="cell"><div class="k">Aliveness</div><div class="v">__STYLE__</div><div class="u">0–100, pressure index</div></div>
    <div class="cell"><div class="k">Generations</div><div class="v">__GENERATIONS__</div><div class="u">__REJECTED__ rejected</div></div>
  </div>
</div>

<section>
  <div class="wrap">
    <h2>It writes its own code now</h2>
    <p style="color:var(--ink-2);max-width:46em">
      Until recently the thing being evolved was five numbers. A <em>person</em> had chosen that shape —
      three-in-a-row is worth this much, the centre is worth that much — and the organism could only turn
      the dials inside somebody else's design. That is tuning, not writing.
    </p>
    <p style="color:var(--ink-2);max-width:46em">
      Now the genome is an expression tree. Its evaluation function is a parenthesised program built from
      eight measurements of a position and five arithmetic operators, and mutation edits <strong>the
      program</strong> — replacing whole subtrees, swapping operators, moving numbers around. When it
      levels up, the code it runs is genuinely different code, and it wrote it.
    </p>
    <div class="term"><pre>__PROGRAM__</pre></div>
    <p class="cap" style="font-size:.8rem;color:var(--ink-3);font-family:var(--mono);margin-top:10px">the brain it is running right now, printed from board/state.json</p>
    <p style="color:var(--ink-2);max-width:46em">
      <strong>What it cannot do is write Python.</strong> The tree is data, interpreted by
      <code>sprout/brain.py</code> against a fixed vocabulary. There is no <code>eval</code>, no
      <code>exec</code>, no import, and no way to express anything that is not arithmetic over those
      eight numbers — a test feeds it <code>__import__('os').system('ls')</code> and expects a refusal.
      That limit is not a compromise. It is the reason this can run unattended in CI every six hours
      without anybody reading a diff first.
    </p>
  </div>
</section>

<section>
  <div class="wrap">
    <h2>It remembers its mistakes</h2>
    <p style="color:var(--ink-2);max-width:46em">
      A program with no memory makes the same blunder every month and has no way of noticing.
      <code>board/memory.json</code> is a book of positions where it has lost before, and the move it made
      in them. Next time it sees that position, the remembered move is priced far below anything the
      evaluation could produce — so it will not play it again unless every other move loses too.
    </p>
    <div class="receipt" style="margin-top:24px">
      <div class="cell"><div class="k">Positions booked</div><div class="v">__MEMPOS__</div><div class="u">exact positions only</div></div>
      <div class="cell"><div class="k">Games watched</div><div class="v">__MEMGAMES__</div><div class="u">against itself</div></div>
      <div class="cell"><div class="k">Moves booked</div><div class="v">__MEMLEARNED__</div><div class="u">blame placed on the move</div></div>
      <div class="cell"><div class="k">In the exam</div><div class="v">no</div><div class="u">on purpose</div></div>
    </div>
    <p style="color:var(--ink-2);max-width:46em;margin-top:22px">
      <strong>The memory is deliberately kept out of the exam.</strong> A book that grows between generations
      would mean the exam changed while the candidates did not — and a score you cannot compare across
      months is not a score. Memory helps it play. The exam alone decides whether it levelled up.
    </p>
    <div class="two">
      <div class="box no">
        <h3>What it actually is</h3>
        <ul>
          <li>A <strong>lookup table, not understanding</strong>. Hand it a position it has never seen and
              it is exactly as naive as it was on day one.</li>
          <li>It learns only from <strong>its own losses</strong>, and cannot say <em>why</em> a move was bad,
              only that this one was.</li>
          <li>Exact positions only. One move different is a different key — which is why the book is small
              and why it helps less than it sounds like it should.</li>
        </ul>
      </div>
      <div class="box yes">
        <h3>What it genuinely does</h3>
        <ul>
          <li>Survives restarts. The book is on disk before the next job picks it up, so memory outlives
              the process that formed it.</li>
          <li>Changes behaviour. A booked move is skipped when there is anything else to play.</li>
          <li>Is inspectable. Every remembered position is in a JSON file you can read.</li>
        </ul>
      </div>
    </div>
  </div>
</section>

<section id="chart">
  <div class="wrap">
    <h2>What the growth actually looks like</h2>
    <p style="color:var(--ink-2);max-width:44em">
      The line only moves when a mutation survives the exam. Flat stretches are
      generations that were tried, measured, and thrown away — and they are
      printed here because a growth curve that hides its flat parts is a poster.
    </p>
    <div class="chartbox">
      __CHART__
      <div class="cap">x: generation · y: exam score against the three opponents that plan · flat tail = nothing better was found</div>
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2>The exam it cannot cheat</h2>
    <p style="color:var(--ink-2);max-width:44em">Sprout plays Connect Four, because the rules fit on a page, a wrong move costs nothing, and any game can be replayed by anyone — so every result is checkable. Every generation sits the same exam: the same six opponents, the same seeds, the same number of games. Only three of them count toward the score.</p>
    <div class="two">
      <div class="box yes">
        <h3>Counts toward the score</h3>
        <ul>
          <li><strong>hand-2</strong> — a hand-written player looking two moves ahead</li>
          <li><strong>hand-3</strong> — the same, one move deeper</li>
          <li><strong>hand-4</strong> — deeper still, and deliberately one ply beyond what Sprout is allowed to grow to. <strong>A perfect score is not reachable by design.</strong></li>
        </ul>
      </div>
      <div class="box no">
        <h3>Sanity checks, not scored</h3>
        <ul>
          <li><strong>random</strong>, <strong>first</strong>, <strong>centre</strong> — three opponents that do not plan at all</li>
          <li>Beating a coin flip is not evidence of thinking, so those games never enter the score</li>
          <li>They still run every generation: losing to one would mean a bug, not a bad training run</li>
        </ul>
      </div>
    </div>
    <p style="color:var(--ink-2);max-width:44em;margin-top:24px">The exam is fixed forever on purpose. An exam that gets easier, or that changes between candidates, measures nothing — and a score you can compare across six months is worth more than a score that keeps going up because the test got softer.</p>
  </div>
</section>

<section id="how">
  <div class="wrap">
    <h2>How a level-up happens</h2>
    <ol class="steps">
      <li>
        <h3>Copy itself, badly</h3>
        <p>Each child is the parent with its weights nudged by random amounts. Even the settings that govern mutation — how wild the changes are, how many children to try, how big a win is needed to take over — are part of what gets mutated. It evolves how it evolves.</p>
      </li>
      <li>
        <h3>Sit the same exam</h3>
        <p>Every child plays the identical fixed schedule against the identical opponents, alternating who moves first so the first-move gift cannot be mistaken for skill.</p>
      </li>
      <li>
        <h3>Survive a longer exam before being believed</h3>
        <p>The best child of the generation then has to sit a second exam three times longer than the one used to shortlist it. Only that longer score can become the record. Picking the winner of twenty-four noisy measurements and calling it the truth is how a curve gets flattering without getting better — see the box below.</p>
      </li>
      <li>
        <h3>Beat the record by a margin, or be thrown away</h3>
        <p>Even on the long exam, it has to beat the current champion by a margin. A tie is not a win. Most generations are thrown away, and the count of throw-aways is published above.</p>
      </li>
      <li>
        <h3>When stuck, search wider</h3>
        <p>After a long flat stretch, the mutation width is temporarily multiplied. Being stuck is a property of the method, so the method is what moves.</p>
      </li>
    </ol>

    <div class="term"><pre>__LOG__</pre></div>
    <p class="cap" style="font-size:.8rem;color:var(--ink-3);font-family:var(--mono);margin-top:10px">last few generations, straight from the ledger</p>

    __REJECTION__
  </div>
</section>

<section>
  <div class="wrap">
    <h2>The mistake this repository made once, in public</h2>
    <p style="color:var(--ink-2);max-width:46em">
      The first version shortlisted every child on a 24-game exam and wrote the winner straight into the record. It worked, and then it didn't: one mutation scored <strong>0.958</strong> and took over, and every generation for the next eight scored between 0.458 and 0.729 against it. Nothing was wrong with the newcomers. The <em>record</em> was wrong — it was the luckiest of twenty-four noisy samples, and a maximum of noise always looks like a signal.
    </p>
    <p style="color:var(--ink-2);max-width:46em">
      The fix is a confirmation exam three times longer, sat by the best child only. A score can now only enter the record after 144 games instead of 24. It costs a couple of seconds a generation, and it is the difference between a number and a claim.
    </p>
    <div class="box no" style="margin-top:20px">
      <h3>Why this is printed here</h3>
      <p style="font-size:.94rem;color:var(--ink-2);margin:.4em 0 0">A project about honest measurement that hid its own measurement bug would be a joke at its own expense. The version that is live now is the one with the gate. The version without it produced a nicer-looking curve and meant less.</p>
    </div>
  </div>
</section>

<section id="limits">
  <div class="wrap">
    <h2>What this is not</h2>
    <p style="color:var(--ink-2);max-width:44em">Read this before believing anything above.</p>
    <div class="two">
      <div class="box no">
        <h3>It is not a general intelligence</h3>
        <ul>
          <li><strong>It has no brain in the modern sense.</strong> There is no neural network here. It is a small arithmetic expression over 69 four-in-a-row windows, read by alpha-beta search. It writes that expression itself now — but the vocabulary it writes in was chosen by a person, and eight numbers is not a mind.</li>
          <li><strong>It cannot improve at anything except this game.</strong> The thing that improves is a list of five numbers. Point it at a different problem and it is 30 lines from useless.</li>
          <li><strong>It has no internet access and cannot get any.</strong> There is no network code in the package, and a test fails the build if one appears. It cannot download a better version of itself, or read up on strategy.</li>
          <li><strong>Improvement is not infinite.</strong> It stops when it reaches its ceiling. See below.</li>
        </ul>
      </div>
      <div class="box no">
        <h3>It is not the Ultron fantasy</h3>
        <ul>
          <li>It cannot rewrite its own source code.</li>
          <li>It cannot change its own exam.</li>
          <li>It cannot decide that it wants something.</li>
          <li><strong>What it actually does</strong> is a genuine, honest version of the idea: a thing that measures itself, changes itself, and only keeps changes that survive measurement. That is real, and it is this.</li>
        </ul>
      </div>
    </div>

    <h3 style="margin-top:34px">The ceiling, and where it is</h3>
    <p style="color:var(--ink-2);max-width:46em">
      Sprout can look at most __MAXDEPTH__ moves ahead. One opponent in the exam looks four ahead. That opponent is worth beating and hard to beat, which is the point: a perfect score is not reachable, so the organism can never <em>finish</em> the exam and call it done.
      When the line goes flat and stays flat, that is the ceiling arriving. <strong>Current peak: __PEAK__, reached at level __PEAKLEVEL__.</strong>
      <span style="color:var(--ink-3)">Flat for __STALL__ generation(s) right now.</span>
    </p>
  </div>
</section>

<section id="world">
  <div class="wrap">
    <h2>It is allowed to meet the world. It is not allowed to fetch it.</h2>
    <p style="color:var(--ink-2);max-width:46em">
      A program cannot absorb GitHub. Reading a repository does not make anything cleverer. But being
      measured against something stronger is the one mechanism on this page that has ever produced a
      real improvement — so the organism has a <strong>ladder</strong>: engines that live outside this
      repository, each pinned to an exact revision, that it plays on command.
    </p>
    <p style="color:var(--ink-2);max-width:46em">
      The split is deliberate and it is the whole safety story.
      <strong>A person scouts.</strong> <code>tools/scout.py</code> searches GitHub and writes candidates
      to <code>board/scout.json</code> — right now __SCOUTCOUNT__ real engine repositories. Nothing runs.
      <strong>A person adds one.</strong> It goes into <code>board/ladder.json</code> by hand, pinned.
      <strong>Then the organism plays it</strong>, over a pipe, one process per game, with a timeout.
    </p>
    <div class="two">
      <div class="box yes">
        <h3>What it can do</h3>
        <ul>
          <li>Start an engine that a human put on the ladder</li>
          <li>Lose to it, and have that recorded</li>
          <li>Read the position, answer with a column, nothing else</li>
        </ul>
      </div>
      <div class="box no">
        <h3>What it can never do</h3>
        <ul>
          <li><strong>Search GitHub itself.</strong> No network code in the package — a test fails the build if any appears</li>
          <li><strong>Choose what to download.</strong> The ladder is a file a person edits and pins</li>
          <li><strong>Promote itself.</strong> World scores never change a level. Otherwise the ladder would decide the record, and the record would depend on who happened to be on it that month</li>
        </ul>
      </div>
    </div>
    <div class="term"><pre>__WORLD__</pre></div>
    <p class="cap" style="font-size:.8rem;color:var(--ink-3);font-family:var(--mono);margin-top:10px">against the world — a separate score from the exam, and it can go down</p>
    <p style="color:var(--ink-2);max-width:46em">
      __WORLDNOTE__
    </p>
  </div>
</section>

<section>
  <div class="wrap">
    <h2>Why the repo is read-only</h2>
    <p style="color:var(--ink-2);max-width:46em">
      You cannot push to a repository you do not own — GitHub does that for me, for free. On top of that, a test in CI refuses any commit that touches the engine: the whole promise is that no human edited it to make the curve look better, and a rule that can be enforced is worth more than a claim.
    </p>
    <p style="color:var(--ink-2);max-width:46em">
      You can still <a href="https://github.com/chirag120670598-dotcom/sprout/fork">fork it</a>, and your fork is <em>yours</em> — you can edit it, break it, make your own organism and let it run. What you cannot do is quietly make <em>this</em> one better and pretend it happened on its own.
    </p>
    <div class="two">
      <div class="box yes">
        <h3>Frozen</h3>
        <ul>
          <li><code>sprout/*.py</code> — the engine, the exam, the rules</li>
          <li><code>sprout/organism.py</code> — the ceiling, the opponents</li>
        </ul>
      </div>
      <div class="box yes">
        <h3>Written by the organism</h3>
        <ul>
          <li><code>board/state.json</code> — where it has got to</li>
          <li><code>board/ledger.jsonl</code> — every generation, accepted or not</li>
          <li><code>board/live.board</code> — a game it just played</li>
        </ul>
      </div>
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2>Questions worth asking</h2>
    <details>
      <summary>Who is telling it that it improved?</summary>
      <p>Nobody. It measures itself against a fixed set of opponents and a fixed set of seeds, and the comparison is a real game result, not a self-report. The failure mode people worry about — a model grading its own homework — is exactly what a fixed exam avoids. The weakness is the other one: it can only get good at what the exam asks, so the exam has to be worth passing.</p>
    </details>
    <details>
      <summary>Is "level" just a counter?</summary>
      <p>Yes, and that is deliberate. A level increments only when a mutation wins its examination by a margin, so level = number of survived improvements + 1. It is a count of accepted changes, not a claim about intelligence, and it stops counting the moment nothing better is found.</p>
    </details>
    <details>
      <summary>Will it run forever?</summary>
      <p>The schedule does. The improvement does not. A GitHub job has a maximum life, so "forever" here means one long run every six hours that picks up exactly where the last one stopped, using a checkpoint file. It has been running since __BORN__.</p>
    </details>
    <details>
      <summary>Could it ever become dangerous?</summary>
      <p>No. It plays Connect Four, has no network code at all, and cannot write code. It can start an engine that a person already put on the ladder — that is how it meets opponents from outside this repository — but it cannot fetch one, and a test fails the build if any network import appears in the package. The distinction is the whole safety story: a process it can start but cannot choose is a sparring partner. A network it can reach is a supply chain. The interesting part is not the danger; it is how far a thing gets with measurement, mutation and patience.</p>
    </details>
    <details>
      <summary>What is the aliveness number?</summary>
      <p>Not strength. It asks whether the thing creates problems for a serious opponent: how often a move leaves a threat that has to be answered, and how often a move creates two at once. Measured only against the two strongest fixed opponents — against a coin flip every player looks quiet. A player can lose while pressing constantly and still score as alive.</p>
    </details>
  </div>
</section>

</main>

<footer>
  <div class="wrap">
    <div class="row">
      <strong style="color:var(--ink-2)">Sprout</strong>
      <span class="badge">read-only</span>
      <a href="https://github.com/chirag120670598-dotcom/sprout">GitHub</a>
      <a href="https://github.com/chirag120670598-dotcom/sprout/blob/main/README.md">README</a>
      <a href="https://github.com/chirag120670598-dotcom/sprout/blob/main/LICENSE">Apache-2.0</a>
    </div>
    <p style="margin-top:16px;max-width:50em">Born __BORN__, updated __UPDATED__. Every number on this page is copied out of <code>board/state.json</code> by <code>tools/build_site.py</code>, and the build fails if the page and the state disagree.</p>
  </div>
</footer>

</body>
</html>
"""


def chart(history: list[dict], generators: int) -> str:
    """A step curve of the exam record against generation number."""
    width, height = 720, 250
    left, right, top, bottom = 46, 16, 16, 30
    plot_w = width - left - right
    plot_h = height - top - bottom

    max_gen = max([generators, 1])
    points = [(0, history[0]["exam"])] if history else [(0, 0.0)]
    for entry in history[1:]:
        points.append((entry["generation"], entry["exam"]))
    points.append((max_gen, points[-1][1]))

    def x(gen: float) -> float:
        return left + (gen / max_gen) * plot_w

    def y(score: float) -> float:
        return top + (1.0 - score) * plot_h

    path = [f"M {x(points[0][0]):.1f} {y(points[0][1]):.1f}"]
    for gen, score in points[1:]:
        path.append(f"L {x(gen):.1f} {y(points[-2][1] if False else score):.1f}")
    # draw as steps: horizontal to the new generation, then vertical to the score
    step = [f"M {x(points[0][0]):.1f} {y(points[0][1]):.1f}"]
    prev_score = points[0][1]
    for gen, score in points[1:]:
        step.append(f"L {x(gen):.1f} {y(prev_score):.1f}")
        step.append(f"L {x(gen):.1f} {y(score):.1f}")
        prev_score = score
    line = " ".join(step)

    grid = []
    for level in (0.0, 0.25, 0.5, 0.75, 1.0):
        yy = y(level)
        grid.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{width - right}" y2="{yy:.1f}" stroke="#1e2a22" stroke-width="1"/>')
        grid.append(f'<text x="{left - 8}" y="{yy + 4:.1f}" fill="#6d8377" font-size="10" '
                    f'font-family="ui-monospace,monospace" text-anchor="end">{level:.2f}</text>')

    dots = "".join(
        f'<circle cx="{x(gen):.1f}" cy="{y(score):.1f}" r="3.4" fill="#7ee787"/>'
        for gen, score in points[:-1]
    )
    area = (f'<path d="{line} L {x(max_gen):.1f} {y(0.0):.1f} L {x(0):.1f} {y(0.0):.1f} Z" '
            f'fill="#7ee787" opacity="0.07"/>')

    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" '
        f'aria-label="Exam score by generation, currently {points[-1][1]:.3f}">'
        + "".join(grid)
        + area
        + f'<path d="{line}" fill="none" stroke="#7ee787" stroke-width="2" stroke-linejoin="round"/>'
        + dots
        + f'<text x="{width - right}" y="{height - 8}" fill="#6d8377" font-size="10" '
          f'font-family="ui-monospace,monospace" text-anchor="end">generation {max_gen}</text>'
        + f'<text x="{left}" y="{height - 8}" fill="#6d8377" font-size="10" '
          f'font-family="ui-monospace,monospace">0</text>'
        + "</svg>"
    )


def log_tail(ledger: Path, lines: int = 8) -> str:
    if not ledger.exists():
        return "(the ledger is empty)"
    entries = ledger.read_text(encoding="utf-8").strip().splitlines()[-lines * 3:]
    out = []
    for raw in entries:
        try:
            e = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if "accepted" not in e:
            continue                    # a memory line, not a generation
        verdict = '<span class="g">ACCEPTED -> level %d</span>' % e["level"] if e["accepted"] \
            else '<span class="w">rejected</span>'
        out.append(f'gen {e["generation"]:05d}  child {e["child"]:.3f}  '
                   f'record {e["record"]:.3f}  {verdict}')
    return "\n".join(out[-lines:])


def rejection_story(entries: list[dict]) -> str:
    """The most interesting thing in the ledger is usually a rejection.

    A mutation that scored higher than the record and was still thrown away is
    proof that the margin is real and not decoration -- and it is the kind of
    honest detail a hand-written dashboard would quietly leave out.
    """
    rounds = [e for e in entries if "accepted" in e]
    misses = [e for e in rounds if not e["accepted"] and e["delta"] > 0]
    if not misses:
        return ""
    best = max(misses, key=lambda e: e["delta"])
    return (
        '<div class="box no" style="margin-top:22px">'
        "<h3>The mutation that was better, and was still thrown away</h3>"
        f'<p style="font-size:.94rem;color:var(--ink-2);margin:.5em 0 0">At generation '
        f'{best["generation"]}, a child scored <strong>{best["child"]:.3f}</strong> against a '
        f'record of <strong>{best["record"]:.3f}</strong> — better by {best["delta"]:.3f} — and the '
        "exam threw it away anyway. The margin exists because a "
        f'{best["delta"]:.3f} difference on a few dozen games is noise, and a program that '
        "chases noise climbs a curve that means nothing. That decision costs it real gains now "
        "and buys back a number you can trust later.</p></div>"
    )


def build() -> Path:
    state_path = ROOT / "board" / "state.json"
    if not state_path.exists():
        raise SystemExit("board/state.json is missing. run: python3 -m sprout run")
    state = json.loads(state_path.read_text(encoding="utf-8"))

    history = state["history"]
    peak = state["peak"]
    exam = state["exam"]

    ledger = ROOT / "board" / "ledger.jsonl"
    entries = []
    if ledger.exists():
        for raw in ledger.read_text(encoding="utf-8").splitlines():
            try:
                entries.append(json.loads(raw))
            except json.JSONDecodeError:
                continue

    world = ROOT / "board" / "world.json"
    world_report = {"engines": []}
    if world.exists():
        try:
            world_report = json.loads(world.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    scout = ROOT / "board" / "scout.json"
    scout_count = 0
    if scout.exists():
        try:
            scout_count = len(json.loads(scout.read_text(encoding="utf-8"))["repositories"])
        except (json.JSONDecodeError, KeyError):
            pass

    world_lines, world_notes = [], []
    for entry in world_report.get("engines", []):
        world_lines.append(
            f"vs {entry['name']:<14} {entry['wins']:>2}W {entry['draws']:>2}D "
            f"{entry['losses']:>2}L   score {entry['score']:.3f}")
        if entry.get("crashes"):
            world_notes.append(f"{entry['name']} failed to answer "
                               f"{entry['crashes']} time(s) and was disqualified.")
    if not world_lines:
        world_lines = ["(the ladder has not been played yet)"]

    best = max(world_report.get("engines", []), key=lambda e: e["score"], default=None)
    if best and best["score"] >= 0.5:
        world_note = (f"Against <strong>{best['name']}</strong> it currently scores "
                      f"<strong>{best['score']:.3f}</strong>. That is a genuine result "
                      "against code it did not write, and it is the number worth watching over "
                      "the next few months — not the exam, which the organism has already been "
                      "shaped by.")
    elif best:
        world_note = (f"Against <strong>{best['name']}</strong> it currently scores "
                      f"<strong>{best['score']:.3f}</strong> — it loses. That is printed because a "
                      "ladder with only wins on it would not be a ladder.")

    html = TEMPLATE
    replacements = {
        "__PROGRAM__": state["genome"].get("program") or "(still running the old numeric brain)",
        "__MEMPOS__": str((state.get("memory") or {}).get("positions", 0)),
        "__MEMGAMES__": str((state.get("memory") or {}).get("games", 0)),
        "__MEMLEARNED__": str((state.get("memory") or {}).get("learned", 0)),
        "__WORLD__": "\n".join(world_lines),
        "__WORLDNOTE__": world_note,
        "__SCOUTCOUNT__": str(scout_count),
        "__CSS__": CSS,
        "__CHART__": chart(history, state["generations"]),
        "__LOG__": log_tail(ROOT / "board" / "ledger.jsonl"),
        "__LEVEL__": str(state["level"]),
        "__EXAM__": f'{state["record"]:.3f}',
        "__BORN__": f'{history[0]["exam"]:.3f}',
        "__STYLE__": f'{state["style"]:.1f}',
        "__GENERATIONS__": str(state["generations"]),
        "__ACCEPTED__": str(state["accepted"]),
        "__REJECTED__": str(state["rejected"]),
        "__POPULATION__": str(state["genome"]["population"]),
        "__PEAK__": f'{peak["exam"]:.3f}',
        "__PEAKLEVEL__": str(peak["at_level"]),
        "__STALL__": str(state["stall"]),
        "__MAXDEPTH__": "three",
        "__BORN_DATE__": state["born"][:10],
        "__UPDATED__": state["updated"].replace("T", " ").replace("Z", " UTC"),
        "__REJECTION__": rejection_story(entries),
    }
    for key, value in replacements.items():
        html = html.replace(key, value)

    SITE.mkdir(parents=True, exist_ok=True)
    out = SITE / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} · level {state['level']} · exam {state['record']:.3f}")
    return out


if __name__ == "__main__":
    build()
