---
name: built-with
description: >-
  Passive, headless recon of a web app's frontend to infer its backend and tech
  stack - API endpoints, third-party vendors, CSP allow-lists, auth provider,
  framework/build tooling, and public config tokens - then produce a
  plain-English vendor dossier (Artifact + landscape PDF). Use this whenever the
  user wants to know what a web app is "built on", "runs on", or "uses under the
  hood", asks you to fingerprint / profile / tear down / map a competitor's or
  vendor's stack, wants to enumerate a site's APIs, endpoints, or third-party
  services from its JavaScript, or asks "what's their backend / what platforms
  do they use" for a URL like app.example.com - even if they don't say
  "recon" or "platform analysis". Everything runs via curl/Python and headless
  Chrome; no browser window opens.
user-invocable: true
allowedTools:
  - Bash
  - Read
  - Write
  - Edit
  - Artifact
---

# Built-With

Map what a web app is built on, using only what it ships to every visitor. The
goal is a dossier a fresh reader can scan: what third parties the app uses, how
sure we are, and what each one is for - each claim backed by a verbatim endpoint,
header, or on-screen string.

This is passive analysis of publicly-served assets and response headers. It does
not authenticate, submit data, or exercise anything behind a login. Say so in the
output. If the user asks to go further (log in, hit authed endpoints), that's a
different, authorized-testing conversation - confirm scope first.

## Workflow

### 1. Extract (the script does the heavy lifting)
Run the analyzer on the target. It fetches the page + headers, recursively
discovers and downloads the JS chunks, and extracts endpoints, hosts, the CSP
allow-lists, vendor signatures, framework/build tooling, and public config
tokens - writing `report.json` + `report.md` to a per-target data folder.

```bash
python3 ~/.claude/skills/built-with/scripts/analyze.py <url>
```

Useful flags: `--no-probe` (skip backend/auth header probes), `--save-raw` (keep
the downloaded JS), `--max-files N` / `--max-mb N` (crawl budget), `--out DIR`.

Output lands in `~/.claude/data/built-with/<host>/<timestamp>/`. The
script prints that path on the last line - read `report.md` from there.

### 2. Read and probe further
Read the generated `report.md`. Then fill gaps with targeted follow-up:
- **Confirm inferred vendors.** If a vendor is flagged by convention (a
  distinctive header, a first-party proxy subdomain, an embedded widget),
  reproduce the call the app makes with `curl` to turn "High" into "Confirmed".
  Don't guess.
- **Follow the auth host.** SPAs often redirect login to a separate host
  (e.g. `auth.<domain>`, or a hosted auth provider). Vendors wired in on the auth
  host won't appear in the main app's bundle - analyze that host too if the stack
  matters.
- **Grep the raw bundle** (with `--save-raw`) for exact UI strings to quote as
  proof, and for how a vendor is actually used (which endpoint its ID rides on).

### 3. Categorize and write the dossier
Sort every vendor into one of three uses and assign a confidence level, then
author a spec JSON (vendor rows grouped by use, plus notes) and build the dossier
with the generator, which reuses the styled shell + all print fixes from
`assets/template.html`. The spec fields are documented at the top of
`scripts/build_dossier.py`:

```bash
python3 ~/.claude/skills/built-with/scripts/build_dossier.py <spec.json> <dossier.html> <report.json>
```

Passing the run's `report.json` as the third argument auto-appends two appendix
sections after your notes: **Domains & assets** (the target's own subdomains -
often a map of its internal services - plus the external hosts it talks to) and
**API surface** (endpoints rendered as a collapsed path tree). Both are
alphabetized. The dossier header leads with the domain itself as the visual hero.

**Per-host split + base-URL alias resolution.** Endpoints are attributed to the
host that serves them, using only the already-downloaded JS (no probing). Modern
apps hide their API hosts behind a named base - a variable or function bound to a
subdomain URL (often `env.X || "https://svc.example.com"`), then used as
`${base()}/path`, `${base}/path`, or `base()+"/path"`. The analyzer resolves that
generically in two passes (build a name→host map, then attribute each appended
path back to its host), so a subdomain like `api.example.com` gets its own
real route tree under `API surface — {host}`, not just a name. It generalizes
across styles (some apps bind the base with a function, others with a plain
variable) rather than matching any one app. Hosts we resolved endpoints for are
marked `*` in Domains & assets; the app you analyzed leads the API surface,
subdomains follow.

**No truncation.** JS files are downloaded in full - alias→host maps frequently
live deep inside a single multi-megabyte chunk, and cutting it off loses the
attribution. Large apps therefore take longer to analyze (tens of seconds to a
minute-plus); that's expected, not a hang.

`--api-depth N` (default 3) controls how many path levels the API tree expands.
Depth 3 gives one row per resource (e.g. `/api/v1/orders`, `/users`,
`/products`) with a route count and a trailing `/…` where more sits below -
compact, roughly a page. Bump to 4+ for per-action granularity (e.g.
`/api/v1/orders/{id}/cancel`) when the extra pages are worth it. Variable path segments are collapsed to `{id}` so repeated shapes merge into
one inferred route.

**Read `references/design-notes.md` first**: it carries the four-column layout,
the confidence levels, the category definitions, the quote-vs-analysis
provenance rule, and the landscape-print requirements.

**Do not add any author/consultancy branding** - no "prepared by", no company
name, no external links - unless the user explicitly asks. This runs on
arbitrary sites (a competitor, your own app, a company you're curious about);
auto-stamping a firm name onto someone else's teardown is wrong. The generator
omits all of it by default.

A firm that *does* want its own default author/footer on every dossier can drop
a `branding.json` at the skill root (`{"prepared_by": "...", "footer_links":
[["Terms","url"], ...]}`); the generator picks it up automatically, and a spec
can still override per-run. Shipped/shared copies of the skill omit this file,
so they stay unbranded.

### 4. Default output: PDF into the data folder, then offer an artifact
Render the PDF straight into the run's data folder (next to `report.json`), and
relay the on-screen TLDR the analyzer already printed:

```bash
bash ~/.claude/skills/built-with/scripts/render_pdf.sh <dossier.html> \
  ~/.claude/data/built-with/<host>/<timestamp>/dossier.pdf
```

Then **ask the user** whether they'd also like it (a) published as a private
claude.ai Artifact (nice on screen, shareable link), and/or (b) copied to the
Desktop to email. Don't publish an artifact or write to the Desktop unprompted -
these are one-off runs and the user picks the destination.

### Diffing against the last run
The analyzer automatically compares each run to the previous run for the same
host and reports what vendors, endpoints, hosts, or config tokens were **added or
removed** - in the TLDR and in a "Changes since last run" section of the report.
This is the intended way to answer "what changed since I last looked at them?"
without any scheduling; just run it again whenever you want a fresh comparison.

## What the extractor catches (and doesn't)

Strong signals, in rough order of reliability:
- **Response headers + CSP.** The CSP `connect-src` / `frame-src` / `img-src`
  allow-lists are the single richest map of the stack - every backend, storage
  bucket, and embedded widget the app is allowed to talk to. `server` /
  `x-vercel-id` / `x-powered-by` reveal hosting.
- **Vendor signatures** matched across the bundle + hosts + CSP.
- **API endpoints** expressed as `/api/...`, `/v1/...`, `/graphql`, etc.
- **Public config tokens** - Sentry DSN, WorkOS `client_id`, Fingerprint public
  key, `VITE_*` / `NEXT_PUBLIC_*` names, GA/GTM ids. These are browser-exposed by
  design; report them. Never hunt for server-side secrets.

Known blind spots - call these out rather than pretending coverage:
- **Auth-gated SPAs.** If the app only ships a login shell pre-auth and loads its
  real bundle after sign-in, endpoint extraction will be thin. That's expected,
  and a finding in itself: they don't leak their API surface pre-auth. Note it;
  don't try to defeat the gate.
- **Configured base URLs.** Apps that call a separate API host via an axios
  `baseURL` may express routes as bare paths (`/tenants/...`) without an `/api`
  prefix; some won't be captured. Grep the raw bundle if the API surface matters.
- **Cross-subdomain vendors.** Something wired into `auth.<domain>` won't show in
  the main app scope - analyze that host separately.

## Notes on tone and accuracy
- Quote the target's own strings verbatim; never paraphrase inside quotation
  marks. Keep your interpretation in the "what it's for" column only.
- Don't inflate counts: providers reached through one aggregator (e.g. several
  ATSes behind a single unified-API vendor) are one dependency, not many.
- Flag anything a security reviewer would want (e.g. Sentry `sendDefaultPii:true`,
  PII in error reports) as a side note.
