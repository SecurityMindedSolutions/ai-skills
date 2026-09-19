# Resume Mirror Eval

Give your AI agent a job description (JD) and a set of resumes. Get back a
spreadsheet evaluating which resume MAY have used the JD to generate the resume, with the evidence, so a person knows which ones to investigate first.

**Contents**

- [Disclaimer](#disclaimer)
- [How this is different](#how-this-is-different)
- [What it does](#what-it-does)
- [How it works](#how-it-works)
- [What the output is](#what-the-output-is)
- [How to read it](#how-to-read-it)
- [How to install and use it](#how-to-install-and-use-it)
- [Cost and time](#cost-and-time)
- [What it gets wrong](#what-it-gets-wrong)
- [Files](#files)

## Disclaimer

This is a research proof of concept, built to test whether one idea works:
measuring how closely a resume's wording tracks a job description. It does not
determine whether someone used AI, and it says nothing about whether a
candidate is right for the job. Its output is a list of resumes a person
should read first, with the reasons. The first column, **Needs human review**,
exists for exactly that purpose: this directs human review, it does not
replace it.

Any use must comply with the laws, regulations and policies that apply to you
and your applicants; automated tools in hiring are regulated in many places.
Consult your legal team before using this on real applicants. It is provided as
is, for research and education, without warranty. Everything in `mock-data/`
is fictional.

## How this is different

Most "AI resume screening" means handing resumes to a chatbot and asking for an
opinion. This does not do that. The scoring is done by
[TypeSafe's Jev](https://typesafe.ai), a separate tool from whatever AI agent
you use. Jev is a decision model, not a text generator: you give it two
documents and a fixed set of typed questions, and it returns numbers (a 0-3
score, a probability) that come out the same way every time for the same
input. The mirror score is built from those numbers alone, with the weights
written down in one file for anyone to read. Plain code adds the text match
analysis, and your AI agent adds its own analysis; neither touches the score.

Your AI agent (Claude Code, Codex, Cursor or similar) does the fetching, runs
the analysis, and writes the short review notes. Jev does the judging.

**You need a TypeSafe account to use this.** Sign up at
[typesafe.ai](https://typesafe.ai) (there is currently a waitlist), then create
an API key at [console.typesafe.ai/keys](https://console.typesafe.ai/keys).
The cost is small: about a cent per hundred resumes, detailed under
[Cost and time](#cost-and-time).

## What it does

- You give your AI agent one job description and a set of resumes.
- It scores every resume file for how closely its *wording* tracks the posting.
- It marks the files a person should read first and says why, three ways: Jev's score, exact text-match counts, and your AI agent's own read.
- You get a sorted spreadsheet. Here is the end result on the fictional set in
`mock-data/`, trimmed to the first bullet of each analysis column to fit the page
(full files in [`mock-data/example-output/`](mock-data/example-output/)):


| Needs human review | File | Mirror score (Jev) | Text match analysis (code) | AI analysis (agent) |
|---|---|---|---|---|
| **YES** | `soojin_kim.md` | 89 | 1 posting sentence appears verbatim, e.g. "Expert-level Terraform skills and a s... | The resume's "Key Qualifications" section copies the JD's "What we are looking for" list word for word, so it tells you what the posting asked for, no... |
| **YES** | `petr_ivanov.md` | 82 | 2 posting sentences appear verbatim, e.g. "Strong understanding of observability... | The resume's opening "Mission" paragraph is the JD's "About the role" paragraph reworded into the first person, so the candidate's stated goal is the... |
| **YES** | `linh_nguyen.md` | 80 | 7 posting sentences appear verbatim, e.g. "Build and maintain CI/CD pipelines in... | The resume's current-job bullets copy the JD's "What you will do" list: all nine duties, in the JD's order, in nearly the JD's words, which is what yo... |
| **YES** | `jordan_harris.md` | 70 | Longest shared word run is 8 words: "soc 2 type ii and pci dss compliance" | The resume's current-job bullets restate the JD's "What you will do" list with one word swapped per bullet (the JD's "Design, build and operate" becom... |
| **YES** | `arjun_singh.md` | 48 | Longest shared word run is 12 words: "secrets and identity using hashicorp vault... | The resume's current-job bullets follow the JD's "What you will do" list in order and wording, with a percentage added to the end of each, so the resu... |
|  | `tyler_brooks.md` | 33 |  |  |
| **YES** | `marcus_chen.docx` | 15 | 8 of 9 posting acronyms present (89%) | Flagged only because most of the JD's acronyms appear in the resume, which is expected for someone who has this stack; the resume's wording is its own... |
|  | `dana_whitfield.md` | 15 |  |  |
|  | `hanna_mueller.md` | 12 |  |  |
|  | `ngozi_okafor.md` | 9 |  |  |
|  | `riya_patel.pdf` | 6 |  |  |
|  | `andre_williams.md` | 2 |  |  |
|  | `sofia_garcia.md` | 2 |  |  |


Why wording, not keywords: a real platform engineer's resume mentions the same
tools the posting asks for, and so does a resume a chatbot wrote from the
posting. Keyword matching cannot tell them apart. What can: whole phrases
copied from the posting, requirements repeated back in the posting's order, no
employers, numbers or dates behind the claims, and posting language ("you
will", "the ideal candidate") in a document the applicant supposedly wrote.

The tool looks only at the file's relationship to the posting. It does not
rate the candidate's qualifications or fit, on purpose.

## How it works

Three separate methods, each with its own column. None of them feeds another.

**1. Mirror score (Jev).** For each resume, one request goes to TypeSafe's Jev
carrying the posting and the resume, with six fixed questions. Jev answers all
six at once, in under a second, for about a tenth of a cent, as numbers. The
mirror score is built from those six answers and nothing else, using weights
written down in one file. The questions:

- How much of the wording is copied or lightly reworded from the posting (0-3)
- How completely it claims every requirement, including the niche ones, in the posting's order (0-3)
- How much concrete, checkable detail it has beyond the posting (0-3)
- Does it read like a generic template (probability)
- Does it contain job-posting language like "the ideal candidate" (probability)
- Are the claimed skills plausible for the listed roles (probability)

**2. Text match analysis (code).** Plain Python string matching, no AI of any
kind. The script counts things and fills the counts into fixed sentences:

- Posting sentences that appear verbatim in the resume, with a quote
- The longest run of consecutive words the two documents share
- How many of the posting's acronyms appear
- The share of the posting's four-word phrases reused word for word
- Whether matched terms show up in the posting's order

That is why every row uses the same wording: "N posting sentences appear
verbatim, e.g. ..." is a template with the number and the quote pasted in.
These counts do not enter the mirror score. They are there so a person can
check Jev's number against something concrete.

**3. AI analysis (agent).** Your AI agent reads each flagged resume against the
posting itself and writes two to four observations in its own words: things
that cannot be counted, like "every metric is a round number" or "employers are
unnamed", plus something to ask on a phone screen. This is the only column an
AI writes. It is not scored; the agent's closing `review: yes` or `review: no`
is the one thing from it that feeds the review flag.

Every Jev question, weight and threshold is in one file,
[`scripts/questions.py`](scripts/questions.py). If you disagree with how
something scored, that is the file to change.

## What the output is

A spreadsheet (`results.xlsx`), one row per resume file, sorted with the most
posting-like on top. The first sheet has just the five columns below. A second
sheet, **Details**, has every statistic and Jev answer behind the score for
anyone who wants to check the math or re-weight it. The same two views are
written as `results.csv` and `results-detail.csv`, plus `results.json`.


| Column | Who produces it | What it tells you |
|---|---|---|
| **Needs human review** | The script (an OR of the other three) | YES if anything looked worth a look, blank otherwise. It means "a person should read this file", nothing more. |
| **File** | | The resume file name (plus any ids your agent carried over from an ATS). |
| **Mirror score (Jev)** | TypeSafe's Jev | 0-100. How closely the file's wording tracks the posting. Higher is closer. No grades or buckets, on purpose. |
| **Text match analysis (code)** | Python string matching, no AI | Exact counts a person can verify: "7 posting sentences appear verbatim", "8 of 9 posting acronyms present". |
| **AI analysis (agent)** | Your AI agent | Two to four bullets from reading the resume: what it noticed, why that matters, and what to ask on a phone screen. |


## How to read it

- Start at the top. Rows are sorted with the most posting-like first.
- Read every row marked **YES**. The text match and AI analysis columns say why it is there.
- A YES with a low score is normal: something looked worth a glance, the row
explains it, you move on.
- Nothing on the sheet says whether a candidate is qualified. That is your
call, made by reading the resume.

Two rows from the example, in full, because they show what the flag means
and how the three columns differ.

**A generated resume that added fake-looking numbers.** The numbers got past
the "does this have specifics" question, so the score is middling. The AI
analysis carries the case:

```
arjun_singh.md   mirror score 48
Text match analysis (code):
- Longest shared word run is 12 words: "secrets and identity using hashicorp vault and aws iam with least-privilege access"
- 8 of 9 posting acronyms present (89%)
- 15% of posting 4-word phrases reused verbatim
AI analysis (agent):
- The resume's current-job bullets follow the JD's "What you will do" list in order and wording, with a percentage added to the end of each, so the results look measured but the underlying claims are still the posting's
- Every percentage in the resume is a round number (80%, 60%, 50%, 40%, 90%, 100%, 300%) and every uptime figure is 99.99%, which is what invented metrics tend to look like
- The resume's employers and dates look real, but no number is tied to a specific system, incident or time period, so the specifics may be decoration rather than evidence
- Phone screen: pick two of the percentages and ask how they were measured; real ones come with a story, invented ones do not
```

**A strong human candidate, in their own words.** Flagged only because most of
the posting's acronyms appear. The row itself tells the reviewer to move on:

```
marcus_chen.docx   mirror score 15
Text match analysis (code):
- 8 of 9 posting acronyms present (89%)
AI analysis (agent):
- Flagged only because most of the JD's acronyms appear in the resume, which is expected for someone who has this stack; the resume's wording is its own and names tools the JD never mentions
- The resume's detail is specific enough to check (14 AWS accounts, about $2B in payment volume, a 31% cost cut with the steps that got there), which is the opposite of what a resume written from a posting looks like
- Nothing suggests the resume's wording came from the JD
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

**2. Add your TypeSafe key** (from [https://console.typesafe.ai/keys](https://console.typesafe.ai/keys)). Either:

- `export TYPESAFE_API_KEY=...` in your shell, or
- a line `TYPESAFE_API_KEY=...` in the file `~/.config/typesafe/env`

**3. Ask your agent.** Examples that work:

> Run resume-mirror-eval on the posting in `~/Hiring/platform-eng/jd.pdf`
> against everything in `~/Hiring/platform-eng/applicants/`, with AI analysis on
> the flagged ones.

> Use the resume mirror eval skill. The job description is the Senior Platform
> Engineer req in Greenhouse and the resumes are the 62 active applications on
> it. Put the spreadsheet in my Downloads folder.

> Which of the CVs in the shared Drive folder "Q4 SRE hiring" look like they
> were written from the posting? Here is the posting: [pasted text]

**4. The agent does the rest.** It pulls the documents from wherever you
pointed it (folder, shared drive, ATS, link, pasted text) into a temporary
folder, runs the analysis, writes the AI analysis for the flagged files itself
(no second AI account needed), tells you how many need a human and which ones and
why, gives you the spreadsheet, repeats the disclaimer, and offers to delete
the temporary copies.

**Requirements:** Python 3.10 or newer, and the TypeSafe key. Nothing else to
install; the first run sets up what it needs in a temp folder by itself.

## Cost and time

Measured on the fictional set, one-page resumes, at TypeSafe's list price. 100
and 500 are extrapolated from timed runs at 25 and 50.

**Score and evidence (the TypeSafe part):**


| Resumes | Cost   | Time       |
| ------- | ------ | ---------- |
| 25      | $0.002 | 3 seconds  |
| 100     | $0.01  | 10 seconds |
| 500     | $0.05  | 45 seconds |


Two-page resumes cost about double and take about the same time. This does
not include the AI analysis.

**AI analysis on the flagged files (the optional part):**


| Who writes them                          | Cost                         | Time                                  |
| ---------------------------------------- | ---------------------------- | ------------------------------------- |
| Your agent, as part of the run (default) | Covered by your agent's plan | A few seconds per flagged file        |
| Claude Opus 5 by API                     | About $0.012 per note        | 5 to 10 seconds per note, 4 at a time |
| Claude Sonnet 5 by API                   | About $0.005 per note        | 3 to 6 seconds per note, 4 at a time  |


API figures are estimates from list prices, not measurements. In the fictional
set about 40% of files were flagged; real batches should be lower.

So for a posting with 100 applicants and 40 flagged: about a cent and ten
seconds for the score and text match analysis, then under a dollar and a couple
of minutes for AI analysis with a frontier model, or no separate bill if your
agent writes it.

## What it gets wrong

- A generated resume that invents named employers and round-number metrics
looks specific, so it scores moderate rather than high. That is the right
outcome: it needs a human, and the AI analysis says why.
- Someone who honestly tailors their resume hard to the posting will score
moderate too. That is why the output is a review list, not a decision.
- If the posting itself is boilerplate, everyone scores higher. The batch z
column is the better guide then.
- Scanned PDFs with no text layer are reported as errors, not scored.
- Jev is English-first. Other languages work with less accuracy.
- The fictional set separates cleanly. That proves the mechanics work, not
that the method works on real applicants. Real, labelled data is the next
step.

## Files


| File                                                     | What it is                                                                  |
| -------------------------------------------------------- | --------------------------------------------------------------------------- |
| [`SKILL.md`](SKILL.md)                                   | Instructions the agent follows, step by step                                |
| [`scripts/questions.py`](scripts/questions.py)           | Every question, weight and threshold                                        |
| [`scripts/analyze.py`](scripts/analyze.py)               | The script the agent runs (`python3 scripts/analyze.py --help`)             |
| [`references/methodology.md`](references/methodology.md) | Why each signal exists and what fools it                                    |
| [`mock-data/`](mock-data/)                               | Fictional posting, 13 fictional resumes, labels, and a finished example run |


