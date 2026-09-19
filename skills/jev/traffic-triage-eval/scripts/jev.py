"""Minimal TypeSafe (Jev) client over the raw HTTP API.

Uses only the standard library so the skill has one fewer moving part. Retries
429, 529 and 5xx with exponential backoff, honoring retry-after when present.
Endpoint and request shape: https://docs.typesafe.ai/api
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
KEY_FILE = Path("~/.config/typesafe/env").expanduser()
RETRY_STATUSES = {429, 500, 502, 503, 504, 529}


def load_api_key() -> str:
    """TYPESAFE_API_KEY from the environment, else from ~/.config/typesafe/env."""
    key = os.environ.get("TYPESAFE_API_KEY")
    if key:
        return key
    if KEY_FILE.is_file():
        for line in KEY_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("TYPESAFE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(
        "No TypeSafe API key. Export TYPESAFE_API_KEY or put "
        f"TYPESAFE_API_KEY=... in {KEY_FILE}. Keys: https://console.typesafe.ai/keys")


class JevClient:
    def __init__(self, api_key: str, model: str, max_retries: int = 5, timeout: float = 30.0):
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout

    def evaluate(self, state: dict, questions: dict) -> dict:
        """POST one state with a map of questions; return the parsed response."""
        body = json.dumps({"state": state, "model": self.model,
                           "questions": questions}).encode()
        request = urllib.request.Request(
            ENDPOINT, data=body, method="POST",
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"})
        delay = 1.0
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as err:
                if err.code not in RETRY_STATUSES or attempt == self.max_retries:
                    detail = err.read().decode(errors="replace")[:500]
                    raise RuntimeError(f"TypeSafe HTTP {err.code}: {detail}") from err
                delay = _retry_delay(err, delay)
            except (urllib.error.URLError, TimeoutError) as err:
                if attempt == self.max_retries:
                    raise RuntimeError(f"TypeSafe connection failed: {err}") from err
            time.sleep(delay)
            delay = min(delay * 2, 30.0)
        raise RuntimeError("unreachable")


def _retry_delay(err: urllib.error.HTTPError, fallback: float) -> float:
    header = err.headers.get("retry-after") if err.headers else None
    try:
        return float(header) if header else fallback
    except ValueError:
        return fallback
