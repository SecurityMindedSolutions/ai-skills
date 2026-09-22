# Methodology

How this was built, tuned and validated, and what the numbers do not cover.

## What Jev is asked, per email

One request, five kinds of answer:

| Question | Primitive | Returns |
|---|---|---|
| `category` | choice, 16 options | The option, its confidence, and the full distribution |
| `risk` | score, 4 levels | Expected value 0-3 plus the distribution |
| `pressure` | score, 4 levels | Expected value 0-3 plus the distribution |
| 8 red flags | noul | p(true) each |

Jev returns typed answers with probabilities and generates no text, so every output is directly
scoreable and comparable across runs. A run costs about 2,500 input tokens per email; the
27-control suite is ~72k tokens and about two seconds at six-way parallelism.

## The division of labour

Code does everything mechanical and everything that can be decided rather than judged:

- **Redaction**, before anything leaves the machine: IBANs, 13-19 digit card/account runs, and
  any 6+ digit run. In `analyze.redact()`, applied in `normalize()` so a caller cannot skip it.
- **Regex facts** (`rules.code_signals`): wallet addresses, urgency phrases, look-alike TLDs,
  punycode, shorteners, enable-macros language, role-address senders, bulk-mail markers. These
  are handed to Jev as `code_signals` so it is *told* the fact rather than asked to spot it.
- **Reply-to mismatch**: a domain comparison, not a judgment.
- **Whether identity was assessable at all** - see below.
- **The verdict roll-up**: thresholds in `rules/_core.toml`, applied in `derive()`.

Jev does only the part that needs judgment: what the email is *trying to get someone to do*.
That is the part regex, SPF and attachment sandboxing cannot reach, and the reason a
well-authenticated message from a compromised vendor mailbox is the most dangerous case there
is - every deterministic check passes, and only intent gives it away.

## Absent is not adverse

The single most consequential design decision, and the one that took a real field check to find.

`identity_consistent` asks whether the technical signals support the sender being who they claim
to be. With no `auth` and no `relationship` - a screenshot, a paste, an API that does not expose
`Authentication-Results` - there is nothing to check against. Jev answers low, meaning
*unsupported*. Code cannot tell that apart from *contradicted*.

So code decides instead. `analyze.identity_assessable()` checks whether any field in
`[verdict].identity_evidence` was supplied, treating the `auth_absent` placeholder values as
"never captured". When nothing was, the result carries `identity_unknown` instead of
`identity_inconsistent`, and is barred from escalating a verdict on its own.

**This class of bug is invisible to a synthetic control set.** All 23 original controls carry
auth strings, because whoever writes a control writes a complete one. The fault only appeared on
real mail pulled through a connector that exposes no auth headers, where it produced two false
alarms out of 23 - a legitimate Vercel "new sign-in detected" alert and a SaaS welcome mail, both
escalated because a benign "sign in to your account" ask met an apparent identity mismatch that
was really just missing headers. If you tune this skill, field-check on partial input
specifically.

## Validation

**Controls** (`evals/controls.json`): 27 synthetic emails, at least one per category, including
deliberately tricky legitimates - a real vendor invoice, an authenticated Microsoft security
alert, a genuine DocuSign, a cloud notice arriving via a Google Group relay - and both sides of
the `cold_outreach` / `reconnaissance` line, which is the boundary this taxonomy gets wrong most
easily. Four are degraded-input controls: a headerless screenshot of ordinary mail, a headerless
screenshot of a credential lure, a header-only item with no body, and a paste carrying prompt
injection. Current: **category 26/26, verdict 26/26**, every labelled signal in agreement.
(26 not 27 because one control labels only a signal, not a category.)

**Field check A**: 301 real messages from one mailbox, metadata only, no bodies. Four iterations:

| # | change | strict | lenient | false alarms | misses |
|---|---|---|---|---|---|
| 0 | `cold_outreach` added | 80.4% | 87.7% | 73 | 0 |
| 1 | risk alone never escalates; group-relay awareness; recon needs evidence and caps at suspicious; bulk = role address, cold = named person; notifications are legitimate | 91.7% | 95.3% | 9 | 0 |
| 2 | malicious needs confidence ≥ 0.5; fine/tax/penalty lures in `fake_invoice`; government impersonation; dataset NULL-auth bug fixed | 93.4% | 99.3% | 2 | 0 |
| 3 | two-way history counts as identity evidence | 93.4% | 99.3% | 1 | 0 |

**Field check B** (2026-09-22): 23 real messages from a different mailbox, **full bodies, and no
authentication data at all** - the connector exposed no `Authentication-Results`, so every item
ran with `auth: "not recorded"`. Notifications, receipts, invoices, security alerts, vendor
marketing, a Google Group moderator digest that quotes a spam pitch inside a legitimate
notification, a calendar acceptance, and two genuine cold-outreach pitches.

| # | change | strict | lenient | false alarms | misses |
|---|---|---|---|---|---|
| 0 | as shipped | 87.0% | 95.7% | 2 | 0 |
| 1 | `identity_assessable()` guard | 87.0% | 95.7% | **0** | 0 |
| 2 | rules folder; regex `code_signals` per email | 82.6% | **100%** | 0 | 0 |

Iteration 2 moved three items across the `legitimate_business` / `spam_marketing` line, which is
why strict fell while lenient reached 100%. Both are harmless categories rolling up to harmless
verdicts, so nothing changed in what a reader is told; the `bulk_markers` and `role_sender`
signals simply make bulk mail read as bulk mail.

## What the numbers do not cover

- **Field check B contained no threats.** The mailbox's spam folder held 57 messages but the
  connector would not return `SPAM`-labelled threads under any query, so the threat side of that
  run is empty. Threat recall rests on the controls and field check A, not on B. A precision
  number from a corpus with no positives is a false-alarm measurement and nothing more.
- **n=23 is small.** It is enough to find a systematic false-alarm mechanism - it did - and not
  enough to put a confidence interval on anything.
- **The reference in check B is Gmail's own placement**, which cannot separate `cold_outreach`
  from `spam_marketing` from `legitimate_business`; all three are "not spam" to it. Strict
  category accuracy against that reference is therefore not very meaningful, and the useful
  numbers are false alarms and misses.
- **Both field checks are single mailboxes** in one industry. Category priors elsewhere will
  differ.

## Known soft spots

- `risk` confidence sits at 0.45-0.65 between adjacent levels. The expected value is stable; the
  level label is not, so rank by `risk` rather than switching on `risk_level`.
- A legitimate DocuSign reads as `requests_credentials` ≈ 0.7. It does ask you to click through
  and identify yourself, so this is arguably right and deliberately left alone.
- Bodies under about fifteen words often land on `none_fits`. That is the honest answer to a
  seven-word snippet, but it scores as a category miss.
- `spam_marketing` versus `cold_outreach` versus `legitimate_business` is the residual error
  population in both field checks. All three are harmless and the verdict is the same, so this is
  the cheapest kind of error to have.

## Why Jev and not a rule engine or an LLM

The rules live in `rules/` and they do real work - they compute the facts. What they cannot do is
say whether "please update our remittance details" is a vendor changing banks or an attacker, or
whether a short vague email is a busy colleague or a pretext. That is a judgment, and Jev returns
it calibrated in a couple of hundred milliseconds for a fraction of a cent - cheap enough to run
on every message in a mailbox.

A generative model could write a nicer explanation, but it costs more per email than this whole
run, it returns prose that has to be parsed back into a decision, and it can be argued with by
text inside the email. Jev answers only the typed questions it was asked; the `targets_ai_reader`
signal exists precisely because email bodies do try to give instructions to whatever is reading
them.
