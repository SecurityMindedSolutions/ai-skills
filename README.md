# AI Skills

Skills that let a coding agent do real work on a codebase: audit one you inherited,
clear a vulnerability backlog, or take a long implementation and run it unattended.

Each skill is a directory holding a `SKILL.md` and whatever modules, templates or
scripts it needs. They are written for [Claude
Code](https://docs.anthropic.com/en/docs/claude-code) today, and the format is plain
markdown plus shell, so most of it ports to any agent that can read instructions and
run tools.

## Skills

| Skill | Command | What it does |
|---|---|---|
| [Security audit](skills/auditing/audit-security/) | `/audit-security` | Finds exploitable vulnerabilities across code, APIs, frontend, tenancy, secrets, dependencies, Terraform and CI/CD |
| [Frontend audit](skills/auditing/audit-frontend/) | `/audit-frontend` | Reviews client-side architecture: design tokens, components, accessibility, performance, SEO |
| [Backend audit](skills/auditing/audit-backend/) | `/audit-backend` | Reviews server-side patterns: handler hygiene, service layers, data access, error handling, observability |
| [GitHub vulnerability remediation](skills/vulnerability-management/github-remediate-vulns/) | `/github-remediate-vulns` | Scans a GitHub org for Dependabot, code scanning and secret scanning alerts, then fixes what it safely can and reports the rest |
| [Ralph plan](skills/autonomous-development/ralph-plan/) | `/ralph-plan` | Interactive builder for a PRD with checkboxed tasks and acceptance criteria |
| [Ralph loop](skills/autonomous-development/ralph-loop/) | `/ralph-loop` | Autonomous runner that works through that PRD one task at a time, no human in the loop |
| [Built-With](skills/reconnaissance/built-with/) | `/built-with` | Passive, headless recon of a web app's frontend - maps its third-party vendors, backend hosts and API surface from public JS, into a plain-English dossier |

The three audit skills dispatch parallel sub-agents and consolidate their findings
into one report. They overlap deliberately: the security audit asks whether something
is *exploitable*, while the frontend and backend audits ask whether the *pattern* is
sound.

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

A skill lives at the directory named in the table above. Copy the whole directory,
not just its `SKILL.md` - the audit skills keep their checks in `modules/`, and the
Ralph loop ships `ralph.sh` alongside its templates.

Restart Claude Code, then type the command. Each skill's own README covers its
options and prerequisites.

## Layout

```
skills/
├── auditing/                        codebase review, one skill per layer
├── vulnerability-management/        finding and fixing known vulns
├── autonomous-development/          planning and running unattended work
└── reconnaissance/                  passive recon of a live web app's stack
```

## Previously

These skills were published as three separate repositories, now archived and
pointing here:

- `claude-audit-skills`
- `claude-github-vuln-remediation-skill`
- `claude-ralph-loop-skill`

## License

MIT. See [LICENSE](LICENSE).
