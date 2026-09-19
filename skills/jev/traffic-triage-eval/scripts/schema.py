"""The canonical request-event schema: the contract between whoever pulls the
logs and this skill.

One JSON object per HTTP request. The retrieving agent maps its source (GCLB,
AWS ALB, AWS WAF, CloudFront, nginx, anything) onto these names; nothing in
this skill knows or cares where the rows came from. `references/schema.md` is
the human-readable version of this file and must say the same thing.
"""

from __future__ import annotations

import ipaddress
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

# name -> (required, type, note). Types: str, int, float, ts, list.
FIELDS: dict[str, tuple[bool, str, str]] = {
    "ts":         (True,  "ts",    "request time: ISO 8601 with zone, or epoch seconds"),
    "ip":         (True,  "str",   "client IP as the edge saw it (the real client, not the LB/CDN hop)"),
    "method":     (True,  "str",   "HTTP method"),
    "path":       (True,  "str",   "URL path only, no host, no query; `url` is accepted instead and split"),
    "status":     (False, "int",   "HTTP response status; 0 if the edge closed it; omit when the source does not log it (most WAF logs)"),
    "host":       (False, "str",   "Host header / SNI as requested (raw IP hosts are a signal, keep them)"),
    "query":      (False, "str",   "raw query string without the leading `?`"),
    "ua":         (False, "str",   "User-Agent header"),
    "referer":    (False, "str",   "Referer header"),
    "waf_action": (False, "str",   "allow | deny | throttle | count | challenge | none"),
    "waf_rule":   (False, "str",   "the rule or policy that produced waf_action"),
    "waf_labels": (False, "list",  "labels the WAF attached (AWS WAF `labels[].name`); list, or one string separated by spaces or commas"),
    "asn":        (False, "int",   "client ASN if the edge records it"),
    "country":    (False, "str",   "ISO country code if the edge records it"),
    "ja3":        (False, "str",   "TLS JA3 fingerprint"),
    "ja4":        (False, "str",   "TLS JA4 fingerprint"),
    "bytes_in":   (False, "int",   "request bytes"),
    "bytes_out":  (False, "int",   "response bytes"),
    "latency_ms": (False, "float", "backend or total latency in milliseconds"),
    "protocol":   (False, "str",   "HTTP/1.1, HTTP/2, ..."),
    "target":     (False, "str",   "backend / target group / function the LB routed to"),
    "source":     (False, "str",   "gclb | alb | awswaf | cloudfront | nginx | other"),
}

REQUIRED = [k for k, (req, _, _) in FIELDS.items() if req]
OPTIONAL = [k for k, (req, _, _) in FIELDS.items() if not req]

WAF_ACTIONS = {"allow", "deny", "throttle", "count", "challenge", "none"}
_WAF_ALIASES = {
    "accept": "allow", "allowed": "allow", "pass": "allow",
    "block": "deny", "blocked": "deny", "denied": "deny", "reject": "deny",
    "rate_limit": "throttle", "ratelimit": "throttle", "throttled": "throttle",
    "captcha": "challenge", "": "none", "null": "none",
}

_EPOCH_RE = re.compile(r"^\d{9,13}(\.\d+)?$")


class RowError(ValueError):
    pass


def parse_ts(value) -> datetime:
    """ISO 8601 (with or without zone; naive is taken as UTC) or epoch s/ms."""
    if isinstance(value, (int, float)) or (isinstance(value, str) and _EPOCH_RE.match(value.strip())):
        n = float(value)
        if n > 1e11:  # milliseconds
            n /= 1000.0
        return datetime.fromtimestamp(n, tz=timezone.utc)
    if not isinstance(value, str):
        raise RowError(f"ts: unsupported type {type(value).__name__}")
    s = value.strip().replace("Z", "+00:00")
    # trim sub-microsecond precision that fromisoformat rejects on older Pythons
    s = re.sub(r"(\.\d{6})\d+", r"\1", s)
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as err:
        raise RowError(f"ts: cannot parse {value!r}") from err
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_row(raw: dict) -> dict:
    """Coerce one input object into a canonical event. Raises RowError with a
    reason a person can act on. Unknown keys are dropped, not rejected."""
    row: dict = {}
    if "path" not in raw and raw.get("url"):
        parts = urlsplit(str(raw["url"]))
        raw = {**raw, "path": parts.path or "/", "query": raw.get("query") or parts.query,
               "host": raw.get("host") or parts.netloc}
    for name in REQUIRED:
        if raw.get(name) in (None, ""):
            raise RowError(f"missing required field `{name}`")
    for name, (_, kind, _) in FIELDS.items():
        value = raw.get(name)
        if value in (None, ""):
            continue
        try:
            row[name] = _coerce(name, kind, value)
        except (TypeError, ValueError, RowError) as err:
            if name in REQUIRED:
                raise RowError(f"{name}: {err}") from err
            # a bad optional value is dropped, the row survives
    try:
        ipaddress.ip_address(row["ip"])
    except ValueError as err:
        raise RowError(f"ip: {row['ip']!r} is not an IP address") from err
    row["method"] = row["method"].upper()
    if not row["path"].startswith("/"):
        row["path"] = "/" + row["path"]
    row["waf_action"] = _WAF_ALIASES.get(row.get("waf_action", "").lower(), row.get("waf_action", "").lower()) or "none"
    if row["waf_action"] not in WAF_ACTIONS:
        row["waf_action"] = "none"
    return row


def _coerce(name: str, kind: str, value):
    if kind == "list":
        if isinstance(value, str):
            return [v for v in re.split(r"[,\s]+", value.strip()) if v]
        return [str(v.get("name") if isinstance(v, dict) else v).strip() for v in value if v]
    if kind == "ts":
        return parse_ts(value).isoformat()
    if kind == "int":
        return int(float(value))
    if kind == "float":
        return float(value)
    return str(value).strip()
