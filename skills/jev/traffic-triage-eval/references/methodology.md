# Methodology

## The split: code counts, Jev judges

TypeSafe's Jev returns calibrated answers to typed questions about a JSON
state. Its documented weak spots (docs.typesafe.ai/model-jaggedness) are
counting, arithmetic, dates as ordered quantities, and large states full of
unrelated detail. Edge logs are nothing but counts, timestamps and unrelated
detail, so the design is:

1. **`profile.py`** reduces every request from one IP to a profile: request
   count, time span, peak per minute, median gap, status mix, 404 rate, WAF
   verdicts, distinct hosts and paths, User-Agent classes, static-asset
   fraction, referer presence, auth-endpoint hits, enumeration templates,
   probe-family hits, payload-family hits, and short samples of the paths,
   error paths, payloads and queries. Every number is accompanied by a word
   bucket ("hundreds of requests over about 3 hours, in aggressive bursts",
   "mostly not-found") because Jev judges words better than magnitudes.
2. **`signals.py`** holds the regexes: User-Agent classes (scanner, AI agent,
   monitor, crawler, script, headless, browser), probe path families
   (WordPress, PHP admin, env files, backups, Java consoles, cloud metadata,
   admin panels, shells, other CMSs), payload families (traversal, SQLi, XSS,
   command, template, JNDI, SSRF, deserialization, encoding tricks, scanner
   callback markers), auth and health path shapes, and cache-buster query
   keys. Their hits become named facts in the profile, so Jev never has to
   spot a string.
3. **`questions.py`** asks Jev one Choice (the category), ten Nouls (generic
   probing, app-aware, exploit payloads, credential attack, enumeration,
   automated, declared bot, AI-operated, monitoring, wrong host, scanner
   tool) and one Score (threat severity 0-3), all over the same state in one
   request. The state is `{"app": ..., "window": ..., "profile": ...}`.
4. **`classify.py`** composes the verdict. The category is Jev's choice,
   raised (never lowered) by floors where code is certain: exploit payloads
   or WAF attack-signature labels plus app-awareness, credential-attack
   volume with WAF evidence plus app-awareness, scanner or wrong-host
   evidence with no app-awareness. A choice under the confidence gate
   becomes `unclear`, unless the probability is merely split between
   `benign_user` and `benign_bot` (harmless either way, the top one stands);
   fewer than three requests with no code signal becomes `unclear`. **Attention** (the rows a
   person reads first) is severity >= 2 with confidence, or an attack floor
   firing.

## Path consolidation: what Jev sees when an IP has 500 paths

A top-N list by frequency is a window, not the picture: on real scanner
IPs the 30 most-requested paths cover 8-24% of requests, and id-templating
does not help because a scanner wordlist is 500 distinct paths by nature.
So `profile.paths` carries five layers, and the sample budget goes to
whatever code has not already summarized:

| Layer | Field | What it shows |
|---|---|---|
| Families | `probes.families`, `payloads.families` | Requests by meaning: `env_files=305, java_actuator=31`. Covers most scanner traffic. |
| Templates | `paths.templates` | Ids, UUIDs, hex and asset hashes collapsed to `{n}`, `{uuid}`, `{hex}`, `{hash}`. Only emitted when it actually compresses (an application's routes do, a wordlist does not); its absence is itself reported as "the shape of a wordlist". |
| Directories | `paths.directories` | Prefix rollup at depth 3 with request and distinct-leaf counts, for directories holding 3+ paths: `/api/v1/tenants/*: 349 requests, 83 paths`, `/assets/assets/*: 154 requests, 121 paths`. |
| Extensions | `paths.extensions` | `.env 325, .js 107, .php 32, (none) 90`. |
| Unmatched sample | `paths.unmatched_sample` | The most-requested paths that no probe, payload, static or health rule describes. The only raw paths worth a sample slot. |

`paths.coverage` is a sentence that tells Jev what the samples do and do
not cover ("563 distinct paths; the 30 in `top` cover about 11%; the rules
describe about 82%; the paths do not roll up into templates"), because Jev
cannot work that out from the numbers itself.

## The categories

| Category | Means | Typical evidence |
|---|---|---|
| `benign_user` | A person in a browser or the product's own client | Browser UA, page loads with assets and referers, human pacing, 2xx |
| `benign_bot` | Well-behaved automation | One consistent named UA, fixed paths at a fixed interval, or a customer's script hitting entitled routes with 2xx |
| `ai_agent` | AI assistant, LLM crawler or agent | GPTBot, ClaudeBot, Claude-User, ChatGPT-User, PerplexityBot, an MCP client, a headless browsing agent |
| `background_scan` | Internet background noise | Probes for absent software, raw-IP host, mass exploit sprays; no knowledge of this app's hosts, routes or parameters |
| `malicious` | Malicious scanning or attack on this app | Payloads against real routes, credential attempts on real auth endpoints, enumeration of real ids, recon of real routes, identity-rotating campaigns across this site's hosts |
| `unclear` | Not enough evidence | 1-2 ordinary requests, or a spread distribution |

The line between `background_scan` and `malicious` is **knowledge of this
application**, and severity carries the rest. A `/cgi-bin/../bin/sh` probe
at the raw LB IP is noise at severity 1; the same payload against
`/api/v1/tenants/acme/documents` on the real hostname is malicious at
severity 3. Both categories can carry exploit strings; only one knows where
it is.

## What was validated (2026-09-19)

**Mock set** (`mock-data/`, 3,689 events, 33 labelled IPs): 9 malicious
personas covering SQLi, XSS, path traversal, SSRF, JNDI/log4shell, command
and template injection, deserialization, credential stuffing, OAuth
client-registration abuse, tenant enumeration (IDOR), a nuclei run against
the real API, and slow low-and-slow recon; 7 background scanners (WordPress,
PHP admin, IoT, backup files, Censys, zgrab, wrong hostname); 5 AI agents
(GPTBot, ClaudeBot, PerplexityBot, an MCP client, a browser-use agent); 7
benign bots; 4 benign users including hard negatives (a curious `/admin`
click, a typo 404, a curl user reading `security.txt`, a sign-in with an MFA
retry); 1 unclear. Result: **9/9 malicious given attention, 0 benign
flagged, 94% exact category agreement.** The two disagreements are the curl
user (`benign_bot`, arguably right) and a Jev `benign_bot` for a customer
cron script that was relabelled to match, since an unattended script is a
bot.

**Real logs**, two days of GCLB request logs from three GCP projects
(~42,000 requests, ~1,900 IPs). Findings that changed the code:

- The operator's own IP was flagged because `/api/v1/.../dashboard` matched
  an `admin_panels` regex 1,077 times and `?cb=` cache-busters looked like
  enumeration. Fix: admin-panel patterns anchored at the path root;
  cache-buster keys excluded from enumeration.
- WordPress scanners were raised to a credential attack because `wp-login.php`
  and 404s on `/login`, `/register`, `/signup` counted as auth-endpoint
  requests. Fix: auth hits exclude 404/405; the credential floor requires
  app-awareness.
- A five-IP scanning campaign on one project rotated through 33 User-Agents,
  21 of them spoofed AI-crawler identities (Amazonbot, cohere-ai,
  DuckAssistBot, OAI-SearchBot, CCBot, Google-Extended). Fix: the
  `ua_spoofed_bots` code signal (5+ distinct named-bot UAs from one IP), and
  the `declared_bot` / `ai_operated` criteria now say rotation means fake.
- Mass exploit sprays at the raw LB IP (the CVE-2021-41773 `cgi-bin` probe,
  `.aws/credentials`, `.anthropic/config.json`) were all coming out as
  `targeted_attack` at severity ~1.0 once payloads were in the criteria. Fix:
  the category was renamed `malicious`, "knows this application" became the
  dividing line in the criteria, and attention became severity-driven.
- Static buckets return 200 with the SPA shell for any path, so a 200 on
  `/.git/config` means nothing there; the `app` paragraph has to say so. It
  still produced one attention row (2 requests, severity 2.2), which is a
  reasonable "go check" rather than a false alarm.

After those changes: one project flagged the six-IP campaign and nothing
else, one flagged the `.git/config` pair, one flagged nothing.

## Token limits (measured with `scripts/limits.py`)

| | |
|---|---|
| Hard limit | 32,653 total input tokens accepted; ~40k refused with `HTTP 400 max_tokens_exceeded`. Matches the documented 32k state + longest question. |
| Fixed overhead | ~3,500 tokens per request for the app paragraph plus the 12 questions |
| Profile budget | Up to ~28k tokens possible; default 6k |
| Typical profile | 500-3,500 tokens; ~3,400 total per IP median on real logs, max ~7,100 |
| Drift with size | Category and severity unchanged from 4k to 32k on the probe IP; one Noul moved 0.2 |
| Tokenization | Profile JSON runs 1.5-2.9 chars per token (slashes, hex ids, punctuation); the estimator uses 1.5 |
| Cost | ~$0.14 per 1,000 IPs at $0.042/Mtok; output tokens are free |
| Latency | ~330 ms median per IP; 8 workers clear 600 IPs in about half a minute |

## Sources without a response status

Most WAF logs record the verdict and not the backend's answer, so `status`
is optional. Without it the profile drops the 404 rate and the
"mostly successful / mostly rejected" sentence and says why, `auth` hits
cannot exclude 404s, and the questions that mention response codes are
worded to fall back to volume and WAF verdicts. Tested on a WAF-shaped
copy of the mock set (epoch-millisecond timestamps, AWS action names, no
status, `labels`): the two attackers still get attention, the scanner and
Googlebot land where they did with statuses, and the browser user goes
from a benign_user / benign_bot split to `benign_user`. AWS WAF `labels`
are worth sending: managed rule groups label matches even in COUNT mode,
and the profile turns attack-signature, bot-control and IP-reputation
labels into code signals (`waf_attack_labels`, `waf_reputation_labels`) and
a `labels_summary` sentence.

## Known limits

- **No reverse-DNS or ASN allow-list verification.** A UA that says
  Googlebot is taken at its word unless the IP rotates identities. Adding an
  rDNS check for the big crawlers is the obvious next step.
- **Status is weak behind SPA fallbacks.** Buckets that serve the shell for
  any path make 404-rate meaningless on those hosts; the probe-family
  regexes carry the weight there.
- **One IP is one actor.** NAT, CGNAT and Cloudflare-fronted origins merge
  many actors into one profile; the origin-endpoint IPs should be excluded
  or grouped by a forwarded header the schema does not carry yet.
- **Regexes are lists.** A new scanner UA or probe family is invisible until
  added to `signals.py`; a run's `unclear` and `benign_bot` rows are where to
  look for candidates.
- **Jev can be steered by state.** A UA string or path written to argue for
  its own classification can move an answer; the code floors exist so that a
  payload on a real route is malicious whatever the UA says.
- **English-first, text-only.** Bodies, headers beyond UA/Referer, and
  response content are not in the schema.
