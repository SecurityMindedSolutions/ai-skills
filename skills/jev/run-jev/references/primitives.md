# Jev quick reference

Everything on this page was verified against https://docs.typesafe.ai/api on
2026-09-20 or measured in a real run. Re-read the live doc only if something
here fails; do not re-derive it per run.

## Wire contract

- `POST https://api.typesafe.ai/v1/systemone`, header `Authorization: Bearer <key>`.
- Key: `TYPESAFE_API_KEY` in the environment, else `~/.config/typesafe/env`
  (`TYPESAFE_API_KEY=...`). `scripts/jev.py` resolves both. Keys are minted at
  https://console.typesafe.ai/keys.
- Model: `jev-latest` (responses echo the pinned version, e.g. `jev-1.13.0`).
- Retry `429`, `529`, and `5xx` with backoff; `jev.py` already does, honoring
  `retry-after`.
- One request = one `state` + a map of independent `questions`. Questions
  cannot see each other's answers. Question ids are for code only; the model
  never sees them, so the full meaning must be in `instructions`.

```json
{"state": <string | object | array>,
 "model": "jev-latest",
 "questions": {"<qid>": {"type": "noul|choice|score", "instructions": "...", "criteria": ...}}}
```

## The three primitives

| Need | Type | `criteria` | Answer fields |
|---|---|---|---|
| Whether a condition holds | `noul` | optional `{"true": "...", "false": "..."}` | `noul` = P(yes) in 0..1. No separate confidence. |
| One of a defined set | `choice` | required `{option: description}`, 2..255 options | `choice`, `confidence`, `probabilities` {option: p} |
| Degree along an ordered dimension | `score` | required `[level0, level1, ...]`, 2..10 levels, ordered | `score` (probability-weighted position), `confidence`, `probabilities` {index: p}, `legend` {index: level text} |

Response: `{"model", "answers": {qid: {...}}, "usage": {"input_tokens", "output_tokens"}}`.

## Reading the numbers

- A `noul` near 0.5 means the model finds yes and no about equally likely; it
  is not "medium". Threshold it per use, and look at the 0.3..0.7 band by hand.
- `choice` / `score` `confidence` summarizes how concentrated the distribution
  is. Low confidence with two options near 0.5 usually means the ITEM is
  genuinely ambiguous between those two, which is often the most useful output
  of the whole run. Report those, do not hide them.
- `probabilities` on a choice is the cheap way to check a prior label: "how
  much mass did Jev put on MY answer" is more informative than agree/disagree.
- Typed output guarantees the shape, not the truth. Spot-check a handful of
  high-confidence answers against the source before trusting a batch.

## Writing questions that work

- One narrow judgment per question. Split independent dimensions into separate
  questions and ask them in the same request; they run in parallel.
- Put the judgment in `instructions`, the answer space in `criteria`. Every
  option or level description must stand on its own; the model compares them.
- Include an escape option (`none_fits`, `unclear`) on a choice when nothing may
  fit. If it never fires across a batch that is itself a signal the taxonomy is
  exhaustive.
- Prefer named JSON fields in `state` over one prose blob when the input has
  several parts (source text, metadata, relationships). Reference nested
  fields in instructions with backticked paths like `item.docstring`.
- The model selects and judges; it does not generate categories. To "discover"
  structure, ask several orthogonal axes and let code cluster the answers.

## Measured limits and cost

- Soft cap of roughly **6,000 input tokens per request** before answers degrade
  (measured by the code-audit-jev skill). `run.py` warns per item over that.
  Summarize or slice big inputs in code before sending; do not send a whole
  file when its docstring, signatures and imports carry the meaning.
- Price at last check: **$0.042 per million input tokens**. A 75-item, 8-question
  batch over ~175k tokens cost under one cent and took about 40 s at
  concurrency 6.
- Concurrency 6 has never tripped rate limits; raise carefully.
