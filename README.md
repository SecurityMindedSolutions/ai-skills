# AI Skills

Skills that let a coding agent do real work: audit a codebase you inherited, clear a
vulnerability backlog, map what a web app is built on, run a long implementation
unattended, say the last message again for a different reader, or use TypeSafe's Jev
to screen resumes against a posting and to gate prompts for injection.

Each skill is a directory holding a `SKILL.md` plus whatever modules, references,
templates or scripts it needs. They are written for [Claude
Code](https://docs.anthropic.com/en/docs/claude-code) and lean on it: the three audits
and the vulnerability remediator dispatch parallel sub-agents, and the audit, remediation,
recon and Ralph skills read their own bundled files from `~/.claude/skills/`. The four
communication skills are plain instructions with no such dependency, and the `jev/`
skills reference their files relative to their own folder, so both groups work in any
agent that follows the [Agent Skills](https://agentskills.io) format (Codex, Cursor,
Cline and others via `npx skills add SecurityMindedSolutions/ai-skills --skill <name>`).

## Skills

Grouped by category, matching the folders under [`skills/`](skills/). Each category
README carries the full detail: usage, options, output format and customization.

<!-- BEGIN SKILL INDEX -->
### Auditing

[`skills/auditing/`](skills/auditing/) - codebase review, one skill per layer. Usage, options and output format in [its README](skills/auditing/README.md).

| Command | What it does |
|---|---|
| [`/audit-security`](skills/auditing/audit-security/) | Finds exploitable vulnerabilities across code, APIs, frontend, tenancy, secrets, dependencies, Terraform and CI/CD |
| [`/audit-frontend`](skills/auditing/audit-frontend/) | Reviews client-side architecture: design tokens, components, accessibility, performance, SEO |
| [`/audit-backend`](skills/auditing/audit-backend/) | Reviews server-side patterns: handler hygiene, service layers, data access, error handling, observability |

### Vulnerability management

[`skills/vulnerability-management/`](skills/vulnerability-management/) - finding and fixing known vulns. Usage, options and output format in [its README](skills/vulnerability-management/README.md).

| Command | What it does |
|---|---|
| [`/github-remediate-vulns`](skills/vulnerability-management/github-remediate-vulns/) | Scans a GitHub org for Dependabot, code scanning and secret scanning alerts, then fixes what it safely can and reports the rest |

### Autonomous development

[`skills/autonomous-development/`](skills/autonomous-development/) - planning and running unattended work. Usage, options and output format in [its README](skills/autonomous-development/README.md).

| Command | What it does |
|---|---|
| [`/ralph-plan`](skills/autonomous-development/ralph-plan/) | Interactive builder for a PRD with checkboxed tasks and acceptance criteria |
| [`/ralph-loop`](skills/autonomous-development/ralph-loop/) | Autonomous runner that works through that PRD one task at a time, no human in the loop |

### Reconnaissance

[`skills/reconnaissance/`](skills/reconnaissance/) - passive recon of a live web app's stack. Usage, options and output format in [its README](skills/reconnaissance/README.md).

| Command | What it does |
|---|---|
| [`/built-with`](skills/reconnaissance/built-with/) | Passive, headless recon of a web app's frontend, mapping its third-party vendors, backend hosts and API surface from public JS into a plain-English dossier |

### Communication

[`skills/communication/`](skills/communication/) - restating what the agent just said, for a different reader. Usage, options and output format in [its README](skills/communication/README.md).

| Command | What it does |
|---|---|
| [`/again`](skills/communication/again/) | Restates the last message in plain English, keeping every path, line number and count exactly as written |
| [`/elim`](skills/communication/elim/) | Restates the last message for a manager: no code names, no shop talk, and no invented urgency |
| [`/ugh`](skills/communication/ugh/) | One breath. Restates the last message as a single sentence, plus a You line only when something actually needs you |
| [`/huh`](skills/communication/huh/) | Now, next, you. Restates the last message as three labelled lines for picking a dropped thread back up |

### Jev

[`skills/jev/`](skills/jev/) - skills built on TypeSafe's Jev, a decision model that answers typed questions about a document with calibrated numbers instead of generating text; code does the math, Jev does the judgment, and the agent does the fetching. Usage, options and output format in [its README](skills/jev/README.md).

| Command | What it does |
|---|---|
| [`/resume-mirror-eval`](skills/jev/resume-mirror-eval/) | Scores a batch of resumes against a job description with TypeSafe Jev plus code-side text statistics, flags the ones a human should read, and writes a sortable spreadsheet with evidence bullets |
| [`/prompt-injection-eval`](skills/jev/prompt-injection-eval/) | Scores prompts for injection with TypeSafe Jev and returns allow / review / block for a backend gate; ships a batch evaluator that measures Jev against a regex list and an LLM judge on labelled prompts |
| [`/traffic-triage-eval`](skills/jev/traffic-triage-eval/) | Triages edge-log traffic per client IP with TypeSafe Jev: benign user / benign bot / AI agent / background scan / malicious, with a 0-100 threat score, the signals and the evidence, from a documented JSON event schema the calling agent fills from any log source |
| [`/code-audit-jev`](skills/jev/code-audit-jev/) | Unit-level security judgment of a repository, a fleet, or the units a pull request changed, with TypeSafe Jev: every function, Terraform block, CI job and Dockerfile judged against 22 rule files (one TOML file per category, add your own) and a severity scale; SARIF for the Security tab and a composite GitHub Action; about a cent per PR, a dollar per 300k lines |
| [`/jev-email-analysis`](skills/jev/jev-email-analysis/) | Classifies what an email is trying to get someone to do with TypeSafe Jev: 16 categories, eight red-flag signals, risk and pressure, and a malicious / suspicious / spam / benign verdict, from one documented schema whose fields are all optional - a screenshot with a subject and body is a valid input |
| [`/run-jev`](skills/jev/run-jev/) | Ad-hoc typed judgments over a list with TypeSafe's Jev - the agent shapes the questions, code runs and reports them, with agreement stats against your own labels. |
<!-- END SKILL INDEX -->

## Install

Skills go in your **personal** skills directory. Most of them resolve their own bundled
files through `~/.claude/skills/<name>/`, so install there rather than into a project's
`.claude/skills/`.

```bash
git clone https://github.com/SecurityMindedSolutions/ai-skills.git
mkdir -p ~/.claude/skills
cp -R ai-skills/skills/auditing/audit-security ~/.claude/skills/
```

The `mkdir -p` matters. Without it, `cp -R` creates a directory named `skills` holding
that one skill's *contents*, and nothing ever loads.

Or symlink, so a `git pull` updates the skill in place:

```bash
mkdir -p ~/.claude/skills
ln -s "$PWD/ai-skills/skills/auditing/audit-security" ~/.claude/skills/audit-security
```

Copy the whole directory, not just its `SKILL.md`: the audit skills keep their checks
in `modules/` and their shared validation method in `references/`, and the Ralph loop
ships `ralph.sh` alongside its templates. The directory name is the command name, so
keep it as it is.

Start a new Claude Code session, then type the command. The category README linked
beside each table above covers that skill's options and output. Three need outside tools:
`/github-remediate-vulns` needs the `gh` CLI, `/built-with` needs Python 3, `curl`
and Chrome, and the two `jev/` skills need Python 3.10+ and a TypeSafe API key.

The `jev/` skills carry a research-only disclaimer. Read
[skills/jev/README.md](skills/jev/README.md) before pointing one at a real applicant.

## License

MIT. See [LICENSE](LICENSE).
