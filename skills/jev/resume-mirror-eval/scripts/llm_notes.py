"""Optional anecdotal notes from a generative model.

Jev gives calibrated numbers. This module adds the "why" a recruiter can read:
which phrases mirror the posting, whether the specifics look lived-in, and what
to verify on a phone screen. Three providers so the skill is not tied to one
vendor:

  anthropic  Official Anthropic SDK, model claude-opus-5 by default.
  openai     Any OpenAI-compatible chat endpoint (OpenAI, OpenRouter, Ollama...).
             Set OPENAI_API_KEY, optionally OPENAI_BASE_URL, and pass --llm-model.
  agent      No API call. Writes notes-request.json so the coding agent running
             this skill can write the notes itself, then re-run with
             --merge-notes to fold them into the spreadsheet.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

SYSTEM_PROMPT = (
    "You are helping a recruiter scan a statistical screen of many resumes against "
    "one job description. You will see the job description, one resume, scores, and "
    "evidence bullets already computed in code. Reply with 2 to 4 bullet points and "
    "nothing else: no summary sentence, no heading, no markdown beyond a leading "
    "'- ' per line. Each bullet is one short factual observation a human could "
    "verify by reading the two documents, for example which requirement bullets are "
    "restated as experience, whether employers, dates, systems and numbers read as "
    "lived detail or as generic filler, or which claim to probe on a phone screen. "
    "Do not repeat the code evidence bullets. Never state or guess whether the "
    "candidate used AI, and never comment on whether the candidate is a good fit "
    "for the role; only on the file's relationship to the posting. After the bullets, add one final line that is exactly "
    "'review: yes' if anything you saw deserves a human's eyes before this resume "
    "is ranked, otherwise exactly 'review: no'."
)


def split_flag(text: str) -> tuple[str, bool | None]:
    """Strip the trailing 'review: yes|no' line and return (bullets, flag)."""
    lines = [line.rstrip() for line in text.strip().splitlines() if line.strip()]
    if lines and lines[-1].lower().startswith("review:"):
        flag = "yes" in lines[-1].lower()
        return "\n".join(lines[:-1]), flag
    return "\n".join(lines), None

ANTHROPIC_DEFAULT_MODEL = "claude-opus-5"


def note_prompt(jd_text: str, resume_text: str, row: dict) -> str:
    scores = {k: row[k] for k in (
        "mirror_score", "phrase_overlap", "longest_span_words",
        "phrasing_mirror_raw", "concrete_specifics_raw") if k in row}
    return (f"JOB DESCRIPTION:\n{jd_text}\n\nRESUME ({row['file']}):\n{resume_text}"
            f"\n\nSCORES:\n{json.dumps(scores, indent=2)}"
            f"\n\nCODE EVIDENCE:\n{row.get('evidence') or '- none'}")


def anthropic_note(prompt: str, model: str | None) -> str:
    try:
        import anthropic
    except ImportError:
        if not _pip_install("anthropic"):
            return "[llm error: anthropic SDK not installed and pip install failed]"
        import anthropic
    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=model or ANTHROPIC_DEFAULT_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.RateLimitError as err:
        return f"[llm error: rate limited: {err}]"
    except anthropic.APIStatusError as err:
        return f"[llm error: HTTP {err.status_code}: {err.message}]"
    except anthropic.APIConnectionError as err:
        return f"[llm error: connection: {err}]"
    if response.stop_reason == "refusal":
        return "[llm declined to answer]"
    return " ".join(b.text for b in response.content if b.type == "text").strip()


def openai_note(prompt: str, model: str | None) -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return "[llm error: OPENAI_API_KEY not set]"
    if not model:
        return "[llm error: --llm-model is required for the openai provider]"
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    body = json.dumps({"model": model, "messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}]}).encode()
    request = urllib.request.Request(
        f"{base}/chat/completions", data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()
    except Exception as err:  # noqa: BLE001 - surfaced in the sheet, not fatal
        return f"[llm error: {err}]"


def _pip_install(package: str) -> bool:
    """Install into whatever Python is running us (the private venv, normally)."""
    import subprocess
    import sys

    result = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                             "--disable-pip-version-check", package], capture_output=True)
    return result.returncode == 0


PROVIDERS = {"anthropic": anthropic_note, "openai": openai_note}


def write_agent_request(out_dir: Path, jd_text: str, texts: dict[str, str],
                        rows: list[dict]) -> Path:
    """Dump everything an agent needs to write the notes without any API key."""
    payload = {
        "instructions": SYSTEM_PROMPT + " Write one note per entry in `resumes` (bullets "
        "plus the final review line) and save them as a JSON object mapping file name "
        "to note text, then re-run analyze.py with --merge-notes <that file> and the "
        "same --out folder.",
        "job_description": jd_text,
        "resumes": [{"file": row["file"], "scores": {k: row.get(k) for k in (
            "mirror_score", "phrasing_mirror_raw", "concrete_specifics_raw")},
            "code_evidence": row.get("evidence", ""),
            "text": texts[row["file"]]} for row in rows],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "notes-request.json"
    path.write_text(json.dumps(payload, indent=2))
    return path


def merge_notes(rows: list[dict], notes_path: Path) -> int:
    notes = json.loads(notes_path.read_text())
    merged = 0
    for row in rows:
        if row["file"] in notes:
            row["llm_notes"], row["llm_flag"] = split_flag(notes[row["file"]])
            merged += 1
    return merged
