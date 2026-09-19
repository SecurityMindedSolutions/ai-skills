"""Combine lexical metrics and Jev answers into one 0..100 mirror score.

All weights and thresholds come from questions.py. Nothing here is tuned
inline, so a reviewer can change behavior without reading this file.
"""

from __future__ import annotations

import questions as q


def semantic_signals(answers: dict) -> dict:
    """Flatten Jev answers into named 0..1 signals plus raw values for the report."""
    out: dict = {}
    for key, spec in q.QUESTIONS.items():
        answer = answers[key]
        if spec["type"] == "score":
            top = len(spec["criteria"]) - 1
            out[key] = round(answer["score"] / top, 4)
            out[f"{key}_raw"] = round(answer["score"], 3)
            out[f"{key}_confidence"] = round(answer["confidence"], 3)
        elif spec["type"] == "noul":
            out[key] = round(answer["noul"], 4)
    return out


def weighted(signals: dict, weights: dict, inverted: set[str] = frozenset()) -> float:
    total = 0.0
    for name, weight in weights.items():
        value = signals[name]
        if name in inverted:
            value = 1.0 - value
        total += weight * value
    return total


def mirror_score(lexical: dict, semantic: dict) -> dict:
    lex = weighted(lexical, q.LEXICAL_WEIGHTS)
    sem = weighted(semantic, q.SEMANTIC_WEIGHTS, q.INVERTED_SIGNALS)
    combined = q.GROUP_WEIGHTS["lexical"] * lex + q.GROUP_WEIGHTS["semantic"] * sem
    return {
        "lexical_score": round(100 * lex, 1),
        "semantic_score": round(100 * sem, 1),
        "mirror_score": round(100 * combined, 1),
    }


def review_reasons(row: dict) -> list[str]:
    """Short reason codes for the 'Needs human review' column, from REVIEW_TRIGGERS."""
    t = q.REVIEW_TRIGGERS
    reasons = []
    if t["score"] and row.get("mirror_score", 0) >= q.REVIEW_SCORE:
        reasons.append(f"mirror score {row['mirror_score']} (threshold {q.REVIEW_SCORE})")
    if t["pool_outlier"] and row.get("pool_outlier"):
        reasons.append("batch outlier")
    if t["any_code_evidence"] and row.get("evidence"):
        reasons.append("code evidence")
    if row.get("posting_language_leak", 0) >= t["posting_language_leak"]:
        reasons.append("posting language")
    if row.get("generic_template", 0) >= t["generic_template"]:
        reasons.append("generic text")
    if row.get("career_consistency", 1) < t["career_consistency_below"]:
        reasons.append("career inconsistency")
    if t["llm_flag"] and row.get("llm_flag"):
        reasons.append("LLM flag")
    return reasons
