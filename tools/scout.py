"""Find Connect Four engines on GitHub and write them to board/scout.json.

    python3 tools/scout.py

This is a *tool*, run by a person. The organism in sprout/ has no network code
and can never run this. That distinction matters: scouting finds candidates, a
human reads one, and only then does it go on the ladder in board/ladder.json —
pinned to the commit it was read at.

Nothing here executes anything it finds. Downloading a repository and running
its code is a supply-chain decision, and that is not a decision a program gets
to make on its own.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "board" / "scout.json"

QUERIES = [
    "connect4 engine",
    "connect-four ai",
    "connect4 minimax",
    "connect4 bitboard",
    "connect four alpha beta",
]

HEADERS = {"Accept": "application/vnd.github+json",
           "User-Agent": "sprout-scout"}


def search(query: str, per_page: int = 8) -> list[dict]:
    url = ("https://api.github.com/search/repositories?"
           + urllib.parse.urlencode({"q": query, "sort": "stars",
                                     "order": "desc", "per_page": per_page}))
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    found = []
    for item in payload.get("items", []):
        found.append({
            "name": item["full_name"],
            "stars": item["stargazers_count"],
            "language": item.get("language"),
            "url": item["html_url"],
            "default_branch": item.get("default_branch", "main"),
            "pushed": item.get("pushed_at", "")[:10],
            "query": query,
        })
    return found


def main() -> int:
    seen: dict[str, dict] = {}
    for query in QUERIES:
        try:
            for repo in search(query):
                known = seen.setdefault(repo["name"], repo)
                if repo["stars"] > known["stars"]:
                    seen[repo["name"]] = repo
        except Exception as exc:  # noqa: BLE001 - a rate limit is not a crash
            print(f"  {query}: {exc}")

    repos = sorted(seen.values(), key=lambda r: r["stars"], reverse=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "scouted": date.today().isoformat(),
        "note": "Candidates only. Nothing here is on the ladder until a person "
                "reads it and adds it to board/ladder.json pinned to a commit.",
        "repositories": repos,
    }, indent=2) + "\n", encoding="utf-8")

    print(f"{len(repos)} candidate engines written to {OUT.relative_to(ROOT)}\n")
    for repo in repos[:12]:
        print(f"  {'*' * min(5, repo['stars'] // 20):<5} {repo['stars']:>6}  "
              f"{repo['name']:<45} {repo['language'] or '?':<10} {repo['pushed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
