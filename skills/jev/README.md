# Jev

Skills built on TypeSafe's Jev, a decision model that answers typed questions about a document with calibrated numbers instead of generating text; code does the math, Jev does the judgment, and the agent does the fetching.

These differ from the other skills in this repository. Each one is a small
pipeline: the agent stages source documents into a temp folder from wherever
the user points it, a Python script computes statistics and sends the documents
to Jev with a fixed set of questions, and code combines the answers under
weights a reviewer can read in one file. They need a TypeSafe API key
(`TYPESAFE_API_KEY` or `~/.config/typesafe/env`) and
[uv](https://docs.astral.sh/uv/); nothing else is installed by hand.

> ## Disclaimer: research proof of concept, not a hiring tool
>
> The skill in this folder was built to test whether a methodology works. It
> measures how closely a resume's *wording* tracks a job description. It does
> not and cannot determine whether a person used AI to write their resume, and a
> candidate whose experience genuinely matches a role will score above the
> average of the batch. Its output is a list of resumes a human should read
> first. It is not a ranking, not a filter, and not evidence of anything about
> a candidate.
>
> The use of automated tools in hiring is regulated in many jurisdictions,
> among them the EU AI Act (employment is a high-risk use), New York City Local
> Law 144 (bias audits and notice for automated employment decision tools),
> the Illinois Artificial Intelligence Video Interview Act and its 2026 Human
> Rights Act amendment, Colorado SB 24-205, and US EEOC guidance on algorithmic
> tools under Title VII and the ADA. Requirements commonly include candidate
> notice, independent bias auditing, record-keeping, and a human decision-maker.
>
> **If you use this, or anything derived from it, on real applicants, you are
> solely responsible for complying with every law and regulation that applies to
> you, and you should consult your own legal counsel before doing so.** The
> author offers it for research and education only, without warranty, and
> accepts no responsibility for how it is used. The mock data shipped with it is
> entirely fictional.

---

## `/resume-mirror-eval`

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

### Usage

```bash
uv run skills/jev/resume-mirror-eval/scripts/analyze.py \
  --jd posting.md --resumes ./resumes --llm-notes agent
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

Requirements: [uv](https://docs.astral.sh/uv/) and a TypeSafe API key in
`TYPESAFE_API_KEY` or `~/.config/typesafe/env`. uv resolves the two Python
dependencies (pypdf, openpyxl) and Python itself into its own cache; nothing is
installed by hand. `.docx` is parsed with the standard library. Without uv the
script still runs under `python3` with reduced output (CSV instead of xlsx, PDF
via `pdftotext` if present).

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

### Customization

- Weights, thresholds and every Jev question: `scripts/questions.py`.
- Evidence bullet rules: `scripts/evidence.py`.
- Notes prompt and providers: `scripts/llm_notes.py`.
- Why each signal exists and what fools it: `references/methodology.md`.

### Install for other agents

```bash
npx skills add SecurityMindedSolutions/ai-skills --skill resume-mirror-eval
```

All paths in the skill are relative to its own folder, so it runs from
`.agents/skills/`, `~/.codex/skills/`, `~/.cursor/skills/` or `~/.claude/skills/`
alike.
