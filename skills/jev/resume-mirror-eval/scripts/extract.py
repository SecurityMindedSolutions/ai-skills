"""Turn resume and job description files into plain text.

Supports .pdf, .docx, .txt and .md. Anything else is skipped with a warning
so a stray .DS_Store or image in a shared folder does not abort the run.

Dependencies are kept to a minimum on purpose: .docx is parsed with the
standard library, and .pdf uses pypdf when available (bootstrap.py installs it) or the
`pdftotext` command as a fallback.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

SUPPORTED = {".pdf", ".docx", ".txt", ".md", ".markdown"}


def read_document(path: Path) -> str:
    """Return the text of one supported file, or raise ValueError."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix == ".docx":
        return _read_docx(path)
    if suffix in {".txt", ".md", ".markdown"}:
        return path.read_text(encoding="utf-8", errors="replace")
    raise ValueError(f"unsupported file type: {path.name}")


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return _read_pdf_cli(path)
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _read_pdf_cli(path: Path) -> str:
    """Fallback when pypdf is not installed: poppler's pdftotext if present."""
    if not shutil.which("pdftotext"):
        raise ValueError("PDF support needs pypdf (see bootstrap note above) or the pdftotext command")
    result = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                            capture_output=True, text=True, check=True)
    return result.stdout


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _read_docx(path: Path) -> str:
    """A .docx is a zip; the text lives in word/document.xml as w:p paragraphs."""
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    lines = []
    for paragraph in root.iter(f"{_W}p"):
        text = "".join(t.text or "" for t in paragraph.iter(f"{_W}t"))
        if text.strip():
            lines.append(text)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines))


def collect_resumes(sources: list[str]) -> list[Path]:
    """Expand files and directories into a sorted list of supported files."""
    found: list[Path] = []
    for source in sources:
        path = Path(source).expanduser()
        if path.is_dir():
            found.extend(p for p in sorted(path.rglob("*")) if _is_resume(p))
        elif path.is_file() and _is_resume(path):
            found.append(path)
        else:
            print(f"warning: skipping {source} (not a supported file or folder)",
                  file=sys.stderr)
    return found


def _is_resume(path: Path) -> bool:
    return (path.is_file()
            and path.suffix.lower() in SUPPORTED
            and not path.name.startswith("."))


def load_job_description(source: str) -> tuple[str, str]:
    """Return (label, text) for a JD given as a file, a folder, or '-' for stdin."""
    if source == "-":
        return "stdin", sys.stdin.read()
    path = Path(source).expanduser()
    if path.is_dir():
        candidates = [p for p in sorted(path.iterdir()) if _is_resume(p)]
        if len(candidates) != 1:
            names = ", ".join(p.name for p in candidates) or "none"
            raise SystemExit(
                f"--jd folder must contain exactly one supported file, found: {names}")
        path = candidates[0]
    if not path.is_file():
        raise SystemExit(f"--jd not found: {source}")
    return path.name, read_document(path)
