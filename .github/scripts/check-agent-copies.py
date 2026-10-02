#!/usr/bin/env python3
"""Fail if copies of a shipped worker agent differ between skills.

Each orchestrating skill carries its own copy of the worker agent definitions it uses
(`skills/<category>/<skill>/agents/<name>.md`) so that a single copied skill folder is
self-contained. The copies install to the same path, `~/.claude/agents/<name>.md`, so
they must be byte-identical: otherwise two skills would keep offering to replace each
other's version. Edit one copy, then copy it over the others.

Usage: python3 .github/scripts/check-agent-copies.py
"""
import sys
from collections import defaultdict
from pathlib import Path

GREEN, RED, RESET = "\033[92m\033[1m", "\033[91m\033[1m", "\033[0m"


def main() -> int:
    root = Path(__file__).resolve().parents[2] / "skills"
    copies = defaultdict(list)
    for path in sorted(root.glob("*/*/agents/*.md")):
        copies[path.name].append(path)

    drift = False
    for name, paths in sorted(copies.items()):
        contents = {p.read_bytes() for p in paths}
        if len(contents) > 1:
            drift = True
            print(f"{RED}{name} differs across skills:{RESET}")
            for p in paths:
                print(f"  {p.relative_to(root.parent)}")
    if drift:
        return 1
    print(f"{GREEN}Agent copies in sync: "
          + ", ".join(f"{n} x{len(p)}" for n, p in sorted(copies.items())) + RESET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
