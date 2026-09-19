# Jev

Skills built on TypeSafe's Jev, a decision model that answers typed questions about a document with calibrated numbers instead of generating text; code does the math, Jev does the judgment, and the agent does the fetching.

These differ from the other skills in this repository. Each one is a small
pipeline: the agent stages source documents into a temp folder from wherever
the user points it, a Python script computes statistics and sends the documents
to Jev with a fixed set of questions, and code combines the answers under
weights a reviewer can read in one file. They need a TypeSafe API key
(`TYPESAFE_API_KEY` or `~/.config/typesafe/env`) and a plain Python 3.10+
install; each script bootstraps its own private environment for its few
pure-Python dependencies on first run, so nothing is installed by hand.

Because they are more involved than the rest of the repository, each skill in
this folder carries its own `README.md` with the full detail: how it works,
usage, output, cost and time, results, and its legal disclaimer. This page is
only the index.

> **Research proofs of concept.** Everything here was built to test whether a
> methodology works. Where a skill touches a regulated area, such as hiring,
> its README opens with the disclaimer; read it before using the skill on
> anything real, and consult your own legal counsel first.

## Skills

| Skill | What it does | Detail |
|---|---|---|
| `resume-mirror-eval` | Scores a batch of resumes against a job description for how closely their wording mirrors the posting, flags the ones a human should read, and writes a sortable spreadsheet with evidence bullets and optional review notes. About a cent and ten seconds per hundred resumes. | [README](resume-mirror-eval/README.md) |

## Install

```bash
# Claude Code
git clone https://github.com/SecurityMindedSolutions/ai-skills.git
mkdir -p ~/.claude/skills
cp -R ai-skills/skills/jev/resume-mirror-eval ~/.claude/skills/

# Codex, Cursor, Cline and other Agent Skills hosts
npx skills add SecurityMindedSolutions/ai-skills --skill resume-mirror-eval
```

Paths inside each skill are relative to its own folder, so the same copy works
from any of those locations.
