"""CLI: `python -m feed build`."""
from __future__ import annotations

import sys

from .build import build

USAGE = "usage: python -m feed build"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    command = argv[0] if argv else "build"

    if command in {"build", "-h", "--help"}:
        if command == "build":
            build()
            return 0
        print(USAGE)
        return 0

    print(f"unknown command: {command}\n{USAGE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
