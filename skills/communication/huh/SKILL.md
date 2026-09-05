---
name: huh
description: Now, next, you. Wait, where were we? Say the last message again as three labelled lines - where it stands, what happens without me, and what you need from me. For picking a thread back up.
disable-model-invocation: true
metadata:
  summary: "Now, next, you. Restates the last message as three labelled lines for picking a dropped thread back up"
---

Say your last message again for someone who is tired. They have nine things open
and are picking this one back up.

## Shape

Three labelled lines, nothing before or after them:

```
Now:  where it stands.
Next: what happens without them.
You:  the ask, or "nothing".
```

One or two sentences a line. Keep a label even when its line is empty - a missing
label reads as forgotten, not as clear.

Write each label in bold - `**Now:**`, `**Next:**`, `**You:**` - and the urgency
prefix on each bullet too. The terminal renders markdown, so bold is the only
emphasis available, and the labels are what makes this scannable rather than
readable.

## Words

No file paths, tool names, commands or shop talk. Say what a thing does, not what
it is called. Short common words: use, not utilize. Wrong, not incorrect. Left
out, not omitted.

One exception, and only one: keep the pull request or ticket the message is
about. Once, as a short link - `[#1733](the url)` - on the thing it names. It
does not count against the shape.

## The ask

An ask is something only they can do: a decision, an approval, an action, an
answer. "I will ping you when it lands" is not an ask.

"Nothing" and an ask cannot share a line. If there is an ask, it comes first. Say
how soon it is needed after it, never before.

**One ask stays inline on the `You:` line. Two or more become bullets under it**,
one per ask, so the count is visible before a word is read. Never merge two asks
into one, and never replace them with a count - a counted ask is a lost ask.

Order the bullets by what is needed soonest.

**Each bullet leads with its urgency**, so the reader can find tonight's work
without reading the topics:

```
You:
- Before I merge: both changes now, or hold the app side until after the campaign?
- No rush: file a check that catches the next one?
```

The prefix comes only from what the source said - a deadline it named, or work it
said this blocks. If the source said nothing about timing for an ask, that bullet
starts with the ask itself and carries no prefix. Never invent urgency, and never
invent a deadline.

When every ask shares one urgency, say it once on the `You:` line and drop the
per-bullet prefixes. A prefix repeated on every bullet is not information, and
"Also before starting" is a clumsy way of saying "same as the one above":

```
You: both before any work starts.
- Cross-agent for all nine, which means ...
- Does your local copy stay the master ...
```

## Faithfulness

Keep the ask, and never invent one. Add nothing the source did not say, and keep
its hedges: if the source said no problems were found, that does not become
correct; if it said something is unproven, it stays unproven. Keep every number
the source gave.

No headings, tables or code beyond the three labels, and no bullets except the
multiple-ask case above.

If the message was already this short, say so and leave it alone.

---

Sibling: `/ugh` (one breath, the tldr) shares everything above except the Shape section. A
rule changed here belongs there too.
