"""Turn email content in any FORMAT into the items `analyze.py` judges.

This skill does not retrieve mail and takes no position on where it came from. The contract is
the schema in `references/schema.md`: every field is optional, and a run uses whatever it was
given. This script is a convenience for the three mechanical formats, not a list of supported
sources - anything that can produce the schema is a valid input.

  ingest.py --eml msg.eml                 one .eml, a directory of them, or an .mbox (RFC 5322)
  ingest.py --json msgs.json              JSON in any shape: schema items, a mail API message,
                                          or flat records; "-" reads stdin
  ingest.py --text pasted.txt             a pasted blob, headers optional; "-" reads stdin
  ingest.py --text - | analyze.py --stdin one-off judgment, no temp file

Formats code cannot parse - a screenshot, a PDF, a chat transcript, a ticket - are the AGENT's
job: transcribe what is visible into the --text form or write the schema directly, and record in
`provenance` what could not be captured. See "Getting an email into the schema" in SKILL.md.

Every mode prints a field-coverage line to stderr so the caller knows which signals the run has.

Nothing is redacted here on purpose - `analyze.normalize()` redacts on the way out, which is the
one place a caller cannot forget.
"""
from __future__ import annotations

import argparse, email, html, json, mailbox, re, sys
from email import policy
from email.message import EmailMessage
from pathlib import Path

MAX_LINKS = 15
STATE_FIELDS = ("sender", "reply_to", "subject", "auth", "body", "links", "attachments",
                "relationship", "provenance")

# Every spelling of a state field seen across mail APIs, MCP servers and hand-written JSON.
ALIASES = {
    "sender": ("sender", "from", "from_", "fromAddress", "from_address", "sender_address", "author"),
    "reply_to": ("reply_to", "replyTo", "reply-to", "replyto"),
    "subject": ("subject", "title"),
    "auth": ("auth", "authentication", "authentication_results", "authenticationResults"),
    "body": ("body", "text", "plain", "textBody", "body_text", "bodyText", "content",
             "plainTextBody", "snippet"),
    "links": ("links", "urls", "link_hosts"),
    "attachments": ("attachments", "files"),
    "relationship": ("relationship", "history"),
    "provenance": ("provenance", "source"),
}
HTML_KEYS = ("html", "htmlBody", "body_html", "bodyHtml", "htmlContent")


def html_to_text(s: str) -> str:
    s = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h[1-6])>", "\n", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", s).strip()


def link_hosts(*texts: str) -> list[str]:
    """Link HOSTS, not full URLs: the host is what identifies the destination, and full URLs
    carry tracking tokens and recipient identifiers that need not leave the machine."""
    seen: dict[str, None] = {}
    for t in texts:
        for m in re.finditer(r"https?://([^/\s\"'<>\)\]]+)", t or ""):
            host = m.group(1).lower().rstrip(".").split("@")[-1]
            if host and host not in seen:
                seen[host] = None
    return list(seen)[:MAX_LINKS]


def summarize_auth(raw: str) -> str:
    """Condense Authentication-Results into the one-line form the questions expect.
    Absent auth is UNKNOWN, never a failure - it must read as 'not recorded'."""
    if not raw:
        return "not recorded"
    parts = []
    for mech in ("spf", "dkim", "dmarc"):
        m = re.search(rf"\b{mech}=(\w+)", raw, re.I)
        if m:
            d = re.search(rf"\b{mech}=\w+[^;]*?\b(?:header\.d|header\.from|smtp\.mailfrom)=([^\s;]+)",
                          raw, re.I)
            parts.append(f"{mech.upper()} {m.group(1).lower()}" + (f" ({d.group(1)})" if d else ""))
    return ", ".join(parts) if parts else "not recorded"


def _clean(v) -> str:
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v if x)
    return re.sub(r"\s+", " ", str(v or "")).strip()


def state_from_headers(get, body: str, htm: str, attachments: list[str], provenance: str) -> dict:
    """get(name) -> header value or ''. Shared by the .eml and JSON front doors."""
    auth = get("authentication-results") or get("arc-authentication-results") or get("received-spf")
    st = {
        "sender": _clean(get("from")),
        "reply_to": _clean(get("reply-to")),
        "subject": _clean(get("subject")),
        "auth": summarize_auth(auth),
        "body": (body or html_to_text(htm)).strip(),
        "links": link_hosts(body, htm),
        "attachments": "\n".join(attachments),
        "provenance": provenance,
    }
    return {k: v for k, v in st.items() if v not in ("", [], None)}


# --- .eml / mbox ------------------------------------------------------------------------------

def from_message(msg: EmailMessage, provenance: str) -> dict:
    body, htm, atts = "", "", []
    for part in msg.walk():
        if part.is_multipart():
            continue
        disp, ctype = part.get_content_disposition(), part.get_content_type()
        name = part.get_filename()
        if disp == "attachment" or name:
            size = len(part.get_payload(decode=True) or b"")
            atts.append(f"{name or 'unnamed'} ({ctype}, {size} bytes): not scanned")
        elif ctype == "text/plain" and not body:
            body = part.get_content()
        elif ctype == "text/html" and not htm:
            htm = part.get_content()
    return state_from_headers(lambda h: msg.get(h, ""), body, htm, atts, provenance)


def load_eml(path: Path) -> list[dict]:
    if path.is_dir():
        files = sorted(p for p in path.iterdir() if p.suffix.lower() in (".eml", ".msg", ".txt"))
        return [{"id": p.stem, "state": from_message(
            email.message_from_bytes(p.read_bytes(), policy=policy.default), f"{p.suffix.lstrip('.')} file")}
            for p in files]
    if path.suffix.lower() == ".mbox":
        return [{"id": msg.get("message-id", f"mbox-{i + 1}").strip("<>")[:60],
                 "state": from_message(msg, "mbox export")}
                for i, msg in enumerate(mailbox.mbox(str(path), factory=None))]
    return [{"id": path.stem,
             "state": from_message(email.message_from_bytes(path.read_bytes(), policy=policy.default),
                                   "eml file")}]


# --- JSON in any shape -------------------------------------------------------

def _b64(data: str) -> str:
    import base64
    try:
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")
    except Exception:
        return ""


def _walk_payload(part: dict, acc: dict) -> None:
    """Collect text, html and attachment lines from a MIME-style payload tree (Gmail API and
    several other mail APIs use this shape)."""
    mime, fn = part.get("mimeType", ""), part.get("filename") or ""
    data = (part.get("body") or {}).get("data")
    if fn:
        acc["atts"].append(f"{fn} ({mime}, {(part.get('body') or {}).get('size', 0)} bytes): not scanned")
    elif mime == "text/plain" and data and not acc["body"]:
        acc["body"] = _b64(data)
    elif mime == "text/html" and data and not acc["htm"]:
        acc["htm"] = _b64(data)
    for child in part.get("parts") or []:
        _walk_payload(child, acc)


def from_mapping(d: dict, idx: int, provenance: str) -> dict:
    """Tolerant: accepts a schema item, a mail API message (MIME payload tree), or a flat record.

    A state object passes through; a MIME payload tree is decoded; flat keys are matched by alias.
    Unknown keys are ignored rather than guessed at - a wrong guess would be worse than a gap.
    """
    if "state" in d and isinstance(d["state"], dict):           # already canonical
        return {"id": str(d.get("id") or f"email-{idx}"), "state": d["state"],
                **({"expect": d["expect"]} if d.get("expect") else {})}

    payload = d.get("payload") or {}
    hdrs = {h.get("name", "").lower(): h.get("value", "")
            for h in (payload.get("headers") or d.get("headers") or []) if isinstance(h, dict)}
    acc = {"body": "", "htm": "", "atts": []}
    if payload:
        _walk_payload(payload, acc)

    def get(name: str) -> str:
        if hdrs.get(name):
            return hdrs[name]
        for alias in ALIASES.get(name.replace("-", "_"), ()):   # flat keys: from/subject/reply_to
            if d.get(alias):
                return _clean(d[alias])
        return ""

    body = acc["body"] or next((_clean(d[k]) for k in ALIASES["body"] if d.get(k)), "")
    htm = acc["htm"] or next((str(d[k]) for k in HTML_KEYS if d.get(k)), "")
    atts = acc["atts"] or ([_clean(a) for a in d["attachments"]]
                           if isinstance(d.get("attachments"), list) else
                           [_clean(d["attachments"])] if d.get("attachments") else [])

    st = state_from_headers(get, body, htm, atts, _clean(d.get("provenance")) or provenance)
    for f in ("links", "relationship"):                          # caller-supplied wins
        if d.get(f):
            st[f] = d[f] if f == "links" and isinstance(d[f], list) else _clean(d[f])
    labels = d.get("labelIds") or d.get("labels")
    mid = d.get("id") or d.get("messageId") or d.get("message_id") or f"email-{idx}"
    out = {"id": str(mid)[:60], "state": st}
    if labels:
        out["labels"] = labels if isinstance(labels, list) else [labels]
    return out


def load_json(path: Path, provenance: str) -> list[dict]:
    raw = json.loads(read(path))
    rows = raw if isinstance(raw, list) else raw.get("messages") or raw.get("results") or [raw]
    return [from_mapping(r, i + 1, provenance) for i, r in enumerate(rows)]


# --- pasted text ------------------------------------------------------------------------------

HEADER_LINE = re.compile(r"^\s*(from|sender|to|reply[- ]?to|subject|date|cc|authentication[- ]results)"
                         r"\s*:\s*(.*)$", re.I)


def load_text(path: Path, provenance: str) -> list[dict]:
    """A pasted blob. Leading 'From:/Subject:/...' lines are used when present; otherwise the whole
    thing is the body. A paste with no headers is a legitimate input, not an error - the questions
    treat absent signals as unknown."""
    raw = read(path)
    hdrs: dict[str, str] = {}
    lines = raw.splitlines()
    i = 0
    while i < len(lines) and (not lines[i].strip() or HEADER_LINE.match(lines[i])):
        m = HEADER_LINE.match(lines[i])
        if m:
            hdrs[m.group(1).lower().replace(" ", "-").replace("replyto", "reply-to")] = m.group(2).strip()
        elif hdrs:
            i += 1
            break
        i += 1
    body = "\n".join(lines[i:]).strip() if hdrs else raw.strip()
    norm = {"reply-to": hdrs.get("reply-to") or hdrs.get("reply to", ""),
            "from": hdrs.get("from") or hdrs.get("sender", ""),
            "subject": hdrs.get("subject", ""),
            "authentication-results": hdrs.get("authentication-results", "")}
    st = state_from_headers(lambda h: norm.get(h, ""), body, "", [], provenance)
    return [{"id": "pasted" if str(path) == "-" else path.stem, "state": st}]


def read(path: Path) -> str:
    return sys.stdin.read() if str(path) == "-" else path.read_text(errors="replace")


def report(items: list[dict]) -> None:
    """Which signals does this run actually have? Every field is optional, so the honest answer
    matters: a set with no `auth` and no `relationship` cannot have its senders verified, and the
    verdicts will lean on content alone. Printed to stderr so `--out -` style piping still works."""
    n = len(items)

    def have(it, f):                       # "not recorded" is a placeholder, not a captured value
        v = it["state"].get(f)
        return bool(v) and not (f == "auth" and str(v).strip().lower() == "not recorded")
    cov = {f: sum(1 for it in items if have(it, f)) for f in STATE_FIELDS}
    print(f"ingest: {n} item(s)", file=sys.stderr)
    print("ingest: field coverage - " +
          ", ".join(f"{f} {c}/{n}" for f, c in cov.items() if c) or "ingest: no fields populated",
          file=sys.stderr)
    missing = [f for f in ("sender", "subject", "body") if not cov[f]]
    if missing:
        print(f"ingest: NOTE no {', '.join(missing)} on any item - judged on what is present",
              file=sys.stderr)
    if not cov["auth"] and not cov["relationship"]:
        print("ingest: NOTE no auth and no relationship history - sender identity cannot be "
              "assessed; verdicts rest on content (flagged `identity_unknown`)", file=sys.stderr)
    blank = [it["id"] for it in items if not it["state"].get("body") and not it["state"].get("subject")]
    if blank:
        print(f"ingest: WARNING {len(blank)} item(s) have neither subject nor body: {blank[:5]}",
              file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--eml", type=Path, help=".eml file, directory of them, or .mbox")
    src.add_argument("--json", type=Path, help="JSON in any shape: schema items, a mail API "
                                               "message, or flat records ('-' for stdin)")
    src.add_argument("--text", type=Path, help="pasted blob, headers optional ('-' for stdin)")
    ap.add_argument("--provenance", default="", help="where this content came from and what is missing")
    ap.add_argument("--out", type=Path, help="default stdout")
    a = ap.parse_args()

    if a.eml:
        items = load_eml(a.eml)
    elif a.text:
        items = load_text(a.text, a.provenance or "pasted text; headers may be incomplete")
    else:
        items = load_json(a.json, a.provenance or "JSON export; field coverage as shown")
    if a.provenance:
        for it in items:
            it["state"]["provenance"] = a.provenance

    out = json.dumps(items, indent=1)
    a.out.write_text(out) if a.out else print(out)
    report(items)


if __name__ == "__main__":
    main()
