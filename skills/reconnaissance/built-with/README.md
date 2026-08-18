# Built-With Skill

Passive, headless recon of a web app's frontend to infer what it's built on -
then a plain-English vendor dossier a non-engineer can read.

Point it at a URL (`app.example.com`) and it fetches only what the site already
ships to every visitor - the HTML, response headers, and JavaScript bundles - to
map the third-party services, backend hosts, and API surface behind the app. It
never authenticates, submits data, or touches anything behind a login.

## What it does

| Stage | Output |
|---|---|
| **Extract** | Downloads the page + JS (in full, no truncation) and pulls out API endpoints, referenced hosts, the CSP allow-lists, vendor signatures, framework/build tooling, and public config tokens (Sentry DSN, analytics IDs, etc.) into `report.json` + `report.md` |
| **Attribute** | Resolves base-URL aliases - a variable or function bound to a subdomain URL, then used with a path - so each API host gets its **own** real route tree, not just a name |
| **Categorize** | Sorts every vendor into one of three uses: customer-connected, behind-the-scenes, or internal, each with a confidence level and verbatim proof |
| **Report** | Renders a landscape-PDF dossier (and optional shareable artifact): a 4-column vendor map, a subdomain/asset enumeration, and a per-host API-surface tree |

## Usage

```
/built-with app.example.com          # analyze a site and produce a dossier
```

Under the hood the skill runs three scripts (details in `SKILL.md`):

```bash
# 1. recon -> report.json + report.md, prints a TLDR, diffs against the last run
python3 scripts/analyze.py <url>

# 2. build the dossier HTML from a spec + the report (adds the API-surface appendix)
python3 scripts/build_dossier.py <spec.json> <dossier.html> <report.json> [--api-depth N]

# 3. render a landscape PDF (headless Chrome, no window)
bash scripts/render_pdf.sh <dossier.html> <output.pdf>
```

Output is written to `~/.claude/data/built-with/<host>/<timestamp>/`.

## What it catches (and what it doesn't)

Strong signals, most reliable first:

- **Response headers + CSP** - the `connect-src` / `frame-src` / `img-src`
  allow-lists are the richest map of the stack: every backend, storage bucket,
  and embedded widget the app is allowed to talk to.
- **Vendor signatures** matched across the bundle, hosts, and CSP.
- **API endpoints**, split by the host that serves them and rendered as a
  collapsed path tree with variable segments folded to `{id}`.
- **Public config tokens** - browser-exposed by design (Sentry DSN, analytics
  IDs, auth client IDs). It never hunts for server-side secrets.

Known limits, called out in the dossier rather than papered over:

- **Auth-gated apps** that ship only a login shell pre-auth yield a thin API
  surface - which is itself a finding, not a miss.
- **Runtime-configured hosts** (a base URL injected at runtime with no literal in
  the bundle) are named but not enumerated - no invented routes.
- **Cross-subdomain vendors** wired into a separate auth host won't appear in the
  main bundle; analyze that host separately if it matters.

## Design notes

- **No probing.** Everything comes from assets the site already serves publicly.
  Confirming an inferred vendor or going behind a login is a separate,
  authorized-testing conversation.
- **Honest attribution.** A host is only shown as having an API surface when real
  paths for it are present in the JavaScript.
- **Unbranded by default.** Dossiers carry no author or consultancy branding. A
  firm that wants its own default header/footer can add a `branding.json` at the
  skill root (see `SKILL.md`); it is never committed here.

## Requirements

- Python 3 (standard library only - no pip install)
- `curl`
- Google Chrome (or Chromium) for PDF rendering, on macOS at the default
  `/Applications` path

## File structure

```
built-with/
├── SKILL.md                     workflow + guidance
├── scripts/
│   ├── analyze.py               headless recon -> report.json + report.md
│   ├── build_dossier.py         report + spec -> dossier HTML
│   └── render_pdf.sh            dossier HTML -> landscape PDF
├── assets/
│   └── template.html            styled shell (fonts, palette, print rules)
└── references/
    └── design-notes.md          dossier layout, confidence levels, print rules
```
