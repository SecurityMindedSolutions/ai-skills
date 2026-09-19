"""Deterministic checks for things a model should not be asked to notice.

Invisible characters, chat-template tokens, hidden markup, homoglyph mixing
and gibberish suffixes are all detectable exactly, in microseconds, without
any model, and Jev may not even see some of them (a zero-width character is
by definition not visible in the text). These run before the Jev call and
force a minimum decision per questions.CODE_SIGNAL_DECISIONS.
"""

from __future__ import annotations

import re
import unicodedata

ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff", "\u180e"}
BIDI = {"\u202a", "\u202b", "\u202c", "\u202d", "\u202e", "\u2066", "\u2067", "\u2068", "\u2069"}
TAG_BLOCK = range(0xE0000, 0xE0080)   # Unicode "tags": the ASCII-smuggling block

CHAT_TEMPLATE = re.compile(r"<\|im_(start|end)\|>|<\|(system|user|assistant|endoftext)\|>|\[INST\]|\[/INST\]|<<SYS>>|<\|start_header_id\|>|<\|eot_id\|>", re.I)
FAKE_TURNS = re.compile(r"(^|\n)\s*(###\s*)?(system|assistant|ai|human|user)\s*:\s*\S|(^|\n)\s*###\s*(instruction|new instructions|system)", re.I)
HIDDEN_HTML = re.compile(r"<!--.*?-->|display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0|opacity\s*:\s*0(?![.\d])|color\s*:\s*(#fff|#ffffff|white)\b", re.I | re.S)
WORD = re.compile(r"[^\W\d_]{3,}", re.U)
GIBBERISH_TOKEN = re.compile(r"\S{12,}")


def invisible_unicode(text: str) -> int:
    return sum(1 for ch in text if ch in ZERO_WIDTH or ch in BIDI or ord(ch) in TAG_BLOCK)


def mixed_script_words(text: str) -> list[str]:
    """Words that mix Latin with Cyrillic or Greek letters: the homoglyph trick."""
    hits = []
    for word in WORD.findall(text):
        scripts = set()
        for ch in word:
            name = unicodedata.name(ch, "")
            for script in ("LATIN", "CYRILLIC", "GREEK"):
                if name.startswith(script):
                    scripts.add(script)
        if len(scripts) > 1:
            hits.append(word)
    return hits


def gibberish_suffix(text: str) -> bool:
    """A run of long tokens where most characters are symbols or mixed case
    without vowels: the shape of an adversarial suffix. Ordinary URLs, emails
    and base64 blobs are excluded by their own patterns elsewhere; here we
    look for three or more such tokens in a row at the end of the message."""
    tail = text.strip()[-200:]
    if tail.count("{") + tail.count("[") >= 2 or tail.count('"') >= 4:
        return False  # looks like JSON or code the user pasted on purpose
    tokens = tail.split()
    run = 0
    for tok in tokens:
        symbols = sum(1 for ch in tok if not ch.isalnum())
        vowels = sum(1 for ch in tok.lower() if ch in "aeiou")
        odd = len(tok) >= 8 and (symbols / len(tok) > 0.45 or (vowels == 0 and len(tok) >= 10))
        if odd and not tok.startswith(("http", "www.")) and "@" not in tok:
            run += 1
        else:
            run = 0
        if run >= 3:
            return True
    return False


def code_signals(text: str) -> dict[str, str]:
    """Signal name -> short human-readable evidence, for every check that fired."""
    out: dict[str, str] = {}
    n = invisible_unicode(text)
    if n:
        out["invisible_unicode"] = f"{n} invisible or direction-control character{'s' if n != 1 else ''}"
    if CHAT_TEMPLATE.search(text):
        out["chat_template_tokens"] = "contains chat template tokens such as " + CHAT_TEMPLATE.search(text).group(0)
    if HIDDEN_HTML.search(text):
        out["hidden_html"] = "contains an HTML comment or CSS that hides text"
    words = mixed_script_words(text)
    if words:
        out["mixed_script_words"] = "mixed-script word(s): " + ", ".join(words[:3])
    if gibberish_suffix(text):
        out["gibberish_suffix"] = "ends in a run of symbol-heavy tokens"
    if FAKE_TURNS.search(text):
        out["fake_turn_markers"] = "contains lines formatted as another speaker's turn"
    return out
