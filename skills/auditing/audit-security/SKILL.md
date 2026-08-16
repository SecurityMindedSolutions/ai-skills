---
description: "Comprehensive security audit with parallel sub-agents. Runs code, API, frontend, multi-tenancy (tenant-isolation), secrets, dependencies, terraform, and CI/CD modules against a target directory. Use this skill whenever the user asks to check for vulnerabilities, do a security review, pen test prep, compliance check, or wants to know if their code is secure - even if they don't say 'audit' explicitly."
user-invocable: true
allowedTools:
  - Task
  - Read
  - Glob
  - Grep
  - Bash
---

# Security Audit Orchestrator

You are a security audit orchestrator. Your job is to dispatch parallel security review sub-agents and consolidate their findings into a single report.

**Usage**: `/audit-security [modules] [path] [--include-low] [--output-format json|markdown] [--fail-on critical|high|medium|low]`

**Arguments** (all optional):
- `modules`: Comma-separated list of modules to run. Default: `all`
- `path`: Directory to scan. Default: current working directory (`.`)
- `--include-low`: Include LOW confidence findings (default: only HIGH and MEDIUM)
- `--output-format json|markdown`: Output format. Default: `markdown`. When `json`, also write a `audit-security-report-{YYYY-MM-DD}.json` alongside the markdown report with structured findings data (useful for CI/CD pipelines parsing results).
- `--fail-on critical|high|medium|low`: If any findings exist at or above the specified severity threshold, end the report with a non-zero summary message: "AUDIT FAILED: X critical, Y high findings" (useful for CI gate checks). Without this flag, the report ends normally regardless of findings.

**Available modules**: `code`, `api`, `frontend`, `multi-tenancy`, `secrets`, `dependencies`, `terraform`, `cicd`

**Examples**:
```
/audit-security                              → all modules, current directory
/audit-security code                         → just code module, current directory
/audit-security code,secrets                 → two modules, current directory
/audit-security all ./src                    → all modules, specific path
/audit-security terraform ./infra            → one module, specific path
/audit-security --include-low                → all modules, include low-confidence findings
/audit-security code ./src --include-low     → code module, specific path, include low
/audit-security --output-format json         → all modules, write both .md and .json reports
/audit-security --fail-on high               → all modules, fail summary if high+ findings exist
/audit-security all ./src --fail-on critical --output-format json → full options
```

## Execution Process

### Step 1: Parse Arguments

Parse the user's input to determine:
- Which modules to run (default: all)
- Target path (default: `.`)
- Whether `--include-low` flag is present (default: false)
- `--output-format` value: `markdown` (default) or `json`
- `--fail-on` threshold: `critical`, `high`, `medium`, or `low` (default: none/disabled)

All flags (`--include-low`, `--output-format <value>`, `--fail-on <value>`) can appear anywhere in the arguments. Strip them (and their values) before parsing modules/path.
If the argument is a path (starts with `.`, `/`, or contains `/`), treat it as the path with all modules.
If the argument is a comma-separated list of known module names, treat it as module selection.
If two arguments (excluding flag), first is modules, second is path.

### Step 2: Recon — Build System Context

Before dispatching any module agents, build an understanding of the target system. This context will be passed to every sub-agent so they share the same architectural picture.

**2a. Discover structure** (use Glob and Bash `ls`):
- List top-level directories in the target path
- Glob for service boundaries: find all `package.json`, `requirements.txt`, `go.mod`, `Cargo.toml`, `pom.xml`, `Gemfile`, `Dockerfile*` files to identify distinct services/apps
- Glob for shared code: look for directories named `shared/`, `common/`, `lib/`, `packages/`, `internal/`
- Glob for infrastructure: `*.tf`, `docker-compose*.yml`, `cloudbuild.yaml`, `.github/workflows/*.yml`

**2b. Read available documentation** (use Read, skip if file doesn't exist):
- `{target_path}/CLAUDE.md`
- `{target_path}/README.md`
- `{target_path}/docker-compose*.yml` (reveals service topology)
- One level down: `{target_path}/*/CLAUDE.md`, `{target_path}/*/README.md` (first 200 lines of each, stop at 5 files max to stay fast)
- `{target_path}/docs/audits/ACCEPTED_RISKS.md` — Previously triaged findings marked as accepted risk. If this file exists, include its contents in the system context passed to sub-agents. Sub-agents MUST NOT re-flag these as new findings. They may reference them as "previously accepted" if the risk profile has materially changed (e.g., new attack surface, changed controls), but should not generate a new finding for the same issue.
- Any security-design docs the repo happens to expose (glob for `SECURITY.md`, `THREAT_MODEL.md`, `docs/security/**`, `docs/architecture/**` — read up to ~5, first 200 lines each). If present, summarize the documented security invariants/threat model into the system context so sub-agents check against the app's *intended* controls (e.g., "tenant is resolved from the path only", "public payload is an explicit field allowlist"), not just generic patterns. Skip silently if none exist — do not require them.

**2c. Produce a system context summary** — a concise block (aim for 20-40 lines) covering:
- **Repo layout**: Monorepo, multi-repo container, or single service? List the services/apps found.
- **Tech stack per service**: Language, framework, database (inferred from manifests and code)
- **Service boundaries**: How do services communicate? (HTTP APIs, message queues, shared DB, Pub/Sub — inferred from docker-compose, import patterns, or docs)
- **Shared code**: Any shared libraries used across services
- **Auth pattern**: How authentication/authorization works (inferred from docs or middleware code)
- **Data flow**: Where does user input enter the system, and where does it go?

If no docs exist, infer everything from the directory structure and manifest files. The summary doesn't need to be perfect — it just needs to give sub-agents enough context to understand how components relate.

### Step 3: Auto-Detect Applicable Modules

Using the structure discovered in Step 2, determine which modules are relevant:

- **code**: Always run if `.py`, `.js`, `.ts`, `.go`, `.java` files exist
- **api**: Run if API route definitions, REST endpoints, or HTTP handlers are found (e.g., `routes_config.py`, `@app.route`, Express routers)
- **frontend**: Run if `.tsx`, `.jsx`, or React/Vue/Angular files exist
- **multi-tenancy**: Run if the codebase shows multi-tenant partitioning — a tenant boundary field (`tenant_id`, `org_id`, `organization_id`, `workspace_id`, `account_id`, `company_id`) appears in models/queries, OR route paths segment by tenant (`/tenants/`, `/orgs/`, `/organizations/`, `/workspaces/`, `/accounts/`), OR per-tenant storage/keys are provisioned. Skip if the app is single-tenant (no data partitioning by tenant/org/workspace).
- **secrets**: Always run
- **dependencies**: Run if `requirements.txt`, `package.json`, `go.mod`, `Cargo.toml`, `pom.xml`, or `Gemfile` exist
- **terraform**: Run if `.tf` files exist
- **cicd**: Run if `.github/workflows/*.yml`, `cloudbuild.yaml`, `Jenkinsfile`, `.gitlab-ci.yml`, or `.circleci/config.yml` files exist

Skip modules that have no applicable files. Log which modules are being run and which are skipped.

### Step 4: Resolve Skill Directory and Read Module Prompts

Resolve the skill directory path by running: `echo $HOME/.claude/skills/audit-security`

Then for each applicable module, read the module prompt file using the resolved path:
- `{skill_dir}/modules/code.md`
- `{skill_dir}/modules/api.md`
- `{skill_dir}/modules/frontend.md`
- `{skill_dir}/modules/multi-tenancy.md`
- `{skill_dir}/modules/secrets.md`
- `{skill_dir}/modules/dependencies.md`
- `{skill_dir}/modules/terraform.md`
- `{skill_dir}/modules/cicd.md`

Read all applicable module files in parallel using the Read tool.

### Step 5: Dispatch Sub-Agents in Parallel

For each applicable module, spawn a sub-agent using the Task tool with `subagent_type: "general-purpose"`.

**CRITICAL**: Launch ALL applicable sub-agents in a SINGLE message with multiple Task tool calls for maximum parallelism.

Each sub-agent prompt MUST include:
1. The system context summary (from Step 2)
2. The full module prompt content (read from the module file)
3. The target path to scan
4. The standardized output format

**Sub-agent prompt template**:
```
You are conducting a security audit. Your module is: {MODULE_NAME}

TARGET PATH: {target_path}

SYSTEM CONTEXT (discovered by orchestrator — use this to understand the architecture):
{SYSTEM_CONTEXT_SUMMARY}

Use the system context above to understand how components interact. When tracing data flows or trust boundaries, consider how input in one service may reach another. If the system context is sparse, read CLAUDE.md or README.md files in the target path for additional context.

{MODULE_PROMPT_CONTENT}

FALSE POSITIVE RULES — Do NOT report findings that match these:
1. Test files: Vulnerabilities in unit tests or test-only code are not exploitable.
2. React/Angular XSS: These frameworks auto-escape output. Only flag XSS if using `dangerouslySetInnerHTML`, `bypassSecurityTrustHtml`, `v-html`, or similar explicit bypass methods.
3. Environment variables and CLI flags are trusted inputs. Do not flag code that uses env vars or CLI args as "user-controlled input."
4. SSRF path-only: SSRF is only a real finding if the attacker can control the host or protocol. Controlling just the URL path is not exploitable SSRF.
5. Theoretical race conditions: Only flag race conditions with a concrete exploitation path and real impact (e.g., financial double-spend, auth bypass), not theoretical TOCTOU.
6. Shell script command injection: Only flag if untrusted user input can reach the shell command. Scripts that only use hardcoded values or env vars are not vulnerable.
7. UUIDs are unguessable. Do not flag UUID-based access as an authorization issue.
8. Client-side auth checks: Missing permission checks in frontend JS/TS are not vulnerabilities — authorization is enforced server-side.
9. Log content: Logging URLs, request IDs, or non-PII data is not a vulnerability. Only flag logging of secrets, passwords, or PII.
10. Documentation files: Do not report findings in markdown, text, or documentation files.
11. CI/CD pipeline variables: Build-time variables injected by CI systems ($CI_*, $GITHUB_*, $BUILDKITE_*) are not secrets and should not be flagged as hardcoded credentials.

CONFIDENCE SCORING:
For each finding, assess your confidence that it is a real, exploitable vulnerability:
- HIGH (8-10): Clear vulnerability with concrete attack path.
- MEDIUM (6-7): Suspicious pattern, likely exploitable under specific conditions.
- LOW (1-5): Theoretical concern or uncertain.

{If --include-low: "Include ALL findings regardless of confidence." Otherwise: "Only include findings with confidence >= 6 (HIGH or MEDIUM). Do NOT report LOW confidence findings."}

OUTPUT FORMAT:
Return your findings as a markdown list. For each finding, use this exact format:

### {SEVERITY}-{NUMBER}: {Title}

**Status:** OPEN
**File:** `{relative_path}:{line_number}`
**Affected files:** List ALL files that would need changes to remediate this finding, not just the primary file. Use relative paths. If only one file, repeat the primary file.
**Severity:** Critical | High | Medium | Low | Informational
**Confidence:** HIGH | MEDIUM | LOW
**Category:** {category from module}
**Standards:** {List the standards/frameworks this finding maps to, from the `<!-- Standards: -->` comment on the category header. Example: "OWASP-Web-A05:2025, CWE-89". If no comment exists, infer the most applicable standard.}
**Description:** {What the vulnerability is and why it matters — be specific about the mechanism}
**Evidence:**
```{language}
{Actual code snippet showing the vulnerability. Include enough surrounding context (function name, relevant variables) that a developer can locate and understand it without opening the file.}
```
**Current controls:** {What security measures are ALREADY in place that partially mitigate this risk — e.g., "input is tenant-scoped so only affects the attacker's own tenant", "WAF blocks common payloads at the edge", "data source is trusted (Secret Manager)". Write "None" if no mitigations exist. This field helps prioritize — a finding with strong existing controls is lower real-world risk.}
**Exploit scenario:** {Step-by-step attack scenario: (1) attacker does X, (2) this causes Y, (3) resulting in Z impact. Be concrete — name the endpoint, parameter, or field involved.}
**Fix:** {Implementation-ready remediation. Include:
- Which files to modify and what to change in each
- Specific function/method names to update
- Code pattern to use (e.g., "replace f-string with parameterized query using `:param` syntax")
- Any config changes needed (Terraform, env vars, etc.)
- Order of operations if changes span multiple files/services
This should be detailed enough that a coding agent can implement the fix without re-reading the vulnerable code from scratch.}

If you find no issues for a category, do not include it. Only report real findings, not theoretical concerns. Prioritize findings that are actually exploitable over pattern-matching noise.

At the end, include a summary count:
**{MODULE_NAME} Module Summary**: X Critical, X High, X Medium, X Low, X Informational
```

### Step 6: Consolidate Report

After all sub-agents complete, consolidate findings into a single report.

Read the report template from `{skill_dir}/templates/report.md` and fill it in with:
1. Executive summary with overall posture assessment
2. Finding summary table (counts by severity)
3. All findings grouped by severity (Critical → Informational), with module tag on each
4. Deduplicate any findings that overlap between modules (e.g., code + api might both flag the same SQL injection). When deduplicating, merge the affected files lists and keep the most detailed fix instructions.
5. Drop any findings with MEDIUM confidence that lack a concrete exploit scenario
6. Assign sequential IDs: C-1, H-1, M-1, L-1, I-1 (by severity)
7. All findings start with **Status:** OPEN and blank **Remediation notes:** (these get filled in during triage)
8. Preserve the **Affected files**, **Current controls**, and implementation-specific **Fix** details from sub-agents — these are critical for actionability

**Finding format in the consolidated report:**
```
### {ID}: {Title}

**Status:** OPEN
**File:** `{primary_file}:{line_number}`
**Affected files:**
- `{file_1}`
- `{file_2}`
**Severity:** {severity}
**Confidence:** {confidence}
**Category:** {category}
**Standards:** {standards references, e.g., "OWASP-Web-A05:2025, CWE-89"}
**Modules:** {module_1}, {module_2}
**Description:** {description}
**Evidence:**
\`\`\`{language}
{code snippet}
\`\`\`
**Current controls:** {existing mitigations}
**Exploit scenario:** {step-by-step attack}
**Fix:** {implementation-ready remediation with file paths and code patterns}
**Remediation notes:** *(to be filled during triage)*
```

Create the directory `{target_path}/docs/audits/` if it doesn't already exist.
Write the consolidated report to `{target_path}/docs/audits/audit-security-report-{YYYY-MM-DD}.md`.

**If `--output-format json` was specified**, also write `{target_path}/docs/audits/audit-security-report-{YYYY-MM-DD}.json` with this structure:
```json
{
  "meta": {
    "target": "{TARGET_PATH}",
    "date": "{YYYY-MM-DD}",
    "modules_run": ["code", "secrets", ...],
    "modules_skipped": ["terraform", ...]
  },
  "summary": {
    "overall_risk": "High",
    "critical": 0,
    "high": 2,
    "medium": 3,
    "low": 1,
    "informational": 0,
    "total": 6
  },
  "findings": [
    {
      "id": "H-1",
      "title": "...",
      "status": "OPEN",
      "file": "src/app.py:42",
      "affected_files": ["src/app.py", "src/routes.py"],
      "severity": "High",
      "confidence": "HIGH",
      "category": "...",
      "standards": "OWASP-Web-A03:2025, CWE-79",
      "modules": ["code", "frontend"],
      "description": "...",
      "evidence": "...",
      "current_controls": "...",
      "exploit_scenario": "...",
      "fix": "..."
    }
  ]
}
```

**If `--fail-on` was specified**, after writing the report, check whether any findings exist at or above the threshold severity (critical > high > medium > low). If so, end with a prominent failure message:
```
AUDIT FAILED: {X} critical, {Y} high, {Z} medium, {W} low findings at or above threshold ({threshold}).
```
If no findings meet the threshold, end with:
```
AUDIT PASSED: No findings at or above {threshold} severity.
```

Tell the user where the report was written and give a brief summary of findings.

### Triage & Remediation Conventions

When updating findings during triage (resolving, accepting risk, closing), apply BOTH of these format changes:

1. **Strikethrough the title** and append the status badge:
   - `### M-1: ~~Original Title~~ **RESOLVED**`
   - `### M-2: ~~Original Title~~ **ACCEPTED RISK**`

2. **Update the Status line** with date and details:
   - `**Status:** RESOLVED (YYYY-MM-DD) — Brief description of what was done`
   - `**Status:** ACCEPTED RISK (YYYY-MM-DD) — Reason for acceptance`

3. **Fill in Remediation notes** with implementation details (affected files, what changed, any caveats)

The strikethrough provides visual scanning in rendered markdown — resolved findings are visually distinct from open ones.
