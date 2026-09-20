---
name: code-audit-jev
description: >-
  Cheap first-pass security audit of a repository, or a folder of hundreds of
  repositories, using TypeSafe's Jev: code splits every source, Terraform, CI
  and container file into units, computes regex facts, and asks Jev a fixed
  set of typed questions per unit (injection, missing authorization, tenant
  isolation, secrets, SSRF, traversal, deserialization, weak crypto,
  disclosure, XSS, insecure infra, supply chain, unsafe deletion, severity).
  Writes a spreadsheet of candidates sorted attention-first, ready for a
  person or a reasoning agent to trace. Use whenever the user wants a fast
  or cheap security scan of code, wants to triage many repos before a full
  /audit-security, or asks which files or repos deserve a deep review -
  even if they do not say "TypeSafe" or "Jev". Research proof of concept;
  a candidate list, not a verified finding list.
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
metadata:
  summary: "Unit-level security judgment of a repository, a fleet, or the units a pull request changed, with TypeSafe Jev: every function, Terraform block, CI job and Dockerfile judged against 22 rule files (one TOML file per category, add your own) and a severity scale; SARIF for the Security tab and a composite GitHub Action; about a cent per PR, a dollar per 300k lines"
---

# Code Audit Eval

> **Research proof of concept.** Jev reads one unit of code at a time. It
> can see what is in the unit, the file's imports and guard names, and a
> paragraph about the system; it cannot follow a call into another file,
> read a route table elsewhere, or reason about a lifecycle across
> services. So every row it produces is a **candidate** for a person or a
> reasoning agent to trace, and a clean unit means "nothing visible here",
> not "safe". Cross-file and architectural defects are outside its reach by
> design; the full `/audit-security` skill exists for those. Repeat the
> short form of this at the end of every run.

## What it does

1. **Inventory.** `scripts/inventory.py` walks the target, skips vendored,
   generated, lock and binary files, classifies each file's language and
   role (http_handler, event_worker, shared_library, frontend,
   infra_terraform, ci_pipeline, container, config, script, test, docs).
   A folder whose children are git repositories is a fleet: every
   repository is run separately and summarised in `fleet.csv`.
2. **Extract.** `scripts/extract.py` splits files into units: Python by
   `ast` (functions, methods, class bodies, the module top), TypeScript /
   JavaScript / Go / Java / Terraform by brace depth (declarations, route
   registrations, resource blocks), YAML / Dockerfile / shell as one unit
   per file. Units over ~4.4k tokens are chunked. Every unit carries the
   file's imports and the guard names found anywhere in the file.
3. **Rules.** `rules/*.toml`, one file per category (22 of them: injection, missing
   authorization, tenant isolation, IDOR, secrets, SSRF, open redirect, CSRF,
   traversal, upload validation, deserialization, XXE, NoSQL/LDAP injection,
   mass assignment, weak crypto, session and token handling, disclosure,
   XSS, resource exhaustion, insecure configuration, supply chain, unsafe
   deletion). Each declares the class text Jev chooses
   between, its yes/no questions, its regex signals (computed in code and
   handed to Jev as facts with line numbers) and how the answers compose
   into a vector. `_core.toml` holds the model, the scoring, the severity
   scale and the shared questions. `scripts/rules.py` loads the folder; the
   runner knows nothing about any category. `rules/README.md` is the
   author's guide; a repo adds its own rules with `--rules DIR`.
4. **Judge.** `scripts/run.py` sends each unit with the file context, the
   signals and the `app` paragraph to Jev in one request (one Choice, one
   Noul per declared question, 29 questions in all, one Score) and composes the answers: vectors
   ("missing authorization" is handles-request AND privileged AND
   no-auth-check, multiplied in code), a 0-100 score, a band, drops test and
   non-production units, and applies the rules' floors. About 7-9k tokens
   and 450 ms per unit (the 22 rules' questions are ~7k of that, sent once
   per unit and evaluated in parallel: a rule adds tokens, not calls).
5. **Report.** The same `run.py` prints the band counts and the attention
   rows, and writes `results.json` / `results.csv`, `findings.md` (one entry
   per file and category with the snippet, for the tracing agent), the PR
   summary and SARIF when asked, and `results.xlsx` if openpyxl is installed.
   `--diff BASE` judges only the units a change touched, on both sides of
   the merge base, and reports band rises. `--explain FILE[:UNIT]` prints
   the exact state Jev saw.
6. **Compare.** `scripts/compare.py` matches a run against a reference
   finding list (an `/audit-security` report, or a CSV) finding by finding.
7. **Share.** `action.yml` packages it as a composite GitHub Action:
   `uses: .../code-audit-jev@<sha>` with the key as a secret, SARIF to the
   Security tab.

Every question, class, weight, threshold and regex lives in `rules/`.

## Workflow

`SKILL_DIR` means the folder containing this SKILL.md.

### 1. Understand what the user wants

- **"Scan this repo"**: one target, default scope, then you read
  `findings.md` and explain the top candidates.
- **"Which of these N repos need a real audit"**: a fleet folder; the
  deliverable is `fleet.csv` plus the top candidates per repo.
- **"Is Jev good enough to replace the full audit"**: run both and use
  `compare.py`; the honest answer is in `references/methodology.md`.

### 2. Write the `app` paragraph

One paragraph about the system, written by you from the repo's docs
(CLAUDE.md, README, architecture docs). It must say: how requests are
authenticated and whether a framework gate covers every handler or each
handler must guard itself; how tenants or customers are isolated and where
the tenant id is supposed to come from; which inputs are trusted
(environment, CI substitutions); which resources are intentionally public;
which sanitizers and pinned clients exist. This is the difference between
Jev flagging every handler without a decorator and Jev knowing the
framework gate exists. Write it to the staging folder (your scratchpad or
`$TMPDIR/code-audit-jev/<timestamp>/app.md`), never into the target repo.
`mock-data/sample-repo/app.md` is a model.

### 3. Check prerequisites

```bash
python3 --version   # 3.10 or newer
test -n "$TYPESAFE_API_KEY" || test -f ~/.config/typesafe/env || echo "need a TypeSafe key"
```

Nothing to install: stdlib only (openpyxl, if present, adds an xlsx). Keys come from
https://console.typesafe.ai/keys; if the user has none, stop and ask.

### 4. Dry-run, then run

```bash
python3 "$SKILL_DIR/scripts/run.py" --target /path/to/repo --app "$STAGING/app.md" \
  --exclude archive --out "$STAGING/out" --dry-run
```

prints the file and unit counts, the role mix and the token estimate with
no API calls, and writes `units.json`. Exclude frozen or vendored trees the
inventory cannot recognise (`--exclude archive`). Then:

```bash
python3 "$SKILL_DIR/scripts/run.py" --target /path/to/repo --app "$STAGING/app.md" \
  --exclude archive --out "$STAGING/out" --workers 8
```

`--scope signals` judges only units with a regex signal or a
security-relevant role (about 40% cheaper, misses defects with no
greppable shape). `--include PREFIX` narrows to a directory. `--limit N`
is for a trial. `--labels labels.csv` (columns `path,category[,id]`)
scores agreement with a reference list. To debug one unit:
`python3 "$SKILL_DIR/scripts/run.py" --target REPO --explain path.py:fn --app app.md`
prints the exact state Jev saw and every answer.

For a fleet, point `--target` at the folder of repositories; one `app.md`
applies to all unless you run them separately with their own paragraph
(better: a paragraph per repo is where the accuracy is).

### 5. Read the candidates and trace the ones that matter

Open `findings.md`. For each entry in the Likely and Review bands, do what
the audit-security trace protocol does: open the unit, walk the path from
source to sink or from principal to capability, and decide. Jev has
already paid for the reading of every unit; you spend tokens only on the
rows it selected. Say which rows you traced and what each turned out to be
(real, a false positive with the fact that killed it, or unverifiable from
the unit alone).

### 6. Report back, as tables

1. **The run table**: files, lines, units judged, attention units,
   findings, bands, Jev tokens, cost, wall time (one row per repo for a
   fleet, from `fleet.csv`).
2. **The candidate table**: the Likely and Review rows with band, score,
   category, file:lines, unit, Jev signals, code signals, and your
   trace verdict for the ones you traced.
3. Where the spreadsheet and `findings.md` are; the offer to delete the
   staged files.
4. The disclaimer in two sentences: research proof of concept; candidates,
   not findings; cross-file and lifecycle defects are out of reach by
   design.

## Reading the output

| Column | Meaning |
|---|---|
| Attention | `YES` when the score is 50+ and a category was assigned, or the credential floor fired. Start here. |
| Category | Jev's issue-class choice when confident, else the strongest composed vector. `none` = nothing visible in the unit; `dropped` = test or non-production code. |
| Score (0-100) | 50% Jev's impact rating, 50% the strongest vector, discounted by half when Jev sees a mitigation in the unit. Weights in `rules/_core.toml`. |
| Band | 0-24 Clean, 25-49 Note, 50-74 Review, 75-100 Likely. Derived from the score. |
| Signals (Jev) | Defect questions answered at 0.5+, strongest first. |
| Code signals | Regex facts with the line, established before Jev was asked. |
| Mitigation P | Jev's probability that the unit itself defeats the defect. |

The Details sheet has every probability and the per-unit tokens and latency.

## Mock data

`mock-data/sample-repo/` is a fictional Flask + React + Terraform + GitHub
Actions portal with 27 labelled defects (`labels.csv`) across every class
and 17 hard negatives (`negatives.csv`: parameterized queries, confined
paths, sanitized HTML, SHA-pinned actions, a placeholder secret, a test
file). To regression-test:

```bash
cd "$SKILL_DIR/mock-data/sample-repo"
python3 ../../scripts/run.py --target . --app app.md --exclude labels.csv --exclude negatives.csv --exclude app.md --out /tmp/caj-mock
python3 ../../scripts/compare.py --results /tmp/caj-mock/results.json --reference labels.csv
```

Expected: 27/27 labelled defects flagged, 16/17 negatives clean (the one
is a bulk-delete helper Jev reads as unbounded work), about 375k tokens and
$0.02.

## Technical details

**Dependencies.** Python 3.11+ (tomllib), stdlib only; openpyxl adds an
xlsx if it happens to be installed. The TypeSafe call is plain `urllib` with
backoff.

**Limits.** Jev accepts 32k tokens of state plus the longest question; the
20 questions cost ~4k and the app paragraph ~600, so a unit may reach
~20k. `extract.py` caps units at ~4.4k tokens and chunks the rest.
Measured on a 303k-line repository: 5,273 units, ~5.5k tokens per unit
including overhead, 8 workers, about 6 minutes, about $1.20. Full numbers
and the comparison against `/audit-security` are in
`references/methodology.md`.

**Data handling.** Each request carries one unit's source code, the file's
import lines and guard names, and the app paragraph, to `api.typesafe.ai`.
Nothing else leaves the machine. Outputs default to
`<system temp>/code-audit-jev/<timestamp>/`. `results.json` does not
include the code; `findings.md` includes snippets of the attention units.

**Why Jev and not a scanner or an LLM.** A regex scanner cannot tell a
parameterized query from a formatted one reliably, cannot see that a
"path" concatenated onto a host is host control, and has no notion of
severity in context; that is why the rules' signals produce facts and Jev
produces judgments. A generative model reading every unit costs two to
three orders of magnitude more and, for a fleet, does not finish in an
afternoon. What Jev cannot do is trace; so the design is a cascade: Jev
reads everything for a dollar, the reasoning agent reads what Jev picked.
