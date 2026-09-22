---
name: jev-email-analysis
description: >-
  Judge what an email is trying to get someone to do, with TypeSafe's Jev:
  a category across 16 kinds of mail (vendor payment fraud / BEC, fake
  invoice, executive impersonation, payroll diversion, credential harvest,
  OAuth consent phishing, malware delivery, callback/TOAD phishing, QR
  phishing, extortion, advance-fee, reconnaissance, bulk spam, cold sales
  outreach, legitimate), eight independent red-flag signals including prompt
  injection aimed at AI readers, risk and pressure scores, and a rolled-up
  verdict of malicious / suspicious / spam / benign. The calling agent gets
  the email into one documented schema from whatever source it has - a mail
  API, an MCP server, an .eml file, a paste, a screenshot - and every field
  is optional, so a subject and a body are enough. Redacts account, card and
  IBAN numbers before anything leaves the machine. Use whenever the user
  wants to know if an email is phishing, a scam, spam or safe, wants a batch
  of mail triaged or classified, or wants a second opinion on a suspicious
  message - even if they do not say "TypeSafe" or "Jev". Research proof of
  concept; a second reader, not a mail gateway.
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
metadata:
  summary: "Classifies what an email is trying to get someone to do with TypeSafe Jev: 16 categories, eight red-flag signals, risk and pressure, and a malicious / suspicious / spam / benign verdict, from one documented schema whose fields are all optional - a screenshot with a subject and body is a valid input"
---

# Jev Email Analysis

> **Research proof of concept.** This skill asks TypeSafe's Jev what an email is trying to
> get someone to do. It is a **second reader for a person or another agent, not a mail
> gateway**: `malicious` means "do not act on this without verifying out of band", not
> "block the sender", and `benign` means "nothing in what you sent stood out", not "this
> message is safe". It does not check authentication, resolve domains or open attachments -
> feed it those results as evidence. Repeat the short form of this at the end of every run.

## What it does

1. **Take the email in whatever form it arrived.** The contract is the schema in
   [`references/schema.md`](references/schema.md), and **every field in it is optional**.
   `scripts/ingest.py` converts the three mechanical formats (`.eml`/mbox, JSON in any shape,
   a pasted blob). Anything else - a screenshot, a PDF, a ticket, a chat transcript - you
   transcribe yourself. Every run prints which fields it actually got.
2. **Redact, then judge.** `scripts/analyze.py` strips IBANs, card/account runs and any 6+ digit
   run **before** the request leaves the machine, then sends one request per email: a 16-way
   category choice, eight yes/no red-flag signals, and risk and pressure on 0-3 scales. Email
   text is framed to Jev as untrusted data. About 2,500 tokens and ~1.5 s for 25 emails in
   parallel.
3. **Roll up in code.** `derive()` turns the typed answers into `malicious` / `suspicious` /
   `spam` / `benign`. Category decides, risk and flags adjust, and **an identity mismatch only
   counts when identity was assessable at all** - with no `auth` and no history, code records
   `identity_unknown` and the content has to carry the verdict.
4. **Report.** You read the verdicts and tell the user what each flagged message is trying to
   do, in plain words, with the evidence.

Nothing about any category is hard-coded. Everything lives in [`rules/`](rules/README.md): one
`<category>.toml` per category (the option Jev chooses between, the verdict it rolls up to, its
regex facts) and `_core.toml` (the model, the framing, the scales, the eight shared red-flag
questions, the verdict thresholds, the facts every email gets). Pass `--rules <dir>` to add or
replace categories without forking.

## Workflow

`SKILL_DIR` means the folder containing this SKILL.md.

### 1. Understand what the user wants

- **"Is this phishing?"** - one message, usually pasted or screenshotted. Answer with the
  verdict, the category, the red flags, and what to do.
- **"Triage these"** / **"check my inbox"** - a batch. Report attention-first; do not list
  every benign message.
- **"Does it hold up on our mail?"** - an evaluation. Use `evals/field_check.py` (step 5).

If the user has a mailbox connected and asks about "my email", work out the scope with them
(how far back, which folder). Pulling a whole mailbox is rarely what they meant.

### 2. Get the email into the schema

**This skill does not retrieve mail and does not dictate how you do.** Use whatever the
environment gives you - an MCP mail server, an API, IMAP, a file the user dropped, a screenshot
they pasted. Map what you get onto the schema in `references/schema.md` and write the staged
items into your scratchpad, never into the user's working tree.

For the mechanical formats:

```bash
python3 "$SKILL_DIR/scripts/ingest.py" --eml  msg.eml          # or a directory, or an .mbox
python3 "$SKILL_DIR/scripts/ingest.py" --json export.json      # schema items, a mail API
                                                               # message, or flat records
python3 "$SKILL_DIR/scripts/ingest.py" --text pasted.txt       # "-" reads stdin
```

`--json` is deliberately tolerant: it accepts items already in the schema, a MIME-style payload
tree (`payload.headers` / `payload.parts`, as several mail APIs return), or flat records, and it
matches field names by alias (`from`/`sender`, `replyTo`/`reply_to`, `plainTextBody`/`body`, …).
If your source does not fit, do not force it - just write the schema JSON directly. That is the
supported path, not a fallback.

**For a screenshot, a photo, a PDF or anything else code cannot parse:** you read it, and you
transcribe it. Put the visible header lines and body into the `--text` form, or write the schema
object yourself. Then say what you could not capture:

```
provenance: "screenshot of a mail client; sender and authentication headers not visible"
```

**Every field is optional, and partial input is a first-class case.** A subject and a body are
enough. The two rules that make that safe:

- **Absent is not adverse.** Write `auth: "not recorded"` or leave it out. Never write `"fail"`
  or `"none"` for a check that was never performed - a NULL auth column in a log export is "not
  recorded", and calling it a failure invents a threat that is not there.
- **Never put a reference labeller's opinion in `state`** - not "Gmail marked this spam", not
  "our gateway quarantined it". That leaks the answer into the question. Keep it in your labels.

Read the coverage line `ingest.py` prints. If it warns that `auth` and `relationship` are both
absent, say so in your report: the run could not assess sender identity, and the verdicts rest
on content alone.

### 3. Check prerequisites

```bash
python3 --version   # 3.10 or newer
test -n "$TYPESAFE_API_KEY" || test -f ~/.config/typesafe/env || echo "need a TypeSafe key"
```

Nothing to install; the TypeSafe call is plain `urllib` with backoff on 429/529/5xx. Keys come
from https://console.typesafe.ai/keys. `analyze.py` exits **3** when there are no credentials, so
a caller can treat the whole step as "skipped" rather than failed.

Optionally tell Jev who the recipient is, which sharpens internal-impersonation and look-alike
judgments: `--org-name "Acme" --own-domains acme.com,acme.io`, or
`~/.config/jev-email-analysis/config.json` (see `config.example.json`). Nothing org-specific
lives in this folder.

### 4. Run

```bash
python3 "$SKILL_DIR/scripts/analyze.py" --input items.json --out results.json \
  --org-name "Acme" --own-domains acme.com

python3 "$SKILL_DIR/scripts/ingest.py" --text - | \
  python3 "$SKILL_DIR/scripts/analyze.py" --stdin        # one pasted email, no temp file
```

Before changing any criterion, run the bundled controls and keep them passing:

```bash
python3 "$SKILL_DIR/scripts/analyze.py" --eval
```

### 5. Report back

1. **The verdict table**, attention-first: id / sender / subject / verdict / category (with
   confidence) / risk / flags. Do not pad it with benign rows.
2. **Two or three sentences per flagged message**: what it is trying to get the recipient to do,
   which signals fired, and what to verify out of band. Name the link hosts and the ask.
3. **What the run could not see.** If there was no `auth` or history, say the sender was not
   verified. If bodies were missing, say so. This is the difference between a second reader and
   a false sense of safety.
4. Tokens, cost and latency in one line; where the results file is.
5. The disclaimer, in two sentences: research proof of concept; a second reader, verify before
   acting.

Three readings worth calling out explicitly when they appear:

- **Authenticated sender + malicious intent** (e.g. `vendor_payment_fraud` with DMARC pass) is
  most likely a **compromised vendor mailbox** - the most dangerous case there is. Say so.
- **A malicious category below 0.8 confidence, or a `suspicious` verdict**, is a prompt to lean
  on deterministic evidence (auth, attachments, history), not a conviction.
- **`targets_ai_reader` true** is always worth reporting, even when everything else is benign.
  Someone wrote instructions in that email for a machine to read.

## Reading the output

| Field | Meaning |
|---|---|
| `verdict` | `malicious` / `suspicious` / `spam` / `benign`. Category decides; risk and flags adjust. |
| `category` + `_conf` + `_probs` | The 16-way choice, its confidence, and the full distribution. |
| `risk` / `pressure` + `_level` | 0-3 scores: harm from acting as asked, and how hard it pushes. |
| `flags` | Red-flag signals at p > 0.5, plus `identity_inconsistent` (assessed and contradicted) or `identity_unknown` (could not be assessed). |
| `answers` | Every raw typed answer, including p(true) for each yes/no signal. |

`spam_marketing` and `cold_outreach` both roll up to verdict `spam`: the first is bulk promotion
from a role address, the second is one-to-one prospecting from a named person, however personal
it sounds. `reconnaissance` is a first touch that sets up a later fraud and **caps at
`suspicious`** - it never reaches `malicious` on its own.

## Mock data

`mock-data/` has one sample per mechanical format - `sample.eml` (a payment-change lure with a
mismatched reply-to, failing auth and an attachment), `sample-api-message.json` (a MIME payload
tree with a base64 HTML body), and `sample-paste.txt` (a headerless executive-impersonation
paste). To check every front door still works:

```bash
cd "$SKILL_DIR/mock-data"
python3 ../scripts/ingest.py --eml  sample.eml              | python3 ../scripts/analyze.py --stdin
python3 ../scripts/ingest.py --json sample-api-message.json | python3 ../scripts/analyze.py --stdin
python3 ../scripts/ingest.py --text sample-paste.txt        | python3 ../scripts/analyze.py --stdin
```

Measured 2026-09-22: `vendor_payment_fraud` 1.00 / **malicious**; `spam_marketing` 1.00 /
**spam**; `reconnaissance` 0.78 / **suspicious**. The third is the one to watch - it is a
headerless paste, so it carries `identity_unknown` rather than `identity_inconsistent` and still
reaches `suspicious` on content alone. That is the partial-input contract working.

## Tuning

1. Edit the category's `rules/<id>.toml`, or `rules/_core.toml` for a shared question or
   threshold. Both are plain English plus a few numbers; `derive()` reads the thresholds.
2. `python3 scripts/analyze.py --eval` - all 27 controls must still pass.
3. Field-check against real labelled mail, kept **outside** this skill:
   ```bash
   python3 evals/field_check.py --dataset items.json --labels labels.json \
     --out run.itN.json --baseline run.itN-1.json
   ```
   Reports strict and lenient category accuracy, **false alarms** (harmless mail rated
   suspicious or malicious), **misses** (threats rated benign or spam), a confusion table, and
   what changed against the baseline.
4. Turn every real miss into a synthetic control in `evals/controls.json` (synthetic text only,
   never real customer mail). Stop when the remaining disagreements are ones a careful human
   would also argue about; past that you are overfitting.

## Eval baseline

**Controls** (2026-09-22, jev-latest, 27 synthetic, one or more per category): **category 26/26,
verdict 26/26, every signal in agreement.** Includes tricky legitimates (vendor invoice,
authenticated Microsoft alert, real DocuSign, relayed cloud notice), both sides of the
cold-outreach / reconnaissance line, and four degraded-input controls (headerless screenshot of
ordinary mail, headerless screenshot of a credential lure, header-only item with no body, a
paste carrying prompt injection).

**Field check A** (301 real messages, one mailbox, metadata only - no bodies), four tuning
iterations: 80.4% → 93.4% strict, 87.7% → 99.3% lenient, 73 → 1 false alarms, 0 misses.

**Field check B** (2026-09-22, 23 real messages from a different mailbox, **bodies included and
no authentication data at all** - the connector exposed no `Authentication-Results`):

| iteration | change | strict | lenient | false alarms | misses |
|---|---|---|---|---|---|
| 0 | as shipped | 87.0% | 95.7% | 2 | 0 |
| 1 | identity mismatch only counts when identity was assessable | 87.0% | 95.7% | **0** | 0 |
| 2 | rules folder; regex `code_signals` computed per email | 82.6% | **100%** | 0 | 0 |

Iteration 2 moved three items across the `legitimate_business` / `spam_marketing` line, which is
why strict fell while lenient reached 100%. Both are harmless categories and both roll up to a
harmless verdict, so nothing changed about what a reader would be told; the code signals
(`bulk_markers`, `role_sender`) simply make bulk mail read as bulk mail.

Iteration 1 is the `identity_assessable()` guard. Both false alarms at iteration 0 were the same
fault and neither was visible to the synthetic controls, which all carry auth strings: with no
`auth` and no history, Jev answered `identity_consistent` ≈ 0.2 for *unsupported*, code read it
as *contradicted*, and a legitimate "new sign-in detected" alert plus a benign sign-in ask became
`suspicious`. **Partial input needs its own field check; controls will not find this class of
bug.**

The residual strict gap in check B is harmless-vs-harmless (bulk vs cold vs legitimate), and one
snippet-only item with a seven-word body read as `none_fits` - honest behaviour on near-zero
input. Check B contained no threats (its spam folder was unreachable), so **threat recall rests
entirely on the synthetic controls and check A.**

Known soft spots: `risk` confidence sits at 0.45-0.65 between adjacent levels; a legitimate
DocuSign reads as `requests_credentials` ≈ 0.7; bodies under about fifteen words often land on
`none_fits`, which is the right answer but scores as a category miss.
