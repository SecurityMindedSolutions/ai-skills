#!/usr/bin/env python3
"""Regenerate the skill index in the root README from the skills themselves.

Nothing here is written by hand twice. Each fact has exactly one home:

    skills/<category>/README.md   the category blurb (first paragraph) and all
                                  human-facing detail about its skills
    <skill>/SKILL.md              metadata.summary, the skill's one-liner

This script reads both and rewrites the block between the BEGIN/END SKILL INDEX
markers in the root README. That block is the only place either fact is
repeated, and because it is generated it cannot drift. Category READMEs carry no
index table of their own: a reader who is already in one does not need a list of
what is directly below, and GitHub renders an outline for them anyway.

Usage:
    python3 .github/scripts/sync-readme-index.py          # rewrite the block
    python3 .github/scripts/sync-readme-index.py --check  # exit 1 if stale, write nothing
"""

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SKILLS = REPO / "skills"

BEGIN = "<!-- BEGIN SKILL INDEX -->"
END = "<!-- END SKILL INDEX -->"

# Category order, display title, and the order skills appear within it.
# The blurb is NOT here: it is the first paragraph of the category README.
# A skill on disk but missing from `order` is appended alphabetically and
# reported, so adding one shows up here rather than silently sorting itself.
CATEGORIES = [
    ("auditing", "Auditing",
     ["audit-security", "audit-frontend", "audit-backend"]),
    ("vulnerability-management", "Vulnerability management",
     ["github-remediate-vulns"]),
    ("autonomous-development", "Autonomous development",
     ["ralph-plan", "ralph-loop"]),
    ("reconnaissance", "Reconnaissance",
     ["built-with"]),
    ("communication", "Communication",
     ["again", "elim", "ugh", "huh"]),
]

RED, GREEN, YELLOW, BOLD, OFF = "\033[91m", "\033[92m", "\033[93m", "\033[1m", "\033[0m"


def frontmatter(skill_md: Path) -> dict:
    """Parse SKILL.md frontmatter. Uses PyYAML when available, else a flat scan."""
    text = skill_md.read_text()
    if not text.startswith("---\n"):
        return {}
    raw = text[4:].split("\n---\n", 1)[0]
    try:
        import yaml
        return yaml.safe_load(raw) or {}
    except ImportError:
        # Only metadata.summary is needed, so a two-line scan is enough.
        in_meta = False
        for line in raw.splitlines():
            if line.startswith("metadata:"):
                in_meta = True
                continue
            if in_meta:
                m = re.match(r'\s+summary:\s*"?(.*?)"?\s*$', line)
                if m:
                    return {"metadata": {"summary": m.group(1)}}
                if not line.startswith((" ", "\t")):
                    in_meta = False
        return {}


def blurb(category: str) -> str:
    """The category's one-line description: first paragraph of its README."""
    readme = SKILLS / category / "README.md"
    if not readme.exists():
        print(f"{RED}  missing skills/{category}/README.md{OFF}")
        return "(no category README)"
    lines = readme.read_text().splitlines()
    for i, line in enumerate(lines):
        if line.startswith("# "):
            for follow in lines[i + 1:]:
                if follow.strip():
                    # Lower-cased and stripped of its period so it reads as a
                    # clause after the folder path in the root README.
                    text = follow.strip().rstrip(".")
                    return text[0].lower() + text[1:]
            break
    print(f"{RED}  no blurb paragraph under the H1 in skills/{category}/README.md{OFF}")
    return "(no blurb)"


def discover(category: str, order: list[str]) -> tuple[list[tuple[str, str]], list[str]]:
    """Return [(command, summary)] for a category, plus any unlisted skill names."""
    found = sorted(p.name for p in (SKILLS / category).iterdir()
                   if p.is_dir() and (p / "SKILL.md").exists())
    unlisted = [n for n in found if n not in order]
    rows = []
    for name in [n for n in order if n in found] + unlisted:
        summary = (frontmatter(SKILLS / category / name / "SKILL.md").get("metadata") or {}).get("summary")
        if not summary:
            print(f"{RED}  missing metadata.summary: {category}/{name}/SKILL.md{OFF}")
            summary = "(no summary set)"
        rows.append((name, summary))
    return rows, unlisted


def build() -> tuple[str, list[str]]:
    """Render the whole index block. Returns the markdown and any unlisted skills."""
    sections, unlisted_all = [], []
    for category, title, order in CATEGORIES:
        if not (SKILLS / category).is_dir():
            print(f"{RED}  missing category directory: skills/{category}{OFF}")
            continue
        rows, unlisted = discover(category, order)
        unlisted_all += [f"{category}/{n}" for n in unlisted]
        table = "\n".join(
            ["| Command | What it does |", "|---|---|"]
            + [f"| [`/{n}`](skills/{category}/{n}/) | {s} |" for n, s in rows]
        )
        sections.append(
            f"### {title}\n\n"
            f"[`skills/{category}/`](skills/{category}/) - {blurb(category)}. "
            f"Usage, options and output format in "
            f"[its README](skills/{category}/README.md).\n\n"
            + table
        )
    return "\n\n".join(sections), unlisted_all


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report staleness without writing, exit 1 if stale")
    args = ap.parse_args()

    body, unlisted = build()

    root = REPO / "README.md"
    text = root.read_text()
    if BEGIN not in text or END not in text:
        print(f"{RED}{BOLD}No SKILL INDEX markers in README.md{OFF}")
        return 1

    new = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END),
                 f"{BEGIN}\n{body}\n{END}", text, flags=re.DOTALL)

    if unlisted:
        print(f"{YELLOW}{BOLD}Skills not in CATEGORIES order (appended alphabetically):{OFF}")
        for n in unlisted:
            print(f"{YELLOW}  {n}{OFF}")
        print(f"{YELLOW}  Add them to CATEGORIES in {Path(__file__).name} to fix their position.{OFF}")

    if args.check:
        if new != text:
            print(f"{RED}{BOLD}README index is STALE.{OFF}")
            print(f"{RED}  Run: python3 .github/scripts/sync-readme-index.py{OFF}")
            return 1
        print(f"{GREEN}{BOLD}README index is up to date.{OFF}")
        return 0

    if new != text:
        root.write_text(new)
        print(f"{YELLOW}  updated README.md{OFF}")
    print(f"{GREEN}{BOLD}README index regenerated.{OFF}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
