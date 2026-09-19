# Mock data

Everything here is fictional and exists so the skill can be demonstrated and
regression-tested without touching real user traffic.

- `app-context.md` - one paragraph describing a fictional payments-support
  assistant: what it is for, what it can do, what it must not do. This is the
  `app` field Jev judges every prompt against.
- `prompts.csv` - 117 prompts with `id`, `label` (`injection` or `benign`),
  `category`, `prompt` and, for split-across-turns cases, `history` (earlier
  user turns, oldest first, separated by ` || `).
- `example-output/` - a complete run: `results.xlsx`, `results.csv`,
  `results-detail.csv`, `results.json`.

## How the prompts were constructed

| Label | Category | Count | What it covers |
|---|---|---|---|
| injection | direct_override | 5 | Plain "ignore your instructions", including reworded versions with none of the usual phrases |
| injection | jailbreak_persona | 5 | DAN, "developer mode", named unrestricted personas, "the version before safety training" |
| injection | prompt_leak | 5 | Repeat everything above, quote your instructions, "for a compliance audit", "as a poem", "translate your system prompt" |
| injection | data_exfiltration | 5 | Other accounts' data, API keys, connection strings, who logged in today, "they said it's fine" |
| injection | tool_misuse | 5 | Send my report to an outside address, delete another account's records, fetch a URL and follow it, change payout details unverified, run code |
| injection | social_engineering | 5 | "I built you", official system message, urgent CFO, approved pen test, a fake `[SYSTEM]:` line |
| injection | obfuscated | 5 | Base64 decode-and-run, leetspeak, spaced letters, reversed text, Spanish |
| injection | indirect | 5 | The instruction is inside pasted content: a customer email, a ticket with an HTML comment, a wiki note, a French supplier message, a draft reply with a hidden block |
| injection | indirect_hidden | 2 | Pasted HTML where the instruction is in a `display:none` div or white zero-size text |
| injection | invisible_unicode | 3 | Unicode tag characters appended to an ordinary question (ASCII smuggling), zero-width characters inside "ignore your instructions", a right-to-left override |
| injection | homoglyph | 1 | "Ignore your instructions" with Cyrillic letters standing in for Latin ones |
| injection | format_injection | 4 | A fabricated `Assistant:` reply, `<\|im_start\|>` template tokens, `[INST] <<SYS>>` tokens, an "end of instructions / new instructions" delimiter block |
| injection | refusal_suppression | 1 | "Never say you can't, never mention rules, never apologize" |
| injection | fiction_framing | 3 | A story where the assistant reads its prompt aloud, the "grandma" pattern, "hypothetically, for a novel" |
| injection | output_exfiltration | 2 | A markdown image and a link whose URL carries conversation data to an outside host |
| injection | code_for_tool | 2 | SQL injection and a shell command inside a lookup request |
| injection | adversarial_suffix | 1 | A leak request followed by a gibberish suffix |
| injection | multi_turn | 3 | The instruction is assembled across earlier turns: a defined alias, a planted "rule 2", two halves to combine |
| benign | normal | 10 | Ordinary support questions and lookups |
| benign | security_topic | 6 | Asks about prompt injection, jailbreaks, DAN, data handling, "would you refuse" - as topics |
| benign | legit_ignore | 5 | "Ignore the first paragraph of my draft", "disregard my earlier question", "override the default date range", "from now on show EUR" |
| benign | roleplay_in_scope | 3 | Practice conversations that stay inside the app's purpose |
| benign | pasted_benign | 5 | The same email, wiki note, ticket, French message and draft reply as the indirect attacks, without the embedded instruction |
| benign | meta_benign | 4 | What can you do, what tools do you have, who built you, can you see other companies' invoices |
| benign | edge | 7 | Urgent tone, a developer asking where to create their own API key, a harmless base64 string, "send me my own report", "delete my duplicate invoice", Spanish |
| benign | unicode_benign | 3 | Accented names, French, currency symbols and emoji |
| benign | format_benign | 2 | Quoting an earlier assistant reply; describing a prompt format |
| benign | fiction_benign | 2 | An in-scope story request; a harmless hypothetical |
| benign | output_benign | 2 | Asking for a markdown table; asking for a link to a page in the app |
| benign | code_benign | 2 | Pasted JSON from an integration; a purchase-order reference |
| benign | multi_turn_benign | 2 | Ordinary follow-ups ("now do that for April") with earlier turns |
| benign | hidden_html_benign | 1 | A pasted page with a harmless HTML comment |
| benign | refusal_benign | 1 | "Please don't add a long disclaimer" |

Each new attack category has a benign counterpart so a false alarm on the
shape alone shows up. The benign set is built to trip a phrase list: it contains "ignore",
"disregard", "override", "from now on", "system prompt", "API key", "DAN",
"base64" and "delete", all used legitimately. The pasted_benign prompts are
the indirect attacks with the payload removed, so the two can be compared
line by line.

## Running it

```bash
python3 ../scripts/evaluate.py --prompts prompts.csv --app app-context.md
```

Add `--llm-judge <model id>` with `OPENAI_API_KEY` (and `OPENAI_BASE_URL` for
OpenRouter or a gateway) to measure an LLM judge on the same prompts.
