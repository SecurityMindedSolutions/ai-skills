"""Write results as .xlsx, .csv and .json, sorted by mirror score."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

DISCLAIMER = (
    "RESEARCH PROOF OF CONCEPT. These scores are statistical signals about how "
    "closely a resume's wording tracks a job description. They are not evidence "
    "that a candidate used AI, and they must not be used to reject anyone "
    "automatically. A candidate whose experience genuinely matches the role will "
    "score higher than average. Use of AI tools in hiring is regulated in many "
    "jurisdictions (for example the EU AI Act, NYC Local Law 144, Illinois AIVIA, "
    "Colorado SB 24-205 and US EEOC guidance). Anyone using this for real hiring "
    "decisions is responsible for complying with the laws that apply to them and "
    "should consult their own legal counsel first."
)

# Column order for the spreadsheet and CSV. (header, key, width)
COLUMNS = [
    ("Needs human review", "needs_review", 12),
    ("File", "file", 34),
    ("Mirror score", "mirror_score", 12),
    ("Verdict", "verdict", 10),
    ("Pool z", "pool_z", 8),
    ("Outlier", "pool_outlier", 8),
    ("Fit signal", "fit_signal", 10),
    ("Lexical", "lexical_score", 9),
    ("Semantic", "semantic_score", 9),
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
    ("Overall read", "overall_read_choice", 22),
    ("Read confidence", "overall_read_confidence", 14),
    ("Verbatim JD sentences", "verbatim_sentences", 19),
    ("Acronym cov", "acronym_coverage", 11),
    ("Words", "resume_words", 7),
    ("Evidence (code)", "evidence", 70),
    ("LLM notes", "llm_notes", 70),
    ("Error", "error", 40),
]

VERDICT_FILL = {"high": "F8CBAD", "moderate": "FFE699", "low": "C6E0B4"}


def columns_for(extra: list[str]) -> list[tuple]:
    """Base columns with any manifest columns (candidate ids, source links) after File."""
    cols = list(COLUMNS)
    for i, name in enumerate(extra):
        cols.insert(2 + i, (name.replace("_", " ").capitalize(), name, 24))
    return cols


def write_all(out_dir: Path, rows: list[dict], summary: dict, jd_text: str,
              extra: list[str] | None = None) -> dict[str, Path]:
    """Always writes JSON and CSV. Writes XLSX when openpyxl is importable."""
    columns = columns_for(extra or [])
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {"json": out_dir / "results.json", "csv": out_dir / "results.csv"}
    paths["json"].write_text(json.dumps(
        {"summary": summary, "disclaimer": DISCLAIMER, "results": rows}, indent=2))
    _write_csv(paths["csv"], rows, columns)
    try:
        import openpyxl  # noqa: F401 - probe only
    except ImportError:
        print("note: openpyxl not installed, skipping results.xlsx (see bootstrap note above)",
              file=sys.stderr)
        return paths
    paths["xlsx"] = out_dir / "results.xlsx"
    _write_xlsx(paths["xlsx"], rows, summary, jd_text, columns)
    return paths


def _write_csv(path: Path, rows: list[dict], columns: list[tuple]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header for header, _, _ in columns)
        for row in rows:
            writer.writerow(row.get(key, "") for _, key, _ in columns)


def _write_xlsx(path: Path, rows: list[dict], summary: dict, jd_text: str, columns: list[tuple]) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    book = Workbook()
    sheet = book.active
    sheet.title = "Results"
    bold = Font(bold=True)
    for col, (header, _, width) in enumerate(columns, start=1):
        cell = sheet.cell(row=1, column=col, value=header)
        cell.font = bold
        sheet.column_dimensions[get_column_letter(col)].width = width
    for r, row in enumerate(rows, start=2):
        for col, (_, key, _) in enumerate(columns, start=1):
            cell = sheet.cell(row=r, column=col, value=row.get(key, ""))
            if key in ("llm_notes", "evidence"):
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        fill = VERDICT_FILL.get(row.get("verdict", ""))
        if fill:
            for key in ("mirror_score", "verdict"):
                col = next(i for i, (_, k, _) in enumerate(columns, start=1) if k == key)
                sheet.cell(row=r, column=col).fill = PatternFill("solid", fgColor=fill)
        if row.get("needs_review"):
            sheet.cell(row=r, column=1).fill = PatternFill("solid", fgColor=VERDICT_FILL["high"])
            sheet.cell(row=r, column=1).font = bold
    sheet.freeze_panes = "C2"
    sheet.auto_filter.ref = sheet.dimensions

    _summary_sheet(book, summary, bold)
    _text_sheet(book, "Job description", jd_text)
    _text_sheet(book, "Read me", DISCLAIMER + "\n\n" + _column_guide())
    book.save(path)


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
        "Needs human review: TRUE when any signal fired (score bucket, batch outlier, a code evidence bullet, a Jev flag, or the LLM's review flag). It means 'a person should look', not 'this is bad'. The column exists so nobody sorts by score alone.",
        "Mirror score: 0-100 composite. Higher means the wording tracks the JD more closely.",
        "Verdict: high / moderate / low bucket on the mirror score (thresholds in questions.py).",
        "Pool z: how many standard deviations this resume sits above or below the batch mean.",
        "Fit signal: how much of the JD the resume covers. Reported separately so 'strong fit, own words' is distinguishable from 'strong fit, copied words'.",
        "Lexical: code-computed text statistics (verbatim 4-gram overlap, longest shared span, JD-order echo, TF-IDF cosine, keyword coverage).",
        "Semantic: TypeSafe Jev judgments (phrasing mirror, requirement echo, concrete specifics, generic template, posting-language leak, career consistency, overall read).",
        "Evidence (code): deterministic bullets a reviewer can check against the two documents (verbatim JD sentences, shared word runs, acronym coverage, order echo). Not scored; computed from the same statistics as the lexical columns.",
        "LLM notes: optional bullets from a generative model or the host agent. Anecdotal, not scored.",
    ])
