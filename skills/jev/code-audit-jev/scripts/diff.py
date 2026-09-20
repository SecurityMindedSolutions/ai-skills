"""Pull-request mode: which units did this change touch, and what did they
look like before it?

    units, skipped = changed_units(repo, base_ref, files, excludes, includes)

For every file the branch changed since its merge base with `base_ref`, the
head version is split into units and the base version (from `git show`) is
split the same way; units are matched by name and kind. A unit is "changed"
when it is new or its code differs. Both versions are judged, and the PR
report shows only units whose band rose, so a defect that was already there
before the PR is not this PR's finding.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from extract import file_context, units_for
from inventory import language_of, role_of


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def merge_base(repo: Path, base_ref: str) -> str:
    return _git(repo, "merge-base", base_ref, "HEAD").strip()


def changed_files(repo: Path, base_sha: str) -> list[str]:
    out = _git(repo, "diff", "--name-only", "--diff-filter=AMR", base_sha, "--")
    return [l.strip() for l in out.splitlines() if l.strip()]


def base_text(repo: Path, base_sha: str, path: str) -> str | None:
    try:
        return _git(repo, "show", f"{base_sha}:{path}")
    except subprocess.CalledProcessError:
        return None  # new file


def changed_units(repo: Path, base_ref: str, excludes: list[str], includes: list[str]) -> tuple[list[dict], dict]:
    """Returns (items, info). Each item: {head: (unit, ctx, file), base: (unit, ctx, file) | None}."""
    base_sha = merge_base(repo, base_ref)
    items: list[dict] = []
    info = {"base_sha": base_sha, "files_changed": 0, "files_judged": 0, "units_changed": 0, "units_new": 0}
    for rel in changed_files(repo, base_sha):
        info["files_changed"] += 1
        if any(rel.startswith(x.rstrip("/") + "/") or rel == x for x in excludes):
            continue
        if includes and not any(rel.startswith(x.rstrip("/") + "/") or rel == x for x in includes):
            continue
        path = repo / rel
        if not path.is_file():
            continue
        language = language_of(path)
        if language is None:
            continue
        head_txt = path.read_text(encoding="utf-8", errors="replace")
        role = role_of(rel, language, head_txt)
        if role in ("test", "docs", "generated"):
            continue
        if role == "config" and language in ("json", "toml"):
            continue  # a lockfile-adjacent or manifest bump is not a security judgment; YAML (CI) and dotenv stay
        info["files_judged"] += 1
        head_ctx = file_context(head_txt, language)
        old_txt = base_text(repo, base_sha, rel)
        old_units = {}
        old_ctx = None
        if old_txt is not None:
            old_ctx = file_context(old_txt, language)
            for u in units_for(rel, language, old_txt):
                old_units[(u["name"], u["kind"])] = u
        frec = {"path": rel, "language": language, "role": role}
        for u in units_for(rel, language, head_txt):
            old = old_units.get((u["name"], u["kind"]))
            if old is not None and old["code"].strip() == u["code"].strip():
                continue  # untouched by this change
            info["units_changed"] += 1
            if old is None:
                info["units_new"] += 1
            items.append({"head": (u, head_ctx, frec), "base": (old, old_ctx, frec) if old is not None else None})
    return items, info
