# Communication

Restating what the agent just said, for a different reader.

None of these take arguments. Each operates on the assistant's previous message, and
none of them add anything the source did not say. What separates them is who is
reading and how much of them the message gets.

| Command | Reader | What comes back |
|---|---|---|
| `/again` | The engineer who is going to open those files | Plain prose, every identifier kept verbatim |
| `/elim` | A manager making a decision | Plain prose, identifiers and shop talk removed |
| `/ugh` | You, tired, deciding whether this one wants you | One sentence, plus a `You:` line only if something needs you |
| `/huh` | You, picking a dropped thread back up | Three labelled lines: `Now:`, `Next:`, `You:` |

They pair up two ways. `/again` and `/elim` disagree about whether the reader needs
the names: `/again` keeps every identifier because the reader is going to open those
files, `/elim` drops them all because the reader is not. `/ugh` and `/huh` are a
tighter pair still, sharing every rule except their shape, and both drop identifiers
the way `/elim` does.

The failure each guards against differs too. For `/again` it is losing a name the
reader needs. For the other three it is inventing urgency, risk or severity the source
never claimed.

---

## `/again`

Agents write dense. A message that took three tool calls to earn comes out as a wall of
paths, line numbers, ticket IDs and hedges. `/again` restates it as one human talking to
another, without dropping a single thing you would need to act on.

### The rule

> Cut explanation before you cut a name.

That is the whole skill. Paths, line numbers, functions, commands, error strings, issue
numbers, commit hashes, quoted evidence and every number with its unit survive verbatim.
What gets spent is flavour: the throat-clearing, the nested clauses, the words that were
doing no work.

This matters more than it sounds. Measured across several drafts, **identifier retention
predicts fidelity better than word count does.** Nearly every restatement that left a
reader unable to act had de-identified something, saying "the config file" instead of
`vite.config.ts:31`, rather than compressed it. So the skill spends its budget protecting
names and lets length fall where it falls.

### What it will not do

Add anything the source did not say. No invented number, no invented option, no invented
recommendation, and no hedge about what was verified. That last one is the subtle failure:
a caveat you added is a fabrication wearing the costume of honesty.

If the message was already plain, it says so rather than expanding it into sections it
never had.

---

## `/elim`

Explain it like I am a manager. The name is a riff on ELI5, but the audience is not a
five-year-old. It is a director, an executive, a non-technical lead. They are smart. They
just do not know the words.

### The rule

> Would this reader say it themselves?

One test, run per word. Keep the words they use, drop the words only the team uses, and
when the answer is unclear keep the source's word.

That last clause matters. A vaguer word is not a plainer one. A reader can ask about a
term they do not know, but they cannot ask for a detail you deleted.

### Before and after

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

### Two things it does that are easy to get wrong

**It splits done from not done.** Most long findings are ninety percent work the author
already handled and ten percent that needs the reader. Leading with that split is what
makes a wall of text usable by someone who has thirty seconds.

**It keeps the hedge.** If the source said no problems were found, that does not get
promoted to correct. If the source said something is unproven, it stays unproven. A
summary badly wants to flatten those, and flattening them is a fabrication.

It will also never invent risk, money, urgency or severity. If the source never said why
something matters, the skill says what happened and stops.

### Plainness, not brevity

The skill does not ask for anything to be shorter, and output is often *longer* than the
source. Unpacking a term costs more room than the term did.

Two findings from tuning it, both measured:

- **Word length is the lever, not sentence length.** Flesch weights word length about four
  times sentence length. An earlier draft governed sentences only and read *harder* than
  the raw engineering it was translating, because it swapped short shop talk for long
  formal words: *prod* became *production environment*, *fix* became *remediation*.
  Trading a term the reader did not know for a term they do not want is not a translation.
- **Names alone were never the target.** A message can carry zero code identifiers and
  fourteen pieces of shop talk. *Canary, drain, ramp, smoke test, backfill, cut over* all
  look like ordinary English and are not. A rule that matches on typography has nothing to
  bite on there.

---

## `/ugh`

One breath. For when you have nine things open and need to know whether this one wants
you.

One sentence for where things stand. Then, only if the source asked you for something,
a second line labelled `You:` carrying the ask and how soon it is needed. There is no
`You:` line when there is no ask, and never an empty one. Its absence is the message.
Two lines is the ceiling.

### The ask

An ask is something only you can do: a decision, an approval, an action, an answer.
"I will ping you when it lands" is not an ask.

One ask stays inline. Two or more become bullets, one per ask, so the count is visible
before a word is read. Two asks are never merged, and never replaced by a count,
because a counted ask is a lost ask. Bullets are ordered by what is needed soonest and
each leads with its urgency, so you can find tonight's work without reading the topics:

```
You:
- Before I merge: both changes now, or hold the app side until after the campaign?
- No rush: file a check that catches the next one?
```

That prefix comes only from what the source said, a deadline it named or work it said
this blocks. When every ask shares one urgency, it is said once on the `You:` line and
the per-bullet prefixes are dropped, because a prefix repeated on every bullet is not
information.

---

## `/huh`

Now, next, you. Wait, where were we? For picking a thread back up.

Three labelled lines, nothing before or after them:

```
Now:  where it stands.
Next: what happens without you.
You:  the ask, or "nothing".
```

One or two sentences a line. A label stays even when its line is empty, because a
missing label reads as forgotten rather than as clear.

It shares every rule with [`/ugh`](#ugh) except the shape: same definition of an ask,
same bullet rules, same urgency prefixes, same refusal to invent a deadline. A rule
changed in one belongs in the other.

### Words, in both

No file paths, tool names, commands or shop talk. Say what a thing does, not what it is
called. Short common words: use, not utilize. Wrong, not incorrect. Left out, not
omitted.

One exception, and only one: the pull request or ticket the message is about survives,
once, as a short link.

### Faithfulness, in both

Keep the ask and never invent one. Keep the source's hedges: if it said no problems
were found, that does not get promoted to correct; if it said something is unproven, it
stays unproven. Keep every number the source gave. If the message was already this
short, say so and leave it alone.
