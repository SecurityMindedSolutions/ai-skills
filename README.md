# AI Skills

Skills that let a coding agent do real work on a codebase: audit one you inherited,
clear a vulnerability backlog, take a long implementation and run it unattended, or
say what it found in language the reader can actually use.

Each skill is a directory holding a `SKILL.md` and whatever modules, templates or
scripts it needs. They are written for [Claude
Code](https://docs.anthropic.com/en/docs/claude-code) today, and the format is plain
markdown plus shell, so most of it ports to any agent that can read instructions and
run tools.

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
<!-- END SKILL INDEX -->

## Install

Copy the skills you want into your Claude Code skills directory:

```bash
git clone https://github.com/SecurityMindedSolutions/ai-skills.git
cp -R ai-skills/skills/auditing/audit-security ~/.claude/skills/
```

Or symlink, so a `git pull` updates the skill in place:

```bash
ln -s "$PWD/ai-skills/skills/auditing/audit-security" ~/.claude/skills/audit-security
```

A skill lives at the directory named in its category table above. Copy the whole directory,
not just its `SKILL.md` - the audit skills keep their checks in `modules/` and their shared
validation method in `references/`, and the Ralph loop ships `ralph.sh` alongside its
templates.

Restart Claude Code, then type the command. The category README linked beside each
table covers that skill's options, output and prerequisites.

## License

MIT. See [LICENSE](LICENSE).
