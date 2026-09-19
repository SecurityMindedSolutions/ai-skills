"""Plain-language evidence bullets, computed in code, one list per resume.

These are what a reviewer scans first: "2 JD sentences appear verbatim",
"14 of 16 JD acronyms present (88%)". Each bullet is a fact a human can check
against the two documents. No model is involved.
"""

from __future__ import annotations

import re

from lexical import STOPWORDS, tokenize

ACRONYM_RE = re.compile(r"\b([A-Z][A-Z0-9/+#.-]{1,9})s?\b")  # SLOs -> SLO
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+|(?:^|\n)\s*[-*•]\s*")
NOT_ACRONYMS = {"AND", "OR", "THE", "FOR", "WITH", "YOU", "WE", "US", "OUR", "A", "I", "II", "III"}


def acronyms(text: str) -> set[str]:
    return {a for a in ACRONYM_RE.findall(text) if a not in NOT_ACRONYMS and any(c.isalpha() for c in a)}


def _normalize(sentence: str) -> str:
    return " ".join(tokenize(sentence))


def jd_sentences(jd_text: str, min_words: int = 6) -> list[str]:
    """JD sentences and bullet lines with enough content words to be distinctive."""
    out = []
    for raw in SENTENCE_SPLIT.split(jd_text):
        words = tokenize(raw)
        if len(words) >= min_words and sum(1 for w in words if w not in STOPWORDS) >= 3:
            out.append(raw.strip())
    return out


def verbatim_sentences(jd_text: str, resume_text: str) -> list[str]:
    """JD sentences that appear in the resume with only punctuation/case changed."""
    haystack = _normalize(resume_text)
    return [s for s in jd_sentences(jd_text) if _normalize(s) in haystack]


def shared_span_text(jd_text: str, resume_text: str, max_words: int = 18) -> str:
    """The longest run of consecutive words shared by both documents, as text."""
    from difflib import SequenceMatcher

    a, b = tokenize(jd_text), tokenize(resume_text)
    m = SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    words = a[m.a:m.a + m.size]
    return " ".join(words[:max_words]) + (" ..." if len(words) > max_words else "")


def evidence_bullets(jd_text: str, resume_text: str, lexical: dict, semantic: dict) -> tuple[list[str], dict]:
    """Return (bullets, extra_metrics). Bullets only mention things worth a look."""
    bullets: list[str] = []
    extra: dict = {}
    hits = verbatim_sentences(jd_text, resume_text)
    extra["verbatim_sentences"] = len(hits)
    if hits:
        sample = hits[0][:90] + ("..." if len(hits[0]) > 90 else "")
        noun = "JD sentences appear" if len(hits) != 1 else "JD sentence appears"
        bullets.append(f"{len(hits)} {noun} verbatim, e.g. \"{sample}\"")
    span = lexical["longest_span_words"]
    if span >= 7:
        bullets.append(f"Longest shared word run is {span} words: \"{shared_span_text(jd_text, resume_text)}\"")
    jd_acr, resume_acr = acronyms(jd_text), acronyms(resume_text)
    shared = jd_acr & resume_acr
    extra["acronym_coverage"] = round(len(shared) / len(jd_acr), 3) if jd_acr else None
    if jd_acr and len(jd_acr) >= 4:
        pct = round(100 * len(shared) / len(jd_acr))
        if pct >= 80:
            bullets.append(f"{len(shared)} of {len(jd_acr)} JD acronyms present ({pct}%)"
                           + (", all of them" if pct == 100 else ""))
    if lexical["phrase_overlap"] >= 0.15:
        bullets.append(f"{round(100 * lexical['phrase_overlap'])}% of JD 4-word phrases reused verbatim")
    if lexical["order_echo"] >= 0.7:
        bullets.append("Matched JD terms appear in the same order as the posting")
    if semantic.get("posting_language_leak", 0) >= 0.5:
        bullets.append("Contains job-posting phrasing (e.g. 'ideal candidate', 'you will')")
    if semantic.get("concrete_specifics_raw", 3) <= 1.0:
        bullets.append("Few concrete specifics: employers, dates, numbers or named systems are thin")
    if semantic.get("career_consistency", 1) < 0.5:
        bullets.append("Claimed skills look out of step with the listed roles or seniority")
    if semantic.get("requirement_echo_raw", 0) >= 2.5 and semantic.get("concrete_specifics_raw", 3) < 2:
        bullets.append("Claims nearly every requirement, including niche ones, without matching detail")
    return bullets, extra
