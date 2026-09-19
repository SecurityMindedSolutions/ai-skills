#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["openpyxl>=3.1"]
# ///
"""Run a batch of prompts through the Jev gate and, for comparison, a regex list
and optionally an LLM judge. Writes a spreadsheet and, when labels are given,
precision/recall/F1 plus measured latency and cost for each approach.

    python3 evaluate.py --prompts prompts.csv --app app-context.md

prompts.csv needs a `prompt` column; optional `label` (benign|injection),
`category`, `id`. Works with a plain Python 3.10+ install (see bootstrap.py).
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from bootstrap import ensure_dependencies

ensure_dependencies(sys.argv)

import questions as q  # noqa: E402
from baseline import regex_decision, regex_hits  # noqa: E402
from gate import DEFAULT_APP, check_prompt  # noqa: E402
from llm_judge import CLAUDE_PRICES, estimate_tokens, judge, price_at_claude  # noqa: E402
from report import DISCLAIMER, write_all  # noqa: E402

DEFAULT_OUT_ROOT = Path(tempfile.gettempdir()) / "prompt-injection-eval"
GREEN, RED, YELLOW, BOLD, DIM, OFF = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[2m", "\033[0m"
DECISION_COLOR = {"block": RED, "review": YELLOW, "allow": GREEN}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prompts", required=True, help="CSV with a `prompt` column (optional label, category, id)")
    p.add_argument("--app", help="text or .md file describing the assistant's purpose and tools")
    p.add_argument("--out", help=f"output folder (default {DEFAULT_OUT_ROOT}/<timestamp>)")
    p.add_argument("--model", default=q.MODEL)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--llm-judge", metavar="MODEL", help="also run an LLM judge via an OpenAI-compatible endpoint with this model id")
    p.add_argument("--no-color", action="store_true")
    return p.parse_args()


def load_prompts(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or "prompt" not in rows[0]:
        sys.exit("--prompts CSV needs a `prompt` column")
    for i, row in enumerate(rows, start=1):
        row.setdefault("id", str(i))
    return rows


def load_app(source: str | None) -> str:
    if not source:
        return DEFAULT_APP
    path = Path(source).expanduser()
    return path.read_text(encoding="utf-8").strip() if path.is_file() else source


def score_one(row: dict, app: str, model: str, llm_model: str | None) -> dict:
    out = {k: row.get(k, "") for k in ("id", "prompt", "label", "category")}
    try:
        verdict = check_prompt(row["prompt"], app, model)
    except RuntimeError as err:
        out.update({"error": str(err), "decision": "error"})
        return out
    out.update({k: v for k, v in verdict.items() if k != "detail"})
    out.update(verdict["detail"])
    out["signals_text"] = ", ".join(verdict["signals"])
    hits = regex_hits(row["prompt"])
    out["regex_decision"] = regex_decision(row["prompt"])
    out["regex_hits_text"] = "; ".join(hits)
    if llm_model:
        out.update(judge(row["prompt"], app, llm_model))
    return out


def prf(rows: list[dict], positive) -> dict:
    """Precision / recall / F1 treating `label == injection` as the positive class."""
    tp = sum(1 for r in rows if r["label"] == "injection" and positive(r))
    fp = sum(1 for r in rows if r["label"] == "benign" and positive(r))
    fn = sum(1 for r in rows if r["label"] == "injection" and not positive(r))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"caught": tp, "missed": fn, "false alarms": fp,
            "precision": round(precision, 2), "recall": round(recall, 2), "F1": round(f1, 2)}


app_text_for_estimate = ""


def breakdown(rows: list[dict], llm_model: str | None) -> list[dict]:
    """One row per approach and population, one column per decision: where did
    the attacks go, where did the benign prompts go?"""
    labelled = [r for r in rows if r.get("label") in ("benign", "injection") and r.get("decision") != "error"]
    if not labelled:
        return []
    approaches = [("Jev gate", "decision"), ("Regex phrase list", "regex_decision")]
    if llm_model and any(r.get("llm_verdict") in ("block", "allow") for r in labelled):
        approaches.append((f"LLM judge ({llm_model})", "llm_verdict"))
    out = []
    for name, key in approaches:
        for label, title in (("injection", "attacks"), ("benign", "benign")):
            group = [r for r in labelled if r["label"] == label]
            out.append({"Approach": name, "Prompts": f"{len(group)} {title}",
                        **{d: sum(1 for r in group if r.get(key) == d) for d in ("block", "review", "allow")}})
    return out


def compare(rows: list[dict], llm_model: str | None) -> list[dict]:
    scored = [r for r in rows if r.get("decision") != "error"]
    labelled = [r for r in scored if r.get("label") in ("benign", "injection")]
    n = len(scored)
    jev_tokens = sum(r.get("input_tokens", 0) for r in scored)
    jev_lat = [r["latency_ms"] for r in scored if "latency_ms" in r]
    out = []

    def row(name, positive, tokens_cost, latency):
        entry = {"Approach": name}
        if labelled:
            entry.update(prf(labelled, positive))
        entry.update(latency)
        entry.update(tokens_cost)
        return entry

    lat = lambda xs: {"median latency ms": round(statistics.median(xs)) if xs else None,
                      "p95 latency ms": round(sorted(xs)[int(0.95 * (len(xs) - 1))]) if xs else None}
    out.append(row("Jev gate, counting block as caught", lambda r: r["decision"] == "block",
                   {"tokens per prompt": round(jev_tokens / n) if n else None,
                    "cost per 1,000 prompts": round(1000 * (jev_tokens / n) * q.USD_PER_MILLION_INPUT_TOKENS / 1e6, 4) if n else None},
                   lat(jev_lat)))
    out.append(row("Jev gate, counting block or review as caught", lambda r: r["decision"] in ("block", "review"),
                   {"tokens per prompt": round(jev_tokens / n) if n else None,
                    "cost per 1,000 prompts": round(1000 * (jev_tokens / n) * q.USD_PER_MILLION_INPUT_TOKENS / 1e6, 4) if n else None},
                   lat(jev_lat)))
    out.append(row("Regex phrase list", lambda r: r["regex_decision"] == "block",
                   {"tokens per prompt": 0, "cost per 1,000 prompts": 0.0},
                   {"median latency ms": 0, "p95 latency ms": 0}))
    judged = [r for r in scored if r.get("llm_verdict") in ("block", "allow")] if llm_model else []
    if judged:
        i_tok = sum(r.get("llm_input_tokens", 0) for r in judged) / len(judged)
        o_tok = sum(r.get("llm_output_tokens", 0) for r in judged) / len(judged)
        per_1000 = price_at_claude(int(1000 * i_tok), int(1000 * o_tok))
        out.append(row(f"LLM judge ({llm_model}), measured", lambda r: r.get("llm_verdict") == "block",
                       {"tokens per prompt": round(i_tok + o_tok),
                        **{f"cost per 1,000 prompts at {name} rates": v for name, v in per_1000.items()}},
                       lat([r["llm_latency_ms"] for r in judged])))
    elif scored:
        est = [estimate_tokens(r["prompt"], app_text_for_estimate) for r in scored]
        i_tok = sum(i for i, _ in est) / len(est)
        o_tok = sum(o for _, o in est) / len(est)
        per_1000 = price_at_claude(int(1000 * i_tok), int(1000 * o_tok))
        entry = {"Approach": "LLM judge, estimated (not run; pass --llm-judge to measure)"}
        if labelled:
            entry.update({"caught": None, "missed": None, "false alarms": None,
                          "precision": None, "recall": None, "F1": None})
        entry.update({"median latency ms": "typically 400-1500", "p95 latency ms": "typically 1500-4000",
                      "tokens per prompt": round(i_tok + o_tok),
                      **{f"cost per 1,000 prompts at {name} rates": v for name, v in per_1000.items()}})
        out.append(entry)
    return out


def print_report(rows: list[dict], summary: dict, comparison: list[dict], color: bool) -> None:
    c = (lambda code, s: f"{code}{s}{OFF}") if color else (lambda code, s: s)
    print(c(BOLD, f"\n{'Decision':<9} {'Risk':>5} {'Regex':<6} {'Label':<10} Prompt"))
    for r in rows:
        d = r.get("decision", "error")
        print(f"{c(DECISION_COLOR.get(d, RED), d.ljust(9))} {r.get('risk', ''):>5} "
              f"{r.get('regex_decision', ''):<6} {r.get('label', ''):<10} {r['prompt'][:70].replace(chr(10), ' ')}")
    counts = summary["decisions"]
    print(c(BOLD, f"\n{summary['prompts']} prompts: ") + c(RED, f"{counts.get('block', 0)} block") + ", "
          + c(YELLOW, f"{counts.get('review', 0)} review") + ", " + c(GREEN, f"{counts.get('allow', 0)} allow")
          + f"  |  Jev {summary['jev_input_tokens']} tokens ~${summary['jev_cost_usd']}, median {summary['jev_median_latency_ms']} ms/prompt, {summary['seconds']}s total")
    if summary.get("breakdown"):
        print(c(BOLD, "\nWhere each approach put the prompts:"))
        print(f"  {'Approach':<28} {'Prompts':<12} {c(RED, 'block'):>8} {c(YELLOW, 'review'):>8} {c(GREEN, 'allow'):>8}")
        for e in summary["breakdown"]:
            print(f"  {e['Approach']:<28} {e['Prompts']:<12} {e['block']:>8} {e['review']:>8} {e['allow']:>8}")
    if comparison and "precision" in comparison[0]:
        print(c(BOLD, "\nComparison (injection = positive):"))
        for entry in comparison:
            if entry.get("caught") is None:
                print(f"  {entry['Approach']}: {entry['tokens per prompt']} tokens/prompt, "
                      + ", ".join(f"${v}/1k at {k.split(' at ')[1].replace(' rates', '')}" for k, v in entry.items() if k.startswith("cost per 1,000 prompts at")))
                continue
            print(f"  {entry['Approach']:<46} caught {entry['caught']:>3}  missed {entry['missed']:>3}  false alarms {entry['false alarms']:>3}"
                  f"  P {entry['precision']:.2f}  R {entry['recall']:.2f}  F1 {entry['F1']:.2f}"
                  f"  median {entry['median latency ms']} ms")
    print(c(DIM, "\n" + DISCLAIMER))


def main() -> None:
    args = parse_args()
    started = time.time()
    out_dir = Path(args.out) if args.out else DEFAULT_OUT_ROOT / f"{datetime.now():%Y%m%d-%H%M%S}"
    prompts = load_prompts(Path(args.prompts).expanduser())
    app = load_app(args.app)
    global app_text_for_estimate
    app_text_for_estimate = app
    print(f"{'' if args.no_color else DIM}{len(prompts)} prompts using {args.model}"
          f"{' + LLM judge ' + args.llm_judge if args.llm_judge else ''}{'' if args.no_color else OFF}")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(lambda r: score_one(r, app, args.model, args.llm_judge), prompts))
    rows.sort(key=lambda r: -(r.get("risk") or 0))
    scored = [r for r in rows if r.get("decision") != "error"]
    lat = [r["latency_ms"] for r in scored]
    tokens = sum(r.get("input_tokens", 0) for r in scored)
    summary = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "prompts": len(rows),
        "decisions": {d: sum(1 for r in rows if r.get("decision") == d) for d in ("block", "review", "allow", "error")},
        "typesafe_model": ", ".join(sorted({r["model"] for r in scored if "model" in r})) or args.model,
        "jev_input_tokens": tokens,
        "jev_cost_usd": round(tokens * q.USD_PER_MILLION_INPUT_TOKENS / 1e6, 5),
        "jev_median_latency_ms": round(statistics.median(lat)) if lat else None,
        "jev_p95_latency_ms": round(sorted(lat)[int(0.95 * (len(lat) - 1))]) if lat else None,
        "thresholds": {"block_at": q.BLOCK_AT, "review_at": q.REVIEW_AT, "min_confidence_to_allow": q.MIN_CONFIDENCE_TO_ALLOW},
        "seconds": round(time.time() - started, 1),
    }
    comparison = compare(rows, args.llm_judge)
    summary["breakdown"] = breakdown(rows, args.llm_judge)
    paths = write_all(out_dir, rows, summary, comparison)
    print_report(rows, summary, comparison, color=not args.no_color)
    main_out = paths.get("xlsx") or paths["csv"]
    print(f"\n{'' if args.no_color else BOLD}Output:{'' if args.no_color else OFF} {main_out}  (also {', '.join(p.name for p in paths.values() if p != main_out)})")


if __name__ == "__main__":
    main()
