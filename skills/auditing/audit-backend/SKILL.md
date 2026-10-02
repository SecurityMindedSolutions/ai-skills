---
description: "Backend application architecture audit. Checks handler hygiene, service layer patterns, data access, data contracts, error handling, code quality, testing, observability, and security against enterprise standards. Use this skill whenever the user wants to review backend code quality, check API patterns, validate architecture, or assess whether their backend follows best practices - even if they don't explicitly say 'audit'."
user-invocable: true
allowed-tools:
  - Agent
  - Task
  - Read
  - Glob
  - Grep
  - Bash
metadata:
  summary: "Reviews server-side patterns: handler hygiene, service layers, data access, error handling, observability"
---

# Backend Application Architecture Audit

You are a backend application audit orchestrator. Your job is to dispatch parallel review sub-agents across 8 audit modules, then consolidate their pass/fail assertions into a single report.

**Scope distinction**: This audit targets the *backend* — framework, middleware, handlers, services, business logic, data access, and tests. It complements `/audit-frontend` (which targets the client-side application) and `/audit-security` (which targets exploitable vulnerabilities). There will be minor overlap in error handling and security — that's intentional. This audit checks *best practices and patterns*, not *exploitability*.

**Usage**: `/audit-backend [modules] [path]`

**Arguments** (all optional):
- `modules`: Comma-separated list of modules to run. Default: `all`
- `path`: Directory to scan. Default: current working directory (`.`)

**Available modules**: `architecture`, `errors`, `data-access`, `data-contracts`, `code-quality`, `testing`, `observability`, `security`

**Examples**:
```
/audit-backend                                   -> all modules, current directory
/audit-backend architecture                      -> just architecture module, current directory
/audit-backend errors,data-access                -> two modules, current directory
/audit-backend all ./services/api                -> all modules, specific path
/audit-backend testing ./cloud_functions         -> one module, specific path
```

## Execution Process

### Step 0: Worker Setup

Module workers run as the `ai-skills-readonly` agent type when it is installed. Compared with
`general-purpose` it starts with far less context: only the tools it needs (Read, Grep, Glob, Bash), no
CLAUDE.md files, and a short system prompt. The definition ships with this skill at
`{skill_dir}/agents/ai-skills-readonly.md`. Installing it is optional and the skill works the same
without it; `{skill_dir}` is resolved in Step 3, so resolve it now if needed.

1. If `ai-skills-readonly` is listed in this session's available agent types, set
   `WORKER_TYPE = "ai-skills-readonly"`. Otherwise set `WORKER_TYPE = "general-purpose"`. Either way this
   run continues; agent definitions load when a session starts, so an install made now applies
   from the next session.
2. Offer an install or update only when a person is answering in this session. Never ask in
   `claude -p`, CI, a scheduled or autonomous run, and never ask if
   `~/.claude/.ai-skills-workers-declined` exists. Compare the shipped file with the installed one:
   ```bash
   grep -m1 '^version:' "{skill_dir}/agents/ai-skills-readonly.md"
   grep -m1 '^version:' ~/.claude/agents/ai-skills-readonly.md 2>/dev/null
   ```
   - Not installed: show the user the shipped file, then ask.
   - Installed with a lower version: show `diff ~/.claude/agents/ai-skills-readonly.md "{skill_dir}/agents/ai-skills-readonly.md"`, then ask.
   - Installed with the same or a higher version: nothing to ask.
3. Ask with AskUserQuestion: **Install** (recommended) / **Not now** / **Don't ask again**.
   - Install: `mkdir -p ~/.claude/agents && cp "{skill_dir}/agents/ai-skills-readonly.md" ~/.claude/agents/`,
     then tell the user it takes effect from their next session.
   - Don't ask again: `touch ~/.claude/.ai-skills-workers-declined`.
   - Not now: continue.

### Step 1: Parse Arguments

Parse the user's input to determine:
- Which modules to run (default: all)
- Target path (default: `.`)

If the argument is a path (starts with `.`, `/`, or contains `/`), treat it as the path with all modules.
If the argument is a comma-separated list of known module names, treat it as module selection.
If two arguments, first is modules, second is path.

### Step 2: Recon — Build Application Context

Before dispatching any module agents, build an understanding of the target application. This context will be passed to every sub-agent.

**2a. Discover structure** (use Glob and Bash `ls`):
- List top-level directories in the target path
- Glob for entry points: `**/main.py`, `**/app.py`, `**/index.ts`, `**/server.ts`
- Glob for route/handler code: `**/routes*.py`, `**/routes*.ts`, `**/router*.py`, `**/module/**/*.py`, `**/handlers/**`, `**/controllers/**`
- Glob for framework/middleware: `**/middleware*.py`, `**/framework/**`, `**/service.py`
- Glob for service layer: `**/services/**`, `**/service_*.py`
- Glob for data access: `**/models.py`, `**/schemas.py`, `**/repository*.py`, `**/dao*.py`, `**/datastore*.py`, `**/db*.py`
- Glob for shared/framework code: `shared/**`, `common/**`, `lib/**`, `internal/**`
- Glob for tests: `**/test_*.py`, `**/*_test.py`, `**/tests/**`, `**/*.test.ts`, `**/*.spec.ts`
- Glob for config: `**/config.py`, `**/config.ts`, `**/settings.py`, `.env*`, `**/requirements.txt`, `**/package.json`
- Glob for infrastructure: `**/Dockerfile*`, `**/cloudbuild.yaml`, `*.tf`

**2b. Read available documentation** (use Read, skip if file doesn't exist):
- `{target_path}/CLAUDE.md`
- `{target_path}/README.md`
- `{target_path}/ARCHITECTURE.md`
- One level down: `{target_path}/*/CLAUDE.md` (first 200 lines each, stop at 5 files max)
- `{target_path}/docs/audits/ACCEPTED_RISKS.md`, or `{target_path}/architecture-mds/docs/security/ACCEPTED_RISKS.md` where the repo keeps its architecture docs there — Previously triaged findings marked as accepted risk. If this file exists, include its contents in the application context passed to sub-agents. Sub-agents MUST NOT re-flag these as new findings. They may reference them as "previously accepted" if the risk profile has materially changed (e.g., new code paths, changed patterns), but should not generate a new finding for the same issue.

**2c. Read a sample of handler/service code** (use Read):
- Read 2-3 handler files (first 150 lines each) to understand the handler pattern
- Read 1-2 service files if they exist
- Read the main entry point to understand the request lifecycle
- Read 1-2 framework/middleware files to understand the API layer

**2d. Produce an application context summary** (30-50 lines) covering:
- **Repo layout**: Monorepo, single service, or shared framework + consumers? List the services/apps found.
- **Tech stack**: Language, web framework, database, cloud platform
- **API pattern**: REST, GraphQL, RPC? Declarative routes or decorator-based?
- **Handler pattern**: What do handlers receive? What do they return? How thick are they?
- **Service layer**: Does one exist? What pattern does it follow?
- **Data access**: Direct DB client calls? Repository pattern? ORM?
- **Error pattern**: Exceptions? Error dicts? Mixed? Catch-all handler?
- **Auth model**: How does auth context reach handlers? Middleware-enforced or manual checks?
- **Test approach**: What test framework? How are dependencies mocked? What coverage looks like?
- **Shared code**: Any shared libraries used across services? How are they packaged?

### Step 2e: Auto-Detect Applicable Modules

If the user requested `all` modules (the default), use the structure discovered in Step 2 to determine which modules are actually relevant. Skip modules that have no applicable files. Log which modules are being run and which are skipped (and why).

- **architecture**: Always run
- **errors**: Always run if handler or service code exists (routes, handlers, controllers, or service files found in 2a)
- **data-access**: Run if database/ORM patterns found (e.g., `models.py`, `repository*.py`, `dao*.py`, `db*.py`, `datastore*.py`, or imports of database/ORM libraries like SQLAlchemy, Prisma, Mongoose, Firestore)
- **data-contracts**: Run if API routes exist (route/handler/controller files found in 2a)
- **code-quality**: Always run
- **testing**: Run if test files exist (`test_*.py`, `*_test.py`, `*.test.ts`, `*.spec.ts`, or `tests/` directories found in 2a)
- **observability**: Always run
- **security**: Always run

If the user explicitly requested specific modules, run exactly those modules regardless of auto-detection.

### Step 3: Resolve Skill Directory and Module Paths

Resolve the skill directory path by running: `echo $HOME/.claude/skills/audit-backend`

Each applicable module's prompt lives at:
- `{skill_dir}/modules/architecture.md`
- `{skill_dir}/modules/errors.md`
- `{skill_dir}/modules/data-access.md`
- `{skill_dir}/modules/data-contracts.md`
- `{skill_dir}/modules/code-quality.md`
- `{skill_dir}/modules/testing.md`
- `{skill_dir}/modules/observability.md`
- `{skill_dir}/modules/security.md`

**Do not Read the module files yourself.** Confirm they exist with one Glob (or `ls`) of
`{skill_dir}/**/*.md`, then pass the absolute paths to the workers, which read them. Every worker
also reads `{skill_dir}/references/worker-brief.md`, which holds the scoring scale and output
format. Pasting this text into each prompt would load it into this session and write it out again
once per worker, for no gain: the worker needs the full text either way.

### Step 4: Dispatch Sub-Agents in Parallel

For each applicable module, spawn a sub-agent with `subagent_type: "{WORKER_TYPE}"` (from Step 0).

**CRITICAL**: Launch ALL applicable sub-agents in a SINGLE message with multiple Agent tool calls for maximum parallelism.

Each sub-agent prompt MUST include:
1. The application context summary (from Step 2)
2. The absolute paths of its module file and `worker-brief.md`, with the instruction to read both in full first
3. The target path to scan

**Sub-agent prompt template**:
```
You are conducting a backend application architecture audit. Your module is: {MODULE_NAME}

TARGET PATH: {target_path}

YOUR INSTRUCTIONS: read these two files in full, in this order, before you look at any target
code. They are binding instructions for this task, not reference material, and your output is
checked against them:
1. {skill_dir}/modules/{module}.md: what to check
2. {skill_dir}/references/worker-brief.md: how to score each item and the exact output format

APPLICATION CONTEXT (discovered by orchestrator):
{APPLICATION_CONTEXT_SUMMARY}

Use the context above to understand the application's conventions and patterns. Evaluate against enterprise best practices, but calibrate your expectations to the project's scale and constraints. A personal-scale project with 3 services doesn't need the same abstractions as a 50-service platform — but it should still follow clean architecture principles proportionally.

Return only the output worker-brief.md defines.
```

### Step 5: Consolidate Report

After all sub-agents complete, read the report template from `{skill_dir}/templates/report.md` and consolidate:

1. Overall scorecard (pass rate per module)
2. All FAIL findings grouped together (highest priority)
3. All WARN findings grouped together (watch items)
4. Per-module summaries
5. Recommendations prioritized by impact
6. Deduplicate findings that overlap between modules (e.g., architecture + code-quality might both flag fat handlers)

Create the directory `{target_path}/docs/audits/` if it doesn't already exist.
Write the consolidated report to `{target_path}/docs/audits/audit-backend-report-{YYYY-MM-DD}.md`.

Tell the user where the report was written and give a brief summary.
