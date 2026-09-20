#!/usr/bin/env python3
"""code-audit-jev: judge every unit of code in a repository (or only the units
a change touched) against the rules in `rules/` with TypeSafe Jev.

    python3 run.py --target REPO --app app.md                  # whole tree
    python3 run.py --target REPO --app app.md --diff origin/main   # PR mode
    python3 run.py --target REPO --app app.md --explain path/file.py[:unit]

--rules DIR      extra rules directory (repeatable; a file with an existing id overrides it)
--exclude P      path prefix to skip (repeatable), e.g. --exclude archive
--include P      only paths under these prefixes (repeatable)
--scope signals  judge only units with a regex signal or a security-relevant role
--sarif PATH     also write SARIF 2.1.0 (GitHub code scanning)
--summary PATH   also write the markdown PR summary
--dry-run        inventory, units and signals with no Jev calls
--limit N        judge at most N units (a trial)

Stdlib only. openpyxl, if installed, adds results.xlsx. A folder whose
children are git repositories is a fleet: one run per repository under
out/<repo>/ plus fleet.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import output
import rules as rules_mod
from extract import estimate_tokens, file_context, units_for
from inventory import find_repos, language_of, role_of, summarize, walk
from jev import JevClient, load_api_key

DEFAULT_OUT_ROOT = Path(tempfile.gettempdir()) / "code-audit-jev"
SKIP_ROLES = {"test", "docs", "generated"}
ALWAYS_JUDGE_ROLES = {"http_handler", "event_worker", "infra_terraform", "infra_manifest", "ci_pipeline", "container"}
FIXED_OVERHEAD_TOKENS = 4_600
GREEN, RED, YELLOW, BLUE, BOLD, DIM, OFF = "\033[92m", "\033[91m", "\033[93m", "\033[94m", "\033[1m", "\033[2m", "\033[0m"
BAND_COLOR = {"Likely": RED, "Review": YELLOW, "Note": BLUE, "Clean": GREEN}
BAND_RANK = {"": 0, "Clean": 0, "Note": 1, "Review": 2, "Likely": 3}
DEFAULT_APP = ("A web application with an HTTP API and a browser front end. Handlers must apply their own "
               "authentication; there is no global gate. Data is stored per customer account. Environment "
               "variables and command-line flags are trusted configuration.")


# --- one unit -----------------------------------------------------------------

class Judge:
    def __init__(self, rs: rules_mod.RuleSet, app: str, model: str | None = None):
        self.rs = rs
        self.app = app
        self.model = model or rs.model
        self.client = JevClient(load_api_key(), self.model)
        self.fatal: list[str] = []

    def state(self, unit: dict, ctx: dict, role: str, sig: dict) -> dict:
        code = unit["code"]
        cap = int(self.rs.core["model"].get("max_unit_tokens", 6000))
        if estimate_tokens(code) > cap:
            code = code[: cap * 3] + "\n... [truncated]"
        return {"app": self.app,
                "file": {"path": unit["path"], "language": unit["language"], "role": role, "imports": ctx["imports"], "guard_markers": ctx["guard_markers"]},
                "unit": {"name": unit["name"], "kind": unit["kind"], "lines": f"{unit['start']}-{unit['end']}", "code": code},
                "code_signals": sig or {"none": "no regex signal fired in this unit"}}

    def unit(self, unit: dict, ctx: dict, frec: dict) -> dict:
        base = {"path": unit["path"], "unit": unit["name"], "kind": unit["kind"], "start": unit["start"], "end": unit["end"],
                "lines": f"{unit['start']}-{unit['end']}", "language": unit["language"], "role": frec["role"], "code": unit["code"]}
        if self.fatal:
            return base | {"category": "error", "score": 0, "band": "", "attention": False, "error": f"skipped after fatal error: {self.fatal[0]}", "input_tokens": 0, "latency_ms": 0}
        sig = self.rs.scan(unit["code"], unit["start"])
        try:
            t0 = time.perf_counter()
            resp = self.client.evaluate(self.state(unit, ctx, frec["role"], sig), self.rs.questions)
            latency = round((time.perf_counter() - t0) * 1000)
        except Exception as err:  # noqa: BLE001
            text = str(err)
            if any(code in text for code in ("HTTP 402", "HTTP 401", "HTTP 403")):
                self.fatal.append(text[:200])
            return base | {"category": "error", "score": 0, "band": "", "attention": False, "error": text[:300], "input_tokens": 0, "latency_ms": 0}
        v = self.rs.judge(resp["answers"], sig, frec["role"])
        a = v["answers"]
        return base | {
            "category": v["category"], "jev_class": a["issue_class"], "class_confidence": a["issue_class_confidence"],
            "score": v["score"], "band": v["band"], "attention": v["attention"],
            "attention_text": "YES" if v["attention"] else "",
            "severity_level": a["severity_level"], "severity_expectation": a["severity"], "severity_confidence": a["severity_confidence"],
            "signals": v["signals_fired"], "signals_text": ", ".join(v["signals_fired"]),
            "vectors": v["vectors"], "code_signals": self.rs.flat(sig), "code_signal_detail": sig,
            "code_signals_text": "; ".join(f"{g}.{n}: {x}" for g, hits in sig.items() for n, x in hits.items()),
            "rule_reasons": v["reasons"], "rule_reasons_text": "; ".join(v["reasons"]), "detail": a,
            "mitigation_in_unit": a["mitigation_in_unit"], "not_production_code": a["not_production_code"],
            "model": resp["model"], "input_tokens": resp["usage"]["input_tokens"], "latency_ms": latency,
        }


# --- selecting units ------------------------------------------------------------

def _included(rel: str, excludes: list[str], includes: list[str]) -> bool:
    if any(rel.startswith(x.rstrip("/") + "/") or rel == x for x in excludes):
        return False
    return not includes or any(rel.startswith(x.rstrip("/") + "/") or rel == x for x in includes)


def select_units(repo: Path, files: list[dict], rs: rules_mod.RuleSet, args) -> tuple[list[tuple], dict]:
    chosen, skipped = [], Counter()
    for f in files:
        if not _included(f["path"], args.exclude, args.include):
            skipped["excluded"] += 1
            continue
        if f["role"] in SKIP_ROLES:
            skipped[f["role"]] += 1
            continue
        text = (repo / f["path"]).read_text(encoding="utf-8", errors="replace")
        ctx = file_context(text, f["language"])
        for u in units_for(f["path"], f["language"], text):
            if args.scope == "signals" and f["role"] not in ALWAYS_JUDGE_ROLES and not rs.security_relevant(rs.scan(u["code"], u["start"])):
                skipped["no_signal"] += 1
                continue
            chosen.append((u, ctx, f))
    return chosen, dict(skipped)


# --- modes ---------------------------------------------------------------------

def run_full(repo: Path, rs: rules_mod.RuleSet, app: str, args, out_dir: Path) -> dict:
    t0 = time.perf_counter()
    files = walk(repo)
    inv = summarize(files)
    chosen, skipped = select_units(repo, files, rs, args)
    if args.limit:
        chosen = chosen[: args.limit]
    est = sum(u["tokens_est"] for u, _, _ in chosen) + FIXED_OVERHEAD_TOKENS * len(chosen)
    usd = rs.core["model"]["usd_per_million_input_tokens"]
    print(f"\n{BOLD}{repo}{OFF}: {inv['files']} files, {inv['lines']:,} lines; {len(chosen)} units to judge "
          f"(skipped: {', '.join(f'{k} {n}' for k, n in skipped.items()) or 'none'})\n  estimated Jev input: {est:,} tokens (~${est * usd / 1e6:.2f})")
    if args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "units.json").write_text(json.dumps([{"path": u["path"], "unit": u["name"], "lines": f"{u['start']}-{u['end']}", "tokens_est": u["tokens_est"],
                                                          "role": f["role"], "signals": rs.flat(rs.scan(u["code"], u["start"]))} for u, _, f in chosen], indent=1))
        return {"repo": str(repo), "units": len(chosen), "dry_run": True}
    judge = Judge(rs, app, args.model)
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, v in enumerate(pool.map(lambda it: judge.unit(*it), chosen), start=1):
            rows.append(v)
            if args.verbose or i % 250 == 0:
                print(f"  {i}/{len(chosen)}  {BAND_COLOR.get(v.get('band', ''), DIM)}{v.get('band', ''):6}{OFF} {v.get('score', 0):5} {v['path']}:{v['start']} {v['unit']}")
    rows.sort(key=lambda r: (-int(bool(r.get("attention"))), -(r.get("score") or 0), r["path"]))
    summary = _summary(repo, rs, rows, time.perf_counter() - t0, {"mode": "full", "scope": args.scope, "files": inv["files"], "lines": inv["lines"], "skipped": skipped})
    findings = output.group_findings(rows)
    paths = output.write_run(out_dir, rows, summary, findings)
    if args.sarif:
        output.write_sarif(Path(args.sarif), [r for r in rows if r.get("attention")], summary, rs.classes)
    _print_full(summary, findings, paths)
    if judge.fatal:
        print(f"{RED}run stopped early: {judge.fatal[0]}{OFF}", file=sys.stderr)
        sys.exit(2)
    return summary


def run_diff(repo: Path, rs: rules_mod.RuleSet, app: str, args, out_dir: Path) -> dict:
    from diff import changed_units
    t0 = time.perf_counter()
    items, info = changed_units(repo, args.diff, args.exclude, args.include)
    if args.limit:
        items = items[: args.limit]
    print(f"\n{BOLD}{repo}{OFF} vs {args.diff} ({info['base_sha'][:10]}): {info['files_changed']} files changed, "
          f"{info['files_judged']} judged, {info['units_changed']} units changed ({info['units_new']} new)")
    if args.dry_run:
        for it in items:
            u = it["head"][0]
            print(f"  {u['path']}:{u['start']}-{u['end']} {u['name']}{' (new)' if it['base'] is None else ''}")
        return {"repo": str(repo), "units": len(items), "dry_run": True}
    judge = Judge(rs, app, args.model)

    def work(it):
        head = judge.unit(*it["head"])
        # a Clean head cannot have risen; the base is judged only when it matters
        needs_base = it["base"] is not None and BAND_RANK.get(head.get("band", ""), 0) >= 1
        base = judge.unit(*it["base"]) if needs_base else None
        if it["base"] is None:
            head["base_band"], head["base_score"], head["rose"] = "", None, bool(head.get("attention"))
        elif base is None:
            head["base_band"], head["base_score"], head["rose"] = "not judged", None, False
        else:
            head["base_band"], head["base_score"] = base.get("band", ""), base.get("score")
            head["rose"] = BAND_RANK.get(head.get("band", ""), 0) > BAND_RANK.get(base.get("band", ""), 0) and head.get("category") not in ("none", "dropped", "error")
            head["input_tokens"] = head.get("input_tokens", 0) + base.get("input_tokens", 0)
        return head

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(work, items))
    rows.sort(key=lambda r: (-int(bool(r.get("rose"))), -int(bool(r.get("attention"))), -(r.get("score") or 0)))
    summary = _summary(repo, rs, rows, time.perf_counter() - t0, {"mode": "diff", "base_ref": args.diff, "base_sha": info["base_sha"],
                                                                     "files_changed": info["files_changed"], "files_judged": info["files_judged"],
                                                                     "units_changed": info["units_changed"], "units_new": info["units_new"],
                                                                     "rose": sum(1 for r in rows if r.get("rose"))})
    findings = output.group_findings([r for r in rows if r.get("rose")])
    paths = output.write_run(out_dir, rows, summary, findings)
    md = output.pr_summary(rows, summary, info)
    (out_dir / "pr-summary.md").write_text(md)
    if args.summary:
        Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary).write_text(md)
    if args.sarif:
        output.write_sarif(Path(args.sarif), [r for r in rows if r.get("rose")], summary, rs.classes)
    print(md)
    print(f"\nwritten: {', '.join(str(p) for p in paths.values())}")
    if judge.fatal:
        print(f"{RED}run stopped early: {judge.fatal[0]}{OFF}", file=sys.stderr)
        sys.exit(2)
    return summary


def run_explain(repo: Path, rs: rules_mod.RuleSet, app: str, args) -> None:
    """One file (or one unit): print the exact state Jev saw and every answer."""
    spec, _, unit_name = args.explain.partition(":")
    path = repo / spec
    text = path.read_text(errors="replace")
    lang = language_of(path) or "text"
    frec = {"path": spec, "language": lang, "role": role_of(spec, lang, text)}
    ctx = file_context(text, lang)
    judge = Judge(rs, app, args.model)
    for u in units_for(spec, lang, text):
        if unit_name and u["name"] != unit_name:
            continue
        v = judge.unit(u, ctx, frec)
        v.pop("code", None)
        print(json.dumps(v, indent=2))
        if unit_name:
            print("--- state sent ---", file=sys.stderr)
            print(json.dumps(judge.state(u, ctx, frec["role"], rs.scan(u["code"], u["start"])), indent=1)[:6000], file=sys.stderr)


# --- summaries -----------------------------------------------------------------

def _summary(repo: Path, rs: rules_mod.RuleSet, rows: list[dict], wall: float, extra: dict) -> dict:
    tokens = sum(r.get("input_tokens", 0) for r in rows)
    lat = [r["latency_ms"] for r in rows if r.get("latency_ms")]
    return {"target": str(repo), "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": next((r.get("model") for r in rows if r.get("model")), rs.model), "rules": sorted(rs.rules),
            "units_judged": len(rows), "errors": sum(1 for r in rows if r.get("error")),
            "attention_units": sum(1 for r in rows if r.get("attention")),
            "by_band": dict(Counter(r.get("band", "") for r in rows)),
            "by_category": dict(Counter(r["category"] for r in rows if r.get("attention"))),
            "jev_input_tokens": tokens, "jev_cost_usd": round(tokens * rs.core["model"]["usd_per_million_input_tokens"] / 1e6, 4),
            "latency_ms_median": statistics.median(lat) if lat else 0, "wall_seconds": round(wall, 1), **extra}


def _print_full(s: dict, findings: list[dict], paths: dict) -> None:
    print(f"\n{BOLD}Units judged{OFF}: {s['units_judged']} ({s['errors']} errors)   bands: "
          + ", ".join(f"{BAND_COLOR.get(b, DIM)}{b}{OFF} {n}" for b, n in sorted(s['by_band'].items(), key=lambda kv: -kv[1])))
    print(f"{BOLD}Attention{OFF}: {s['attention_units']} units in {len(findings)} findings   by category: "
          + ", ".join(f"{k} {n}" for k, n in sorted(s['by_category'].items(), key=lambda kv: -kv[1])))
    print(f"{BOLD}Jev{OFF}: {s['jev_input_tokens']:,} input tokens, ${s['jev_cost_usd']:.2f}, median {s['latency_ms_median']:.0f} ms, wall {s['wall_seconds']:.0f}s")
    print(f"\n{BOLD}Top findings{OFF}:")
    for f in findings[:25]:
        print(f"  {BAND_COLOR.get(f['band'], DIM)}{f['band']:6} {f['score']:5}{OFF}  {f['category']:22} {f['path']}:{f['lines']}  {f['unit']}  [{', '.join(f['signals'][:3])}]")
    print(f"\nwritten: {', '.join(str(p) for p in paths.values())}")


# --- CLI -----------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--target", required=True)
    p.add_argument("--app", help="text or .md file describing the system")
    p.add_argument("--rules", action="append", default=[], help="extra rules directory (repeatable)")
    p.add_argument("--out")
    p.add_argument("--diff", metavar="BASE_REF")
    p.add_argument("--explain", metavar="FILE[:UNIT]")
    p.add_argument("--scope", choices=["all", "signals"], default="all")
    p.add_argument("--exclude", action="append", default=[])
    p.add_argument("--include", action="append", default=[])
    p.add_argument("--sarif")
    p.add_argument("--summary")
    p.add_argument("--model")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--limit", type=int)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--no-color", action="store_true")
    args = p.parse_args()
    if args.no_color:
        global GREEN, RED, YELLOW, BLUE, BOLD, DIM, OFF
        GREEN = RED = YELLOW = BLUE = BOLD = DIM = OFF = ""
        BAND_COLOR.update({k: "" for k in BAND_COLOR})
    rs = rules_mod.load(args.rules)
    target = Path(args.target).expanduser().resolve()
    app = DEFAULT_APP
    if args.app:
        ap = Path(args.app).expanduser()
        app = ap.read_text(encoding="utf-8").strip() if ap.is_file() else args.app
    if args.explain:
        run_explain(target, rs, app, args)
        return
    out_root = Path(args.out).expanduser() if args.out else DEFAULT_OUT_ROOT / datetime.now().strftime("%Y%m%d-%H%M%S")
    repos = find_repos(target)
    results = []
    for repo in repos:
        out_dir = out_root if len(repos) == 1 else out_root / repo.name
        results.append(run_diff(repo, rs, app, args, out_dir) if args.diff else run_full(repo, rs, app, args, out_dir))
    if len(repos) > 1 and not args.dry_run:
        with (out_root / "fleet.csv").open("w", newline="") as handle:
            w = csv.writer(handle)
            w.writerow(["repo", "files", "lines", "units", "attention_units", "jev_tokens", "jev_cost_usd", "wall_seconds"])
            for s in results:
                w.writerow([s["target"], s.get("files"), s.get("lines"), s["units_judged"], s["attention_units"], s["jev_input_tokens"], s["jev_cost_usd"], s["wall_seconds"]])
        print(f"\nfleet summary: {out_root / 'fleet.csv'}")
    print(f"\n{DIM}{output.DISCLAIMER}{OFF}")


if __name__ == "__main__":
    main()
