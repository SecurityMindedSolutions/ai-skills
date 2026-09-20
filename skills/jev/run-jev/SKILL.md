---
name: run-jev
description: Run an ad-hoc judgment over one thing or a batch of things with TypeSafe's Jev model, without re-deriving the API, credentials, or output handling every time. Takes a plain-language ask ("categorize these modules", "which of these tickets are urgent", "does each row match this policy", "second-opinion my labels") and turns it into typed choice / noul / score questions, runs them in parallel, and returns a ranked markdown report with distributions, low-confidence items and, when the user already has labels, the agreement rate and disagreements. Use whenever the user says "run jev", "/run-jev", "ask jev", "use jev to ...", "categorize/classify/score/rank/triage these with jev", or wants a fast calibrated second reader over a list, even if they don't say "TypeSafe". Not for the packaged Jev skills (code-audit-jev, traffic-triage-eval, resume-mirror-eval, prompt-injection-eval); those have their own fixed rule sets.
metadata:
  summary: Ad-hoc typed judgments over a list with TypeSafe's Jev - the agent shapes the questions, code runs and reports them, with agreement stats against your own labels.
---

# run-jev

Jev is a System One model: it returns typed answers with probabilities, fast
and cheap, and does not generate text. That makes it a good second reader
over a list of things when the question can be phrased as "which one of
these", "is this true", or "how much". This skill is the fixed harness so an
ad-hoc run costs a spec file and two commands, not a re-read of the docs.

Everything mechanical is in `scripts/`. The agent's job is the part that needs
judgment: turning the user's ask into items, questions and criteria.

## Workflow

### 1. Shape the ask

Answer these before writing anything:

- **What are the items?** One per row of the report. Files, tickets, rows,
  paragraphs, candidates. If there is one item, it is a single-state run with
  several questions.
- **What judgment per item, and which primitive?** One narrow judgment per
  question; several independent questions per item is normal and they run in
  parallel. `choice` for one-of-a-set, `noul` for a yes/no condition, `score`
  for a degree along ordered levels. Details and answer shapes are in
  `references/primitives.md`; read it once per session if unsure.
- **Does the user already have an opinion?** If they hand over their own labels
  (or the agent drafted them, as in a "does Jev agree with my grouping"
  ask), put them in `expect` so the report measures agreement and shows what
  probability Jev gave the expected answer. That is usually the most useful
  number in the run.
- **What is the state per item?** Compact, named fields carrying what the
  judgment needs and nothing else. Jev cannot see what is not in the state,
  and requests over ~6k tokens degrade. For source files, send the docstring,
  public symbols and imports rather than the file; `examples/build_spec_from_python_modules.py`
  shows the pattern and is adaptable to any tree of things.

Then write the criteria. Each option or level must be a description the model
can compare against the others, not a bare label. Add an escape option
(`none_fits`) to a choice when nothing may apply.

If the user's ask is clear enough to answer these without them, do not ask;
write the spec and show the questions in the summary at the end. Ask only when
the choice of items or axes would materially change what gets run.

### 2. Write the spec

Save it in the session scratchpad as `<topic>.spec.json`. Format and the
validation rules are in `references/spec-format.md`. For more than ~10 items,
generate `items` with a short builder script rather than typing them.

Validate and estimate cost before spending anything:

```bash
python3 ~/.claude/skills/run-jev/scripts/run.py <spec> <results.json> --dry-run
```

### 3. Run

```bash
python3 ~/.claude/skills/run-jev/scripts/run.py <spec> <results.json>
```

Credentials resolve from `TYPESAFE_API_KEY` or `~/.config/typesafe/env`; the
client retries 429/529/5xx. Per-item errors are recorded in the results, not
fatal, so a partial run still reports. For a big batch, `--limit 5` first to
sanity-check the answers against the source, then run the rest.

### 4. Report

```bash
python3 ~/.claude/skills/run-jev/scripts/report.py <results.json> [--sort <qid>] [--low 0.8] [--low-q qid,qid] [--top N] [--csv out.csv]
```

The report is markdown: per-item table, distribution per question,
low-confidence answers with their top alternatives, agreement and
disagreements when `expect` was given. Paste the parts the user needs;
for a long table use `--top` or hand them the CSV.

### 5. Interpret, briefly

Say what the numbers mean for the user's decision, not just what they are:

- Disagreements where Jev gave the expected label very low probability are
  worth a look at the source; ones near 0.5 are the item being ambiguous.
- Low-confidence agreements are the model saying "your label, but only
  just", which is where the taxonomy is thinnest.
- A `none_fits` that never fires suggests the option set is exhaustive; one
  that fires often means the set is missing a category.
- Jev selects, it does not invent. To surface a *different* structure, ask
  orthogonal axes the user did not use (kind, actor, scope, lifecycle) in the
  same run and cluster the answers in code; the clusters are the alternative.

Report cost and wall time from the results meta in one line.

## Anti-patterns

- Sending whole files or documents as state. Summarize in code first.
- One mega-question with many things to judge. Split into questions.
- Bare labels as criteria (`"a": "A"`). Describe each option.
- Treating a 0.55 noul as "somewhat true". It is a coin flip; show it.
- Re-reading https://docs.typesafe.ai per run. `references/primitives.md`
  has the verified contract; go to the docs only if something there fails.
