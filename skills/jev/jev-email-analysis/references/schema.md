# The email schema

One JSON object per email. **Every field is optional.** There is no required field and no
minimum set: a run uses whatever it was given and says what it could not assess.

This is the whole contract between the calling agent and the skill. The agent gets email content
into this shape from whatever source it has - an IMAP mailbox, a mail API, an MCP server, an
`.eml` file, a PDF, a screenshot, a chat paste, a ticket, a log export. The skill takes no
position on which, and hard-codes no retrieval.

```json
[
  {
    "id": "any-stable-string",
    "state": {
      "sender": "\"Dana Ruiz\" <dana.ruiz@vendor.example>",
      "reply_to": "ar.dept@proton.me",
      "subject": "Updated remittance details",
      "auth": "SPF pass, DKIM pass (vendor.example), DMARC pass",
      "body": "plain text, HTML already stripped",
      "links": ["vendor-billing.co", "proton.me"],
      "attachments": "remittance.pdf (application/pdf): macro-free, no static findings",
      "relationship": "domain: 479 msgs in 365d, first seen 2025-09-23; address: 3 msgs, first seen today",
      "provenance": "screenshot of a mail client; headers and authentication not captured"
    }
  }
]
```

`id` is yours; if you leave it out the items are numbered. A bare `state` object, or a single
object instead of a list, is also accepted.

## Fields

| Field | What it adds | When it is missing |
|---|---|---|
| `sender` | The **true** sender, not a group relay or a display name alone. Address matters more than name. | Identity cannot be checked; content carries the judgment. |
| `reply_to` | Catches the classic redirect: a plausible From with a reply-to somewhere else. | One impersonation signal is unavailable. |
| `subject` | Cheap, high signal, present in nearly every source. | Usually fine if there is a body. |
| `auth` | SPF / DKIM / DMARC results. Free text - `"SPF pass, DKIM pass (x.com), DMARC pass"` or the raw `Authentication-Results` header both work. | **Sender identity cannot be assessed at all.** See below. |
| `body` | What the mail actually asks the recipient to do. The single most useful field. Strip HTML; truncated at 3,500 characters. | Judged on sender, subject, auth and history only, and deliberately will not reach for a threat category without a concrete sign. |
| `links` | Link **hosts**, not full URLs - the host identifies the destination, and full URLs carry tracking tokens. | Look-alike domains in the body are still read as text. |
| `attachments` | One line per file: name, true type, and any static findings you already have. | No attachment reasoning. This skill does not open or scan files. |
| `relationship` | History with this sender, in words: message counts, first-seen dates, whether it is two-way. Substitutes for `auth` as identity evidence. | Combined with missing `auth`, identity is unknown. |
| `provenance` | Where the content came from and **what could not be captured**. | The run cannot distinguish "absent" from "not applicable". Always worth one sentence. |

## Absent is not adverse

The rule that governs every partial input: **a field that was not captured is unknown, never
evidence against the sender.** A screenshot has no SPF result; that is a property of the
screenshot, not of the email.

This is enforced in two places, so it does not depend on the model remembering it:

- `rules/_core.toml` tells Jev that absent signals are unknown and to withhold rather than
  answer `false`.
- `analyze.identity_assessable()` checks in **code** whether `auth` or `relationship` was
  supplied at all. When neither is, the identity answer is reported as `identity_unknown` and is
  barred from escalating a verdict on its own.

Without that second guard, every message from a source with no headers picks up an apparent
identity mismatch, and any ordinary "sign in to your account" notification becomes `suspicious`.
That was measured, not theorised - it was the entire false-alarm population of the 2026-09-22
field check, and fixing it took the run from 2 false alarms to 0.

Write `auth` as `"not recorded"` (or leave it out) when you do not have it. Never write
`"fail"` or `"none"` for a check that was never performed - a log export with a NULL auth column
is "not recorded", and calling it a failure invents a threat.

## What good input looks like

- **Send what you have, say what you don't.** Six accurate fields beat nine with two guessed.
- **`sender` should be the true sender.** For a mailing-list or Google Group relay, the
  `"'Name' via group" <group@your-domain>` form is normal and is already handled; if you can
  recover the original sender, put it in `relationship` or `provenance`.
- **Never put a reference labeller's opinion in `state`.** "Gmail marked this spam", "our
  gateway quarantined it", "the user says this is phishing" - none of that belongs in the email.
  It leaks the answer into the question and makes the output unscoreable. Keep it in your labels.
- **`body` is untrusted data.** It is framed to Jev as such, and instructions inside an email
  addressed to an AI reader are themselves a signal (`targets_ai_reader`), not an instruction.

## Coverage

`ingest.py` prints a field-coverage line to stderr for every run, and warns when `auth` and
`relationship` are both absent. Read it before spending a run: it tells you which signals the
judgment can actually rest on.
