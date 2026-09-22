# Rules

One file per email category. The runner (`scripts/analyze.py`) knows nothing about any category;
everything it looks for is declared here. To add a category, copy any `*.toml`, change every
field, and run. To retune in your own environment without forking, put your files in a folder
(say `.jev-email-rules/`) and pass `--rules .jev-email-rules`: a file whose `id` matches a
built-in category **replaces** it, a new `id` **adds** one, and a `_core.toml` there replaces
matching top-level tables.

## A category file

```toml
id = "vendor_payment_fraud"                  # appears in results as the category
title = "Vendor payment fraud (BEC)"

# What this category means once risk, flags and the _core.toml thresholds are applied.
# One of: malicious, suspicious, spam, benign. Nothing is hard-coded in Python.
verdict = "malicious"

# The option Jev sees in the 16-way "what is this email's primary purpose" choice.
# Write it as a literal description of the mail, and say what does NOT count - the
# boundary is where accuracy is won.
class = """BEC via a vendor/supplier: changed or new bank details, redirected remittance ...
Needs a concrete sign of changed payment details or an identity mismatch; an ordinary quote,
invoice or order thread with an established, authenticated vendor is legitimate_business."""

# Regex facts computed in code BEFORE Jev is asked. A hit becomes
# `code_signals.<id>.<name> = "<label>"` in the state, so Jev is told the fact rather than
# asked to spot it. TOML literal strings ('''...''') so backslashes are not escapes.
[signals.bank_details]
label = "new or changed bank details"
patterns = [
    '''(?i)\b(new|updated|changed|revised)\s+(bank|account|remittance|payment|wire|beneficiary)''',
    '''(?i)\b(iban|swift|bic|sort code|routing number|account number)\b''',
]
```

Matching is over `sender`, `reply_to`, `subject`, `body`, `attachments` and the `links` hosts.
Never over `provenance` - that is the calling agent's own note about capture, and letting it
count as evidence from the email would let the wrapper bias the judgment.

## `_core.toml`

Everything shared:

| Table | What it holds |
|---|---|
| `[model]` | Model name, cost per million input tokens, body truncation |
| `[choice]` | How the category question is framed, and the `none_fits` option |
| `[risk]` / `[pressure]` | The 0-3 scales, as ordered level descriptions |
| `[questions.*]` | The eight red-flag Nouls every category shares |
| `[verdict]` | Every threshold `derive()` applies (see below) |
| `[signals.*]` | Regex facts every email gets, as `code_signals.context.*` |

The red-flag questions are **shared, not per-category**, because they are independent of what the
mail turns out to be: "does it ask for a payment change" is worth answering whether the category
lands on `vendor_payment_fraud` or `legitimate_business`. That is the opposite of the code audit,
where each rule owns its questions, and it is deliberate - here the category is one 16-way choice
and the signals are evidence beside it, not inputs to it.

### `[verdict]`

```
category decides -> risk and flags adjust -> flags are evidence, never a verdict alone
```

| Key | Meaning |
|---|---|
| `malicious_min_confidence` / `malicious_min_risk` | A `verdict = "malicious"` category below either is reported `suspicious`. A low-confidence threat label is a warning, not a conviction. |
| `escalate_risk` | A harmless category reaches `suspicious` at this risk, but only with corroboration. Risk alone never escalates. |
| `corroborating` | The flags that count as corroboration: a concrete ask, not an atmosphere. |
| `caps_at_suspicious` | Categories that never reach `malicious` - `reconnaissance` is the setup, not the attack. |
| `identity_mismatch_below` | Below this, `identity_consistent` counts as a mismatch - **if identity was assessable at all**. |
| `identity_evidence` / `auth_absent` | Which fields make identity assessable, and which `auth` values mean "never captured" rather than "failed". |

That last pair is the most important thing in this folder. With no `auth` and no `relationship`,
Jev answers `identity_consistent` low for *unsupported*, which is indistinguishable from
*contradicted*. Code checks whether there was anything to assess against, records
`identity_unknown`, and bars it from escalating. Without it, every screenshot and every
header-free API result turns ordinary notifications into suspicious ones - measured, not
theorised: it was the entire false-alarm population of the 2026-09-22 field check.

## Writing criteria Jev answers well

- **One idea per option.** The `class` text is a description, not a checklist.
- **Put the near-miss in the text.** Most errors are boundary errors, and every boundary this
  skill gets right is written into a `class` string: an ordinary invoice from an authenticated
  vendor is not `vendor_payment_fraud`; a short vague subject from a marketer is
  `cold_outreach`, not `reconnaissance`; a named person pitching is `cold_outreach` while a role
  address broadcasting is `spam_marketing`.
- **Name the state fields** Jev should weigh: `sender`, `auth`, `relationship`, `code_signals`.
- **Absent is not adverse.** Never write a criterion that treats a missing field as a bad sign.
- **Signals state facts, not conclusions.** `label = "new or changed bank details"`, not
  `"fraudulent payment redirect"`. The label is handed to Jev; a conclusion in it is a leading
  question.

## After any change

```bash
python3 scripts/analyze.py --eval          # 27 synthetic controls, all must still pass
```

Then field-check against real labelled mail kept outside the skill (`evals/field_check.py`), and
turn every real miss into a synthetic control. A control set alone will not catch the class of
bug that only appears on partial input - see `references/methodology.md`.
