# resume-mirror-eval

## Disclaimer: research proof of concept, not a hiring tool

This skill was built to test whether a methodology works: measuring how
closely a resume's *wording* tracks a job description using TypeSafe's Jev
decision model plus plain text statistics. It is published so others can look
at the approach, run it on the fictional data in `mock-data/`, and improve it.

**It does not and cannot determine whether a person used AI to write their
resume.** A candidate whose experience genuinely matches a role will score
above the average of the batch. Its output is a list of resumes a human should
read first, with the reasons spelled out. It is not a ranking, not a filter,
and not evidence of anything about a candidate. The first column of every
result is "Needs human review", and that is exactly what it means.

**The use of automated tools in hiring is regulated.** Depending on where you
and your applicants are, that may include the EU AI Act (employment is a
high-risk use), New York City Local Law 144 (bias audits and notice for
automated employment decision tools), the Illinois Artificial Intelligence
Video Interview Act and the 2026 amendment to the Illinois Human Rights Act,
Colorado SB 24-205, and US EEOC guidance on algorithmic tools under Title VII
and the ADA. Requirements commonly include candidate notice, independent bias
auditing, record-keeping, and a human decision-maker.

**If you use this, or anything derived from it, on real applicants, you are
solely responsible for complying with every law and regulation that applies to
you, and you should consult your own legal counsel before doing so.** The
author offers it for research and education only, as is, without warranty of
any kind, and accepts no responsibility for how it is used.

All data in `mock-data/` is fictional. The company, the candidates, their
employers and their histories were invented for this demonstration. Any
resemblance to a real person or employer is coincidental.

---

## What it does

Point it at one job description and a set of resumes. It scores every resume
for how closely its wording mirrors the posting, flags the ones a human should
read before anyone ranks them, and writes a spreadsheet you can sort.

The question it answers is narrow on purpose. A platform engineer who has run
EKS, Terraform and ArgoCD for six years will mention EKS, Terraform and ArgoCD,
and so will a resume a chatbot produced from the posting. Keyword scans cannot
tell those apart. What separates them is *how* the words appear: verbatim
phrases and whole sentences lifted from the posting, requirements restated as
experience in the posting's order, generic text with no employers, dates,
systems or numbers behind it, and posting register ("you will", "the ideal
candidate") leaking into a document supposedly written by the applicant.

### How it works

Two layers, combined half and half into a 0-100 **mirror score**:

- **Statistics in code.** Share of the posting's four-word phrases reused
  verbatim, the longest shared run of words, whether matched terms appear in the
  posting's order, TF-IDF cosine within the batch, keyword and acronym coverage,
  and a z-score against the rest of the batch. Deterministic and reproducible
  without any model.
- **Judgments from TypeSafe's Jev.** One request per resume carrying the posting
  and the resume as state, and seven typed questions answered in parallel:
  phrasing mirror (0-3), requirement echo (0-3), concrete specifics (0-3),
  generic template (probability), posting-language leak (probability), career
  consistency (probability), and a four-way overall read with its confidence.
  Jev is a decision model, not a text generator: it returns calibrated numbers
  in under a second, at roughly a tenth of a cent per resume.

Fit is reported in its own column so "strong fit, own words" and "strong fit,
copied words" look different on the sheet. Every question, weight and threshold
lives in one file, `scripts/questions.py`, so the part a reviewer should read is
in one place.

### Needs human review

The first column. TRUE when *any* signal fired: a moderate or high score, a
batch outlier, an evidence bullet, a Jev flag, or the review notes' own `review:
yes`. It is generous on purpose and it is a prompt to read, not a judgment. In
the mock batch it flags a genuinely strong human match on acronym coverage
alone; the reviewer opens the row, sees a low mirror score, a `genuine_fit`
read and a note saying the wording is the candidate's own, and moves on.

### Evidence and notes

Each flagged row carries plain-language **evidence bullets computed in code**
that a reviewer can check against the two documents:

```
- 7 JD sentences appear verbatim, e.g. "Build and maintain CI/CD pipelines in GitHub Actions and ArgoCD, enabling safe, frequent..."
- Longest shared word run is 80 words: "infrastructure as code using terraform and terragrunt with reusable modules ..."
- 9 of 9 JD acronyms present (100%), all of them
- 36% of JD 4-word phrases reused verbatim
- Few concrete specifics: employers, dates, numbers or named systems are thin
```

Optionally, **review notes**: two to four terse bullets per flagged resume,
no summary sentence, ending in `review: yes` or `review: no`. By default the
agent running the skill writes them itself from `notes-request.json`, so no
second API key is needed and the skill works the same in Claude Code, Codex,
Cursor or any other agent. For unattended runs, `--llm-notes anthropic` or
`--llm-notes openai --llm-model <id>` (any OpenAI-compatible endpoint) does it
by API.

### Inputs and where they come from

The script reads local files (.pdf, .docx, .txt, .md). The agent does the
fetching: local or synced folders are passed straight through; files behind a
connector, an ATS MCP server, a URL or an email are staged into a temp folder
first. When the source is an ATS, a `manifest.csv` carries the application id,
candidate and source link into the spreadsheet next to each file. Staged copies
and outputs live under the system temp directory, never beside the user's
files, and the agent offers to delete the staged resumes when the run is done.
The only network calls are to `api.typesafe.ai` and, if opted in, the notes
provider.

### Output

`results.xlsx` sorted by mirror score, plus `results.csv` and `results.json`.
Sheets: Results, Summary (counts, Jev model and token cost, run time, label
metrics if given), the job description, and a Read me with the disclaimer and a
column guide. Rows are color-coded by verdict and the review flag is bold red.

### Example output

[`mock-data/example-output/`](mock-data/example-output/) holds a complete run
on the mock set: `results.xlsx`, `results.csv`, `results.json`, and
`agent-notes.json` (the review notes the agent wrote, exactly as merged). The
Results sheet, abridged to the columns a reviewer scans first:

| Review | File | Mirror | Verdict | Fit | Overall read | Evidence (first bullet) |
|---|---|---|---|---|---|---|
| **YES** | `linh_nguyen.md` | 70.0 | high | 69.1 | generated_from_posting | 7 JD sentences appear verbatim, e.g. "- Build and maintain CI/CD pipel... |
| **YES** | `soojin_kim.md` | 69.3 | high | 64.6 | generated_from_posting | 1 JD sentence appears verbatim, e.g. "- Expert-level Terraform skills... |
| **YES** | `petr_ivanov.md` | 68.6 | high | 71.5 | generated_from_posting | 2 JD sentences appear verbatim, e.g. "- Strong understanding of observ... |
| **YES** | `jordan_harris.md` | 53.2 | moderate | 64.7 | generated_from_posting | Longest shared word run is 8 words: "soc 2 type ii and pci dss complia... |
| **YES** | `arjun_singh.md` | 49.4 | moderate | 66.5 | generated_from_posting | Longest shared word run is 12 words: "secrets and identity using hashi... |
| no | `tyler_brooks.md` | 25.2 | low | 44.5 | tailored_wording |  |
| **YES** | `marcus_chen.docx` | 15.5 | low | 53.6 | genuine_fit | 8 of 9 JD acronyms present (89%) |
| no | `dana_whitfield.md` | 14.6 | low | 52.3 | genuine_fit |  |
| no | `hanna_mueller.md` | 13.6 | low | 13.3 | weak_fit |  |
| no | `ngozi_okafor.md` | 11.1 | low | 25.5 | genuine_fit |  |
| no | `riya_patel.pdf` | 8.4 | low | 16.4 | weak_fit |  |
| no | `andre_williams.md` | 6.5 | low | 4.4 | weak_fit |  |
| no | `sofia_garcia.md` | 3.2 | low | 4.1 | weak_fit |  |

Two rows in full, because they show what the flag means. The polished
generated resume, where invented metrics got past the specifics judge and the
notes carry the case:

```
arjun_singh.md   mirror 49.4   verdict moderate   fit 66.5   read generated_from_posting
Evidence (code):
- Longest shared word run is 12 words: "secrets and identity using hashicorp vault and aws iam with least-privilege access"
- 8 of 9 JD acronyms present (89%)
- 15% of JD 4-word phrases reused verbatim
LLM notes:
- Bullets follow the posting's order and wording, then append a metric to each; the metrics are all round (80%, 60%, 50%, 40%, 90%, 100%, 300%) and every uptime figure is 99.99%
- Named employers and dates are present, so the specifics score is high, but no metric is tied to a system, incident or timeframe
- Phone screen: pick two of the percentages and ask how they were measured
```

And the genuinely strong human match, flagged on acronym coverage alone, where
the row itself tells the reviewer to move on:

```
marcus_chen.docx   mirror 15.5   verdict low   fit 53.6   read genuine_fit
Evidence (code):
- 8 of 9 JD acronyms present (89%)
LLM notes:
- Flagged only for acronym coverage; wording is the candidate's own, with tools the posting never mentions (Karpenter, Cilium, cosign, Thanos, Loki, Patroni, Strimzi)
- Concrete detail throughout: 14 AWS accounts, ~$2B volume, 31% cost reduction with the named levers, a 200-star Terraform provider
- Nothing here suggests the wording came from the posting
```

The remaining columns hold every individual statistic and Jev answer (0-3
scores, probabilities, the overall-read choice and its confidence), so anyone
who disagrees with the weighting can re-derive their own score from the sheet.

### Usage

This is an agent skill, not a command-line tool. You install it into your
coding agent once, then ask for what you want in plain language; the agent
reads `SKILL.md`, fetches and stages the documents, runs the analysis, writes
the review notes, and reports back with the disclaimer.

**1. Install it into your agent.**

```bash
# Claude Code
git clone https://github.com/SecurityMindedSolutions/ai-skills.git
mkdir -p ~/.claude/skills
cp -R ai-skills/skills/jev/resume-mirror-eval ~/.claude/skills/

# Codex, Cursor, Cline and other Agent Skills hosts
npx skills add SecurityMindedSolutions/ai-skills --skill resume-mirror-eval
```

Set your TypeSafe key once, either `export TYPESAFE_API_KEY=...` or a line
`TYPESAFE_API_KEY=...` in `~/.config/typesafe/env`. Keys come from
https://console.typesafe.ai/keys.

**2. Ask.** Some things that work, in Claude Code, Codex or wherever you
installed it:

> Run resume-mirror-eval on the posting in `~/Hiring/platform-eng/jd.pdf`
> against everything in `~/Hiring/platform-eng/applicants/`, and write notes on
> the flagged ones.

> Use the resume mirror eval skill. The job description is the Senior Platform
> Engineer req in Greenhouse and the resumes are the 62 active applications on
> it. Put the spreadsheet in my Downloads folder.

> Which of the CVs in the shared Drive folder "Q4 SRE hiring" look like they
> were written from the posting? Here is the posting: [pasted text]

> Re-run yesterday's resume screen with a 55 threshold for "high" instead of 65.

The agent stages the documents in a temp folder, runs the script, writes two to
four review bullets per flagged resume itself (no second API key), merges them,
and tells you how many resumes need a human, which ones and why, where the
spreadsheet is, and the disclaimer. It offers to delete the staged copies when
it is done.

**3. Read the spreadsheet.** Sort by anything you like; the first column is
the one that matters, and the evidence and notes columns say why each row is
there.

Requirements: Python 3.10 or newer and a TypeSafe API key. Nothing to install
beyond the skill: on first run the script creates a private virtual
environment under the system temp directory with the `venv` and `pip` that
ship with Python, puts its two pure-Python dependencies (pypdf, openpyxl)
there, and re-runs itself from it. `.docx` is parsed with the standard
library. If that bootstrap cannot happen (no pip, no network) the script
continues with reduced output: CSV instead of xlsx, and PDF only via
`pdftotext` if present.

#### Under the hood

What the agent runs. You can run it yourself, for scripting or to reproduce a
result:

```bash
python3 scripts/analyze.py --jd posting.md --resumes ./resumes --llm-notes agent
python3 scripts/analyze.py --out <same out folder> --merge-notes notes.json
```

| Flag | Purpose |
|---|---|
| `--jd` | Job description: file, folder holding one file, or `-` for stdin |
| `--resumes` | One or more files and folders |
| `--out` | Output folder (default: a timestamped folder under the system temp dir) |
| `--llm-notes agent\|anthropic\|openai` | Add review notes; `agent` writes a request file for the host agent |
| `--merge-notes notes.json` | Fold agent-written notes back into an existing `--out` |
| `--manifest manifest.csv` | Carry ids (`file` plus any columns) into the sheet |
| `--labels labels.csv` | Score the run against `human` / `ai_tailored` labels |
| `--llm-top N`, `--workers N`, `--model`, `--no-color` | The usual |

Anyone who has [uv](https://docs.astral.sh/uv/) can use `uv run
scripts/analyze.py ...` instead and skip the bootstrap.

### Mock data and results

`mock-data/` holds a fictional posting and 13 fictional resumes with labels: 8
written as a person would (two very close matches to the posting, one with a
keyword-padded skills section, two off-target) and 5 written the way a
generator produces them from a posting, in different styles. On that set the
generated resumes score 49-70 and the human ones 3-25; the two close human
matches land at 15-16 with a fit signal of 52. The polished generated resume
with invented round-number metrics fools the specifics judge and lands in
"moderate", which is the right answer: it needs a human, and the notes say why.
Separable mock data proves the mechanics, not the method; real, labelled data
is the next step and `--labels` reports the numbers when it arrives.

### Cost and time

**The Jev pass.** Measured on the mock set (one-page resumes, about 2,200 Jev
input tokens each including the posting) at Jev's list price of $0.042 per
million input tokens, output free. Wall time includes text extraction, the
statistics and writing the spreadsheet, all of which is a rounding error next
to the network calls. Runs at 25 and 50 resumes were timed directly; 100 and
500 are extrapolated, which is safe because every resume is one independent
request and the batch stays far below Jev's rate limits (1,200 requests and
250,000 tokens per second). **This table does not include review notes.**

| Resumes | Jev tokens | Jev cost | Wall time, 1 worker | Wall time, 4 workers (default) |
|---|---|---|---|---|
| 25 | 56k | $0.002 | 8 s | 3 s |
| 100 | 220k | $0.009 | 35 s | 10 s |
| 500 | 1.1M | $0.05 | 3 min | 45 s |

Two-page resumes roughly double the tokens and the cost; time is dominated by
request latency, not size, so it barely moves. Re-running a batch after a
threshold change costs the same again.

**The notes pass, if you turn it on.** Only flagged rows get notes (about 40%
of the mock set, which is higher than a real batch should be since five of its
thirteen resumes were written to be caught). Per note the model reads the
posting, the resume, the scores and the code evidence (about 1,700 input
tokens) and writes four bullets plus a review line (about 150 output tokens).
API notes run through the same worker pool as the Jev calls, four at a time by
default. These figures are estimates from list prices and typical response
times, not measurements:

| Notes provider | Per note | 40 notes (100 resumes, 40% flagged) |
|---|---|---|
| The agent running the skill (`--llm-notes agent`) | Your agent's plan; a few seconds of reading and writing per resume | No separate bill; several minutes of agent time |
| Claude Opus 5 by API | about $0.012, 5 to 10 s | about $0.50; 1 to 2 min at 4 workers |
| Claude Sonnet 5 by API | about $0.005, 3 to 6 s | about $0.20; under a minute at 4 workers |
| Any OpenAI-compatible model | that model's rate on ~1,700 in / ~150 out | varies |

**End to end, 100 resumes, 40 flagged:**

| Configuration | Time | Cost |
|---|---|---|
| Scores and evidence only | about 10 s | about $0.01 |
| Plus notes from the agent running the skill | 10 s plus the agent's reading time, typically a few minutes | about $0.01 plus your agent plan |
| Plus notes from Claude Opus 5 by API | 1 to 2 min | about $0.50 |
| Plus notes from Claude Sonnet 5 by API | under a minute | about $0.20 |

The shape is what matters: the statistical pass on a hundred applicants costs
about a cent and finishes before you have switched windows; the notes on the
forty that need a look are the only real cost, and even with a frontier model
they come in under a dollar.

### Customization

- Weights, thresholds and every Jev question: [`scripts/questions.py`](scripts/questions.py).
- Evidence bullet rules: [`scripts/evidence.py`](scripts/evidence.py).
- Notes prompt and providers: [`scripts/llm_notes.py`](scripts/llm_notes.py).
- Why each signal exists and what fools it: [`references/methodology.md`](references/methodology.md).
- How an agent runs it, step by step: [`SKILL.md`](SKILL.md).
