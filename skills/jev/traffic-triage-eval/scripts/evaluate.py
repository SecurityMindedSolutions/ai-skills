#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["openpyxl>=3.1"]
# ///
"""Validate a canonical event file, profile every IP in code, ask Jev what
each one was doing, and write a spreadsheet sorted attention-first.

    python3 evaluate.py --events events.jsonl --app app.md [--ip A --ip B] [--from ISO --to ISO]

With --labels labels.csv (columns ip,label) the run also reports agreement
per category so the questions can be tuned. --dry-run profiles and prints
token estimates without calling Jev. Every IP whose verdict is malicious,
unclear or flagged for attention has its raw rows carved out to
out/investigate/<ip>.jsonl with an index, so investigation never re-queries
the log source (--carve changes the set). Works with a plain Python 3.10+
install (see bootstrap.py).
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from bootstrap import ensure_dependencies

ensure_dependencies(sys.argv)

import questions as q  # noqa: E402
from classify import DEFAULT_APP, classify_profile  # noqa: E402
from profile import build_profile, group_by_ip, render  # noqa: E402
from report import DISCLAIMER, write_all  # noqa: E402
from schema import parse_ts  # noqa: E402
from validate import print_stats, validate  # noqa: E402

DEFAULT_OUT_ROOT = Path(tempfile.gettempdir()) / "traffic-triage-eval"
GREEN, RED, YELLOW, BLUE, BOLD, DIM, OFF = "\033[92m", "\033[91m", "\033[93m", "\033[94m", "\033[1m", "\033[2m", "\033[0m"
CATEGORY_COLOR = {"malicious": RED, "background_scan": YELLOW, "ai_agent": BLUE,
                  "benign_bot": GREEN, "benign_user": GREEN, "unclear": DIM}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--events", required=True, help="JSONL / JSON array / CSV in the canonical schema")
    p.add_argument("--app", help="text or .md file describing the site (what it serves, what it does not run)")
    p.add_argument("--ip", action="append", help="analyze only these IPs (repeatable)")
    p.add_argument("--from", dest="start", help="ISO 8601 window start")
    p.add_argument("--to", dest="end", help="ISO 8601 window end")
    p.add_argument("--min-requests", type=int, default=1, help="skip IPs with fewer requests (default 1)")
    p.add_argument("--labels", help="CSV with ip,label for agreement scoring")
    p.add_argument("--out", help=f"output folder (default {DEFAULT_OUT_ROOT}/<timestamp>)")
    p.add_argument("--model", default=q.MODEL)
    p.add_argument("--max-tokens", type=int, default=q.MAX_PROFILE_TOKENS, help="profile token budget per IP")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--dry-run", action="store_true", help="profile only; no Jev calls")
    p.add_argument("--carve", default="malicious,unclear,attention",
                   help="comma list of categories (plus `attention`) whose raw rows are written to out/investigate/; `none` disables")
    p.add_argument("--verbose", action="store_true", help="print one line per IP as well as the tables")
    p.add_argument("--no-color", action="store_true")
    return p.parse_args()


def load_app(source: str | None) -> str:
    if not source:
        return DEFAULT_APP
    path = Path(source).expanduser()
    return path.read_text(encoding="utf-8").strip() if path.is_file() else source


def load_labels(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return {r["ip"].strip(): r["label"].strip() for r in csv.DictReader(handle) if r.get("ip")}


def window_text(events: list[dict]) -> str:
    ts = sorted(parse_ts(e["ts"]) for e in events)
    return f"{ts[0].isoformat(timespec='minutes')} to {ts[-1].isoformat(timespec='minutes')} UTC"


def flatten(verdict: dict, profile: dict, label: str) -> dict:
    v = profile["volume"]
    row = {
        "ip": profile["ip"], "label": label,
        "category": verdict.get("category", "error"),
        "jev_category": verdict.get("jev_category", ""),
        "category_confidence": verdict.get("category_confidence", ""),
        "severity": verdict.get("severity", ""),
        "severity_confidence": verdict.get("severity_confidence", ""),
        "attention": verdict.get("attention", False),
        "attention_text": "YES" if verdict.get("attention") else "",
        "requests": v["requests"],
        "span_text": f"{v['first_seen'][11:16]}-{v['last_seen'][11:16]} ({v['span_minutes']} min)",
        "peak_rpm": v["peak_requests_per_minute"],
        "not_found_rate": profile["responses"]["not_found_rate"] if profile["responses"]["not_found_rate"] is not None else "",
        "waf_deny": profile["waf"]["actions"].get("deny", 0),
        "waf_labels_text": ", ".join(f"{l['value'].split(':')[-1]} x{l['requests']}" for l in profile["waf"]["labels"][:5]),
        "signals_text": ", ".join(verdict.get("signals", [])),
        "code_signals_text": "; ".join(f"{k}: {x}" for k, x in profile["code_signals"].items()),
        "code_signal_names": ", ".join(profile["code_signals"]),
        "rule_reasons_text": "; ".join(verdict.get("rule_reasons", [])),
        "top_ua": profile["user_agents"]["top"][0]["ua"] if profile["user_agents"]["top"] else "",
        "asn": profile["asn"] or "",
        "hosts_text": ", ".join(h["value"] for h in profile["hosts"]["top"][:4]),
        "paths_text": "\n".join(f"{p['requests']}x {p['path']} [{p['status']}]" for p in profile["paths"]["top"][:8]),
        "input_tokens": verdict.get("input_tokens", ""),
        "estimated_tokens": verdict.get("estimated_tokens", ""),
        "latency_ms": verdict.get("latency_ms", ""),
        "error": verdict.get("error", ""),
    }
    row.update({k: x for k, x in verdict.get("detail", {}).items() if not isinstance(x, dict)})
    probs = verdict.get("detail", {}).get("traffic_class_probabilities", {})
    row["probabilities_text"] = ", ".join(f"{k} {x}" for k, x in sorted(probs.items(), key=lambda kv: -kv[1]))
    return row


def agreement(rows: list[dict]) -> dict | None:
    labelled = [r for r in rows if r.get("label")]
    if not labelled:
        return None
    hits = sum(r["label"] == r["category"] for r in labelled)
    per: dict[str, dict] = {}
    for cat in q.CATEGORIES:
        want = [r for r in labelled if r["label"] == cat]
        got = [r for r in labelled if r["category"] == cat]
        tp = sum(r["category"] == cat for r in want)
        per[cat] = {"labelled": len(want), "predicted": len(got), "correct": tp,
                    "recall": round(tp / len(want), 2) if want else None,
                    "precision": round(tp / len(got), 2) if got else None}
    # the security question: did anything labelled malicious escape attention?
    attacks = [r for r in labelled if r["label"] == "malicious"]
    missed = [r["ip"] for r in attacks if not r["attention"]]
    false_alarms = [r["ip"] for r in labelled if r["attention"] and r["label"] in ("benign_user", "benign_bot", "ai_agent")]
    return {"labelled": len(labelled), "exact_agreement": round(hits / len(labelled), 2), "per_category": per,
            "attacks_missing_attention": missed, "benign_flagged_for_attention": false_alarms}


def main() -> None:
    args = parse_args()
    c = (lambda code, s: s) if args.no_color else (lambda code, s: f"{code}{s}{OFF}")
    out_dir = Path(args.out).expanduser() if args.out else DEFAULT_OUT_ROOT / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)

    start = parse_ts(args.start) if args.start else None
    end = parse_ts(args.end) if args.end else None
    events, stats = validate(Path(args.events), set(args.ip or []) or None, start, end)
    print_stats(stats, color=not args.no_color)
    if not events:
        sys.exit("no events after validation and filters")
    app = load_app(args.app)
    labels = load_labels(args.labels)
    window = window_text(events)
    groups = {ip: ev for ip, ev in group_by_ip(events).items() if len(ev) >= args.min_requests}
    print(c(BOLD, f"\nProfiling {len(groups)} IPs over {window} ...\n"))
    profiles = {ip: build_profile(ip, ev) for ip, ev in groups.items()}

    if args.dry_run:
        _dry_run(profiles, args.max_tokens, c)
        (out_dir / "profiles.json").write_text(json.dumps(profiles, indent=1))
        print(f"\nprofiles written to {out_dir / 'profiles.json'}; no Jev calls made")
        return

    def run(ip: str) -> dict:
        try:
            return classify_profile(profiles[ip], app, window, args.model, args.max_tokens)
        except RuntimeError as err:
            return {"ip": ip, "error": str(err), "category": "error"}

    order = sorted(profiles, key=lambda ip: -profiles[ip]["volume"]["requests"])
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        verdicts = dict(zip(order, pool.map(run, order)))
    rows = [flatten(verdicts[ip], profiles[ip], labels.get(ip, "")) for ip in order]
    rows.sort(key=lambda r: (not r["attention"], -q.CATEGORY_ORDER.index(r["category"]) if r["category"] in q.CATEGORY_ORDER else 1,
                             -(r["severity"] or 0), -r["requests"]))
    if args.verbose:
        for r in rows:
            col = CATEGORY_COLOR.get(r["category"], RED)
            flag = c(RED, "!! ") if r["attention"] else "   "
            print(f"{flag}{c(col, r['category']):<28} sev {r['severity']!s:<5} {r['ip']:<40} {r['requests']:>6} req  "
                  f"{c(DIM, r['signals_text'][:70])}")
            if r.get("error"):
                print(f"      {c(RED, r['error'][:160])}")
    carved = carve_out(out_dir, rows, groups, args.carve)

    ok = [r for r in rows if not r.get("error")]
    tokens = [r["input_tokens"] for r in ok if r.get("input_tokens")]
    lat = [r["latency_ms"] for r in ok if r.get("latency_ms")]
    summary = {
        "events": len(events), "ips": len(rows), "window": window, "model": args.model,
        "categories": dict(Counter(r["category"] for r in rows)),
        "attention": sum(r["attention"] for r in rows),
        "jev_input_tokens_total": sum(tokens),
        "jev_input_tokens_per_ip_median": int(statistics.median(tokens)) if tokens else 0,
        "jev_input_tokens_per_ip_max": max(tokens) if tokens else 0,
        "usd_per_1000_ips": round(1000 * (statistics.mean(tokens) if tokens else 0) * q.USD_PER_MILLION_INPUT_TOKENS / 1e6, 4),
        "latency_ms_median": int(statistics.median(lat)) if lat else 0,
        "errors": sum(1 for r in rows if r.get("error")),
        "validation": {k: v for k, v in stats.items() if k != "examples"},
        "agreement": agreement(rows),
    }
    summary["carved_out"] = len(carved)
    paths = write_all(out_dir, rows, summary)
    print(summary_table(summary, window))
    print(carve_table(rows, carved))
    print(c(BOLD, "Run: ") + f"{summary['ips']} IPs, {summary['events']} requests; Jev {summary['jev_input_tokens_per_ip_median']} tokens/IP median "
          f"({summary['jev_input_tokens_per_ip_max']} max), ${summary['usd_per_1000_ips']}/1000 IPs, {summary['latency_ms_median']} ms median, "
          f"{summary['errors']} errors")
    if summary["agreement"]:
        a = summary["agreement"]
        tone = GREEN if not a["attacks_missing_attention"] else RED
        print(c(BOLD, "Agreement with labels: ") + f"{a['exact_agreement']} exact on {a['labelled']} IPs; "
              + c(tone, f"attacks missing attention: {a['attacks_missing_attention'] or 'none'}")
              + f"; benign flagged: {a['benign_flagged_for_attention'] or 'none'}")
        for cat, m in a["per_category"].items():
            if m["labelled"] or m["predicted"]:
                print(f"    {cat:<16} labelled {m['labelled']:>3}  predicted {m['predicted']:>3}  correct {m['correct']:>3}  "
                      f"recall {m['recall']}  precision {m['precision']}")
    print("\n" + " ".join(f"{k}={v}" for k, v in paths.items()))
    print(c(DIM, DISCLAIMER))


def carve_out(out_dir: Path, rows: list[dict], groups: dict[str, list[dict]], spec: str) -> list[dict]:
    """Write the raw canonical rows of every IP worth a second look to
    out/investigate/<ip>.jsonl, plus an index, so the investigation starts
    from the run directory instead of a fresh log query."""
    wanted = {s.strip() for s in spec.split(",") if s.strip()}
    if not wanted or "none" in wanted:
        return []
    picked = [r for r in rows if r["category"] in wanted or ("attention" in wanted and r["attention"])]
    if not picked:
        return []
    folder = out_dir / "investigate"
    folder.mkdir(parents=True, exist_ok=True)
    for r in picked:
        name = r["ip"].replace(":", "_")
        with (folder / f"{name}.jsonl").open("w", encoding="utf-8") as fh:
            for ev in sorted(groups[r["ip"]], key=lambda e: e["ts"]):
                fh.write(json.dumps(ev, separators=(",", ":")) + "\n")
        r["raw_file"] = f"investigate/{name}.jsonl"
    lines = ["# Carved out for investigation", "",
             "Raw canonical rows for every IP whose verdict was " + ", ".join(sorted(wanted)) +
             ", one JSONL per IP, time-sorted, every field the source supplied. Attention rows first.", "",
             "| IP | Category | Sev | Attention | Requests | Signals | Code signals | File |", "|---|---|---:|---|---:|---|---|---|"]
    for r in picked:
        lines.append(f"| {r['ip']} | {r['category']} | {r['severity']} | {'YES' if r['attention'] else ''} | {r['requests']} | "
                     f"{r['signals_text']} | {r['code_signal_names']} | `{r['raw_file']}` |")
    (folder / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return picked


def summary_table(summary: dict, window: str) -> str:
    cats = list(q.CATEGORIES)
    head = "| Window | Requests | IPs | " + " | ".join(cats) + " | Attention | Carved out |"
    sep = "|---|---:|---:|" + "---:|" * len(cats) + "---:|---:|"
    row = (f"| {window} | {summary['events']:,} | {summary['ips']:,} | " + " | ".join(str(summary["categories"].get(k, 0)) for k in cats)
           + f" | {summary['attention']} | {summary['carved_out']} |")
    return "\n".join(["", head, sep, row, ""])


def carve_table(rows: list[dict], carved: list[dict]) -> str:
    shown = [r for r in carved if r["attention"] or r["category"] == "malicious"] or [r for r in rows if r["attention"]]
    if not shown:
        return "No IP needs attention.\n"
    lines = ["| IP | Category | Sev | Req | Hosts | Signals | Code signals | Top paths | Raw |", "|---|---|---:|---:|---|---|---|---|---|"]
    for r in shown:
        paths = "; ".join(l.split(" [")[0] for l in r["paths_text"].split("\n")[:3])
        flag = "!! " if r["attention"] else ""
        lines.append(f"| {flag}{r['ip']} | {r['category']} | {r['severity']} | {r['requests']} | {r['hosts_text'][:40]} | "
                     f"{r['signals_text'][:60]} | {r['code_signal_names'][:70]} | {paths[:80]} | {r.get('raw_file', '')} |")
    n_unclear = sum(1 for r in carved if r["category"] == "unclear")
    tail = f"\n{len(shown)} shown; {n_unclear} unclear IPs also carved out to investigate/ (see its README.md).\n" if n_unclear else "\n"
    return "\n".join(lines) + tail


def _dry_run(profiles: dict, max_tokens: int, c) -> None:
    for ip, p in sorted(profiles.items(), key=lambda kv: -kv[1]["volume"]["requests"]):
        full = render(p, 10**9)[1]
        _, est = render(p, max_tokens)
        tone = GREEN if full <= max_tokens else YELLOW
        print(f"{ip:<40} {p['volume']['requests']:>6} req  est tokens full={c(tone, str(full))} sent={est}  "
              f"{c(DIM, '; '.join(p['code_signals']))[:90]}")


if __name__ == "__main__":
    main()
