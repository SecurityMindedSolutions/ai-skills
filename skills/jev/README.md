# Jev

Skills built on TypeSafe's Jev, a decision model that answers typed questions about a document with calibrated numbers instead of generating text; code does the math, Jev does the judgment, and the agent does the fetching.

These differ from the other skills in this repository. Each one is a small
pipeline: the agent stages source documents into a temp folder from wherever
the user points it, a Python script computes statistics and sends the documents
to Jev with a fixed set of questions, and code combines the answers under
weights a reviewer can read in one file. They need a TypeSafe API key
(`TYPESAFE_API_KEY` or `~/.config/typesafe/env`) and a plain Python 3.10+
install; each script bootstraps its own private environment for its few
pure-Python dependencies on first run, so nothing is installed by hand
(`code-audit-jev` and `jev-email-analysis` are stdlib-only, and `code-audit-jev`
also runs as a GitHub Action).

Because they are more involved than the rest of the repository, each skill in
this folder carries its own `README.md` with the full detail: how it works,
usage, output, cost and time, results, and its legal disclaimer. This page is
only the index.

> **Research proofs of concept.** Each was built to test whether a methodology
> works. Each README opens with its own disclaimer: the hiring skill directs
> human review and must be used in compliance with applicable law with your
> legal team's advice; the injection skill is a signal for a gate, to be
> evaluated on your own traffic and run in alert mode before block mode; the
> traffic skill is a triage signal, not an incident finding, to be verified
> against the raw log before acting; the code audit skill produces candidates
> for a person or agent to trace, not confirmed vulnerabilities; the email skill
> is a second reader for an analyst, not a mail gateway, and performs no
> authentication, DNS or detonation of its own.

## Skills

| Skill | What it does | Detail |
|---|---|---|
| `resume-mirror-eval` | Scores a batch of resumes against a job description for how closely their wording mirrors the posting, flags the ones a human should read, and writes a sortable spreadsheet with evidence bullets and optional review notes. About a cent and ten seconds per hundred resumes. | [README](resume-mirror-eval/README.md) |
| `prompt-injection-eval` | Scores prompts for injection before they reach your LLM and returns allow / review / block with a risk score and reasons; a reference gate a backend can call, plus an evaluator that measures Jev against a regex list and an LLM judge on labelled prompts. About 300 ms and 7 cents per thousand prompts. | [README](prompt-injection-eval/README.md) |
| `traffic-triage-eval` | Triages edge-log traffic (GCP LB, AWS ALB / WAF, CloudFront, nginx) per client IP as benign user, benign bot, AI agent, background scanning or malicious, with a 0-100 threat score, the signals and the paths, and carves out the raw rows of anything worth a look, from a documented JSON event schema the agent fills from any log source. About 340 ms and 15 cents per thousand IPs. | [README](traffic-triage-eval/README.md) |
| `code-audit-jev` | Unit-level security judgment of a repository, a folder of repositories, or the units a pull request changed: every function, Terraform block, CI job and Dockerfile judged against 22 rule files (injection, missing authorization, IDOR, secrets, SSRF, CSRF, XXE, mass assignment, session handling, supply chain and more) with a 0-100 score, SARIF for the Security tab, and a composite GitHub Action. About a cent per PR, about a dollar per 300k lines. | [README](code-audit-jev/README.md) |
| `jev-email-analysis` | Classifies what an email is trying to get someone to do: a category across 16 classes (vendor payment fraud / BEC, fake invoice, executive impersonation, payroll diversion, credential harvest, OAuth consent, malware delivery, callback/TOAD, QR, extortion, advance-fee, reconnaissance, bulk spam, cold outreach, legitimate), eight red-flag signals including prompt injection aimed at AI readers, risk and pressure scores, and a malicious / suspicious / spam / benign verdict. Categories are a folder of TOML rule files you can extend. Input is one schema in which every field is optional, so a subject and body off a screenshot is a valid run. About 2,500 tokens and a fraction of a cent per email. | [README](jev-email-analysis/README.md) |
| `run-jev` | Ad-hoc typed judgments over any list from inside a Claude Code session: the agent shapes choice / noul / score questions from a plain-language ask, a stdlib runner fans them out, and the report gives distributions, low-confidence items and agreement against your own labels. Under a cent and seconds per hundred items. | [README](run-jev/README.md) |

## Install

```bash
# Claude Code
git clone https://github.com/SecurityMindedSolutions/ai-skills.git
mkdir -p ~/.claude/skills
cp -R ai-skills/skills/jev/resume-mirror-eval ~/.claude/skills/
cp -R ai-skills/skills/jev/prompt-injection-eval ~/.claude/skills/
cp -R ai-skills/skills/jev/traffic-triage-eval ~/.claude/skills/
cp -R ai-skills/skills/jev/code-audit-jev ~/.claude/skills/
cp -R ai-skills/skills/jev/jev-email-analysis ~/.claude/skills/
cp -R ai-skills/skills/jev/run-jev ~/.claude/skills/

# Codex, Cursor, Cline and other Agent Skills hosts
npx skills add SecurityMindedSolutions/ai-skills --skill resume-mirror-eval
npx skills add SecurityMindedSolutions/ai-skills --skill prompt-injection-eval
npx skills add SecurityMindedSolutions/ai-skills --skill traffic-triage-eval
npx skills add SecurityMindedSolutions/ai-skills --skill code-audit-jev
npx skills add SecurityMindedSolutions/ai-skills --skill jev-email-analysis
npx skills add SecurityMindedSolutions/ai-skills --skill run-jev
```

Paths inside each skill are relative to its own folder, so the same copy works
from any of those locations.
