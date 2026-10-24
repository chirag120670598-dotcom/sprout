"""The brain the organism writes for itself.

Until now the thing being evolved was five numbers: "this much for three in a
row, this much for the centre". A person chose that shape. The organism could
only turn the dials inside somebody else's design.

This module moves the design itself into the genome. A brain is now an
expression tree built from eight measurements of a position, glued together by
five arithmetic operators, written as a parenthesised expression:

    (add (mul my3 4.1) (sub centre (mul op2 2.7)))

That is the organism's own evaluation function. Mutation can replace a whole
subtree, swap an operator, or turn a 4.1 into a 4.7, and nothing outside this
module needs telling. When it levels up, the code it runs is genuinely different
code -- it wrote it, and the text is published so you can read it.

What it cannot do is write Python. The tree is *data*, interpreted here against a
fixed vocabulary of leaves and operators. There is no `eval`, no import, and no
way to express anything that is not arithmetic over the eight features below.
That limit is not a compromise; it is why this can be run in CI every six hours
without anybody having to read the diff first.
"""

from __future__ import annotations

import random

# What a brain is allowed to look at. Eight numbers, measured from the board.
LEAVES = (
    "my1", "my2", "my3",      # windows holding 1, 2 or 3 of mine, untouched by them
    "op1", "op2", "op3",      # the same for the opponent
    "centre",                 # my pieces in the middle three columns
    "mob",                    # my legal replies minus theirs, scaled
)
LEAF_INDEX = {name: i for i, name in enumerate(LEAVES)}
OPS = ("add", "sub", "mul", "max", "min")
CONSTANTS = ("zero", "one")   # the only literals, so a brain cannot inflate itself

MAX_SIZE = 41                  # nodes; a cap keeps the thing readable and cheap


# A node is a tuple:  ("leaf", name) | ("num", value) | ("op", name, left, right)
Leaf = tuple
Node = tuple


def leaf(name: str) -> Node:
    """A feature, a named constant, or a literal number."""
    if name in LEAF_INDEX or name in CONSTANTS:
        return ("leaf", name)
    try:
        return ("num", float(name))
    except ValueError:
        raise ValueError(f"{name!r} is not something a brain may look at") from None


def number(value: float) -> Node:
    return ("num", round(float(value), 3))


def newborn() -> Node:
    """Born with nothing. It evaluates every position as exactly zero, so it
    cannot tell a won game from a lost one until search alone saves it."""
    return leaf("zero")


def random_node(rng: random.Random, depth: int) -> Node:
    if depth <= 0 or rng.random() < 0.35:
        roll = rng.random()
        if roll < 0.80:
            return leaf(rng.choice(LEAVES))
        if roll < 0.92:
            return leaf(rng.choice(CONSTANTS))
        return number(rng.uniform(-6.0, 6.0))
    op = rng.choice(OPS)
    return ("op", op, random_node(rng, depth - 1), random_node(rng, depth - 1))


def size(node: Node) -> int:
    if node[0] != "op":
        return 1
    return 1 + size(node[2]) + size(node[3])


def leaves_used(node: Node) -> set[str]:
    if node[0] == "leaf":
        return {node[1]}
    if node[0] == "num":
        return set()
    return leaves_used(node[2]) | leaves_used(node[3])


def text(node: Node) -> str:
    if node[0] == "leaf":
        return node[1]
    if node[0] == "num":
        return f"{node[1]:g}"
    return f"({node[1]} {text(node[2])} {text(node[3])})"


def from_text(source: str) -> Node:
    """Read a brain back from its published form. Used by the tests, and by
    anyone who wants to paste a line off the site and check it."""
    tokens = source.replace("(", " ( ").replace(")", " ) ").split()
    pos = 0

    def walk() -> Node:
        nonlocal pos
        token = tokens[pos]
        pos += 1
        if token == "(":
            op = tokens[pos]
            pos += 1
            if op not in OPS:
                raise ValueError(f"{op!r} is not an operator")
            left = walk()
            right = walk()
            if tokens[pos] != ")":
                raise ValueError("unbalanced expression")
            pos += 1
            return ("op", op, left, right)
        return leaf(token)

    node = walk()
    if pos != len(tokens):
        raise ValueError("trailing tokens")
    return node


def _subtree_paths(node: Node, path: tuple = ()) -> list[tuple]:
    paths = [path]
    if node[0] == "op":
        paths += _subtree_paths(node[2], path + (2,))
        paths += _subtree_paths(node[3], path + (3,))
    return paths


def _replace(node: Node, path: tuple, new: Node) -> Node:
    if not path:
        return new
    head, rest = path[0], path[1:]
    if head == 2:
        return ("op", node[1], _replace(node[2], rest, new), node[3])
    return ("op", node[1], node[2], _replace(node[3], rest, new))


def mutate(node: Node, rng: random.Random) -> Node:
    """One edit to its own code.

    Three kinds, chosen at random: replace a random subtree with a fresh one,
    swap an operator for another, or -- the cheap one -- nothing at all but a
    different branch. Most edits make it worse; the exam is what decides.
    """
    kind = rng.random()
    paths = _subtree_paths(node)

    if kind < 0.55 or len(paths) == 1:
        target = rng.choice(paths)
        replacement = random_node(rng, rng.choice((0, 1, 2)))
        candidate = _replace(node, target, replacement)
    elif kind < 0.8:
        ops = [p for p in paths if _at(node, p)[0] == "op"]
        if not ops:
            return node
        target = rng.choice(ops)
        sub = _at(node, target)
        candidate = _replace(node, target, ("op", rng.choice(OPS), sub[2], sub[3]))
    else:
        # Rewrite the root wholesale. A big jump, occasionally.
        candidate = random_node(rng, 2)

    if size(candidate) > MAX_SIZE:
        return node
    if not leaves_used(candidate):
        return node                 # a brain that looks at nothing is not a brain
    return candidate


def _at(node: Node, path: tuple) -> Node:
    for step in path:
        node = node[step]
    return node


def features(my: int, opp: int) -> list[float]:
    """Measure a position once. Both evaluation strategies read from here, so a
    brain and the old weights are being judged on exactly the same facts."""
    from .game import CENTER_MASK, ROWS, WINDOWS, popcount

    counts = [0, 0, 0, 0]
    theirs = [0, 0, 0, 0]
    for mask in WINDOWS:
        m = my & mask
        o = opp & mask
        if m and o:
            continue
        if m:
            counts[popcount(m)] += 1
        if o:
            theirs[popcount(o)] += 1
    mobility = 0
    for c in range(7):
        if ((my | opp) >> (c * 7 + ROWS - 1)) & 1 == 0:
            mobility += 1
    return [
        float(counts[1]), float(counts[2]), float(counts[3]),
        float(theirs[1]), float(theirs[2]), float(theirs[3]),
        float(popcount(my & CENTER_MASK)) - float(popcount(opp & CENTER_MASK)),
        float(mobility),
    ]


def run(node: Node, values: list[float]) -> float:
    """Interpret a brain. No eval, no exec, no imports -- arithmetic only."""
    if node[0] == "num":
        return node[1]
    if node[0] == "leaf":
        name = node[1]
        if name == "zero":
            return 0.0
        if name == "one":
            return 1.0
        return values[LEAF_INDEX[name]]
    a = run(node[2], values)
    b = run(node[3], values)
    op = node[1]
    if op == "add":
        return a + b
    if op == "sub":
        return a - b
    if op == "mul":
        return a * b
    if op == "max":
        return a if a > b else b
    return a if a < b else b


def to_json(node: Node) -> dict:
    return {"text": text(node), "size": size(node)}


def from_json(data: dict) -> Node:
    return from_text(data["text"])
