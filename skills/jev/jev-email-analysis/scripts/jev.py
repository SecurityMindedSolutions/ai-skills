"""Self-contained TypeSafe Jev client for jev-email-analysis (stdlib only, no run-jev dependency).

POST https://api.typesafe.ai/v1/systemone {state, model, questions}; retries 429/529/5xx with
exponential backoff honoring retry-after. Answers are flattened per primitive:
  noul -> {q: p_true}   choice -> {q, q_conf, q_probs}   score -> {q, q_conf, q_level, q_probs}
"""
from __future__ import annotations

import json, logging, os, time, urllib.error, urllib.request
from pathlib import Path

log = logging.getLogger("jev-email")
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
KEY_FILE = Path("~/.config/typesafe/env").expanduser()
RETRY = {429, 500, 502, 503, 504, 529}


def api_key() -> str | None:
    if os.environ.get("TYPESAFE_API_KEY"):
        return os.environ["TYPESAFE_API_KEY"]
    if KEY_FILE.is_file():
        for line in KEY_FILE.read_text().splitlines():
            if line.strip().startswith("TYPESAFE_API_KEY="):
                return line.split("=", 1)[1].strip().strip("\"'")
    return None


def evaluate(key: str, state: dict, questions: dict, model: str = "jev-latest", retries: int = 5) -> dict:
    body = json.dumps({"state": state, "model": model, "questions": questions}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    delay = 1.0
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code not in RETRY or attempt == retries:
                raise RuntimeError(f"TypeSafe HTTP {e.code}: {e.read().decode(errors='replace')[:300]}") from e
            ra = e.headers.get("retry-after") if e.headers else None
            delay = float(ra) if ra and ra.replace(".", "", 1).isdigit() else delay
            log.warning("TypeSafe %s, retry %d in %.1fs", e.code, attempt + 1, delay)
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == retries:
                raise RuntimeError(f"TypeSafe connection failed: {e}") from e
            log.warning("TypeSafe connection error (%s), retry %d", e, attempt + 1)
        time.sleep(delay); delay = min(delay * 2, 30.0)
    raise RuntimeError("unreachable")


def flatten(answers: dict, questions: dict) -> dict:
    flat: dict = {}
    for q, spec in questions.items():
        a = answers[q]
        if spec["type"] == "noul":
            flat[q] = round(a["noul"], 3)
        elif spec["type"] == "choice":
            flat |= {q: a["choice"], f"{q}_conf": round(a["confidence"], 3),
                     f"{q}_probs": {k: round(v, 3) for k, v in a.get("probabilities", {}).items()}}
        else:
            probs = {int(k): round(v, 3) for k, v in a.get("probabilities", {}).items()}
            legend = {int(k): v for k, v in a.get("legend", {}).items()} or dict(enumerate(spec["criteria"]))
            top = max(probs, key=lambda k: probs[k]) if probs else None
            flat |= {q: round(a["score"], 3), f"{q}_conf": round(a["confidence"], 3),
                     f"{q}_level": legend.get(top) if top is not None else None,
                     f"{q}_probs": {legend.get(k, str(k)): v for k, v in probs.items()}}
    return flat
