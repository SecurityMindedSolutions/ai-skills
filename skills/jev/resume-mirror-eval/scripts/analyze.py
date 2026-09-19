#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pypdf>=4", "openpyxl>=3.1"]
# ///
"""Score a batch of resumes for how closely their wording mirrors a job description.

    python3 analyze.py --jd posting.md --resumes ./resumes

Works with a plain Python 3.10+ install: on first run it creates a private venv
under the system temp dir for its two pure-Python dependencies (see
bootstrap.py). `uv run analyze.py` works too and skips that step.

Statistics are computed in code; semantic judgments come from TypeSafe's Jev
model; optional free-text notes come from a generative model or the host agent.
See questions.py for every question, weight and threshold.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from bootstrap import ensure_dependencies

ensure_dependencies(sys.argv)

import questions as q  # noqa: E402
from evidence import evidence_bullets  # noqa: E402
from extract import collect_resumes, load_job_description, read_document  # noqa: E402
from jev import JevClient, load_api_key  # noqa: E402
from lexical import TfidfPool, lexical_metrics, tokenize, zscores  # noqa: E402
from llm_notes import PROVIDERS, merge_notes, note_prompt, split_flag, write_agent_request  # noqa: E402
from report import DISCLAIMER, write_all  # noqa: E402
from scoring import mirror_score, review_reasons, semantic_signals  # noqa: E402

# Outputs and any staged copies of resumes go under the system temp dir by
# default, never next to the user's files. Callers copy out what they keep.
DEFAULT_OUT_ROOT = Path(tempfile.gettempdir()) / "resume-mirror-eval"

GREEN, RED, YELLOW, BOLD, DIM, OFF = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[2m", "\033[0m"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--jd", help="job description: file, folder with one file, or - for stdin")
    p.add_argument("--resumes", nargs="+", help="resume files and/or folders (.pdf .docx .txt .md)")
    p.add_argument("--out", help=f"output folder (default {DEFAULT_OUT_ROOT}/<timestamp>)")
    p.add_argument("--model", default=q.MODEL, help=f"TypeSafe model (default {q.MODEL})")
    p.add_argument("--workers", type=int, default=4, help="parallel Jev requests (default 4)")
    p.add_argument("--llm-notes", choices=["anthropic", "openai", "agent"],
                   help="add anecdotal notes via a generative model, or 'agent' to have the host agent write them")
    p.add_argument("--llm-model", help="model id for --llm-notes (required for openai)")
    p.add_argument("--llm-top", type=int, default=0, help="only annotate the top N by mirror score (default: all)")
    p.add_argument("--merge-notes", type=Path, help="JSON file {file: note} to merge into an existing --out folder")
    p.add_argument("--manifest", type=Path,
                   help="CSV with a `file` column plus any ids to carry into the sheet (candidate_id, source_url...)")
    p.add_argument("--labels", type=Path, help="CSV with columns file,label (human|ai_tailored) to score the run against")
    p.add_argument("--no-color", action="store_true")
    return p.parse_args()


def load_texts(resume_paths: list[Path]) -> tuple[dict[str, str], list[dict]]:
    texts: dict[str, str] = {}
    errors: list[dict] = []
    for path in resume_paths:
        try:
            text = read_document(path).strip()
            if len(tokenize(text)) < 40:
                raise ValueError("fewer than 40 words extracted (scanned PDF?)")
            texts[path.name] = text[:q.MAX_CHARS_PER_DOC]
        except Exception as err:  # noqa: BLE001 - one bad file must not stop the batch
            errors.append({"file": path.name, "error": str(err)})
    return texts, errors


def score_one(client: JevClient, jd_text: str, name: str, text: str, lexical: dict) -> dict:
    row = {"file": name, **lexical}
    try:
        response = client.evaluate({"job_description": jd_text, "resume": text}, q.QUESTIONS)
    except RuntimeError as err:
        row.update({"error": str(err), "mirror_score": None})
        return row
    semantic = semantic_signals(response["answers"])
    row.update(semantic)
    row.update(mirror_score(lexical, semantic))
    bullets, extra = evidence_bullets(jd_text, text, lexical, semantic)
    row.update(extra)
    row["evidence"] = "\n".join(f"- {b}" for b in bullets)
    row["_usage"] = response["usage"]["input_tokens"]
    row["_model"] = response["model"]
    return row


def run_batch(args, jd_text: str, texts: dict[str, str]) -> list[dict]:
    client = JevClient(load_api_key(), args.model)
    names = list(texts)
    pool = TfidfPool([tokenize(jd_text)] + [tokenize(texts[n]) for n in names])
    lexicals = {n: lexical_metrics(jd_text, texts[n], pool.cosine(0, i + 1), q.LONGEST_SPAN_CAP)
                for i, n in enumerate(names)}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        rows = list(executor.map(
            lambda n: score_one(client, jd_text, n, texts[n], lexicals[n]), names))
    scored = [r for r in rows if r.get("mirror_score") is not None]
    for row, z in zip(scored, zscores([r["mirror_score"] for r in scored])):
        row["pool_z"] = z
        row["pool_outlier"] = bool(len(scored) >= q.POOL_MIN_SIZE and z >= q.POOL_OUTLIER_Z)
    return rows


def add_llm_notes(args, out_dir: Path, jd_text: str, texts: dict[str, str], rows: list[dict]) -> str | None:
    targets = [r for r in rows if r.get("mirror_score") is not None]
    if args.llm_top:
        targets = targets[:args.llm_top]
    elif args.llm_notes == "agent":
        targets = [r for r in targets if r.get("needs_review")]  # only where a human would look
    if args.llm_notes == "agent":
        path = write_agent_request(out_dir, jd_text, texts, targets)
        return f"agent notes request for {len(targets)} resumes written to {path.name}"
    provider = PROVIDERS[args.llm_notes]

    def annotate(row: dict) -> None:
        raw = provider(note_prompt(jd_text, texts[row["file"]], row), args.llm_model)
        row["llm_notes"], row["llm_flag"] = split_flag(raw)

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        list(executor.map(annotate, targets))
    return f"{len(targets)} notes from {args.llm_notes}"


def apply_manifest(rows: list[dict], manifest_path: Path) -> list[str]:
    """Attach extra columns (anything but `file`) from a staging manifest to each row."""
    import csv

    with manifest_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        extra = [c for c in (reader.fieldnames or []) if c != "file"]
        by_file = {r["file"]: r for r in reader}
    for row in rows:
        meta = by_file.get(row["file"], {})
        for column in extra:
            row[column] = meta.get(column, "")
    return extra


def evaluate_labels(rows: list[dict], labels_path: Path) -> dict:
    """Compare the review flag to a labels CSV. Flagged means needs_review is true."""
    import csv

    labels = {r["file"]: r["label"].strip() for r in csv.DictReader(labels_path.open())}
    scored = [r for r in rows if r.get("mirror_score") is not None and r["file"] in labels]
    by_label: dict[str, list[float]] = {}
    for row in scored:
        by_label.setdefault(labels[row["file"]], []).append(row["mirror_score"])
    tp = sum(1 for r in scored if labels[r["file"]] == "ai_tailored" and r["needs_review"])
    fp = sum(1 for r in scored if labels[r["file"]] == "human" and r["needs_review"])
    fn = sum(1 for r in scored if labels[r["file"]] == "ai_tailored" and not r["needs_review"])
    pairs = [(a, h) for a in by_label.get("ai_tailored", []) for h in by_label.get("human", [])]
    return {
        "labelled": len(scored),
        "mean_score_by_label": {k: round(sum(v) / len(v), 1) for k, v in by_label.items()},
        "flag_precision": round(tp / (tp + fp), 2) if tp + fp else None,
        "flag_recall": round(tp / (tp + fn), 2) if tp + fn else None,
        "auc": round(sum(1 for a, h in pairs if a > h) / len(pairs), 2) if pairs else None,
    }


def mark_review(rows: list[dict]) -> None:
    for row in rows:
        if row.get("mirror_score") is None:
            row["needs_review"] = True
            row["review_reasons"] = "could not be scored"
            continue
        reasons = review_reasons(row)
        row["needs_review"] = bool(reasons)
        row["review_reasons"] = "; ".join(reasons)


def build_summary(args, jd_label: str, rows: list[dict], started: float) -> dict:
    scored = [r for r in rows if r.get("mirror_score") is not None]
    tokens = sum(r.pop("_usage", 0) for r in rows)
    models = {r.pop("_model", None) for r in rows} - {None}
    return {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "job_description": jd_label,
        "resumes": len(rows),
        "needs_human_review": sum(1 for r in rows if r.get("needs_review")),
        "errors": sum(1 for r in rows if r.get("error")),
        "mean_mirror_score": round(sum(r["mirror_score"] for r in scored) / len(scored), 1) if scored else None,
        "typesafe_model": ", ".join(sorted(models)) or args.model,
        "typesafe_input_tokens": tokens,
        "typesafe_cost_usd": round(tokens * q.USD_PER_MILLION_INPUT_TOKENS / 1e6, 5),
        "seconds": round(time.time() - started, 1),
    }


def print_table(rows: list[dict], summary: dict, color: bool) -> None:
    c = (lambda code, s: f"{code}{s}{OFF}") if color else (lambda code, s: s)
    print(c(BOLD, f"\n{'Review':<7} {'File':<30} {'Mirror':>6} {'z':>6}  Evidence"))
    for row in rows:
        review = c(RED, "YES    ") if row.get("needs_review") else "       "
        if row.get("mirror_score") is None:
            print(f"{review} {row['file']:<30} {'':>6} {'':>6}  {c(RED, 'error: ' + row.get('error', ''))}")
            continue
        first = (row.get("evidence") or "").split("\n")[0].lstrip("- ")
        print(f"{review} {row['file']:<30} {row['mirror_score']:>6} {row['pool_z']:>6}  {first[:70]}")
    print(c(BOLD, f"\n{summary['resumes']} resumes, {summary['needs_human_review']} need human review")
          + (", " + c(RED, f"{summary['errors']} could not be read") if summary["errors"] else "")
          + f"  |  Jev {summary['typesafe_input_tokens']} tokens ~${summary['typesafe_cost_usd']}"
          f" in {summary['seconds']}s")
    if "labels" in summary:
        print(c(BOLD, "Labels: ") + json.dumps(summary["labels"]))
    print(c(DIM, "\n" + DISCLAIMER))


def merge_only(args) -> None:
    out_dir = Path(args.out)
    data = json.loads((out_dir / "results.json").read_text())
    rows = data["results"]
    merged = merge_notes(rows, args.merge_notes)
    mark_review(rows)
    data["summary"]["needs_human_review"] = sum(1 for r in rows if r.get("needs_review"))
    jd_text = data.get("job_description_text", "")
    paths = write_all(out_dir, rows, data["summary"], jd_text, data["summary"].get("manifest_columns", []))
    print(f"{GREEN}merged {merged} notes into {paths.get('xlsx') or paths['csv']}{OFF}")


def main() -> None:
    args = parse_args()
    if args.merge_notes:
        if not args.out:
            sys.exit("--merge-notes needs --out pointing at the existing results folder")
        return merge_only(args)
    if not (args.jd and args.resumes):
        sys.exit("--jd and --resumes are required (or --merge-notes with --out)")
    started = time.time()
    out_dir = Path(args.out) if args.out else DEFAULT_OUT_ROOT / f"{datetime.now():%Y%m%d-%H%M%S}"
    jd_label, jd_text = load_job_description(args.jd)
    jd_text = jd_text.strip()[:q.MAX_CHARS_PER_DOC]
    resume_paths = collect_resumes(args.resumes)
    if not resume_paths:
        sys.exit("no supported resume files found")
    dim, off = ("", "") if args.no_color else (DIM, OFF)
    print(f"{dim}{len(resume_paths)} resumes vs {jd_label} using {args.model}{off}")
    texts, errors = load_texts(resume_paths)
    rows = run_batch(args, jd_text, texts) + errors
    rows.sort(key=lambda r: (r.get("mirror_score") is None, -(r.get("mirror_score") or 0)))
    mark_review(rows)
    note_status = add_llm_notes(args, out_dir, jd_text, texts, rows) if args.llm_notes else None
    mark_review(rows)  # again, so an API provider's review flag is included
    extra_columns = apply_manifest(rows, args.manifest) if args.manifest else []
    summary = build_summary(args, jd_label, rows, started)
    if extra_columns:
        summary["manifest_columns"] = extra_columns
    if note_status:
        summary["llm_notes"] = note_status
    if args.labels:
        summary["labels"] = evaluate_labels(rows, args.labels)
    paths = write_all(out_dir, rows, summary, jd_text, extra_columns)
    _stash_jd(paths["json"], jd_text)
    print_table(rows, summary, color=not args.no_color)
    bold = "" if args.no_color else BOLD
    main_out = paths.get("xlsx") or paths["csv"]
    print(f"\n{bold}Output:{off} {main_out}  (also {', '.join(p.name for p in paths.values() if p != main_out)})")


def _stash_jd(json_path: Path, jd_text: str) -> None:
    """Keep the JD text in results.json so --merge-notes can rebuild the sheet."""
    data = json.loads(json_path.read_text())
    data["job_description_text"] = jd_text
    json_path.write_text(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
