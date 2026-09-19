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
        elif spec["type"] == "choice":
            probs = answer["probabilities"]
            out[key] = round(probs.get("generated_from_posting", 0.0)
                             + 0.5 * probs.get("tailored_wording", 0.0), 4)
            out[f"{key}_choice"] = answer["choice"]
            out[f"{key}_confidence"] = round(answer["confidence"], 3)
            for option, p in probs.items():
                out[f"p_{option}"] = round(p, 3)
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


def verdict(score: float) -> str:
    for threshold, label in q.VERDICT_THRESHOLDS:
        if score >= threshold:
            return label
    return q.VERDICT_THRESHOLDS[-1][1]


def fit_signal(lexical: dict, semantic: dict) -> float:
    """How well the resume covers the JD, reported separately from suspicion so
    a reader can tell 'strong fit, own words' from 'strong fit, copied words'."""
    return round(100 * (0.5 * lexical["keyword_coverage"]
                        + 0.5 * semantic["requirement_echo"]), 1)


def review_reasons(row: dict) -> list[str]:
    """Short reason codes for the 'Needs human review' column, from REVIEW_TRIGGERS."""
    t = q.REVIEW_TRIGGERS
    reasons = []
    if t["verdict_not_low"] and row.get("verdict") in ("moderate", "high"):
        reasons.append(f"{row['verdict']} mirror score")
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
