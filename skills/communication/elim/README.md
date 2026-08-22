# /elim

Explain it like I am a manager. Plain English, no code names and no shop talk.

The name is a riff on ELI5, but the audience is not a five-year-old. It is a
director, an executive, a non-technical lead. They are smart. They just do not know
the words.

## Usage

Type it after any message you want restated:

```
/elim
```

No arguments. It operates on the assistant's previous message.

## The rule

> Would this reader say it themselves?

One test, run per word. Keep the words they use, drop the words only the team uses,
and when the answer is unclear keep the source's word.

That last clause matters. A vaguer word is not a plainer one. A reader can ask about
a term they do not know, but they cannot ask for a detail you deleted.

## Before and after

A source message with fifteen identifiers in it:

> **Verdict: KICKBACK.** `F1` - `AC5` cannot be satisfied by this ticket's own work.
> Files opened: `services/checkout/dispatcher.mjs:1397` (the `touchesPayment` gate),
> `docs/runbooks/refund-lanes.md:160-172`. `AC5` `[runtime]` reads *"a refund
> declaring a stored card dispatches to the settlement lane…"* But the
> `## File footprint` block declares `PAY-4471` HOST ONLY, so `AC5`'s subject cannot
> be `PAY-4471` itself. It has to be `PAY-4402` or `PAY-4419`, and both are
> `blocked_by` `PAY-4471`.

After `/elim`:

> The plan did not pass review. I need you to make one call.
>
> The plan makes five promises it must prove before the work is done. It can prove
> four. It cannot prove the fifth. That fifth one can only be tested by a second
> piece of work, and that work is stuck waiting on this one.
>
> Go ahead as written, and whoever finishes has two choices. Both are bad. Tick the
> box with no proof, which is the very thing our reviews exist to catch. Or leave the
> work open for good, which holds up the two things it was meant to free.
>
> So: tell me who proves the fifth promise, or tell me we can sign off without it.

## Two things it does that are easy to get wrong

**It splits done from not done.** Most long findings are ninety percent work the
author already handled and ten percent that needs the reader. Leading with that split
is what makes a wall of text usable by someone who has thirty seconds.

**It keeps the hedge.** If the source said no problems were found, it does not get
promoted to correct. If the source said something is unproven, it stays unproven. A
summary badly wants to flatten those, and flattening them is a fabrication.

It will also never invent risk, money, urgency or severity. If the source never said
why something matters, the skill says what happened and stops.

## Plainness, not brevity

The skill does not ask for anything to be shorter, and output is often *longer* than
the source. Unpacking a term costs more room than the term did.

Two findings from tuning it, both measured:

- **Word length is the lever, not sentence length.** Flesch weights word length about
  four times sentence length. An earlier draft governed sentences only and read
  *harder* than the raw engineering it was translating, because it swapped short shop
  talk for long formal words: *prod* became *production environment*, *fix* became
  *remediation*. Trading a term the reader did not know for a term they do not want is
  not a translation.
- **Names alone were never the target.** A message can carry zero code identifiers and
  fourteen pieces of shop talk. *Canary, drain, ramp, smoke test, backfill, cut over*
  all look like ordinary English and are not. A rule that matches on typography has
  nothing to bite on there.

## When to reach for something else

Use [`/again`](../again/) when the reader is going to open the files. It keeps every
path, line number and ticket exactly as written, on the principle that losing a name
costs more than losing an explanation.
