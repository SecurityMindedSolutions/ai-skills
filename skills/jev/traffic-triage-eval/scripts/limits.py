#!/usr/bin/env python3
"""Measure how big a profile Jev accepts and how its answers move as the
profile grows.

    python3 limits.py --events clean.jsonl [--ip A] --app app.md

Takes one IP (default: the one with the most distinct paths), renders its
profile at increasing sample sizes, then keeps growing it with synthetic
filler paths in the same style until Jev refuses the request. For every
step it prints our token estimate, Jev's real input_tokens, latency, and
the category / severity / key signals, so two things fall out:

  1. the hard limit: the first size that returns an HTTP error, and the
     ratio of real tokens to our chars/3 estimate (used to set the budget);
  2. the soft limit: where the verdict starts drifting from the small-
     profile verdict, which is the size to stay under in practice.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import questions as q
from classify import DEFAULT_APP, _get_client, band_for, signals_from, threat_score
from profile import DEFAULT_SAMPLES, build_profile, estimate_tokens, group_by_ip, render

STEPS = [0.5, 1, 2, 4, 8, 16]            # multipliers on DEFAULT_SAMPLES
FILLER_TOKENS = [8_000, 12_000, 16_000, 20_000, 24_000, 28_000, 30_000, 32_000, 34_000, 40_000]
GREEN, RED, YELLOW, BOLD, DIM, OFF = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[2m", "\033[0m"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--events", required=True)
    p.add_argument("--ip")
    p.add_argument("--app")
    p.add_argument("--model", default=q.MODEL)
    p.add_argument("--out", help="write the table as JSON here")
    args = p.parse_args()
    events = [json.loads(l) for l in Path(args.events).read_text().splitlines() if l.strip()]
    groups = group_by_ip(events)
    ip = args.ip or max(groups, key=lambda k: len({e["path"] for e in groups[k]}))
    app = args.app or DEFAULT_APP
    if Path(app).expanduser().is_file():
        app = Path(app).expanduser().read_text().strip()
    profile = build_profile(ip, groups[ip])
    print(f"{BOLD}IP {ip}: {profile['volume']['requests']} requests, {profile['paths']['distinct']} distinct paths{OFF}")
    client = _get_client(args.model)
    rows: list[dict] = []
    baseline = None

    def send(label: str, prof: dict) -> dict:
        state = {"app": app, "window": "the exported period", "profile": prof}
        est = estimate_tokens(state) + estimate_tokens(q.QUESTIONS)
        t0 = time.perf_counter()
        try:
            resp = client.evaluate(state, q.QUESTIONS)
        except RuntimeError as err:
            row = {"step": label, "estimated_tokens": est, "error": str(err)[:140]}
            print(f"{label:<26} est {est:>6}  {RED}{row['error']}{OFF}")
            return row
        ms = round((time.perf_counter() - t0) * 1000)
        s = signals_from(resp["answers"])
        row = {"step": label, "estimated_tokens": est, "input_tokens": resp["usage"]["input_tokens"],
               "ratio_real_to_est": round(resp["usage"]["input_tokens"] / est, 2), "latency_ms": ms,
               "category": s["traffic_class"], "category_confidence": s["traffic_class_confidence"],
               "score": threat_score(s), "band": band_for(threat_score(s)),
               "signals": {k: s[k] for k, spec in q.QUESTIONS.items() if spec["type"] == "noul"}}
        drift = ""
        if baseline:
            moved = [k for k, v in row["signals"].items() if abs(v - baseline["signals"][k]) >= 0.2]
            cat_changed = row["category"] != baseline["category"]
            drift = (RED if cat_changed else YELLOW if moved else GREEN) + \
                    (f"category changed to {row['category']}" if cat_changed else f"moved: {', '.join(moved) or 'none'}") + OFF
        print(f"{label:<26} est {est:>6}  real {row['input_tokens']:>6} (x{row['ratio_real_to_est']})  {ms:>5} ms  "
              f"{row['category']:<16} {row['score']!s:>5} {row['band']:<11} {drift}")
        return row

    for mult in STEPS:
        sizes = {k: max(2, int(v * mult)) for k, v in DEFAULT_SAMPLES.items()}
        prof, _ = render(profile, 10**9, sizes)
        row = send(f"samples x{mult}", prof)
        rows.append(row)
        if baseline is None and "error" not in row:
            baseline = row
    # keep growing with realistic filler until the API refuses
    full, _ = render(profile, 10**9, {k: v * 16 for k, v in DEFAULT_SAMPLES.items()})
    rng = random.Random(7)
    real_paths = [e["path"] for e in groups[ip]] or ["/"]
    for target in FILLER_TOKENS:
        padded = json.loads(json.dumps(full))
        extra = []
        while estimate_tokens({"app": app, "profile": padded}) < target:
            base = rng.choice(real_paths)
            extra.append({"path": f"{base.rstrip('/')}/{rng.randrange(10**6)}", "requests": 1, "status": "404"})
            padded["paths"]["top"] = full["paths"]["top"] + extra
        row = send(f"filler to ~{target}", padded)
        rows.append(row)
        if "error" in row:
            break
    if args.out:
        Path(args.out).write_text(json.dumps({"ip": ip, "rows": rows}, indent=2))
        print(f"wrote {args.out}")
    good = [r for r in rows if "input_tokens" in r]
    if good:
        ratios = [r["ratio_real_to_est"] for r in good]
        print(f"\n{BOLD}real/estimate ratio: min {min(ratios)} max {max(ratios)}; largest accepted: {max(r['input_tokens'] for r in good)} tokens{OFF}")


if __name__ == "__main__":
    main()
