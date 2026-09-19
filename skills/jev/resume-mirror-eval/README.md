# resume-mirror-eval

Give your AI agent a job description and a pile of resumes. Get back a
spreadsheet that says which resumes read like they were written *from* the
posting, and why, so a person knows which ones to read first.

**Contents:** [What it does](#what-it-does) ·
[How it works](#how-it-works) ·
[What the output is](#what-the-output-is) ·
[How to read it](#how-to-read-it) ·
[How to install and use it](#how-to-install-and-use-it) ·
[Cost and time](#cost-and-time) ·
[What it gets wrong](#what-it-gets-wrong) ·
[Files](#files)

## Disclaimer

- This is a research proof of concept. It was built to test whether one idea
  works: measuring how closely a resume's *wording* tracks a job description.
- It does not determine whether someone used AI. It makes no decision about
  any candidate.
- It produces a list of resumes a person should read first, with reasons. The
  first column, **Needs human review**, exists for exactly that. It directs
  human review; it does not replace it.
- Any use must comply with the laws, regulations and policies that apply to you
  and your applicants. Automated tools in hiring are regulated in many places.
- Talk to your legal team before using this on real applicants.
- Provided as is, for research and education, without warranty.
- Everything in `mock-data/` is fictional.

## What it does

- You give your AI agent one job description and a set of resumes.
- It scores every resume for how closely its *wording* tracks the posting.
- It flags the ones a person should read first, and says why in plain English.
- You get a spreadsheet, sorted, with a **Needs human review** column first.

Why wording, not keywords:

- A real platform engineer's resume mentions the same tools the posting asks
  for. So does a resume a chatbot wrote from the posting.
- Keyword matching cannot tell them apart.
- What does: whole phrases copied from the posting, requirements repeated back
  in the posting's order, no employers or numbers or dates behind the claims,
  and posting language ("you will", "the ideal candidate") in a document the
  applicant supposedly wrote.

## How it works

Two halves, each worth 50% of the mirror score:

**Plain statistics, computed in code.** No AI involved. Reproducible.

- Share of the posting's four-word phrases that appear verbatim in the resume
- Longest run of consecutive words the two documents share
- Whether matched terms show up in the same order as the posting
- Overall word-level similarity, relative to the rest of the batch
- How many of the posting's keywords and acronyms appear
- How far this resume sits from the batch average

**Seven judgments from TypeSafe's Jev.** Jev is a decision model, not a
chatbot: it answers typed questions with calibrated numbers in under a second.
For each resume it is asked:

- How much of the wording is copied or lightly reworded from the posting (0-3)
- How completely it claims every requirement, including the niche ones (0-3)
- How much concrete, checkable detail it has beyond the posting (0-3)
- Does it read like a generic template (probability)
- Does it contain job-posting language like "the ideal candidate" (probability)
- Are the claimed skills plausible for the listed roles (probability)
- Overall, which best describes it: genuine fit, tailored wording, generated
  from the posting, or weak fit (probabilities plus confidence)

Every question, weight and threshold is in one file,
[`scripts/questions.py`](scripts/questions.py). If you disagree with a score,
that is the file to change.

## What the output is

A spreadsheet, one row per resume, sorted so the most posting-like are on top.

| Column | What it tells you |
|---|---|
| **Needs human review** | TRUE if anything looked worth a look. Read these rows. It is a prompt, not a verdict. |
| **Mirror score** (0-100) | How closely the wording tracks the posting. Higher is closer. |
| **Verdict** | `high`, `moderate` or `low` bucket on that score. |
| **Fit** (0-100) | How much of the posting the resume covers. Kept separate so "strong fit, own words" looks different from "strong fit, copied words". |
| **Evidence** | Plain facts you can check against the two documents: "7 posting sentences appear verbatim", "8 of 9 posting acronyms present". |
| **Notes** | Two to four bullets from the agent on what to look at and what to ask on a phone screen. |

Plus every underlying number, for anyone who wants to re-weight.

## How to read it

- Start at the top. Rows are sorted with the most posting-like first.
- Read every row where **Needs human review** is TRUE. The evidence and notes say why it is there.
- A high mirror score with a high fit means the resume covers the posting *in the posting's words*. A low mirror score with a high fit is a strong candidate in their own words.
- A TRUE flag with a low score is common and fine: something looked worth a glance, the row explains it, you move on.

Here is the fictional set in `mock-data/`, as the spreadsheet shows it (full files in
[`mock-data/example-output/`](mock-data/example-output/)):

| Review | File | Mirror | Verdict | Fit | Evidence (first line) |
|---|---|---|---|---|---|
| **YES** | `linh_nguyen.md` | 70 | high | 69 | 7 posting sentences appear verbatim |
| **YES** | `soojin_kim.md` | 69 | high | 65 | 1 posting sentence appears verbatim |
| **YES** | `petr_ivanov.md` | 69 | high | 72 | 2 posting sentences appear verbatim |
| **YES** | `jordan_harris.md` | 53 | moderate | 65 | Longest shared word run is 8 words |
| **YES** | `arjun_singh.md` | 49 | moderate | 67 | Longest shared word run is 12 words |
| no | `tyler_brooks.md` | 25 | low | 45 | |
| **YES** | `marcus_chen.docx` | 16 | low | 54 | 8 of 9 posting acronyms present |
| no | `dana_whitfield.md` | 15 | low | 52 | |
| no | `hanna_mueller.md` | 14 | low | 13 | |
| no | `ngozi_okafor.md` | 11 | low | 26 | |
| no | `riya_patel.pdf` | 8 | low | 16 | |
| no | `andre_williams.md` | 7 | low | 4 | |
| no | `sofia_garcia.md` | 3 | low | 4 | |

Two rows in full, because they show what the flag means.

**A generated resume that added fake-looking numbers.** The numbers got past
the "does this have specifics" check, so it scored only moderate. The notes
carry the case:

```
arjun_singh.md   mirror 49   moderate   fit 67
Evidence:
- Longest shared word run is 12 words: "secrets and identity using hashicorp vault and aws iam with least-privilege access"
- 8 of 9 posting acronyms present (89%)
- 15% of posting 4-word phrases reused verbatim
Notes:
- Bullets follow the posting's order and wording, then append a metric to each; the metrics are all round (80%, 60%, 50%, 40%, 90%, 100%, 300%) and every uptime figure is 99.99%
- Named employers and dates are present, so the specifics score is high, but no metric is tied to a system, incident or timeframe
- Phone screen: pick two of the percentages and ask how they were measured
```

**A genuinely strong human candidate.** Flagged only because most of the
posting's acronyms appear. The row itself tells the reviewer to move on:

```
marcus_chen.docx   mirror 16   low   fit 54
Evidence:
- 8 of 9 posting acronyms present (89%)
Notes:
- Flagged only for acronym coverage; wording is the candidate's own, with tools the posting never mentions
- Concrete detail throughout: 14 AWS accounts, ~$2B volume, 31% cost reduction with the named levers
- Nothing here suggests the wording came from the posting
```

## How to install and use it

This is a skill for an AI coding agent (Claude Code, Codex, Cursor, Cline and
others). You install it once, then ask in plain language.

**1. Install**

```bash
# Claude Code
git clone https://github.com/SecurityMindedSolutions/ai-skills.git
mkdir -p ~/.claude/skills
cp -R ai-skills/skills/jev/resume-mirror-eval ~/.claude/skills/

# Codex, Cursor, Cline and other Agent Skills hosts
npx skills add SecurityMindedSolutions/ai-skills --skill resume-mirror-eval
```

**2. Add your TypeSafe key** (from https://console.typesafe.ai/keys). Either:

- `export TYPESAFE_API_KEY=...` in your shell, or
- a line `TYPESAFE_API_KEY=...` in the file `~/.config/typesafe/env`

**3. Ask your agent.** Examples that work:

> Run resume-mirror-eval on the posting in `~/Hiring/platform-eng/jd.pdf`
> against everything in `~/Hiring/platform-eng/applicants/`, with notes on the
> flagged ones.

> Use the resume mirror eval skill. The job description is the Senior Platform
> Engineer req in Greenhouse and the resumes are the 62 active applications on
> it. Put the spreadsheet in my Downloads folder.

> Which of the CVs in the shared Drive folder "Q4 SRE hiring" look like they
> were written from the posting? Here is the posting: [pasted text]

**4. The agent does the rest:**

- Pulls the documents from wherever you pointed it (folder, shared drive, ATS,
  link, pasted text) into a temporary folder.
- Runs the analysis.
- Writes the notes for the flagged resumes itself. No second AI account
  needed.
- Tells you how many need a human, which ones and why, where the spreadsheet
  is, and the disclaimer.
- Offers to delete the temporary copies of the resumes.

**Requirements:** Python 3.10 or newer, and the TypeSafe key. Nothing else to
install; the first run sets up what it needs in a temp folder by itself.

## Cost and time

Measured on the fictional set, one-page resumes, at TypeSafe's list price.
100 and 500 are extrapolated from timed runs at 25 and 50.

**Scores and evidence (the TypeSafe part):**

| Resumes | Cost | Time |
|---|---|---|
| 25 | $0.002 | 3 seconds |
| 100 | $0.01 | 10 seconds |
| 500 | $0.05 | 45 seconds |

- Two-page resumes: about double the cost, about the same time.
- This does not include the notes.

**Notes on the flagged resumes (the optional part):**

| Who writes them | Cost | Time |
|---|---|---|
| Your agent, as part of the run (default) | Covered by your agent's plan | A few seconds per flagged resume |
| Claude Opus 5 by API | About $0.012 per note | 5 to 10 seconds per note, 4 at a time |
| Claude Sonnet 5 by API | About $0.005 per note | 3 to 6 seconds per note, 4 at a time |

- API figures are estimates from list prices, not measurements.
- In the fictional set about 40% of resumes got flagged. Real batches should be
  lower.

**So for a posting with 100 applicants and 40 flagged:** about a cent and ten
seconds for the scores, then under a dollar and a couple of minutes for notes
with a frontier model, or no separate bill if your agent writes them.

## What it gets wrong

- A generated resume that invents named employers and round-number metrics
  looks specific. It lands in "moderate" instead of "high". That is the right
  outcome: it needs a human, and the notes say why.
- Someone who honestly tailors their resume hard to the posting will score
  "moderate". That is why the output is a review list, not a decision.
- If the posting itself is boilerplate, everyone scores higher. The batch
  z-score column is the better guide then.
- Scanned PDFs with no text layer are reported as errors, not scored.
- Jev is English-first. Other languages work with less accuracy.
- The fictional set separates cleanly. That proves the mechanics work, not
  that the method works on real applicants. Real, labelled data is the next
  step.

## Files

| File | What it is |
|---|---|
| [`SKILL.md`](SKILL.md) | Instructions the agent follows, step by step |
| [`scripts/questions.py`](scripts/questions.py) | Every question, weight and threshold |
| [`scripts/analyze.py`](scripts/analyze.py) | The script the agent runs (`python3 scripts/analyze.py --help`) |
| [`references/methodology.md`](references/methodology.md) | Why each signal exists and what fools it |
| [`mock-data/`](mock-data/) | Fictional posting, 13 fictional resumes, labels, and a finished example run |
