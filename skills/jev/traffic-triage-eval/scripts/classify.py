"""Send one IP profile to Jev and compose the verdict.

    python3 classify.py --events clean.jsonl --ip 1.2.3.4 --app app.md

Prints the profile Jev saw and every answer, for debugging one IP.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import questions as q
from jev import JevClient, load_api_key
from profile import build_profile, group_by_ip, render

DEFAULT_APP = (
    "A small SaaS web application: a React single-page app served from the root, a JSON "
    "API under /api/v1/, static assets under /assets/. It does not run WordPress, PHP, "
    "Java application servers or any CMS."
)

_client: JevClient | None = None


def _get_client(model: str = q.MODEL) -> JevClient:
    global _client
    if _client is None or _client.model != model:
        _client = JevClient(load_api_key(), model)
    return _client


def signals_from(answers: dict) -> dict:
    out: dict = {}
    for key, spec in q.QUESTIONS.items():
        a = answers[key]
        if spec["type"] == "noul":
            out[key] = round(a["noul"], 3)
        elif spec["type"] == "score":
            out[key] = round(a["score"], 2)
            out[f"{key}_confidence"] = round(a["confidence"], 3)
        elif spec["type"] == "choice":
            out[key] = a["choice"]
            out[f"{key}_confidence"] = round(a["confidence"], 3)
            out[f"{key}_probabilities"] = {k: round(v, 3) for k, v in a.get("probabilities", {}).items()}
    return out


def _raise(category: str, floor: str) -> str:
    return max(category, floor, key=q.CATEGORY_ORDER.index)


def decide(s: dict, code: dict[str, str], requests: int) -> tuple[str, list[str], bool]:
    """Category from Jev's choice, raised by code floors; returns
    (category, reasons, attack_floor_fired). The attack floors are the two
    rules where code is certain enough to demand a human look on their own."""
    reasons: list[str] = []
    attack_floor = False
    cat = s["traffic_class"]
    if s["traffic_class_confidence"] < q.CHOICE_MIN_CONFIDENCE:
        reasons.append(f"choice confidence {s['traffic_class_confidence']} below {q.CHOICE_MIN_CONFIDENCE}")
        cat = "unclear"
    if "payloads" in code and s["app_aware"] >= q.PAYLOAD_PLUS_APP_AWARE:
        cat = _raise(cat, "malicious")
        attack_floor = True
        reasons.append("exploit payloads against routes that exist here")
    if s["credential_attack"] >= q.CREDENTIAL_FLOOR and s["app_aware"] >= q.CREDENTIAL_MIN_APP_AWARE \
            and ("waf_denied" in code or "waf_throttled" in code or "auth_volume" in code):
        cat = _raise(cat, "malicious")
        attack_floor = True
        reasons.append("credential attack volume with WAF or auth-volume evidence")
    if ("ua_scanner" in code or "probe_paths" in code or "raw_ip_host" in code or s["wrong_host"] >= q.WRONG_HOST) \
            and s["app_aware"] < q.BACKGROUND_MAX_APP_AWARE and cat in ("unclear", "benign_user", "benign_bot"):
        cat = _raise(cat, "background_scan")
        reasons.append("scanner UA, probe paths or wrong host with no knowledge of this app")
    if requests < q.MIN_REQUESTS_FOR_VERDICT and not code and cat in ("benign_user", "benign_bot"):
        cat = "unclear"
        reasons.append(f"fewer than {q.MIN_REQUESTS_FOR_VERDICT} requests and nothing stood out")
    return cat, reasons, attack_floor


def fired(s: dict) -> list[str]:
    nouls = [(k, s[k]) for k, spec in q.QUESTIONS.items() if spec["type"] == "noul"]
    return [k for k, v in sorted(nouls, key=lambda kv: -kv[1]) if v >= q.SIGNAL_THRESHOLD]


def classify_profile(profile: dict, app: str, window: str, model: str = q.MODEL,
                     max_tokens: int = q.MAX_PROFILE_TOKENS) -> dict:
    trimmed, est = render(profile, max_tokens)
    state = {"app": app, "window": window, "profile": trimmed}
    t0 = time.perf_counter()
    response = _get_client(model).evaluate(state, q.QUESTIONS)
    latency_ms = round((time.perf_counter() - t0) * 1000)
    s = signals_from(response["answers"])
    category, reasons, attack_floor = decide(s, profile["code_signals"], profile["volume"]["requests"])
    attention = attack_floor or (
        s["threat_severity"] >= q.ATTENTION_SEVERITY and s["threat_severity_confidence"] >= q.ATTENTION_SEVERITY_CONF)
    return {
        "ip": profile["ip"],
        "category": category,
        "jev_category": s["traffic_class"],
        "category_confidence": s["traffic_class_confidence"],
        "severity": s["threat_severity"],
        "severity_confidence": s["threat_severity_confidence"],
        "attention": attention,
        "signals": fired(s),
        "code_signals": profile["code_signals"],
        "rule_reasons": reasons,
        "detail": s,
        "model": response["model"],
        "input_tokens": response["usage"]["input_tokens"],
        "estimated_tokens": est,
        "latency_ms": latency_ms,
        "profile_sent": trimmed,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--events", required=True, help="clean JSONL from validate.py")
    p.add_argument("--ip", required=True)
    p.add_argument("--app", help="text or .md file describing the site")
    p.add_argument("--window", default="the exported period")
    p.add_argument("--model", default=q.MODEL)
    p.add_argument("--max-tokens", type=int, default=q.MAX_PROFILE_TOKENS)
    args = p.parse_args()
    events = [json.loads(l) for l in Path(args.events).read_text().splitlines() if l.strip()]
    groups = group_by_ip(events)
    if args.ip not in groups:
        sys.exit(f"{args.ip} has no events in {args.events}")
    app = args.app or DEFAULT_APP
    if app and Path(app).expanduser().is_file():
        app = Path(app).expanduser().read_text().strip()
    verdict = classify_profile(build_profile(args.ip, groups[args.ip]), app, args.window, args.model, args.max_tokens)
    print(json.dumps(verdict, indent=2))


if __name__ == "__main__":
    main()
