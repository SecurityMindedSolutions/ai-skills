# Traffic Triage Eval

Answer "who was hitting us, and does it matter?" from edge logs. Every
client IP in a load-balancer or WAF export gets one row: benign user,
benign bot, AI agent, internet background scanning, or malicious, with a
0-3 severity, the signals behind it, and the paths, so a person can read
the top of the sheet and know where to look.

**Contents**

- [Disclaimer](#disclaimer)
- [How this is different](#how-this-is-different)
- [What it does](#what-it-does)
- [The contract: you retrieve, it classifies](#the-contract-you-retrieve-it-classifies)
- [The categories](#the-categories)
- [Results on the mock set](#results-on-the-mock-set)
- [Results on real logs](#results-on-real-logs)
- [Token limits, measured](#token-limits-measured)
- [Cost and time](#cost-and-time)
- [How to use it](#how-to-use-it)
- [What it gets wrong](#what-it-gets-wrong)
- [Files](#files)

## Disclaimer

Research proof of concept, built to test one idea: whether TypeSafe's Jev
can turn a code-computed summary of an IP's requests into a useful triage
category. It produces a category, a severity and evidence; it does not
produce incident findings. `malicious` means "read these requests", not
"block this address"; `benign_user` means "nothing stood out", not
"verified human". Verify against the raw log before acting. Provided as is,
without warranty. Everything in `mock-data/` is fictional.

## How this is different

| Approach | What it is | The problem |
|---|---|---|
| **Reading the log** | Sort by IP, eyeball the paths | Works, does not scale past a few hundred IPs a day, and every reader has a different threshold for "that looks bad". |
| **WAF verdicts** | Trust `deny` / `throttle` | The WAF only sees what its rules name. It says nothing about enumeration, slow recon, spoofed crawlers, or the 95% of traffic it allowed. |
| **A rule engine** | Regexes for scanner UAs and probe paths, thresholds on 404 rate and req/min | This skill has all of that in `signals.py` and `profile.py`. What rules cannot do is say whether a path set "knows this app", whether a User-Agent is plausible, or whether a pattern reads as a monitor. |
| **Asking an LLM** | Paste the log slice into a chat model | Expensive per IP, slow, non-deterministic, and a User-Agent string can argue with it. |
| **Asking Jev (this skill)** | Code computes the profile; Jev answers twelve typed questions about it in one call | Calibrated numbers, 330 ms, a fraction of a cent, same profile same answer. The judgments are narrow; the numbers stay in code. |

**You need a TypeSafe account.** Sign up at [typesafe.ai](https://typesafe.ai),
then create an API key at [console.typesafe.ai/keys](https://console.typesafe.ai/keys).

## What it does

1. **Validate** the staged events against the schema: required fields,
   types, IP syntax, timestamp formats, WAF-action aliases. Prints drop
   reasons and a coverage table of the optional fields.
2. **Profile** each IP in code: request count, span, peak per minute,
   median gap, status mix, 404 rate, WAF verdicts, distinct hosts and paths,
   User-Agent classes, static-asset fraction, referer presence, auth-endpoint
   hits, enumeration templates (path segments and query parameters), probe
   families, payload families, route templates, directory and extension
   rollups, a coverage sentence, and short samples with the sample slots
   spent on paths no rule already described. Every number gets a word
   bucket, because Jev judges words better than magnitudes.
3. **Classify** with one Jev request per IP: a category choice, ten yes/no
   signals, a 0-3 severity. Code raises the category where it is certain and
   never lowers it.
4. **Report** to `results.xlsx` / `.csv` / `.json`, attention rows first,
   with agreement metrics when labels are given.

## The contract: you retrieve, it classifies

The skill does not pull logs and does not say how to. The calling agent
works that out with the user (a cloud CLI, an MCP server, Athena, a SIEM
export, a file) and writes one JSON line per request in the schema in
[`references/schema.md`](references/schema.md). Four fields are required
(`ts`, `ip`, `method`, `path`); status, host, query, User-Agent, referer,
WAF action, rule and labels, ASN, country, JA3/JA4, sizes, latency and
target add signals. A WAF-only export with no response status is fine;
the profile says what it cannot see and the verdicts, labels, paths and
pacing carry the judgment. The schema page carries a field-source table for GCLB, ALB and AWS
WAF. The agent also writes one paragraph about the site, which is what
"knows this application" is judged against.

## The categories

| Category | Means | Typical evidence |
|---|---|---|
| `benign_user` | A person in a browser or the product's own client | Browser UA, page loads with assets and referers, human pacing, 2xx |
| `benign_bot` | Well-behaved automation | One consistent named UA, fixed paths at a fixed interval, or a customer's script hitting entitled routes with 2xx |
| `ai_agent` | AI assistant, LLM crawler or agent | GPTBot, ClaudeBot, Claude-User, ChatGPT-User, PerplexityBot, an MCP client, a headless browsing agent |
| `background_scan` | Internet background noise | Probes for absent software, raw-IP host, mass exploit sprays; no knowledge of this app's hosts, routes or parameters |
| `malicious` | Malicious scanning or attack on this app | Payloads against real routes, credential attempts on real auth endpoints, enumeration of real ids, recon of real routes, identity-rotating campaigns |
| `unclear` | Not enough evidence | 1-2 ordinary requests, or a spread distribution |

The line between `background_scan` and `malicious` is knowledge of this
application. Both can carry exploit strings; only one knows where it is.
Severity carries the rest, and **attention** (the `!!` rows) is severity 2+
with confidence or a code floor firing.

## Results on the mock set

3,689 requests, 33 labelled IPs, one synthetic day. Personas cover, inside
`malicious`: SQL injection, XSS, path traversal, SSRF, JNDI/log4shell,
command injection, template injection, insecure deserialization, credential
stuffing, OAuth client-registration abuse, tenant enumeration (IDOR), a
nuclei run against the real API, and slow low-and-slow recon. Hard
negatives: a curious `/admin` click, a typo 404, a curl user reading
`security.txt`, a sign-in with an MFA retry, a customer's cron script.

| | |
|---|---|
| Malicious IPs given attention | 9 of 9 |
| Benign IPs given attention | 0 |
| Exact category agreement | 0.94-0.97 across runs (the curl user sits on the benign_user / benign_bot line) |
| Disagreements | curl user -> `benign_bot`; one-request IP -> `unclear` (label says `unclear`, counted as a hit) |

## Results on real logs

Two days of GCP HTTP(S) load balancer request logs from three projects,
~42,000 requests, ~1,900 IPs, September 2026. What the first pass got wrong
and what changed is in [`references/methodology.md`](references/methodology.md);
the short version:

- The operator's own IP was flagged (an app route matched an admin-panel
  regex; cache-busters looked like enumeration). Fixed in the regexes.
- WordPress scanners read as a credential attack because `wp-login.php`
  404s counted as auth hits. Fixed: auth hits exclude 404s, and the
  credential floor requires app-awareness.
- A six-IP campaign rotated through 33 User-Agents, 21 of them spoofed AI
  crawler names. New code signal `ua_spoofed_bots`; the bot questions now
  say rotation means fake.
- Mass exploit sprays at the raw LB IP came out as attacks at nuisance
  severity. The category criteria now hinge on app knowledge; attention
  hinges on severity.

After the changes, one project's attention list is exactly that campaign,
one project has a single "check that `/.git/config` 200 is the SPA shell"
row, and one has nothing.

## Token limits, measured

`scripts/limits.py` grows one IP's profile until Jev refuses it and records
what moves.

| | |
|---|---|
| Hard limit | 32,653 total input tokens accepted; ~40k refused with `HTTP 400 max_tokens_exceeded` |
| Fixed overhead | ~3,500 tokens: the app paragraph plus the 12 questions |
| Usable profile | up to ~28k tokens; default budget 6k; real profiles 500-3,500 |
| Drift with size | none in category or severity from 4k to 32k; one signal moved 0.2 |
| Tokenizer | profile JSON runs 1.5-2.9 chars/token; the estimator assumes 1.5 |

Raw log volume never reaches the API: a million rows is a local CPU cost.

## Cost and time

| | |
|---|---|
| Tokens per IP | ~3,400 median, ~7,100 max on real logs |
| Cost | ~$0.14 per 1,000 IPs at $0.042/Mtok; output tokens free |
| Latency | ~330 ms median per IP; 8 workers clear 600 IPs in about 30 s |

## How to use it

```bash
# 1. stage events.jsonl (schema in references/schema.md) and app.md
# 2. validate
python3 scripts/validate.py --events events.jsonl
# 3. dry run: profiles + token estimates, no API calls
python3 scripts/evaluate.py --events events.jsonl --app app.md --dry-run
# 4. run; --ip / --from / --to / --min-requests / --labels / --workers as needed
python3 scripts/evaluate.py --events events.jsonl --app app.md --out ./out
# one IP, full detail
python3 scripts/classify.py --events events.jsonl --ip 1.2.3.4 --app app.md
# measure the size limit on your own data
python3 scripts/limits.py --events events.jsonl --app app.md
```

## What it gets wrong

- No reverse-DNS check: a UA claiming Googlebot is believed unless the IP
  rotates identities.
- Behind SPA fallbacks a 200 on `/.git/config` is the shell, not the file;
  the `app` paragraph has to say so and Jev may still flag it.
- One IP is one actor: NAT and CDN origins merge many.
- The regexes are lists; a new scanner is invisible until added.
- Jev can be steered by crafted state; the code floors keep a payload on a
  real route malicious whatever the UA says.

## Files

| File | What it is |
|---|---|
| `SKILL.md` | Agent instructions |
| `references/schema.md` | The event schema: the contract with whoever retrieves the logs |
| `references/methodology.md` | Design, categories, validation history, measured limits |
| `scripts/schema.py` | Field definitions and row normalization |
| `scripts/validate.py` | File reader, filters, coverage report |
| `scripts/signals.py` | Every regex: UA classes, probe families, payload families |
| `scripts/profile.py` | Per-IP aggregation and token-budget trimming |
| `scripts/questions.py` | Categories, Jev questions, thresholds, rules |
| `scripts/classify.py` | One IP through Jev, verdict composition |
| `scripts/evaluate.py` | The run: validate, profile, classify, report |
| `scripts/report.py` | xlsx / csv / json writer |
| `scripts/limits.py` | Grows a profile until Jev refuses it; records drift |
| `scripts/jev.py`, `scripts/bootstrap.py` | HTTP client with backoff; venv bootstrap |
| `mock-data/` | `generate.py`, `events.jsonl`, `labels.csv`, `app.md`, `example-output/` |
