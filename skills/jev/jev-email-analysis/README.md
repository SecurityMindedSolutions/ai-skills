# Jev Email Analysis

Intent classification for email. SPF, DKIM, DMARC and attachment sandboxing tell you whether a
message is what it claims to be and whether it carries a payload. They do not tell you what it is
trying to get someone to do, which is why a compromised vendor mailbox passes every check you
have. This skill asks that one question and returns it typed.

Per email: a category across 16 classes, eight independent red-flag Nouls, `risk` and `pressure`
on 0-3 scales, and a rolled-up verdict of **malicious / suspicious / spam / benign**. Built on
TypeSafe's Jev. Code does the redaction, the regex facts and the roll-up; Jev does the judgment.

Input is one schema in which **every field is optional**. A subject and a body scraped off a
screenshot is a valid run.

> Research proof of concept. A second reader for an analyst or an agent, **not a mail gateway**.
> `malicious` means "verify out of band before acting", not "block the sender"; `benign` means
> "nothing in what you sent stood out", not "this message is safe". It performs no
> authentication, no DNS, no detonation - feed it those results as evidence. Everything in
> `mock-data/` and `evals/` is fictional.

## Pipeline

```
any format ──▶ ingest.py ──▶ schema items ──▶ redact ──▶ code_signals ──▶ Jev ──▶ derive() ──▶ verdict
              .eml / mbox                     IBAN,       regex facts     1 req    thresholds
              JSON (any shape)                card/acct   per email       per      from
              pasted text                     6+ digits                   email    _core.toml
              (screenshots: the agent
               transcribes into the schema)
```

1. **Ingest.** `scripts/ingest.py` reads `.eml`, mbox, JSON in almost any shape (schema items, a
   MIME payload tree, flat records, matched by field alias), or a pasted blob. Anything code
   cannot parse - a screenshot, a PDF, a ticket, a Teams paste - the calling agent transcribes
   into the same schema. Every run prints field coverage to stderr and warns when `auth` and
   `relationship` are both absent.
2. **Redact.** IBANs, 13-19 digit card/account runs and any 6+ digit run are replaced *before*
   the request leaves the machine, inside `normalize()` so a caller cannot skip it.
3. **Compute facts.** Regexes from `rules/` produce `code_signals`: wallet addresses, urgency
   and secrecy language, look-alike TLDs, punycode, shorteners, enable-macros phrasing,
   executable and container attachments, role-address senders, bulk-mail markers, plus a
   reply-to/sender domain comparison. Jev is *told* these facts rather than asked to spot them.
4. **Ask Jev.** One request per email: the 16-way choice, two scores, eight Nouls. ~2,500 input
   tokens. Email text is framed as untrusted data.
5. **Derive.** Category decides the verdict; risk and flags adjust it. Thresholds live in
   `rules/_core.toml`, not in Python.

## The schema

Full contract in [`references/schema.md`](references/schema.md). No field is required.

| Field | Carries |
|---|---|
| `sender` | The true sender. Address over display name. |
| `reply_to` | The classic redirect: plausible From, reply elsewhere. Compared to `sender` in code. |
| `subject` | Cheap, high signal, present in nearly every source. |
| `auth` | SPF/DKIM/DMARC. Free text, or paste the raw `Authentication-Results` header. |
| `body` | What the mail asks for. Most useful single field. HTML stripped, 3,500 char cap. |
| `links` | Link **hosts**, not URLs - the host identifies the destination and full URLs carry tracking tokens you do not need to ship. |
| `attachments` | One line per file: name, true type, any static findings you already have. |
| `relationship` | History in words: counts, first-seen, whether two-way. Substitutes for `auth` as identity evidence. |
| `provenance` | Where it came from and **what could not be captured**. |

Two input rules that matter operationally:

- **Write `auth: "not recorded"`, never `"fail"`, for a check that was not performed.** A NULL
  auth column in a log export is missing data, not a DMARC failure. Calling it a failure invents
  a threat.
- **Never put a reference labeller's verdict in `state`** - not "Gmail marked this spam", not
  "the gateway quarantined it". It leaks the answer into the question and makes the run
  unscoreable.

## Categories and signals

`legitimate_business` · `vendor_payment_fraud` (BEC) · `fake_invoice` · `executive_impersonation`
· `payroll_diversion` · `credential_harvest` · `oauth_consent_phish` · `malware_delivery` ·
`callback_phishing` (TOAD) · `qr_phishing` · `extortion` · `advance_fee_or_prize` ·
`reconnaissance` · `spam_marketing` · `cold_outreach` · `none_fits`

`reconnaissance` caps at `suspicious` - it is the setup, not the attack. `spam_marketing` and
`cold_outreach` both roll up to `spam`: role address broadcasting versus a named person
prospecting.

The eight Nouls are answered independently of the category, because they are worth knowing either
way: `asks_payment_change`, `requests_credentials`, `asks_to_open_or_run`, `asks_to_call`,
`secrecy_or_channel_switch`, `brand_or_exec_impersonation`, `identity_consistent`, and
`targets_ai_reader` - prompt injection written into a body for a machine to read, which is worth
reporting even when everything else is clean.

## Rules are a folder

Everything about a category lives in [`rules/`](rules/README.md), one TOML file each: the option
Jev chooses between, the verdict it rolls up to, and its regex facts. `_core.toml` holds the
model, the framing, the scales, the eight shared questions, the verdict thresholds and the
signals every email gets. `analyze.py` knows about none of it.

```bash
python3 scripts/analyze.py --input items.json --rules ./my-rules
```

A file whose `id` matches a built-in category replaces it; a new `id` adds one; a `_core.toml`
there replaces matching tables. Retune `vendor_payment_fraud` for your AP process, or add a
category your sector actually sees, without forking.

## Identity evidence, and why it is decided in code

`identity_consistent` asks whether the technical signals support the sender's claim. Given no
`auth` and no `relationship`, Jev answers low - meaning *unsupported* - which is indistinguishable
from *contradicted*.

So code decides whether the question was answerable. `identity_assessable()` checks whether any
identity evidence was supplied at all; when none was, the result carries `identity_unknown`
rather than `identity_inconsistent`, and cannot escalate a verdict by itself.

Without that guard every header-free source turns routine mail suspicious. On a 23-message field
check with no auth data it was the difference between 2 false alarms and 0, and **neither was
visible to the 23 synthetic controls** - because anyone writing a control writes a complete one.
If you tune this, field-check on partial input specifically.

## Usage

`SKILL.md` is the agent-facing document; the assistant reads it and drives the rest. By hand:

```bash
# one message
python3 scripts/ingest.py --eml  suspect.eml  | python3 scripts/analyze.py --stdin
python3 scripts/ingest.py --text pasted.txt   | python3 scripts/analyze.py --stdin

# a batch, with recipient context so internal-impersonation claims can be judged
python3 scripts/ingest.py --json export.json --out items.json
python3 scripts/analyze.py --input items.json --out results.json \
  --org-name "Acme" --own-domains acme.com,acme.io

# regression suite
python3 scripts/analyze.py --eval

# score a real labelled set: false alarms, misses, confusion, diff vs a baseline
python3 evals/field_check.py --dataset items.json --labels labels.json \
  --out run.it1.json --baseline run.it0.json
```

Python 3.11+ (`tomllib`), no dependencies; the TypeSafe call is `urllib` with backoff on
429/529/5xx. Credentials from `TYPESAFE_API_KEY` or `~/.config/typesafe/env`; keys at
https://console.typesafe.ai/keys. **Exit 3 = no credentials**, so a caller can treat the step as
skipped rather than failed.

## Results

**Controls** - 27 synthetic emails, at least one per category, including a real vendor invoice,
an authenticated Microsoft alert, a genuine DocuSign, a relayed cloud notice, both sides of the
cold-outreach/reconnaissance line, and four degraded-input cases: **category 26/26, verdict
26/26**, every labelled signal in agreement.

**Field check A** - 301 real messages, metadata only, 4 iterations: 80.4% → 93.4% strict, 73 → 1
false alarms, 0 misses.

**Field check B** - 23 real messages, full bodies, no auth data at all:

| # | change | strict | lenient | false alarms | misses |
|---|---|---|---|---|---|
| 0 | as shipped | 87.0% | 95.7% | 2 | 0 |
| 1 | `identity_assessable()` guard | 87.0% | 95.7% | **0** | 0 |
| 2 | rules folder + `code_signals` | 82.6% | **100%** | 0 | 0 |

Strict fell at iteration 2 because three items moved across the
`legitimate_business`/`spam_marketing` line - both harmless, same verdict.

**Check B contained no threats** (its spam folder was unreachable through the connector), so it
measures false alarms and nothing else; threat recall rests on the controls and check A. n=23 is
enough to find a systematic mechanism, not enough for a confidence interval.
[`references/methodology.md`](references/methodology.md) has the full accounting, including what
these numbers do not cover.

## Layout

| Path | What it is |
|---|---|
| `SKILL.md` | Agent-facing instructions |
| `rules/` | One TOML per category, plus `_core.toml`. The whole policy |
| `references/schema.md` | The input contract |
| `references/methodology.md` | How it was tuned and validated, and the gaps |
| `scripts/ingest.py` | Any format → schema, with field-coverage reporting |
| `scripts/rules.py` | Loads `rules/`, builds the questions, computes `code_signals` |
| `scripts/analyze.py` | Redaction, the Jev requests, `derive()` |
| `scripts/jev.py` | TypeSafe client: `urllib`, backoff on 429/529/5xx |
| `evals/controls.json` | 27 labelled synthetic emails |
| `evals/field_check.py` | Scores a real labelled set against your own labels |
| `mock-data/` | One sample per input format |
