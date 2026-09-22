"""Load the rules folder and assemble what Jev is asked.

`analyze.py` knows nothing about any email category. Everything it looks for is declared in
`rules/`: `_core.toml` holds the model, the framing, the scales, the eight shared red-flag
questions, the verdict thresholds and the regex facts every email gets; one `<category>.toml`
per category holds the option Jev chooses between, the verdict that category rolls up to, and
any regex facts specific to it.

To retune without forking, put your own `*.toml` in a folder and pass `--rules <dir>`: a file
whose `id` matches a built-in category replaces it, a new `id` adds a category, and a `_core.toml`
there replaces matching top-level tables. See `rules/README.md`.
"""
from __future__ import annotations

import re, tomllib
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
BUILTIN = SKILL / "rules"
CORE_TABLES = ("model", "choice", "risk", "pressure", "verdict", "questions", "signals")


def _load_dir(d: Path) -> tuple[dict, dict]:
    """-> (core tables, {category id: rule})."""
    core: dict = {}
    cats: dict = {}
    for f in sorted(d.glob("*.toml")):
        data = tomllib.loads(f.read_text())
        if f.name == "_core.toml":
            core = data
        elif "id" in data:
            data["_file"] = str(f)
            cats[data["id"]] = data
    return core, cats


def load(extra: Path | None = None) -> dict:
    core, cats = _load_dir(BUILTIN)
    if not cats:
        raise SystemExit(f"jev-email-analysis: no category rules found in {BUILTIN}")
    if extra:
        ecore, ecats = _load_dir(Path(extra))
        for table, val in ecore.items():                 # replaces matching top-level tables
            core[table] = {**core.get(table, {}), **val} if isinstance(val, dict) else val
        cats.update(ecats)                               # same id replaces, new id adds
    missing = [t for t in CORE_TABLES if t not in core]
    if missing:
        raise SystemExit(f"jev-email-analysis: _core.toml is missing {', '.join(missing)}")
    for cid, r in cats.items():
        for k in ("title", "verdict", "class"):
            if not r.get(k):
                raise SystemExit(f"jev-email-analysis: rule '{cid}' ({r['_file']}) has no '{k}'")
        if r["verdict"] not in ("malicious", "suspicious", "spam", "benign"):
            raise SystemExit(f"jev-email-analysis: rule '{cid}' has unknown verdict '{r['verdict']}'")
    return {"core": core, "categories": cats}


def questions(rules: dict) -> dict:
    """The request body Jev answers: one choice, two scores, eight nouls."""
    core, cats = rules["core"], rules["categories"]
    criteria = {cid: r["class"] for cid, r in cats.items()}
    criteria["none_fits"] = core["choice"]["none_fits"]
    q = {
        "category": {"type": "choice", "instructions": core["choice"]["instructions"],
                     "criteria": criteria},
        "risk": {"type": "score", "instructions": core["risk"]["instructions"],
                 "criteria": core["risk"]["levels"]},
        "pressure": {"type": "score", "instructions": core["pressure"]["instructions"],
                     "criteria": core["pressure"]["levels"]},
    }
    for qid, spec in core["questions"].items():
        q[qid] = {"type": "noul", "instructions": spec["instructions"],
                  "criteria": {"true": spec["true"], "false": spec["false"]}}
    return q


def verdict_map(rules: dict) -> dict:
    """category id -> the verdict it rolls up to, straight from the rule files."""
    return {cid: r["verdict"] for cid, r in rules["categories"].items()}


def _compiled(rules: dict) -> list[tuple[str, str, list]]:
    out = []
    for scope, table in [("context", rules["core"].get("signals", {}))] + \
                        [(cid, r.get("signals", {})) for cid, r in rules["categories"].items()]:
        for name, spec in table.items():
            pats = [re.compile(p) for p in spec.get("patterns", [])]
            out.append((f"{scope}.{name}", spec.get("label", name), pats))
    return out


def code_signals(state: dict, rules: dict) -> dict:
    """Regex facts computed BEFORE Jev is asked, so it is told the fact rather than asked to
    spot it. Jev reads dates and counts poorly and does not need to hunt for a wallet address.

    Matched against the fields that actually carry the text; never against `provenance`, which
    is the agent's own note and must not be read as evidence from the email.
    """
    hay = "\n".join(str(state.get(f, "")) for f in
                    ("sender", "reply_to", "subject", "body", "attachments"))
    links = state.get("links") or []
    hay += "\n" + "\n".join(f"https://{h}" for h in (links if isinstance(links, list) else [links]))
    found: dict = {}
    for key, label, pats in _compiled(rules):
        if any(p.search(hay) for p in pats):
            found[key] = label
    return found


def reply_to_mismatch(state: dict) -> str | None:
    """A computable fact, not a judgment: does reply-to leave the sender's domain?"""
    def dom(v):
        m = re.search(r"[\w.+-]+@([\w.-]+)", str(v or ""))
        return m.group(1).lower().lstrip("www.") if m else ""
    s, r = dom(state.get("sender")), dom(state.get("reply_to"))
    if s and r and s != r and not (s.endswith("." + r) or r.endswith("." + s)):
        return f"reply-to domain ({r}) differs from sender domain ({s})"
    return None
