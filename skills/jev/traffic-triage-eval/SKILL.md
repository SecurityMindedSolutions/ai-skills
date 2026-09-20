---
name: traffic-triage-eval
description: >-
  Classify the traffic behind each client IP in edge logs (GCP load balancer,
  AWS ALB, AWS WAF, CloudFront, nginx, anything) as benign user, benign bot,
  AI agent, internet background scanning, or malicious scanning and attack,
  using TypeSafe's Jev on a code-computed per-IP profile. The calling agent
  retrieves the logs however it can and writes them in one documented JSON
  schema; this skill validates them, profiles every IP in code, asks Jev a
  fixed set of questions, and writes a spreadsheet sorted attention-first.
  Takes a set of IPs or a time window. Use whenever the user wants to know
  whether traffic from an IP or a period was an attack, a scanner, a bot or a
  person, wants to triage WAF or load balancer logs, or asks "who was hitting
  us last night" - even if they do not say "TypeSafe" or "Jev". Research
  proof of concept; a triage signal, not an incident finding.
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
metadata:
  summary: "Triages edge-log traffic per client IP with TypeSafe Jev: benign user / benign bot / AI agent / background scan / malicious, with a 0-100 threat score, the signals and the evidence, from a documented JSON event schema the calling agent fills from any log source"
---

# Traffic Triage Eval

> **Research proof of concept.** This skill reduces each IP's requests to a
> profile in code and asks TypeSafe's Jev what the pattern means. It is a
> triage signal for a person, not an incident finding: `malicious` means
> "read these requests", not "block this address", and `benign_user` means
> "nothing stood out", not "verified human". Verify against the raw log
> before acting. Repeat the short form of this at the end of every run.

## What it does

1. **Validate.** `scripts/validate.py` reads the events you staged (JSONL,
   JSON array or CSV in the schema in `references/schema.md`), drops rows
   that fail a required field with a reason you can act on, applies the IP
   or time-window filter, and prints which optional fields are populated so
   you know which signals the run has.
2. **Profile.** `scripts/profile.py` groups by IP and computes everything
   numeric and temporal in code: counts, span, peak per minute, status mix,
   WAF verdicts, hosts, User-Agent classes, probe-path families, payload
   families, enumeration and route templates, directory and extension
   rollups, a coverage sentence, and short samples spent on the paths no
   rule described. Jev does not count and reads dates as text, so nothing
   numeric is left for it to do.
3. **Classify.** `scripts/classify.py` sends each profile with a paragraph
   about the site (`app`) to Jev in one request: a category choice, ten
   yes/no signals and a four-level threat rating. Code turns the answers
   into a 0-100 threat score with a band (Benign / Nuisance / Concerning /
   Attack), and raises the category where it is certain (payloads on real
   routes, credential volume with WAF evidence, scanner evidence with no
   app knowledge), never lowering it. About 3,500 tokens, 15 cents per
   thousand IPs, 340 ms median.
4. **Report and carve out.** `scripts/evaluate.py` runs all of it, prints
   two tables (category counts; the attention and malicious rows with
   their evidence), writes `results.xlsx` (Results, Details, Summary, Read
   me) plus CSV and JSON, one row per IP, attention rows first, and writes
   the **raw rows of every IP that is malicious, unclear or flagged** to
   `out/investigate/<ip>.jsonl` with an index `README.md`, so the
   investigation starts from the run directory and never re-queries the
   log source. With `--labels` it also scores agreement per category.
5. **Explain.** You, the agent, read the attention rows and tell the user
   what each flagged IP did, in plain words, with the paths.

Every question, category, threshold and rule lives in `scripts/questions.py`.
Every regex lives in `scripts/signals.py`.

## Workflow

`SKILL_DIR` means the folder containing this SKILL.md.

### 1. Understand what the user wants

- **"What was this IP doing?"** or **"Who was hitting us between X and Y?"**:
  they will name IPs or a window. Retrieval scope follows from that.
- **"Triage our WAF / LB logs"**: a window, usually the last day or week.
- **"Is this scanning or an attack?"**: same run; the answer is in the
  category, score and evidence columns.

Ask for the window or IPs if neither is given. Ask which hosts are theirs if
the site has several.

### 2. Get the events into the schema

**This skill does not retrieve logs and does not dictate how.** Work out
with the user how to pull them: a cloud CLI, an MCP server, Athena, a SIEM
export, a log sink, a file they already have. Whatever the source, map each
request to one JSON line in the schema in `references/schema.md` (four
required fields: `ts`, `ip`, `method`, `path`; `status` and the rest add
signals, and a WAF log without statuses is fine) and write the file into a staging folder (your scratchpad, or
`$TMPDIR/traffic-triage-eval/<timestamp>/`), never into the user's working
tree. The schema page has a field-source table for GCLB, ALB and AWS WAF to
speed up the mapping. If you pull only a window, pull the whole window for
every IP; a profile built from a slice of an IP's traffic is a slice.

If the source fronts the origin with a CDN, the client IP is the CDN's; drop
those rows or expect one profile per CDN node.

Also write `app.md`: one paragraph on what the site is, which hostnames are
its own, what its real route families are (API prefixes, page paths, the
query parameters that matter), what health checks and schedulers it runs,
and what it does **not** run (WordPress, PHP, Java, a CMS, `/admin`). Say
if static buckets return 200 with the SPA shell for unknown paths. This is
the `app` field Jev judges against; the difference between "background
noise" and "malicious" is whether the traffic knows this application, and
Jev only knows the application from this paragraph.

### 3. Check prerequisites

```bash
python3 --version   # 3.10 or newer
test -n "$TYPESAFE_API_KEY" || test -f ~/.config/typesafe/env || echo "need a TypeSafe key"
```

Nothing to install. First run creates a private venv under the system temp
dir for the one dependency (openpyxl). `uv run` works too. Key resolution:
`TYPESAFE_API_KEY` in the environment, else `~/.config/typesafe/env`. Keys
come from https://console.typesafe.ai/keys; if the user has none, stop and
ask.

### 4. Validate, then dry-run, then run

```bash
python3 "$SKILL_DIR/scripts/validate.py" --events "$STAGING/events.jsonl"
```

Read the drop reasons and the coverage table. If `ua`, `host` or `query` is
near 0%, fix the mapping before spending Jev calls; those carry most of the
signal. Then:

```bash
python3 "$SKILL_DIR/scripts/evaluate.py" \
  --events "$STAGING/events.jsonl" --app "$STAGING/app.md" \
  --out "$STAGING/out" --dry-run
```

prints every IP with its code signals and token estimate and writes
`profiles.json`, with no API calls. Then the real run, with `--ip A --ip B`
to limit to named IPs, `--from` / `--to` (ISO 8601) for a window inside the
file, `--min-requests N` to skip one-hit IPs, `--labels labels.csv` (columns
`ip,label`) for agreement scoring, `--workers 8` for speed:

```bash
python3 "$SKILL_DIR/scripts/evaluate.py" \
  --events "$STAGING/events.jsonl" --app "$STAGING/app.md" --out "$STAGING/out"
```

The run prints a category-count table, a table of the attention and
malicious rows (IP, category, score, band, attention, hosts, signals,
code signals, top paths, raw file), the token / cost / latency line, and the agreement table if
labelled. `--verbose` adds one line per IP. `--carve` (default
`malicious,unclear,attention`; `none` to disable) chooses which verdicts
get their raw rows written to `out/investigate/`.

To debug one IP, `python3 "$SKILL_DIR/scripts/classify.py" --events
clean.jsonl --ip 1.2.3.4 --app app.md` prints the exact profile Jev saw and
every answer.

### 5. Report back, as tables

1. **The summary table** the run printed (one row per run; if several
   sources or projects were run, one row each in one table): window,
   requests, IPs, count per category, attention, carved out.
2. **The attention table**: every attention and malicious row with IP,
   category, score, band, requests, hosts, signals, code signals, top paths,
   and the `investigate/<ip>.jsonl` file. Under it, two or three sentences
   per attention row: what the IP asked for, how fast, what came back,
   what the WAF did, why it was flagged, and what to check in the raw
   file. Name the paths.
3. Anything notable outside those rows: a scanning campaign in the
   Nuisance band, a burst of AI agents, a customer's script that looks like a
   bot, an IP that is the user's own, a CDN edge standing in for many
   clients.
4. Tokens, cost and latency in one line; where the spreadsheet and the
   `investigate/` folder are; the offer to delete the staged events.
5. The disclaimer, in two sentences: research proof of concept; triage
   signal, verify in the raw file before acting.

The `investigate/` folder is the hand-off: whoever looks next (a person,
another agent, a later session) opens `investigate/README.md` and the
per-IP JSONL, and does not need the log source again.

If the user then wants to tune it, `scripts/questions.py` is the whole
policy and `scripts/signals.py` the whole pattern list; a labelled
`labels.csv` of their own IPs plus `--labels` measures every change.

## Reading the output

| Column | Meaning |
|---|---|
| Attention | `YES` when the score is 50+ and the category is not a benign one, or an attack floor fired. Start here. |
| Category | `benign_user`, `benign_bot`, `ai_agent`, `background_scan`, `malicious`, `unclear`. Jev's choice, raised by code rules. |
| Score (0-100) | Threat score computed in code from Jev's answers (weights in `questions.py`). Ranks rows. |
| Band | 0-24 Benign, 25-49 Nuisance, 50-74 Concerning, 75-100 Attack. Derived from the score. |
| Confidence | Jev's confidence in the category choice. Under 0.45 the category is `unclear`. |
| Signals (Jev) | Yes/no questions at 0.5 or above, strongest first. |
| Code signals | Facts regex and counting established before Jev was asked: scanner UA, probe families, payload families, WAF denials, spoofed bot identities, bursts. |
| Sample paths | The most-requested paths with their usual status. |

The Details sheet has every probability, the category distribution, rule
reasons, tokens and latency per IP.

## Mock data

`mock-data/` holds `app.md` for a fictional trust-center SaaS,
`generate.py` which writes `events.jsonl` (3,689 requests, one day) and
`labels.csv` (33 IPs: 9 malicious covering SQLi, XSS, traversal, SSRF,
JNDI, command and template injection, deserialization, credential stuffing,
OAuth registration abuse, tenant enumeration, a nuclei run and slow recon;
7 background scanners; 5 AI agents; 7 benign bots; 4 benign users with hard
negatives; 1 unclear), and `example-output/` with a finished run. To demo
or regression-test:

```bash
cd "$SKILL_DIR/mock-data"
python3 ../scripts/evaluate.py --events events.jsonl --app app.md --labels labels.csv
```

Expected: all 9 malicious IPs get attention, no benign IP does, and exact
agreement is 0.94-0.97 (the curl-user hard negative sits on the benign_user / benign_bot line).

## Technical details

**Dependencies.** Python 3.10+. One pure-Python package (openpyxl, for the
.xlsx) which `scripts/bootstrap.py` installs into a private venv under the
system temp dir on first run; without it the script writes CSV and JSON.
The TypeSafe call is plain `urllib` with backoff on 429/529/5xx.

**Limits.** Measured with `scripts/limits.py` on 2026-09-19: Jev accepts
32,653 total input tokens and refuses ~40k with `max_tokens_exceeded`; the
app paragraph and questions cost ~3,500 of that, so a profile may reach
~28k. Category and threat rating did not move between 4k and 32k. The default
profile budget is 6k tokens and real profiles run 500-2,000; sample lists
are halved until a profile fits. Full numbers and the validation history
are in `references/methodology.md`.

**Data handling.** Profiles (not raw rows) go to `api.typesafe.ai`; a
profile carries the IP, up to ~30 paths, query samples, User-Agents and
hostnames. Outputs default to `<system temp>/traffic-triage-eval/<timestamp>/`.
`results.json` contains every profile sent.

**Why Jev and not a rule engine or an LLM.** The rules are in the skill;
they make the profile. What they cannot do is say whether a set of paths
"looks like it knows this app", whether a User-Agent is plausible, or
whether a pattern reads as a monitor: those are judgments, and Jev returns
them calibrated in 330 ms for a fraction of a cent, cheap enough to run on
every IP every day. A generative model could write the explanation but
costs more per IP than the whole run and can be argued with by a
well-chosen User-Agent string. Jev only answers the typed questions.
