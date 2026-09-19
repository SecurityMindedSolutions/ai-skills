#!/usr/bin/env python3
"""Validate a staged event file against the canonical schema and write a
clean JSONL copy plus a coverage report.

    python3 validate.py --events events.jsonl --out clean.jsonl [--ip A --ip B] [--from ISO --to ISO]

Accepts JSONL (one object per line), a JSON array, or CSV with the schema's
column names. Rows that fail a required field are dropped and counted; the
first few reasons are printed so the retrieving agent can fix its mapping.
The coverage table says which optional fields are populated and therefore
which signals the analysis will and will not have.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from schema import FIELDS, OPTIONAL, RowError, normalize_row, parse_ts

GREEN, RED, YELLOW, BOLD, DIM, OFF = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[2m", "\033[0m"


def read_events(path: Path):
    """Yield raw dicts from JSONL, a JSON array, or CSV."""
    text_head = path.open("rb").read(2).decode("utf-8", "replace").lstrip()
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            yield from csv.DictReader(handle)
        return
    if text_head.startswith("["):
        data = json.loads(path.read_text(encoding="utf-8"))
        yield from data
        return
    with path.open(encoding="utf-8") as handle:
        for n, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                yield {"__bad_line__": n}


def validate(path: Path, ips: set[str] | None = None, start=None, end=None):
    """Return (clean rows, stats). Filtering by IP and window happens here so
    every later stage sees only the requested slice."""
    clean, reasons, kept_by_filter = [], Counter(), 0
    examples: list[str] = []
    total = 0
    for raw in read_events(path):
        total += 1
        if "__bad_line__" in raw:
            reasons["not JSON"] += 1
            continue
        try:
            row = normalize_row(raw)
        except RowError as err:
            reasons[str(err).split(":")[0]] += 1
            if len(examples) < 5:
                examples.append(f"{err}  <- {json.dumps(raw)[:160]}")
            continue
        if ips and row["ip"] not in ips:
            continue
        if start or end:
            ts = parse_ts(row["ts"])
            if (start and ts < start) or (end and ts > end):
                continue
        kept_by_filter += 1
        clean.append(row)
    coverage = {name: sum(1 for r in clean if name in r) for name in OPTIONAL}
    stats = {"total_rows": total, "dropped": sum(reasons.values()), "drop_reasons": dict(reasons),
             "kept": len(clean), "coverage": coverage, "examples": examples,
             "distinct_ips": len({r["ip"] for r in clean})}
    return clean, stats


def print_stats(stats: dict, color: bool = True) -> None:
    c = (lambda code, s: f"{code}{s}{OFF}") if color else (lambda code, s: s)
    kept, dropped = stats["kept"], stats["dropped"]
    tone = GREEN if dropped == 0 else (YELLOW if dropped < stats["total_rows"] * 0.05 else RED)
    print(c(BOLD, "Validation: ") + c(tone, f"{kept} rows kept, {dropped} dropped") +
          f" of {stats['total_rows']} read; {stats['distinct_ips']} distinct IPs after filters")
    for reason, n in sorted(stats["drop_reasons"].items(), key=lambda kv: -kv[1]):
        print(f"  {c(RED, reason)}: {n}")
    for ex in stats["examples"]:
        print(f"  {c(DIM, ex)}")
    print(c(BOLD, "Optional field coverage") + " (what the analysis can and cannot see):")
    for name in OPTIONAL:
        n = stats["coverage"][name]
        pct = (100 * n // kept) if kept else 0
        tone = GREEN if pct >= 90 else (YELLOW if pct > 0 else DIM)
        print(f"  {name:<11} {c(tone, f'{pct:3d}%')}  {FIELDS[name][2]}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--events", required=True)
    p.add_argument("--out", help="clean JSONL path (default: print stats only)")
    p.add_argument("--ip", action="append", help="keep only these IPs (repeatable)")
    p.add_argument("--from", dest="start", help="ISO 8601 window start (inclusive)")
    p.add_argument("--to", dest="end", help="ISO 8601 window end (inclusive)")
    args = p.parse_args()
    start = parse_ts(args.start) if args.start else None
    end = parse_ts(args.end) if args.end else None
    clean, stats = validate(Path(args.events), set(args.ip or []) or None, start, end)
    print_stats(stats)
    if args.out:
        with Path(args.out).open("w", encoding="utf-8") as handle:
            for row in clean:
                handle.write(json.dumps(row, separators=(",", ":")) + "\n")
        print(f"wrote {args.out}")
    if not clean:
        sys.exit(1)


if __name__ == "__main__":
    main()
