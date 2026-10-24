"""Fail the build if the published page and the organism's own record disagree.

A dashboard you can edit by hand is a poster. This checks the page against
board/state.json, refuses external resources (the page must survive being opened
offline), and confirms the engineer's half of the repository has not been touched.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site" / "index.html"
STATE = ROOT / "board" / "state.json"
HASHES = ROOT / "frozen.sha256"

fails: list[str] = []


class Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.attrs: list[tuple[str, str | None]] = []
        self.tags: list[str] = []
        self.text: list[str] = []
        self.open: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend(attrs)
        if tag not in ("meta", "link", "br", "img", "input", "hr", "circle", "line",
                       "path", "text", "rect", "svg", "source"):
            self.open.append(tag)

    def handle_endtag(self, tag):
        if tag in self.open:
            while self.open and self.open.pop() != tag:
                pass

    def handle_data(self, data):
        self.text.append(data)


def build_number(value: str) -> float:
    return float(value)


def main() -> int:
    if not SITE.exists():
        fails.append("site/index.html is missing -- run tools/build_site.py")
        return report()
    if not STATE.exists():
        fails.append("board/state.json is missing")
        return report()

    html = SITE.read_text(encoding="utf-8")
    state = json.loads(STATE.read_text(encoding="utf-8"))
    collector = Collector()
    collector.feed(html)
    text = re.sub(r"\s+", " ", " ".join(collector.text))

    # 1. no resources from anywhere else
    for name, value in collector.attrs:
        if name in ("src", "href") and value and value.startswith(("http://", "https://")):
            if not re.match(r"https://(github\.com|chirag120670598-dotcom\.github\.io)", value):
                fails.append(f"external resource would not load offline: {value}")

    # 2. the page's claimed numbers must equal the organism's numbers
    receipt = re.search(r'<div class="receipt" id="receipt"(.*?)>', html, re.S)
    if not receipt:
        fails.append("the receipt block is missing, so nothing is verifiable")
    else:
        attrs = dict(re.findall(r'data-(\w+)="([^"]*)"', receipt.group(1)))
        expected = {
            "level": str(state["level"]),
            "generations": str(state["generations"]),
            "accepted": str(state["accepted"]),
            "rejected": str(state["rejected"]),
            "peak": f'{state["peak"]["exam"]:.3f}',
            "exam": f'{state["record"]:.3f}',
            "style": f'{state["style"]:.1f}',
            "stall": str(state["stall"]),
        }
        for key, want in expected.items():
            got = attrs.get(key)
            if got != want:
                fails.append(f"page says {key}={got!r}, state.json says {want!r}")

    # 3. the visible text has to agree too, not just the data attributes
    visible = (f'>{state["level"]}<', f'{state["record"]:.3f}', f'{state["style"]:.1f}')
    for needle in visible:
        if needle not in html:
            fails.append(f"page body never shows {needle!r}")

    # 4. one dot per accepted level on the chart
    dots = len(re.findall(r"<circle ", html))
    if dots != len(state["history"]):
        fails.append(f"chart has {dots} dots but there are {len(state['history'])} accepted levels")

    # 5. structure
    for needle in ("<title>", 'name="description"', 'name="viewport"', "og:title"):
        if needle not in html:
            fails.append(f"missing {needle}")
    if collector.open:
        fails.append(f"unclosed tags: {set(collector.open)}")

    # 6. the honest copy must still be there
    for label, needle in {
        "no neural network": "no neural network",
        "network claim": "no network code",
        "finite improvement": "Improvement is not infinite",
        "read-only note": "read-only",
        "sanity check distinction": "Sanity checks, not scored",
    }.items():
        if needle.lower() not in html.lower():
            fails.append(f"honesty copy missing: {label}")

    # 7. the engine must be byte-identical to what was frozen
    if HASHES.exists():
        for line in HASHES.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, _, name = line.partition("  ")
            path = ROOT / name
            if not path.exists():
                fails.append(f"frozen file missing: {name}")
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != digest:
                fails.append(f"the engine was edited by hand: {name}")

    return report(text=text)


def report(text: str = "") -> int:
    print(f"checked {len(text)} characters of copy, {len(fails)} problem(s)")
    if fails:
        print("FAILED")
        for item in fails:
            print("  -", item)
        return 1
    print("OK -- the page agrees with the organism")
    return 0


if __name__ == "__main__":
    sys.exit(main())
