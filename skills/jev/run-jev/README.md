# run-jev

Ad-hoc typed judgments over a list of things with TypeSafe's Jev, from inside
a Claude Code session. You describe what you want judged; the agent turns it
into `choice` / `noul` / `score` questions with written criteria; a small
stdlib runner sends one request per item in parallel; a reporter turns the
answers into a markdown table, per-question distributions, the low-confidence
items, and, when you already have labels, the agreement rate and every
disagreement with the probability Jev gave your answer.

Jev is a System One model: it returns calibrated probabilities to typed
questions about a JSON state. It does not generate text and it does not
invent categories. It selects among the options you give it and tells you how
sure it is. That makes it a fast, cheap second reader over a list, not an
oracle: typed output guarantees the shape of an answer, not its truth. Spot
check a handful of high-confidence answers against the source before acting
on a batch, and treat a 0.5 as "no idea", not "somewhat".

## How it works

1. **Shape.** The agent decides what the items are, which narrow judgments to
   ask per item, which primitive each one is, and what compact state each
   item needs. If you have your own labels they go in as `expect`.
2. **Spec.** One JSON file: `questions`, `items`, optional `context` shared by
   every item. For more than a handful of items the agent writes a short
   builder script; `examples/build_spec_from_python_modules.py` is the pattern
   for "one item per file in a tree", summarizing each file by AST so a
   3,500-line module still fits comfortably under the per-request cap.
3. **Run.** `scripts/run.py` validates the spec (types, option counts, unique
   ids, `expect` labels that exist), estimates tokens, warns per item over
   the ~6k soft cap, then fans out at concurrency 6 with backoff on
   429/529/5xx. Per-item errors are recorded, not fatal.
4. **Report.** `scripts/report.py` prints markdown and optionally a CSV.

## Usage

Inside Claude Code: `/run-jev categorize the modules under src/services
into these groups ...` or any phrasing that names Jev. The agent does the
rest and shows you the questions it asked.

By hand:

```bash
python3 scripts/run.py spec.json results.json --dry-run     # validate + token estimate
python3 scripts/run.py spec.json results.json --limit 5     # sanity-check a few first
python3 scripts/run.py spec.json results.json
python3 scripts/report.py results.json --sort my_group --low-q my_group --csv out.csv
```

Requirements: Python 3.10+, a TypeSafe API key in `TYPESAFE_API_KEY` or
`~/.config/typesafe/env`. No packages to install.

The spec format and validation rules are in `references/spec-format.md`; the
wire contract, primitives and how to read the numbers are in
`references/primitives.md`.

## Output

- A per-item table, one column per question. Choice and score cells carry
  the answer and its confidence; noul cells carry P(yes).
- The distribution of every question over the batch.
- Low-confidence answers, least confident first, with the top alternatives.
  This is usually the most useful section: when two options sit near 0.5 the
  item itself is ambiguous between them.
- With `expect`: agreement per question and a disagreement table showing
  Jev's pick, its confidence, your label, and the probability Jev gave your
  label. A disagreement where your label got 0.03 is worth a look at the
  source; one where it got 0.45 is a coin flip.

## Cost and time

$0.042 per million input tokens at last check. A representative run:

| Items | Questions each | Input tokens | Cost | Wall time |
|---|---|---|---|---|
| 75 Python modules, summarized by AST | 8 | 175k | under $0.01 | seconds |

## Results

First use: categorizing 75 flat service modules of a Python monorepo into a
proposed 12-package layout, with the agent's own assignment as `expect`.
Jev agreed on 71/75 (72/75 after one criteria description was sharpened).
The disagreements were all low-confidence on Jev's side, which located the
ambiguity in the modules rather than the taxonomy, and one of them
(a purge job the agent had filed as a vendor client, 0.03 for that package)
was a real correction that was adopted. Four extra axes the agent had not used (architectural tier,
primary actor, data scope, I/O nouls) were asked in the same run and
clustered in code; the tier clustering independently identified the
orchestrator modules responsible for every cross-package import cycle.
