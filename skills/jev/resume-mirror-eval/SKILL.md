---
name: resume-mirror-eval
description: >-
  Bulk-evaluate a folder of resumes against one job description and flag the
  ones whose wording mirrors the posting closely enough that a human should
  look before ranking them. Uses TypeSafe's Jev model for calibrated semantic
  judgments, plain code for every statistic, and optionally the agent itself
  (or any LLM) for terse review notes. Produces a spreadsheet sorted by mirror
  score with a "Needs human review" column first. Use this whenever the user
  wants to screen, score, compare or "check" a batch of resumes/CVs against a
  JD, asks which applicants look AI-generated or copied from the posting, or
  wants a resume similarity spreadsheet - even if they do not say "TypeSafe"
  or "Jev". Research proof of concept; not a hiring decision tool.
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
metadata:
  summary: "Scores a batch of resumes against a job description with TypeSafe Jev plus code-side text statistics, flags the ones a human should read, and writes a sortable spreadsheet with evidence bullets"
---

# Resume Mirror Eval

> **Research proof of concept.** This skill measures how closely a resume's
> *wording* tracks a job description. It does not determine whether a person
> used AI and it makes no decision about any candidate. Its output is a list of
> resumes a human should read first; the **Needs human review** column exists
> for exactly that purpose. It is a tool for directing human review, not a
> substitute for it.
>
> Any use must comply with the laws, regulations and policies that apply to
> the user and their applicants; automated tools in hiring are regulated in
> many places, and the user should consult their legal team before running
> this on real applicants. Provided as is, for research and education.
>
> Repeat the short form of this to the user at the end of every run.

## What it does

1. Extracts text from every resume (.pdf, .docx, .txt, .md) in the folders or
   files the user points at.
2. Computes text statistics in code: verbatim 4-word phrase overlap with the
   JD, longest shared word run, whether matched terms appear in the JD's order,
   TF-IDF cosine within the batch, keyword and acronym coverage, and a z-score
   against the rest of the batch.
3. Sends `{job_description, resume}` to TypeSafe's Jev with six typed
   questions in one request per resume (phrasing mirror, requirement echo,
   concrete specifics, generic template, posting-language leak, career
   consistency). Roughly 2,000 tokens and a tenth of a cent per resume; a batch
   of 100 finishes in seconds.
4. Turns Jev's answers into a 0-100 **Mirror score (Jev)**; the statistics
   into **Text match analysis (code)**, template sentences a reviewer can check
   against the two documents; and both into a **Needs human review** flag. Nothing in the output rates the candidate's fit or
   qualifications; the tool judges the file's relationship to the posting only.
5. Writes `results.xlsx` sorted by mirror score: a five-column Results sheet
   (review flag, file, Jev score, text match analysis, AI analysis), a Details sheet with every
   statistic and Jev answer, the JD, and the disclaimer. Also `results.csv`,
   `results-detail.csv` and `results.json`.
6. Optionally adds **AI analysis (agent)**: terse bullets per flagged resume,
   written by you (the agent running this skill) or by an API model. Three
   methods, three columns; none feeds another.

Every question, weight and threshold lives in `scripts/questions.py`. If the
user disagrees with how something scored, that file is where to look first.

## Workflow

`SKILL_DIR` below means the folder containing this SKILL.md.

### 1. Locate the sources and stage them

The script reads local files. Where those files come from is your job. The
user may point you at anything you can reach: a folder, a synced drive, a
connector, an ATS, a URL, an email thread, or text in the conversation. Use
whatever tools you have to fetch the documents, land copies in a temp staging
folder, then run the script on that folder. Do not ask the user to download
things you can download yourself.

| Source | How to stage it |
|---|---|
| Local folder or files | Pass the paths directly; nothing to stage. |
| Synced drive (Google Drive, Dropbox, OneDrive, SharePoint sync) | It is a local path. Pass it directly. |
| Cloud drive via a connector (Google Drive, SharePoint, Box MCP...) | Download each file into the staging folder, keeping the original file name. |
| ATS via an MCP server (Greenhouse, Lever, Ashby, Workable, iCIMS...) | Fetch the requisition's job description to `staging/jd.md` and each application's resume attachment to `staging/resumes/`. Name files `<lastname>_<firstname>_<application_id>.<ext>` and write `staging/manifest.csv` with `file,application_id,candidate,source_url` so those ids appear in the spreadsheet. |
| URL to a posting | Fetch it and save the text as `staging/jd.md`. |
| Pasted text | Save it to `staging/jd.md`. |
| Email or ticket attachments | Save each attachment into `staging/resumes/`. |

The staging folder is a **temp location**, never the user's working directory
or the source folder: use your scratchpad if you have one, otherwise
`$TMPDIR/resume-mirror-eval/<timestamp>/`. The script's own default `--out` is
under the system temp dir for the same reason. Resumes are personal data; the
copies exist only for the run. When the run is done, tell the user where the
staging and output folders are and offer to delete the staged copies (keep the
spreadsheet, or copy it to wherever they asked for it).

Ask for whatever is missing. Two things are required: one job description and
one or more resumes. If a source yields several postings, confirm which one
before pulling resumes.

Never upload resumes anywhere other than the TypeSafe API (and the LLM provider
if the user opts into API notes). Say so if asked.

### 2. Check prerequisites

```bash
python3 --version   # 3.10 or newer; `python` on Windows
test -n "$TYPESAFE_API_KEY" || test -f ~/.config/typesafe/env || echo "need a TypeSafe key"
```

Nothing else. On first run the script creates a private virtual environment
under the system temp directory and installs its two pure-Python dependencies
there (a few seconds); later runs reuse it. If the user has `uv`, `uv run`
works too and skips that step.

The script reads `TYPESAFE_API_KEY` from the environment, or from a line
`TYPESAFE_API_KEY=...` in `~/.config/typesafe/env`. Keys come from
https://console.typesafe.ai/keys. If the user has neither, stop and ask; do
not guess or put a key on the command line.

### 3. Run the analysis

```bash
python3 "$SKILL_DIR/scripts/analyze.py" \
  --jd "$STAGING/jd.md" \
  --resumes "$STAGING/resumes" \
  --out "$STAGING/out" \
  --llm-notes agent
```

Add `--manifest "$STAGING/manifest.csv"` when you staged from an ATS or any
source with ids worth carrying into the sheet; every column but `file` is
copied in after the File column.

`--llm-notes agent` makes the script write `notes-request.json` for the rows it
flagged, so you can write the notes yourself in step 4 without any other API
key. Leave the flag off if the user only wants scores.

Other flags: `--llm-top N` (annotate only the top N by score), `--labels
labels.csv` (score the run against known `human` / `ai_tailored` labels, for
evaluation), `--workers N` (parallel Jev calls, default 4), `--model`
(TypeSafe model, default `jev-latest`), `--no-color`.

The run prints a table (review flag, file, mirror score, batch z, first
evidence bullet) and the output paths. Read `results.json` if you need any field
the table does not show.

### 4. Write the review notes (agent mode)

Open `<out>/notes-request.json`. It holds the JD, and for every flagged resume:
its text, its scores, and the evidence bullets code already produced. For each
one write 2 to 4 bullets that a recruiter could verify by reading the two
documents, in this style:

```
- The nine duties listed in the posting appear as the nine bullets of the current job, in the same order and nearly the same words, which is what you get when a resume is written from the posting rather than from memory of the work
- The employers are given only as "Leading Fintech Company" and "Global Technology Solutions Firm", with no names, team sizes, numbers or incidents, so there is nothing here that could be checked
- Phone screen: ask about one specific Kubernetes upgrade they ran and what went wrong; someone who did the work will have a story
review: yes
```

Rules: no summary sentence, no heading, no markdown beyond `- `. Each bullet
is one plain sentence a recruiter understands on first read, and it says why
the observation matters: what you saw, then what it suggests ("...repeats the
posting's requirements list word for word, so it tells you what the posting
asked for, not what this person has done"). Never leave a bare observation the
reader has to interpret. No shorthand that maps one heading to another. Quote
the resume only when the quote is the point. Do not repeat the text-match
bullets. Never say or guess whether the candidate used AI;
describe what is on the page. End with exactly `review: yes` or `review: no`
depending on whether a human should read it before ranking. Save the notes as
a JSON object mapping file name to note text, then merge:

```bash
python3 "$SKILL_DIR/scripts/analyze.py" --out "$STAGING/out" --merge-notes "$STAGING/notes.json"
```

The merge rewrites the spreadsheet with the notes and folds `review: yes` into
the Needs human review column.

If the user prefers an API model for notes (for unattended runs), use
`--llm-notes anthropic` (`ANTHROPIC_API_KEY`; the Anthropic SDK is installed
into the private venv on first use) or `--llm-notes openai --llm-model <id>` (`OPENAI_API_KEY`,
optional `OPENAI_BASE_URL` for OpenRouter, Ollama or any compatible endpoint).

### 5. Report back

Tell the user, in this order:

1. How many resumes, how many need human review, and the Jev cost line.
2. The flagged rows with their mirror score and one or two of the strongest
   evidence bullets each. Point out any row flagged with a low score (usually
   acronym coverage on a resume written in the candidate's own words) so they
   know the flag is a prompt to read, not an accusation. Never comment on
   whether a candidate seems qualified or a good fit.
3. Where the spreadsheet is (copy it to where the user wants it), what the
   first sheet's columns mean, briefly, and an offer to delete the staged copies
   of the resumes.
4. The disclaimer, in two or three sentences: research proof of concept, it
   directs human review rather than making a determination, and real use must
   comply with applicable law and policy with their legal team's advice.

## Reading the output

| Column | Meaning |
|---|---|
| Needs human review | YES if any signal fired: mirror score at or above `REVIEW_SCORE` (40), batch outlier, a code evidence bullet, a Jev flag (posting language, generic text, career inconsistency) or the notes' `review: yes`. Blank otherwise. Generous on purpose. |
| Mirror score (Jev) | 0-100, from Jev's six answers alone, weighted per `questions.py`. Higher means the file's wording tracks the posting more closely. No high/medium/low buckets: the tool does not grade candidates. |
| Text match analysis (code) | Sentences the script fills in from exact counts: verbatim JD sentences with a quote, longest shared run with the text, acronym coverage, phrase reuse percentage, order echo, thin specifics. No AI involved. Not scored. |
| AI analysis (agent) | The bullets you write in step 4. Your own reading of the file. Not scored. |

The Details sheet and `results-detail.csv` hold every Jev answer (0-3 scores
and probabilities), every text statistic with a separate 0-100 roll-up, and
the batch z-score, for anyone who wants to re-weight.

## Mock data

`mock-data/` holds a fictional job description, 13 fictional resumes with
`labels.csv`, and `example-output/` with a finished run to show the user, for demonstrating the skill without touching a real person's
resume. Two of the human-written ones are deliberately very close matches to
the posting. To demo or regression-test:

```bash
cd "$SKILL_DIR/mock-data"
python3 ../scripts/analyze.py --jd job-description.md --resumes resumes --labels labels.csv --llm-notes agent
```

## Technical details

**Dependencies.** A plain Python 3.10+ install is the only requirement. The
script needs two pure-Python packages, `pypdf` (PDF text) and `openpyxl` (the
.xlsx). On first run `scripts/bootstrap.py` creates a private virtual
environment at `<system temp>/resume-mirror-eval/venv` with the `venv` and
`pip` modules that ship with Python, installs the two packages there, and
re-executes the script from it; nothing is installed globally and the user
runs no install command. `.docx` is parsed with the standard library (a .docx
is a zip holding `word/document.xml`). The TypeSafe call is plain `urllib`.
The entry point also carries PEP 723 inline metadata, so `uv run` works for
anyone who has uv and skips the bootstrap.

**Fallbacks.** If the venv cannot be created or pip cannot reach the network,
the script says so and continues: `.md`, `.txt` and `.docx` always work; `.pdf`
falls back to the `pdftotext` command if present, otherwise that file gets an
error row and the batch continues; without `openpyxl` it writes `results.csv`
and `results.json` and says so. The Anthropic SDK is imported only when
`--llm-notes anthropic` is used and produces a clear per-row message if it is
missing.

**API key resolution.** `TYPESAFE_API_KEY` in the environment, else
`~/.config/typesafe/env`. Nothing else is read and the key is never written to
the output.

**Data handling.** Inputs are read from disk only; the agent stages remote
sources into a temp folder first. The only network calls are to
`api.typesafe.ai` (and the optional notes provider). Outputs default to
`<system temp>/resume-mirror-eval/<timestamp>/`. `results.json` contains the
JD text (so `--merge-notes` can rebuild the sheet) but never the resume text;
`notes-request.json` does contain resume text and lives in the same temp
folder.

**Cost and time.** Measured: about 2,200 Jev input tokens and $0.00009 per
one-page resume, 0.33 s per request sequentially or about 0.08 s at the default
four workers. 100 resumes is roughly 220k tokens, one cent, and ten seconds; 500
is about five cents and 45 seconds. Review notes by API model are the only
significant cost and only run on flagged rows. Quote these to the user when
they ask what a batch will cost.

**Limits.** Jev's context budget is 32k tokens for the state plus the longest
question; each document is capped at 24,000 characters. Rate limits are retried
with exponential backoff, honoring `retry-after`. Jev is English-first; other
languages work with lower accuracy.

**Known weaknesses of the method.** A generated resume that invents named
employers and round-number metrics scores well on the specifics judge and lands
in "moderate", which is the correct outcome: that row needs a human, and the
evidence and notes say why. Paraphrased copies score lower on the lexical half
than verbatim ones; the semantic half carries them. Short resumes (under 40
words extracted, typically scanned PDFs) are reported as errors rather than
scored. See `references/methodology.md` for the reasoning behind each signal.

**Portability.** Follows the Agent Skills format. Install from the repository
with `npx skills add SecurityMindedSolutions/ai-skills --skill
resume-mirror-eval` for Codex, Cursor, Cline and others, or copy the directory
into `~/.claude/skills/` for Claude Code. All paths in this file are relative to
the skill directory, so it works from any of those locations.
