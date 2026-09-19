"""Write results as .xlsx, .csv and .json, sorted by mirror score."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

DISCLAIMER = (
    "RESEARCH PROOF OF CONCEPT. The mirror score is TypeSafe Jev's measure of how closely "
    "a resume's wording tracks a job description. They do not determine whether a person used AI and "
    "make no decision about any candidate. The 'Needs human review' column exists so "
    "that a person reads the flagged rows: this is a tool for directing human review, "
    "not a substitute for it. Any use must comply with the laws, regulations and "
    "policies that apply to you; automated tools in hiring are regulated in many "
    "jurisdictions. Consult your legal team before using this on real applicants."
)

# What a recruiter sees: the Results sheet and results.csv. (header, key, width)
SIMPLE_COLUMNS = [
    ("Needs human review", "needs_review", 12),
    ("File", "file", 34),
    ("Mirror score (Jev)", "mirror_score", 16),
    ("Text match analysis (code)", "evidence", 80),
    ("AI analysis (agent)", "llm_notes", 80),
]

# Everything: the Details sheet and results-detail.csv.
COLUMNS = [
    ("Needs human review", "needs_review", 12),
    ("File", "file", 34),
    ("Mirror score (Jev)", "mirror_score", 16),
    ("Batch z", "pool_z", 8),
    ("Batch outlier", "pool_outlier", 12),
    ("Phrase overlap", "phrase_overlap", 13),
    ("Longest span (words)", "longest_span_words", 18),
    ("Order echo", "order_echo", 10),
    ("TF-IDF cos", "tfidf_cosine", 10),
    ("Keyword cov", "keyword_coverage", 11),
    ("Phrasing mirror (0-3)", "phrasing_mirror_raw", 18),
    ("Requirement echo (0-3)", "requirement_echo_raw", 19),
    ("Specifics (0-3)", "concrete_specifics_raw", 14),
    ("Generic P", "generic_template", 9),
    ("Posting leak P", "posting_language_leak", 13),
    ("Career consistent P", "career_consistency", 17),
    ("Verbatim JD sentences", "verbatim_sentences", 19),
    ("Acronym cov", "acronym_coverage", 11),
    ("Words", "resume_words", 7),
    ("Text match analysis (code)", "evidence", 70),
    ("AI analysis (agent)", "llm_notes", 70),
    ("Error", "error", 40),
]

REVIEW_FILL = "F8CBAD"


def columns_for(base: list[tuple], extra: list[str]) -> list[tuple]:
    """Columns with any manifest columns (candidate ids, source links) after File."""
    cols = list(base)
    for i, name in enumerate(extra):
        cols.insert(2 + i, (name.replace("_", " ").capitalize(), name, 24))
    return cols


def write_all(out_dir: Path, rows: list[dict], summary: dict, jd_text: str,
              extra: list[str] | None = None) -> dict[str, Path]:
    """Always writes JSON and the two CSVs. Writes XLSX when openpyxl is importable."""
    simple = columns_for(SIMPLE_COLUMNS, extra or [])
    detail = columns_for(COLUMNS, extra or [])
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {"json": out_dir / "results.json", "csv": out_dir / "results.csv",
             "detail_csv": out_dir / "results-detail.csv"}
    paths["json"].write_text(json.dumps(
        {"summary": summary, "disclaimer": DISCLAIMER, "results": rows}, indent=2))
    _write_csv(paths["csv"], rows, simple)
    _write_csv(paths["detail_csv"], rows, detail)
    try:
        import openpyxl  # noqa: F401 - probe only
    except ImportError:
        print("note: openpyxl not installed, skipping results.xlsx (see bootstrap note above)",
              file=sys.stderr)
        return paths
    paths["xlsx"] = out_dir / "results.xlsx"
    _write_xlsx(paths["xlsx"], rows, summary, jd_text, simple, detail)
    return paths


def _write_csv(path: Path, rows: list[dict], columns: list[tuple]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header for header, _, _ in columns)
        for row in rows:
            writer.writerow(_cell(row, key) for _, key, _ in columns)


def _cell(row: dict, key: str):
    """Flags show as YES or blank; there is no 'no' to sort past."""
    value = row.get(key, "")
    if key in ("needs_review", "pool_outlier"):
        return "YES" if value else ""
    return value


def _write_xlsx(path: Path, rows: list[dict], summary: dict, jd_text: str,
                simple: list[tuple], detail: list[tuple]) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    book = Workbook()
    bold = Font(bold=True)
    _results_sheet(book.active, "Results", rows, simple, bold)
    _results_sheet(book.create_sheet("Details"), "Details", rows, detail, bold)
    _summary_sheet(book, summary, bold)
    _text_sheet(book, "Job description", jd_text)
    _text_sheet(book, "Read me", DISCLAIMER + "\n\n" + _column_guide())
    book.save(path)


def _results_sheet(sheet, title: str, rows: list[dict], columns: list[tuple], bold) -> None:
    from openpyxl.styles import Alignment, PatternFill
    from openpyxl.utils import get_column_letter

    sheet.title = title
    for col, (header, _, width) in enumerate(columns, start=1):
        sheet.cell(row=1, column=col, value=header).font = bold
        sheet.column_dimensions[get_column_letter(col)].width = width
    for r, row in enumerate(rows, start=2):
        for col, (_, key, _) in enumerate(columns, start=1):
            cell = sheet.cell(row=r, column=col, value=_cell(row, key))
            if key in ("llm_notes", "evidence"):
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        if row.get("needs_review"):
            sheet.cell(row=r, column=1).fill = PatternFill("solid", fgColor=REVIEW_FILL)
            sheet.cell(row=r, column=1).font = bold
    sheet.freeze_panes = "C2"
    sheet.auto_filter.ref = sheet.dimensions


def _summary_sheet(book, summary: dict, bold) -> None:
    sheet = book.create_sheet("Summary")
    sheet.column_dimensions["A"].width = 28
    sheet.column_dimensions["B"].width = 60
    for r, (key, value) in enumerate(summary.items(), start=1):
        sheet.cell(row=r, column=1, value=key).font = bold
        scalar = value if isinstance(value, (str, int, float, bool)) or value is None else json.dumps(value)
        sheet.cell(row=r, column=2, value=scalar)


def _text_sheet(book, title: str, text: str) -> None:
    from openpyxl.styles import Alignment

    sheet = book.create_sheet(title)
    sheet.column_dimensions["A"].width = 120
    for r, line in enumerate(text.splitlines() or [""], start=1):
        cell = sheet.cell(row=r, column=1, value=line)
        cell.alignment = Alignment(wrap_text=True, vertical="top")


def _column_guide() -> str:
    return "\n".join([
        "Column guide",
        "Three separate methods, one column each: Mirror score (Jev) is TypeSafe's decision model; Text match analysis (code) is exact string counting with no AI; AI analysis (agent) is the AI agent's own reading. None feeds another.",
        "Results sheet / results.csv: the five columns a reviewer needs. Details sheet / results-detail.csv: every statistic and Jev answer behind the score.",
        "Needs human review: YES when any signal fired (mirror score at or above the review threshold, batch outlier, a code evidence bullet, a Jev flag, or the notes' review flag). Blank otherwise. It means 'a person should look at this file', not anything about the candidate.",
        "Mirror score (Jev): 0-100, TypeSafe Jev's answers to six fixed questions, weighted as set in questions.py. Deterministic for the same input. Higher means the file's wording tracks the posting more closely. No high/medium/low grades on purpose.",
        "Batch z: how many standard deviations this file sits above or below the batch mean. Batch outlier: YES past the threshold in questions.py.",
        "Text match analysis (code): sentences filled in by the script from exact counts (verbatim sentences, longest shared word run, acronym and phrase reuse, order). No AI writes or reads this column. Not scored. Raw counts are in the Details columns.",
        "AI analysis (agent): the AI agent's own observations after reading the resume against the posting. Judgment, not counting. Not scored; only its final review yes/no feeds the review flag.",
    ])
