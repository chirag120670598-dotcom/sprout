"""Entry point.

Windows is common, and its default console encoding cannot hold every character
this program might print. Streams are switched to UTF-8 once, before any output.
"""

import sys


def _utf8_streams() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


_utf8_streams()

from .cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
