# Spec format for `scripts/run.py`

One JSON file describes a whole run. The agent writes it (by hand for a few
items, or with a throwaway builder script for many), `run.py` executes it,
`report.py` reads the results.

```json
{
  "model": "jev-latest",
  "concurrency": 6,
  "context": {"policy": "Anything every item should see, merged into each state as `context`"},
  "questions": {
    "kind": {
      "type": "choice",
      "instructions": "Which ONE kind best describes `item.text`? Judge by primary purpose.",
      "criteria": {
        "bug_report": "Describes something that used to work or should work and does not.",
        "feature_request": "Asks for a capability that does not exist.",
        "question": "Asks how to do something; nothing is broken.",
        "none_fits": "None of the above."
      }
    },
    "urgent": {
      "type": "noul",
      "instructions": "Is `item.text` asking for help within the next day?",
      "criteria": {"true": "Explicit or clearly implied same-day need.", "false": "No time pressure stated or implied."}
    },
    "tone": {
      "type": "score",
      "instructions": "How frustrated is the author of `item.text`?",
      "criteria": ["calm and neutral", "mildly annoyed", "clearly frustrated", "angry or threatening to leave"]
    }
  },
  "items": [
    {"id": "t-1041", "state": {"text": "..."}, "expect": {"kind": "bug_report"}},
    {"id": "t-1042", "state": {"text": "..."}}
  ]
}
```

Rules `run.py` enforces before spending a token:

- every question has a valid `type` and non-empty `instructions`;
- `choice.criteria` is an object of 2..255 options, `score.criteria` an ordered
  list of 2..10 levels, `noul.criteria` (optional) has exactly `true`/`false`;
- every item has a unique `id`;
- an `expect` label on a choice question must be one of that question's options.

`expect` is optional and per question. When present, `report.py` prints the
agreement rate and a disagreement table showing how much probability Jev gave
the expected label. Use it whenever the agent (or a person) already has an
opinion and wants Jev as a second reader.

`state` can be any JSON. Prefer an object with named fields; keep each item
under ~6k tokens (`run.py --dry-run` estimates and warns).

Results file:

```json
{"meta": {"model", "items", "errors", "questions", "input_tokens", "wall_seconds"},
 "results": [
   {"id": "t-1041", "expect": {"kind": "bug_report"},
    "answers": {"kind": "bug_report", "kind_conf": 0.93, "kind_probs": {"bug_report": 0.93, "question": 0.05, ...},
                "urgent": 0.12,
                "tone": 1.4, "tone_conf": 0.7, "tone_level": "mildly annoyed", "tone_probs": {"calm and neutral": 0.2, ...}},
    "input_tokens": 412, "latency_ms": 640, "model": "jev-1.13.0"}
 ]}
```
