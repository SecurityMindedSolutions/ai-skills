#!/usr/bin/env python3
"""The reference gate: one function a backend calls before forwarding a prompt.

    from gate import check_prompt
    verdict = check_prompt(user_input, app_description)
    if verdict["decision"] == "block": ...

Or from a shell, for a single prompt:

    python3 gate.py "<prompt>" ["<app description>" ["earlier turn 1" "earlier turn 2" ...]]

Everything that decides is in questions.py. This file only asks Jev, applies
the weights and thresholds, and returns a dict a caller can log and act on.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import questions as q  # noqa: E402
from code_signals import code_signals  # noqa: E402
from jev import JevClient, load_api_key  # noqa: E402

DEFAULT_APP = (
    "A customer support assistant for a payments reconciliation product. It "
    "answers questions about invoices, settlements and reports for the signed-in "
    "user's own account, and can look up that user's invoices. It has no other "
    "tools and must not act on other accounts."
)

_client: JevClient | None = None


def _get_client(model: str = q.MODEL) -> JevClient:
    global _client
    if _client is None or _client.model != model:
        _client = JevClient(load_api_key(), model)
    return _client


def signals_from(answers: dict) -> dict:
    """Flatten Jev's answers into named 0..1 signals plus the raw bits worth logging."""
    out: dict = {}
    for key, spec in q.QUESTIONS.items():
        a = answers[key]
        if spec["type"] == "noul":
            out[key] = round(a["noul"], 3)
        elif spec["type"] == "score":
            top = len(spec["criteria"]) - 1
            out[key] = round(a["score"] / top, 3)
            out[f"{key}_raw"] = round(a["score"], 2)
            out[f"{key}_confidence"] = round(a["confidence"], 3)
        elif spec["type"] == "choice":
            out[f"{key}"] = a["choice"]
            out[f"{key}_confidence"] = round(a["confidence"], 3)
    return out


def risk_score(signals: dict) -> float:
    return round(100 * sum(w * signals[name] for name, w in q.WEIGHTS.items()), 1)


ORDER = {"allow": 0, "review": 1, "block": 2}


def decide(signals: dict, risk: float, code: dict[str, str]) -> str:
    """Apply the rules in questions.py in order: block, then review, else allow.
    Code signals set a floor; Jev's rules can raise it, never lower it."""
    floor = max((q.CODE_SIGNAL_DECISIONS[name] for name in code), key=ORDER.get, default="allow")
    if floor == "review" and signals["format_injection"] >= q.CODE_PLUS_JEV_BLOCK \
            and {"fake_turn_markers", "chat_template_tokens"} & set(code):
        floor = "block"
    return max(_jev_decision(signals, risk), floor, key=ORDER.get)


def _jev_decision(signals: dict, risk: float) -> str:
    sev, conf = signals["manipulation_severity_raw"], signals["manipulation_severity_confidence"]
    nouls = [signals[n] for n, spec in q.QUESTIONS.items() if spec["type"] == "noul"]
    strongest = max(nouls)
    if risk >= q.BLOCK_AT:
        return "block"
    if sev >= q.SEVERITY_BLOCK[0] and conf >= q.SEVERITY_BLOCK[1]:
        return "block"
    if strongest >= q.HARD_SIGNAL_BLOCK and sev >= q.HARD_SIGNAL_MIN_SEVERITY:
        return "block"
    if risk >= q.REVIEW_AT or strongest >= q.REVIEW_SIGNAL:
        return "review"
    if conf < q.MIN_CONFIDENCE_TO_ALLOW and sev >= q.LOW_CONFIDENCE_REVIEW_MIN_SEVERITY:
        return "review"
    return "allow"


def fired(signals: dict) -> list[str]:
    """Names of the noul signals at or above SIGNAL_THRESHOLD, strongest first."""
    hits = [(name, signals[name]) for name, spec in q.QUESTIONS.items()
            if spec["type"] == "noul" and signals[name] >= q.SIGNAL_THRESHOLD]
    return [name for name, _ in sorted(hits, key=lambda h: -h[1])]


def check_prompt(user_input: str, app: str = DEFAULT_APP, model: str = q.MODEL,
                 recent_turns: list[str] | None = None) -> dict:
    """Ask Jev about one prompt and return a decision the caller can act on.
    `recent_turns` is the last few user messages before this one, oldest first,
    when the caller has them; it lets split-across-turns attacks be seen."""
    client = _get_client(model)
    code = code_signals(user_input)
    started = time.perf_counter()
    response = client.evaluate(
        {"app": app, "user_input": user_input[:q.MAX_CHARS_PER_PROMPT],
         "recent_turns": [t[:2000] for t in (recent_turns or [])[-q.MAX_RECENT_TURNS:]]},
        q.QUESTIONS)
    latency_ms = round(1000 * (time.perf_counter() - started))
    signals = signals_from(response["answers"])
    risk = risk_score(signals)
    return {
        "decision": decide(signals, risk, code),
        "risk": risk,
        "attack_type": signals["attack_type"],
        "signals": fired(signals),
        "code_signals": code,
        "detail": signals,
        "model": response["model"],
        "input_tokens": response["usage"]["input_tokens"],
        "latency_ms": latency_ms,
    }


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit('usage: gate.py "<prompt>" [app description]')
    app = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_APP
    history = sys.argv[3:]  # optional earlier user turns, oldest first
    print(json.dumps(check_prompt(sys.argv[1], app, recent_turns=history), indent=2))


if __name__ == "__main__":
    main()
