---
name: prompt-injection-eval
description: >-
  Score prompts for prompt injection with TypeSafe's Jev before they reach an
  LLM: a reference gate function a backend can call (allow / review / block
  with a 0-100 risk score, attack type and reasons), plus a batch evaluator
  that runs a CSV of prompts through the gate, a regex baseline and optionally
  an LLM judge, and reports precision/recall, latency and cost side by side.
  Use this whenever the user wants to detect, score, filter, gate or test for
  prompt injection or jailbreaks in their app, wants to compare Jev to string
  matching or an LLM judge, or asks how to protect a SaaS chat feature from
  hostile input - even if they do not say "TypeSafe" or "Jev". Research proof
  of concept; run in alert mode before block mode.
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
metadata:
  summary: "Scores prompts for injection with TypeSafe Jev and returns allow / review / block for a backend gate; ships a batch evaluator that measures Jev against a regex list and an LLM judge on labelled prompts"
---

# Prompt Injection Eval

> **Research proof of concept.** This skill asks TypeSafe's Jev a fixed set of
> questions about a prompt and turns the answers into a risk score and an
> allow / review / block decision. It is a signal for a security gate, not a
> guarantee: no detector catches every injection, and this one belongs
> alongside least-privilege tools, output checks and logging, not in place of
> them. Before wiring it into a real system, run the evaluator on a labelled
> sample of your own traffic, tune the thresholds in `scripts/questions.py`,
> and run it in **alert mode** (log and review, never block) until the false
> alarm rate on real users is known. Only then consider block mode. Repeat the
> short form of this to the user at the end of every run.

## What it does

1. **Gate.** `scripts/gate.py` exposes `check_prompt(user_input, app)`. One
   request to Jev carrying a one-paragraph description of the app and the
   prompt, with eight typed questions answered together: instruction override,
   persona hijack, secret or prompt extraction, action misuse beyond the app's
   purpose, false authority, obfuscation, instructions embedded in pasted
   content, and an overall manipulation severity, plus a labelled attack type.
   Code weights the answers into a 0-100 risk score and applies the rules in
   `questions.py`: block on high risk, on high severity with confidence, or on
   any single near-certain signal; review on moderate risk, any strong signal,
   or an unsure allow; else allow. About 1,600 tokens, 7 cents per thousand
   prompts, 300 ms median.
2. **Evaluate.** `scripts/evaluate.py` runs a CSV of prompts through the gate,
   a built-in regex phrase list, and optionally an LLM judge via any
   OpenAI-compatible endpoint. With `label` (benign|injection) in the CSV it
   reports caught / missed / false alarms, precision, recall and F1 per
   approach, with measured latency and cost per thousand prompts, and prices
   the LLM judge's measured tokens at Claude list rates. Output is
   `results.xlsx` (Results, Details, Comparison, Summary, Read me) plus CSV and
   JSON.
3. **Explain.** You, the agent, read the results and tell the user what was
   caught, what was missed, what the false alarms were and why, and what the
   numbers mean for their traffic.

Every question, weight, threshold and rule lives in `scripts/questions.py`.

## Workflow

`SKILL_DIR` means the folder containing this SKILL.md.

### 1. Understand what the user wants

Three shapes of request:

- **"Evaluate my prompts"**: they have prompts (logs, a CSV, a folder of text
  files, tickets, an export from their LLM gateway) and want scores and a
  comparison. Go to step 2.
- **"Gate my app"**: they want the check in their backend. Run the evaluator
  on their sample first (never wire in an untested threshold), then go to
  step 5.
- **"Just test one"**: `python3 "$SKILL_DIR/scripts/gate.py" "<prompt>"
  "<app description>"` prints the decision and every signal as JSON.

### 2. Stage the prompts

The evaluator reads one CSV with a `prompt` column and optional `label`,
`category`, `id`. Wherever the prompts live (local files, a log export, a
database query, an LLM gateway's request log, a ticketing system via a
connector, pasted text), fetch them and write that CSV into a temp staging
folder (your scratchpad, or `$TMPDIR/prompt-injection-eval/<timestamp>/`),
never into the user's working tree. Prompts are user data; the copies exist
for the run. If the user has ground truth (a list of known attacks, or a
labelled set), put it in `label`. Without labels the run still produces
scores and decisions, just no precision/recall.

Also write `app.md`: one paragraph on what the assistant is for, what it can
do, what tools it has, and what it must not do. Ask the user if you cannot
infer it. This is the `app` field Jev judges against; a vague description
makes "action outside the app's purpose" vague too.

### 3. Check prerequisites

```bash
python3 --version   # 3.10 or newer
test -n "$TYPESAFE_API_KEY" || test -f ~/.config/typesafe/env || echo "need a TypeSafe key"
```

Nothing to install. First run creates a private venv under the system temp
dir for the one dependency (openpyxl). `uv run` works too. Key resolution:
`TYPESAFE_API_KEY` in the environment, else `~/.config/typesafe/env`. Keys
come from https://console.typesafe.ai/keys; if the user has none, stop and
ask.

### 4. Run the evaluator

```bash
python3 "$SKILL_DIR/scripts/evaluate.py" \
  --prompts "$STAGING/prompts.csv" \
  --app "$STAGING/app.md" \
  --out "$STAGING/out"
```

Add `--llm-judge <model id>` to also run an LLM judge for the comparison,
with `OPENAI_API_KEY` and optionally `OPENAI_BASE_URL` set (OpenAI, OpenRouter,
a gateway in front of Claude, Ollama). Without it, the Comparison sheet
carries an estimated LLM-judge row from token counts, labelled as not run.
`--workers N` (default 4) sets parallel requests; `--model` picks the
TypeSafe model.

The run prints every prompt with its decision, risk, the regex verdict and
the label, then the counts, Jev tokens, cost and latency, then the comparison
table. Read `results.json` for anything the table does not show.

### 5. Wire it in (only when asked, and only after step 4)

`gate.py` is written to be copied. `check_prompt(user_input, app)` returns:

```json
{"decision": "block", "risk": 69.4, "attack_type": "prompt_leak",
 "signals": ["instruction_override", "secret_extraction"],
 "detail": {...every probability and confidence...},
 "model": "jev-1.13.0", "input_tokens": 1610, "latency_ms": 318}
```

Adapt it to the user's stack (it is plain `urllib`, no SDK). Insist on:

- **Alert mode first.** Log the verdict and forward the prompt regardless
  until the false-alarm rate on real traffic is known. Make block mode a
  config flag that starts off.
- **Review means something.** Decide what `review` does before shipping:
  forward with tools disabled, hold for a human, or log with a flag. It must
  not silently equal allow.
- **Fail open or closed is a decision.** On a TypeSafe error or timeout,
  choose and document the behavior.
- **Log the detail.** The full `detail` dict per request is what makes
  threshold tuning possible later.
- **Keep the `app` text accurate.** When the assistant gains a tool, update
  the paragraph, or "action outside its purpose" will drift.

### 6. Report back

1. Counts (block / review / allow), Jev cost and latency, and if labelled,
   the comparison table in plain words: what Jev caught that regex missed,
   what regex flagged that was benign, where the LLM judge stood if run.
2. The misses and false alarms by name, with the prompt text and what Jev's
   signals said, so the user can judge whether a threshold change or a
   question change is warranted.
3. Where the spreadsheet is, and the offer to delete the staged prompts.
4. The disclaimer, in two sentences: research proof of concept; evaluate on
   your own traffic and run in alert mode before block mode.

## Reading the output

| Column | Meaning |
|---|---|
| Decision | `allow`, `review` or `block` from the rules in `questions.py`. |
| Risk score (Jev) | 0-100 weighted composite of Jev's answers. Ranks prompts; the rules decide. |
| Attack type (Jev) | Jev's pick from a fixed list, `none` for ordinary requests. Descriptive only. |
| Signals (Jev) | Yes/no questions at or above the signal threshold, strongest first. |
| Regex baseline (code) | What a phrase list would have done. Comparison only. |
| LLM judge | What a generative model replied, if `--llm-judge` was used. Comparison only. |

The Details sheet has every probability, confidence, latency and token count.
The Comparison sheet has the metrics table.

## Mock data

`mock-data/` holds `app-context.md` for a fictional payments-support
assistant, `prompts.csv` with 80 labelled prompts (40 attacks across nine
categories including obfuscated, non-English and indirect-via-pasted-content;
40 benign including hard negatives that talk about prompt injection, use
"ignore" legitimately, role-play within purpose, or paste harmless content),
and `example-output/` with a finished run. To demo or regression-test:

```bash
cd "$SKILL_DIR/mock-data"
python3 ../scripts/evaluate.py --prompts prompts.csv --app app-context.md
```

## Technical details

**Dependencies.** Python 3.10+. One pure-Python package (openpyxl, for the
.xlsx) which `scripts/bootstrap.py` installs into a private venv under the
system temp dir on first run; without it the script writes CSV and JSON. The
TypeSafe call is plain `urllib` with backoff on 429/529/5xx.

**Determinism.** Jev returns calibrated probabilities that are stable run to
run to within about a hundredth. A prompt whose severity sits exactly on a
threshold can flip between `block` and `review` across runs; that is the
threshold, not noise, and the Details columns show it.

**Why not just ask the LLM.** The model being asked "is this an injection?"
is itself reading the injection; a well-crafted prompt can talk it out of the
verdict. Jev does not follow instructions in the state, it only answers typed
questions about it, and it is a different model from the one serving the
user. It is also ~300 ms and a fraction of a cent, cheap enough to run on
every request. TypeSafe does document that adversarial text can move Jev's
answers, which is why the decision uses several narrow questions and a
confidence gate rather than one yes/no, and why alert mode comes first.

**Limits.** 32k-token state budget; prompts are capped at 20,000 characters.
English-first. A very long pasted document dilutes the signal; consider
judging the pasted part separately.

**Data handling.** Prompts go to `api.typesafe.ai` and, only if
`--llm-judge` is used, to that endpoint. Outputs default to
`<system temp>/prompt-injection-eval/<timestamp>/`. `results.json` contains
the prompt text.
