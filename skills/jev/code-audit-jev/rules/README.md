# Rules

One file per category. The runner (`scripts/run.py`) knows nothing about any
category; everything it looks for is declared here. To add a rule, copy any
`*.toml` file, change every field, and run. To use your own rules in a
repository without forking, put them in a folder (say `.jev-rules/`) and pass
`--rules .jev-rules` (or the action's `rules` input); a file whose `id`
matches a built-in rule replaces it, so a repo can also retune one.

## A rule file

```toml
id = "ssrf"                       # the class name in results and SARIF (jev/ssrf)
title = "Server-side request forgery"

# The option Jev sees in the "which class of defect is this" choice. Write it
# as a literal description of what would be visible in one unit of code.
class = """`unit.code` makes an outbound request whose destination ... """

# How this rule's yes/no answers compose into one 0..1 vector, in code:
#   vector = product(all) * product(1 - none)
[vector]
all = ["outbound_destination_from_input"]
none = []

# Yes/no questions (Nouls). One literal condition each; Jev reads literally,
# so put the boundary cases into `true` and `false`, and say what does NOT
# count. Question ids are global: two rules may share one (declare it in one).
[questions.outbound_destination_from_input]
instructions = """Does `unit.code` make an outbound HTTP ... ?"""
true = """An outside value is used to build the outbound URL and ..."""
false = """The outbound destination is a constant, configuration, ..."""

# Regex facts computed in code before Jev is asked. A hit becomes
# `code_signals.<rule id>.<name> = "<label> (line N)"` in the state, so Jev is
# told the fact rather than asked to spot it. Use TOML literal strings ('''...''')
# so backslashes are not escapes.
[signals.outbound_http]
label = "outbound HTTP call"
patterns = ['''requests\.(get|post)\(|\bfetch\(|axios\.\w+\(''']

# Optional. A code fact plus a question answer that makes the unit attention
# whatever the score: here, a provider-shaped credential that Jev also calls
# a credential.
[floor]
signal = "credential_literal"
labels = ["AWS access key id", "private key block"]
min = 0.5
```

Composed rules use several questions:

```toml
[vector]
all = ["handles_external_request", "privileged_operation"]
none = ["auth_check_present"]
```

reads "is a request handler AND does something privileged AND no auth check
is visible", multiplied in code. Jev is never asked the "and".

## `_core.toml`

The model, the scoring constants, the class choice wording, the severity
scale, the two shared questions (`mitigation_in_unit` halves a vector;
`not_production_code` drops the unit) and the generic source/guard signals
every rule can see (`code_signals.context.*`). A `_core.toml` in an extra
rules directory replaces matching top-level tables.

Score = 100 × (w_severity × severity/4 + w_vector × strongest vector × (1 − mitigation_discount × mitigation)).
Bands are edges on that score. Attention is the `attention_score` line plus a
category, or a floor.

## Writing questions that Jev answers well

- One condition per question. "A and B" becomes two questions and a vector.
- Name the state fields: `unit.code`, `file.guard_markers`, `app`.
- Put what does not count into `false`: JSX text is escaped; environment
  variables are trusted; a placeholder is not a secret.
- No double negatives; `true` must mean "the defect is present".
- Test on `mock-data/sample-repo/` (labelled) before trusting a change:
  `python3 scripts/run.py --target mock-data/sample-repo --app mock-data/sample-repo/app.md --out /tmp/x`
  then `python3 scripts/compare.py --results /tmp/x/results.json --reference mock-data/sample-repo/labels.csv`.
