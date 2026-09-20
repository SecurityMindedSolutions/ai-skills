"""Every output the runner writes: results.json / results.csv, findings.md,
the PR summary (markdown for $GITHUB_STEP_SUMMARY or a PR body), SARIF 2.1.0
for GitHub code scanning, and results.xlsx when openpyxl happens to be
installed (never required)."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

DISCLAIMER = (
    "RESEARCH PROOF OF CONCEPT. Each row is TypeSafe Jev's answer to a fixed set of questions "
    "about ONE unit of source code (a function, method, block or config file) with its file's "
    "imports and guard markers, a paragraph about the system, and regex facts computed in code. "
    "Jev reads one unit at a time: it cannot follow a call into another file, so a flagged unit "
    "is a candidate for a person or a reasoning agent to trace, not a confirmed vulnerability, "
    "and a clean unit is 'nothing visible in this unit', not 'safe'. Cross-file and lifecycle "
    "defects are outside what a unit-level pass can see."
)

COLUMNS = [
    ("Attention", "attention_text"), ("Category", "category"), ("Score (0-100)", "score"), ("Band", "band"),
    ("Severity (Jev)", "severity_level"), ("File", "path"), ("Lines", "lines"), ("Unit", "unit"), ("Role", "role"),
    ("Signals (Jev)", "signals_text"), ("Code signals", "code_signals_text"), ("Mitigation P", "mitigation_in_unit"),
    ("Class confidence", "class_confidence"), ("Rule reasons", "rule_reasons_text"), ("Was (base band)", "base_band"),
    ("Rose", "rose"), ("Jev input tokens", "input_tokens"), ("Jev latency ms", "latency_ms"), ("Error", "error"),
]
LEVEL = {"Likely": "error", "Review": "warning", "Note": "note", "Clean": "none"}


def group_findings(rows: list[dict]) -> list[dict]:
    """One finding per (file, category) among attention rows, strongest unit first."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("attention"):
            groups[(r["path"], r["category"])].append(r)
    findings = []
    for (path, category), units in groups.items():
        units.sort(key=lambda r: -r["score"])
        top = units[0]
        findings.append({"path": path, "category": category, "score": top["score"], "band": top["band"],
                         "severity_level": top.get("severity_level"), "units": [f"{u['unit']} ({u['lines']})" for u in units],
                         "lines": top["lines"], "unit": top["unit"], "signals": top.get("signals", []),
                         "code_signals": top.get("code_signals", []), "rule_reasons": top.get("rule_reasons", []),
                         "code": top.get("code", ""), "n_units": len(units)})
    findings.sort(key=lambda f: (-f["score"], f["path"]))
    return findings


def write_run(out_dir: Path, rows: list[dict], summary: dict, findings: list[dict]) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {"json": out_dir / "results.json", "csv": out_dir / "results.csv",
             "findings_md": out_dir / "findings.md", "findings_json": out_dir / "findings.json"}
    slim = [{k: v for k, v in r.items() if k not in ("code", "detail")} | {"answers": r.get("detail", {})} for r in rows]
    paths["json"].write_text(json.dumps({"summary": summary, "disclaimer": DISCLAIMER, "results": slim}, indent=1))
    paths["findings_json"].write_text(json.dumps({"summary": summary, "findings": [{k: v for k, v in f.items() if k != "code"} for f in findings]}, indent=1))
    with paths["csv"].open("w", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(h for h, _ in COLUMNS)
        for r in rows:
            w.writerow(r.get(k, "") for _, k in COLUMNS)
    paths["findings_md"].write_text(findings_markdown(findings, summary))
    try:
        import openpyxl  # noqa: F401
        paths["xlsx"] = out_dir / "results.xlsx"
        _write_xlsx(paths["xlsx"], rows, findings)
    except ImportError:
        pass
    return paths


def findings_markdown(findings: list[dict], summary: dict) -> str:
    out = [f"# Code audit candidates ({summary.get('target', '')})\n",
           f"{summary.get('attention_units', 0)} attention units in {len(findings)} findings, from "
           f"{summary.get('units_judged', 0)} units judged. Jev tokens {summary.get('jev_input_tokens', 0):,}, "
           f"cost ${summary.get('jev_cost_usd', 0):.2f}, wall time {summary.get('wall_seconds', 0):.0f}s.\n", f"> {DISCLAIMER}\n"]
    for i, f in enumerate(findings, start=1):
        out.append(f"## {i}. [{f['band']} {f['score']}] {f['category']} in `{f['path']}`\n")
        out.append(f"- **Units:** {', '.join(f['units'][:6])}{' ...' if len(f['units']) > 6 else ''}")
        out.append(f"- **Jev severity:** {f['severity_level']}; **signals:** {', '.join(f['signals']) or 'none'}")
        out.append(f"- **Code signals:** {', '.join(f['code_signals']) or 'none'}")
        if f["rule_reasons"]:
            out.append(f"- **Rules:** {'; '.join(f['rule_reasons'])}")
        snippet = f["code"].strip().splitlines()
        if len(snippet) > 40:
            snippet = snippet[:40] + ["..."]
        out.append(f"\n```\n# {f['path']}:{f['lines']} ({f['unit']})\n" + "\n".join(snippet) + "\n```\n")
    return "\n".join(out)


def pr_summary(rows: list[dict], summary: dict, info: dict) -> str:
    """Markdown for a PR: risen rows first, then pre-existing attention rows the change touched."""
    risen = [r for r in rows if r.get("rose")]
    touched = [r for r in rows if r.get("attention") and not r.get("rose")]
    out = [f"## Jev code audit: {len(risen)} unit{'s' if len(risen) != 1 else ''} rose in risk band",
           f"Changed files judged: {info.get('files_judged', 0)} of {info.get('files_changed', 0)}; units changed: "
           f"{info.get('units_changed', 0)} ({info.get('units_new', 0)} new). Jev tokens {summary.get('jev_input_tokens', 0):,}, "
           f"${summary.get('jev_cost_usd', 0):.3f}, {summary.get('wall_seconds', 0):.0f}s.", ""]
    if risen:
        out += ["| Band | Score | Was | Class | File | Unit | Jev signals |", "|---|---|---|---|---|---|---|"]
        for r in risen:
            was = r.get("base_band") or "new"
            if r.get("base_score") is not None:
                was += f" {r['base_score']}"
            out.append(f"| **{r['band']}** | {r['score']} | {was} | {r['category']} | `{r['path']}:{r['start']}-{r['end']}` | `{r['unit']}` | {', '.join(r.get('signals') or [])} |")
    else:
        out.append("No changed unit rose in band. Nothing for this change to answer for.")
    if touched:
        out += ["", f"<details><summary>{len(touched)} pre-existing attention unit{'s' if len(touched) != 1 else ''} touched by this change (same band before and after)</summary>\n",
                "| Band | Score | Class | File | Unit |", "|---|---|---|---|---|"]
        out += [f"| {r['band']} | {r['score']} | {r['category']} | `{r['path']}:{r['start']}-{r['end']}` | `{r['unit']}` |" for r in touched]
        out.append("\n</details>")
    out += ["", "_Research proof of concept: each row is TypeSafe Jev's answer about one unit of code, a candidate to trace, "
            "not a confirmed vulnerability. Controls in other files are invisible to it; `app.md` is where they are declared._"]
    return "\n".join(out)


def write_sarif(path: Path, rows: list[dict], summary: dict, classes: dict, version: str = "0.2.0") -> None:
    rules = [{"id": f"jev/{cls}", "name": cls, "shortDescription": {"text": cls.replace("_", " ")},
              "fullDescription": {"text": desc},
              "help": {"text": "TypeSafe Jev unit-level judgment: a candidate to trace, not a confirmed vulnerability. Controls in other files are invisible to it."},
              "properties": {"tags": ["security", "jev"], "precision": "medium"}}
             for cls, desc in classes.items() if cls != "none"]
    results = []
    for r in rows:
        cat = r.get("category")
        if cat in (None, "none", "dropped", "error"):
            continue
        msg = (f"[{r.get('band')} {r.get('score')}] {cat} in {r.get('unit')}. Jev signals: {', '.join(r.get('signals') or []) or 'none'}. "
               f"Code signals: {', '.join(r.get('code_signals') or []) or 'none'}. Jev impact: {r.get('severity_level')}; mitigation seen: {r.get('mitigation_in_unit')}.")
        if r.get("base_band") and r.get("base_band") not in ("", "not judged"):
            msg = f"Band rose from {r['base_band']} ({r.get('base_score')}) to {r['band']} ({r['score']}) in this change. " + msg
        results.append({"ruleId": f"jev/{cat}", "level": LEVEL.get(r.get("band", ""), "note"), "message": {"text": msg},
                        "locations": [{"physicalLocation": {"artifactLocation": {"uri": r["path"], "uriBaseId": "%SRCROOT%"},
                                                            "region": {"startLine": int(r["start"]), "endLine": int(r["end"])}}}],
                        "partialFingerprints": {"jev/unit": f"{r['path']}::{r.get('unit')}::{cat}"},
                        "properties": {"score": r.get("score"), "band": r.get("band"), "jev_class": r.get("jev_class"), "class_confidence": r.get("class_confidence")}})
    doc = {"$schema": "https://json.schemastore.org/sarif-2.1.0.json", "version": "2.1.0",
           "runs": [{"tool": {"driver": {"name": "code-audit-jev", "version": version,
                                         "informationUri": "https://github.com/SecurityMindedSolutions/ai-skills", "rules": rules}},
                     "results": results,
                     "properties": {"summary": {k: v for k, v in summary.items() if isinstance(v, (int, float, str))}}}]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1))


def _write_xlsx(path: Path, rows: list[dict], findings: list[dict]) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    book = Workbook()
    bold = Font(bold=True)
    fcols = [("Band", "band"), ("Score", "score"), ("Category", "category"), ("File", "path"), ("Lines", "lines"), ("Unit", "unit"), ("Units", "n_units")]
    sheet = book.active
    sheet.title = "Findings"
    for c, (h, _) in enumerate(fcols, start=1):
        sheet.cell(row=1, column=c, value=h).font = bold
    for r, f in enumerate(findings, start=2):
        for c, (_, k) in enumerate(fcols, start=1):
            sheet.cell(row=r, column=c, value=f.get(k, ""))
    units = book.create_sheet("Units")
    for c, (h, _) in enumerate(COLUMNS, start=1):
        units.cell(row=1, column=c, value=h).font = bold
    for r, row in enumerate(rows, start=2):
        for c, (_, k) in enumerate(COLUMNS, start=1):
            v = row.get(k, "")
            units.cell(row=r, column=c, value=v if isinstance(v, (int, float, str)) else str(v))
    book.save(path)
