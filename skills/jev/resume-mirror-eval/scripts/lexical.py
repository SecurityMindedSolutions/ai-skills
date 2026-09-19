"""Deterministic text statistics between a job description and a resume.

Everything here is arithmetic Jev should not be asked to do. Each metric is
normalized to 0..1 where higher means the resume looks more like the JD.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from difflib import SequenceMatcher

STOPWORDS = set("""
a an and are as at be by for from has have in is it its of on or that the to
with will you your we our this these those their they them into across within
who what which when where while such than then also both each other any all
more most very can may must should would could about over under between
using use used experience experienced strong ability able work working
""".split())

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#./-]*")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def content_terms(tokens: list[str]) -> list[str]:
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]


def ngrams(tokens: list[str], n: int) -> set[tuple[str, ...]]:
    """Distinct n-grams that contain at least two content words."""
    out = set()
    for i in range(len(tokens) - n + 1):
        gram = tokens[i:i + n]
        if sum(1 for t in gram if t not in STOPWORDS) >= 2:
            out.add(tuple(gram))
    return out


def phrase_overlap(jd_tokens: list[str], resume_tokens: list[str], n: int = 4) -> float:
    """Share of the JD's distinct n-grams that appear verbatim in the resume."""
    jd_grams = ngrams(jd_tokens, n)
    if not jd_grams:
        return 0.0
    resume_grams = ngrams(resume_tokens, n)
    return len(jd_grams & resume_grams) / len(jd_grams)


def longest_shared_span(jd_tokens: list[str], resume_tokens: list[str]) -> int:
    """Longest run of consecutive words shared by both documents."""
    matcher = SequenceMatcher(None, jd_tokens, resume_tokens, autojunk=False)
    match = matcher.find_longest_match(0, len(jd_tokens), 0, len(resume_tokens))
    return match.size


def keyword_coverage(jd_terms: list[str], resume_tokens: list[str]) -> float:
    """Fraction of distinct JD content words present anywhere in the resume."""
    jd_set = set(jd_terms)
    if not jd_set:
        return 0.0
    return len(jd_set & set(resume_tokens)) / len(jd_set)


def order_echo(jd_terms: list[str], resume_tokens: list[str]) -> float:
    """Rank correlation between the order matched terms appear in the JD and in
    the resume. 1.0 means the resume walks the JD top to bottom; 0.0 means no
    relationship or too few shared terms to say."""
    jd_first = _first_positions(jd_terms)
    resume_first = _first_positions(resume_tokens)
    shared = [t for t in jd_first if t in resume_first]
    if len(shared) < 8:
        return 0.0
    jd_rank = _ranks([jd_first[t] for t in shared])
    resume_rank = _ranks([resume_first[t] for t in shared])
    rho = _spearman(jd_rank, resume_rank)
    return max(0.0, rho)


def _first_positions(tokens: list[str]) -> dict[str, int]:
    positions: dict[str, int] = {}
    for index, token in enumerate(tokens):
        positions.setdefault(token, index)
    return positions


def _ranks(values: list[int]) -> list[int]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0] * len(values)
    for rank, index in enumerate(order):
        ranks[index] = rank
    return ranks


def _spearman(a: list[int], b: list[int]) -> float:
    n = len(a)
    if n < 2:
        return 0.0
    d_squared = sum((x - y) ** 2 for x, y in zip(a, b))
    return 1 - (6 * d_squared) / (n * (n * n - 1))


class TfidfPool:
    """TF-IDF over unigrams and bigrams for one batch (JD plus all resumes)."""

    def __init__(self, documents: list[list[str]]):
        self.features = [self._features(tokens) for tokens in documents]
        df: Counter = Counter()
        for feats in self.features:
            df.update(set(feats))
        n = len(documents)
        self.idf = {f: math.log((1 + n) / (1 + count)) + 1 for f, count in df.items()}

    @staticmethod
    def _features(tokens: list[str]) -> list[str]:
        terms = content_terms(tokens)
        bigrams = [f"{a} {b}" for a, b in zip(terms, terms[1:])]
        return terms + bigrams

    def vector(self, index: int) -> dict[str, float]:
        counts = Counter(self.features[index])
        total = sum(counts.values()) or 1
        return {f: (c / total) * self.idf[f] for f, c in counts.items()}

    def cosine(self, i: int, j: int) -> float:
        a, b = self.vector(i), self.vector(j)
        dot = sum(a[f] * b.get(f, 0.0) for f in a)
        norm = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
        return dot / norm if norm else 0.0


def lexical_metrics(jd_text: str, resume_text: str, cosine: float, span_cap: int) -> dict:
    """All lexical signals for one resume, each in 0..1 except raw span length."""
    jd_tokens, resume_tokens = tokenize(jd_text), tokenize(resume_text)
    jd_terms = content_terms(jd_tokens)
    span = longest_shared_span(jd_tokens, resume_tokens)
    return {
        "phrase_overlap": round(phrase_overlap(jd_tokens, resume_tokens), 4),
        "longest_span_words": span,
        "longest_span": round(min(span / span_cap, 1.0), 4),
        "order_echo": round(order_echo(jd_terms, resume_tokens), 4),
        "tfidf_cosine": round(cosine, 4),
        "keyword_coverage": round(keyword_coverage(jd_terms, resume_tokens), 4),
        "resume_words": len(resume_tokens),
    }


def zscores(values: list[float]) -> list[float]:
    """Z-score of each value against the batch. Zero when there is no spread."""
    n = len(values)
    if n < 2:
        return [0.0] * n
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    std = math.sqrt(variance)
    if std == 0:
        return [0.0] * n
    return [round((v - mean) / std, 3) for v in values]
