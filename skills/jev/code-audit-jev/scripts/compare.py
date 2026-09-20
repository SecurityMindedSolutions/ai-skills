"""Compare a Jev run against a reference finding list, such as an
/audit-security report, finding by finding.

    python3 compare.py --results out/results.json --reference audit-security-report.md [--json]

The reference can be (a) an audit-security markdown report (findings are
parsed from `### ID: Title` headings with their `**File:**` and
`**Affected files:**` lines and `**Severity:**`), or (b) a CSV with columns
id,path,line,severity,title.

For each reference finding the tool reports the best Jev unit that covers
the finding's primary file and line (or any affected file): flagged
(attention row), judged-not-flagged (with the best score), or not judged
(the file was skipped: docs, tests, outside scope, or not a code file).
It also lists Jev attention findings whose file appears in no reference
finding, which is where the false positives and the genuinely new
candidates both live; a person decides which.

A reference finding is *unit-visible* when the defect is inside one unit
of code; *cross-file* when it is a relationship between files, a lifecycle
ordering, a missing control elsewhere, or a fact outside the repository.
The tool cannot tell those apart; the `--classify` CSV column lets a
person record it so the recall number is reported for the class Jev can
see as well as overall.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

HEADING = re.compile(r"^###\s+([A-Z]+-\d+|[CHMLI]-\d+):\s*(.+?)\s*$", re.M)
FILE_LINE = re.compile(r"\*\*File:\*\*\s*`([^`:]+)(?::(\d+))?`")
AFFECTED = re.compile(r"\*\*Affected files:\*\*\s*(.+?)(?=\n\*\*|\Z)", re.S)
SEVERITY = re.compile(r"\*\*Severity:\*\*\s*(\w+)")
CONF = re.compile(r"\*\*Confidence:\*\*\s*(\w+)")
BACKTICK = re.compile(r"`([^`]+)`")


def parse_reference_markdown(text: str) -> list[dict]:
    out = []
    heads = list(HEADING.finditer(text))
    for i, h in enumerate(heads):
        body = text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        fm = FILE_LINE.search(body)
        if not fm:
            continue
        affected = []
        am = AFFECTED.search(body)
        if am:
            affected = [p.split(":")[0] for p in BACKTICK.findall(am.group(1))]
        sev = SEVERITY.search(body)
        conf = CONF.search(body)
        out.append({"id": h.group(1), "title": h.group(2), "path": fm.group(1).strip(),
                    "line": int(fm.group(2)) if fm.group(2) else None,
                    "affected": [a for a in affected if "/" in a or "." in a],
                    "severity": sev.group(1) if sev else "", "confidence": conf.group(1) if conf else ""})
    return out


def parse_reference_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [{"id": r.get("id", ""), "title": r.get("title", ""), "path": r["path"].strip(),
             "line": int(r["line"]) if r.get("line") else None, "affected": [],
             "severity": r.get("severity", ""), "confidence": "", "classify": r.get("classify", "")} for r in rows if r.get("path")]


def best_unit(rows: list[dict], path: str, line: int | None) -> dict | None:
    cands = [r for r in rows if r["path"] == path]
    if not cands:
        return None
    if line:
        covering = [r for r in cands if r["start"] <= line <= r["end"]]
        if covering:
            return max(covering, key=lambda r: r.get("score") or 0)
    return max(cands, key=lambda r: r.get("score") or 0)


def compare(rows: list[dict], reference: list[dict]) -> dict:
    per = []
    for f in reference:
        u = best_unit(rows, f["path"], f["line"])
        status = "not_judged"
        via = f["path"]
        if u is None:
            for a in f["affected"]:
                u2 = best_unit(rows, a, None)
                if u2 is not None:
                    u, via = u2, a
                    break
        if u is not None:
            status = "flagged" if u.get("attention") else "judged_not_flagged"
        per.append({"id": f["id"], "title": f["title"], "severity": f["severity"], "path": f["path"], "line": f["line"],
                    "status": status, "via": via if u else "", "jev_score": u.get("score") if u else None,
                    "jev_category": u.get("category") if u else None, "jev_unit": u.get("unit") if u else None,
                    "jev_signals": u.get("signals") if u else None, "classify": f.get("classify", "")})
    ref_paths = {f["path"] for f in reference} | {a for f in reference for a in f["affected"]}
    extra = [r for r in rows if r.get("attention") and r["path"] not in ref_paths]
    counts = {"reference": len(reference),
              "flagged": sum(1 for p in per if p["status"] == "flagged"),
              "judged_not_flagged": sum(1 for p in per if p["status"] == "judged_not_flagged"),
              "not_judged": sum(1 for p in per if p["status"] == "not_judged"),
              "jev_attention_units": sum(1 for r in rows if r.get("attention")),
              "jev_attention_units_outside_reference_files": len(extra)}
    return {"counts": counts, "per_finding": per, "extra_attention": [
        {"path": r["path"], "unit": r["unit"], "lines": f"{r['start']}-{r['end']}", "score": r["score"], "category": r["category"], "signals": r.get("signals")}
        for r in sorted(extra, key=lambda r: -r["score"])]}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--results", required=True, help="results.json from run.py")
    p.add_argument("--reference", required=True, help="audit-security report .md, or a CSV id,path,line,severity,title[,classify]")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    rows = json.loads(Path(a.results).read_text())["results"]
    ref_path = Path(a.reference)
    reference = parse_reference_csv(ref_path) if ref_path.suffix == ".csv" else parse_reference_markdown(ref_path.read_text())
    result = compare(rows, reference)
    if a.json:
        print(json.dumps(result, indent=1))
        return
    c = result["counts"]
    print(f"reference findings: {c['reference']}  flagged by Jev: {c['flagged']}  judged but not flagged: {c['judged_not_flagged']}  not judged: {c['not_judged']}")
    print(f"Jev attention units: {c['jev_attention_units']}, of which {c['jev_attention_units_outside_reference_files']} in files no reference finding names\n")
    print(f"{'id':6} {'sev':8} {'status':20} {'score':>5}  {'jev category':22} file")
    for f in result["per_finding"]:
        print(f"{f['id']:6} {f['severity']:8} {f['status']:20} {str(f['jev_score'] or ''):>5}  {str(f['jev_category'] or ''):22} {f['path']}{':' + str(f['line']) if f['line'] else ''}{'  (via ' + f['via'] + ')' if f['via'] and f['via'] != f['path'] else ''}")
    print("\nJev attention units outside the reference's files (top 30):")
    for e in result["extra_attention"][:30]:
        print(f"  {e['score']:5} {e['category']:22} {e['path']}:{e['lines']} {e['unit']} {e['signals']}")


if __name__ == "__main__":
    main()
