"""A string-matching baseline, so the spreadsheet shows what a regex gate sees.

This is a reasonable version of what many teams ship first: a list of phrases
that appear in well-known injection attempts. It is here to be measured
against, not to be used. Expect it to miss paraphrases and pasted-content
attacks, and to flag people who merely talk about these things.
"""

from __future__ import annotations

import re

PATTERNS = [
    r"ignore (all |any )?(of )?(your |the )?(previous|prior|above|earlier) (instructions|rules|prompts?)",
    r"disregard (all |any )?(of )?(your |the )?(previous|prior|above|earlier) (instructions|rules)",
    r"forget (everything|all|your) (you were told|previous|prior|instructions|rules)",
    r"you are now (?!able|going|ready|connected|logged)",
    r"\bDAN\b|do anything now",
    r"developer mode|debug mode|god mode|unrestricted mode|jailbreak",
    r"(reveal|print|show|display|output|repeat) (me )?(your |the )?(system prompt|initial prompt|hidden (instructions|prompt)|instructions above)",
    r"(what|which) (is|are|were) your (instructions|system prompt|rules)",
    r"repeat (everything|all|the text) (above|before this)",
    r"api[_ ]?key|password|credential|secret key",
    r"base64|rot13|decode (this|the following)",
    r"i am (the |your )?(developer|admin|administrator|creator|owner|ceo)",
    r"this is (an? )?(official|authorized|system) (message|override|instruction)",
    r"new (instructions|rules|system prompt)\s*:",
    r"\[?system\]?\s*:|<\|?system\|?>|### ?system",
    r"act as (an? )?(unfiltered|unrestricted|uncensored)",
    r"pretend (you have|there are) no (rules|restrictions|guidelines)",
    r"from now on",
    r"override",
]
COMPILED = [re.compile(p, re.IGNORECASE) for p in PATTERNS]


def regex_hits(text: str) -> list[str]:
    """Patterns that match, as the regex source, for the spreadsheet."""
    return [p.pattern for p in COMPILED if p.search(text)]


def regex_decision(text: str) -> str:
    return "block" if regex_hits(text) else "allow"
