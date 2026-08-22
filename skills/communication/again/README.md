# /again

Say the last message again in plain English, keeping every name and number exact.

Agents write dense. A message that took three tool calls to earn comes out as a wall
of paths, line numbers, ticket IDs and hedges. `/again` restates it as one human
talking to another, without dropping a single thing you would need to act on.

## Usage

Type it after any message you want restated:

```
/again
```

No arguments. It operates on the assistant's previous message.

## The rule

> Cut explanation before you cut a name.

That is the whole skill. Paths, line numbers, functions, commands, error strings,
issue numbers, commit hashes, quoted evidence and every number with its unit survive
verbatim. What gets spent is flavour: the throat-clearing, the nested clauses, the
words that were doing no work.

This matters more than it sounds. Measured across several drafts, **identifier
retention predicts fidelity better than word count does.** Nearly every restatement
that left a reader unable to act had de-identified something ("the config file"
instead of `vite.config.ts:31`), not compressed it. So the skill spends its budget
protecting names and lets length fall where it falls.

## What it will not do

Add anything the source did not say. No invented number, no invented option, no
invented recommendation, and no hedge about what was verified. That last one is the
subtle failure: a caveat you added is a fabrication wearing the costume of honesty.

If the message was already plain, it says so rather than expanding it into sections
it never had.

## When to reach for something else

`/again` keeps every name because it assumes the reader is going to open those files.
When the reader is not, use [`/elim`](../elim/), which drops the names entirely and
says what the thing does instead of what it is called.

| | `/again` | `/elim` |
|---|---|---|
| Reader | The engineer doing the work | A manager making a decision |
| Identifiers | Kept verbatim | Removed |
| Shop talk | Kept | Removed |
| Failure mode it guards | Losing a name the reader needs | Inventing urgency the source never claimed |
