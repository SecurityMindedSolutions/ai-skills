---
description: "Comprehensive security audit with parallel sub-agents. Runs code, API, frontend, browser extension, multi-tenancy (tenant-isolation), secrets, dependencies, terraform, and CI/CD modules against a target directory. Use this skill whenever the user asks to check for vulnerabilities, do a security review, pen test prep, compliance check, or wants to know if their code is secure - even if they don't say 'audit' explicitly."
user-invocable: true
allowed-tools:
  - Agent
  - Task
  - Read
  - Glob
  - Grep
  - Bash
metadata:
  summary: "Finds exploitable vulnerabilities across code, APIs, frontend, browser extensions, tenancy, secrets, dependencies, Terraform and CI/CD"
---

# Security Audit Orchestrator

You are a security audit orchestrator. Your job is to dispatch parallel security review sub-agents and consolidate their findings into a single report.

**Usage**: `/audit-security [modules] [path] [--trace-scope p1,p2] [--include-low] [--output-format json|markdown] [--fail-on critical|high|medium|low]`

**Arguments** (all optional):
- `modules`: Comma-separated list of modules to run. Default: `all`
- `path`: Directory to scan. Default: current working directory (`.`)
- `--trace-scope <paths>`: Comma-separated additional directory roots that sub-agents may **read in order to follow a call path**, but which are NOT themselves scanned for findings. Use this when the system under audit calls into sibling repositories, shared libraries, or companion services that live outside the target path — without them, any path that leaves the target tree stops at a `[boundary]` hop and the finding's confidence is capped (see `references/trace-protocol.md` §4). Findings are still only reported against files under `path`.
- `--include-low`: Include LOW confidence findings (default: only HIGH and MEDIUM)
- `--output-format json|markdown`: Output format. Default: `markdown`. When `json`, also write a `audit-security-report-{YYYY-MM-DD}.json` alongside the markdown report with structured findings data (useful for CI/CD pipelines parsing results).
- `--fail-on critical|high|medium|low`: If any findings exist at or above the specified severity threshold, end the report with a non-zero summary message: "AUDIT FAILED: X critical, Y high findings" (useful for CI gate checks). Without this flag, the report ends normally regardless of findings.

**Available modules**: `code`, `api`, `frontend`, `extension`, `multi-tenancy`, `secrets`, `dependencies`, `terraform`, `cicd`

**Examples**:
```
/audit-security                              → all modules, current directory
/audit-security code                         → just code module, current directory
/audit-security code,secrets                 → two modules, current directory
/audit-security all ./src                    → all modules, specific path
/audit-security terraform ./infra            → one module, specific path
/audit-security extension ./extension        → browser extension module only
/audit-security --include-low                → all modules, include low-confidence findings
/audit-security code ./src --include-low     → code module, specific path, include low
/audit-security --output-format json         → all modules, write both .md and .json reports
/audit-security --fail-on high               → all modules, fail summary if high+ findings exist
/audit-security api ./svc --trace-scope ../shared-lib,../gateway → trace call paths into sibling repos
/audit-security all ./src --fail-on critical --output-format json → full options
```

## Execution Process

### Step 0: Worker Setup

Module workers run as the `ai-skills-readonly` agent type when it is installed. Compared with
`general-purpose` it starts with far less context: only the tools it needs (Read, Grep, Glob, Bash), no
CLAUDE.md files, and a short system prompt. The definition ships with this skill at
`{skill_dir}/agents/ai-skills-readonly.md`. Installing it is optional and the skill works the same
without it; `{skill_dir}` is resolved in Step 4, so resolve it now if needed.

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
- Glob for browser extensions: `**/manifest.json` (excluding `node_modules`) containing `manifest_version`. Note source vs built copies (`public/` vs `dist/`).
- Glob for **live deployment manifests**, independent of the above: `helm/values*.yaml` (or `chart*/values*.yaml`) containing an `ingress:` block, `docker-compose.prod*.yml`, Kubernetes `Deployment`/`Service`/`Ingress` YAML, `serverless.yml`, `Procfile`. A manifest declaring a real ingress/route is ground truth that a service is actually deployed — treat it as such regardless of what any README, architecture doc, or the repo's own name says, and regardless of whether the repo is marked archived on its host (GitHub/GitLab/etc.). An archived-but-still-deployed service is a known, recurring pattern and exactly the kind of thing likely to have been neglected — a reason to prioritize it, not skip it.

**2a-i. Multi-repo / multi-service containers**: if the target path holds many independently-deployable services (a monorepo-of-repos, or a directory of per-service subdirectories) too large to review exhaustively in one pass, any scope narrowing MUST be checked against 2a's deployment-manifest scan before being finalized. Build the full candidate list from live deployment evidence first, *then* narrow by risk (internet-facing, handles auth, etc.) — never narrow by documentation coverage or naming alone, since the undocumented/oddly-named/archived-looking service is disproportionately likely to be the one nobody has audited. If scope is narrowed, explicitly list which discovered services were excluded and why, so a reader can sanity-check the exclusion.

**2a-ii. Scope by blast radius, not just by network exposure (do not skip this pass).** "Internet-facing" and "handles auth" are exposure/trust signals, but they are not the only thing that makes a service worth auditing — a service that is internal-only (VPC-only ALB, `scheme: internal`, no ingress at all, reachable only from inside the cluster/mesh) can still be one of the highest-value targets in the fleet if compromising it or its unauthenticated routes grants a large blast radius. This matters because internal-only is exactly the label that makes a service *feel* lower priority during triage, when a service's actual risk comes from what it's capable of doing once reached, not from how it's reached. Before finalizing scope, check every candidate service (internet-facing or not) for these blast-radius signals, and pull in any internal-only service that has them even if nothing else about it looks notable:
- **Direct orchestration/infrastructure SDK usage with mutating verbs**: does the service import a Kubernetes/container-orchestration client (`@kubernetes/client-node`, `client-go`, `kubernetes` Python client), a cloud infra SDK capable of creating/deleting compute or IAM resources (`client-batch`, `client-ec2`, `client-iam`, `client-lambda`, `boto3` EC2/IAM/Lambda clients, Docker/containerd control sockets), or shell out to `kubectl`/`docker`/`terraform apply` at runtime (not just in CI)? A service that can create, delete, or execute infrastructure-level resources is high blast-radius regardless of who's allowed to call it externally.
- **Accepts attacker-shapeable execution input**: does any route accept a container image reference, command/args array, script body, or similar "what to run" payload and hand it to one of the above APIs? This is the strongest single signal — it means reaching this service's API, not just compromising its host, is equivalent to code execution using whatever credentials the service holds.
- **Broad IAM/RBAC grant in its own deployment manifest**: `ClusterRole`/`ClusterRoleBinding` (vs. namespace-scoped `Role`), a wildcard-resource IAM policy, `cluster-admin`, or an unusually broad `serviceAccountName`/instance-profile shared with many other services (a shared chart's default grant counts too — see whether the manifest overrides it down or accepts the default).
- **Single-choke-point role**: is this the only (or one of very few) services in the fleet holding a particular elevated credential or capability — the one thing everything else calls into for a sensitive action (e.g., the only service that can mint infra credentials, provision tenants, or schedule cluster workloads)? Compromising a low-traffic internal chokepoint like this yields the same blast radius as compromising the perimeter, and is often less scrutinized precisely because it's internal-only and low-profile.

If a candidate service matches any of these, include it in scope and note explicitly in the exclusion/inclusion list *why* an internal-only service was pulled in — this is exactly the kind of service that both a documentation-driven scope AND a naive "narrow to internet-facing" pass would miss, so its presence is worth calling out the same way an undocumented-but-live-deployed discovery is.

**2a-iii. Establish the trace scope, and record what is missing from it.** Findings are validated by
following paths (see `references/trace-protocol.md`), and a path that leaves the available code
stops at a `[boundary]` hop that caps the finding's confidence. So before dispatching, work out
where the paths are likely to go and whether that code is readable:

- Start from the target path plus any `--trace-scope` roots supplied. That is the readable set.
- Identify **outbound edges**: imports or package references resolving outside the target tree
  (workspace/monorepo siblings, path-based or file-based dependency references, locally-linked
  packages); HTTP/RPC/queue clients pointed at other first-party services; shared client libraries
  or SDKs generated from another component's schema; auth or policy decisions delegated elsewhere.
- For each edge, check whether the destination is already readable. Look for it as a sibling of the
  target path, elsewhere in the same repository, or in an adjacent checkout — a sibling directory
  with its own VCS metadata and a matching name is the common case. **Do not read outside the
  supplied scope on your own initiative; report what you found instead.**
- Produce two lists for the sub-agent prompt: **readable** roots (target + supplied scope, each
  named so hops can be attributed to the right tree) and **unreadable but reachable** components
  (name them, so sub-agents mark those hops `[boundary]` rather than guessing).
- If unreadable-but-reachable components exist, say so in the final report's **Trace Coverage**
  note and tell the user which paths would make those findings verifiable. Do not silently produce
  lower-confidence findings without explaining that the cause was missing code rather than weak
  evidence — those are very different things to a reader deciding what to fix.

This step is cheap and is the difference between "we could not confirm" and an unexplained cap on
half the findings.

**2b. Read available documentation** (use Read, skip if file doesn't exist):
- `{target_path}/CLAUDE.md`
- `{target_path}/README.md`
- `{target_path}/docker-compose*.yml` (reveals service topology)
- One level down: `{target_path}/*/CLAUDE.md`, `{target_path}/*/README.md` (first 200 lines of each, stop at 5 files max to stay fast)
- `{target_path}/docs/audits/ACCEPTED_RISKS.md`, or `{target_path}/architecture-mds/docs/security/ACCEPTED_RISKS.md` where the repo keeps its architecture docs there — Previously triaged findings marked as accepted risk. If this file exists, include its contents in the system context passed to sub-agents. Sub-agents MUST NOT re-flag these as new findings. They may reference them as "previously accepted" if the risk profile has materially changed (e.g., new attack surface, changed controls), but should not generate a new finding for the same issue.
- **Known gaps are not accepted risks.** Only an item the owner explicitly accepted (in `ACCEPTED_RISKS.md`, or marked "accepted" with a decision/owner in a design doc) is suppressed. A gap a design doc lists as known but still open ("Gap (medium): ... Fix: ..." with no acceptance) MUST still be reported as a finding if the code confirms it is open, tagged `Known gap: {doc}:{line}` in **Current controls**. Suppressing it hides real open risk behind the fact that someone once wrote it down.
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
- **extension**: Run if any `manifest.json` outside `node_modules` contains a `manifest_version` key (Chrome/Firefox/Safari web extension). Record each extension root, and treat any web origin in its `externally_connectable.matches` as a principal that can reach the extension.
- **multi-tenancy**: Run if the codebase shows multi-tenant partitioning — a tenant boundary field (`tenant_id`, `org_id`, `organization_id`, `workspace_id`, `account_id`, `company_id`) appears in models/queries, OR route paths segment by tenant (`/tenants/`, `/orgs/`, `/organizations/`, `/workspaces/`, `/accounts/`), OR per-tenant storage/keys are provisioned. Skip if the app is single-tenant (no data partitioning by tenant/org/workspace).
- **secrets**: Always run
- **dependencies**: Run if `requirements.txt`, `package.json`, `go.mod`, `Cargo.toml`, `pom.xml`, or `Gemfile` exist
- **terraform**: Run if `.tf` files exist
- **cicd**: Run if `.github/workflows/*.yml`, `cloudbuild.yaml`, `Jenkinsfile`, `.gitlab-ci.yml`, or `.circleci/config.yml` files exist

Skip modules that have no applicable files. Log which modules are being run and which are skipped.

### Step 4: Resolve Skill Directory and Module Paths

`{skill_dir}` is the directory holding this `SKILL.md`, normally `$HOME/.claude/skills/audit-security`
(resolve it with `echo $HOME/.claude/skills/audit-security`).

Each applicable module's prompt lives at:
- `{skill_dir}/modules/code.md`
- `{skill_dir}/modules/api.md`
- `{skill_dir}/modules/frontend.md`
- `{skill_dir}/modules/extension.md`
- `{skill_dir}/modules/multi-tenancy.md`
- `{skill_dir}/modules/secrets.md`
- `{skill_dir}/modules/dependencies.md`
- `{skill_dir}/modules/terraform.md`
- `{skill_dir}/modules/cicd.md`

Every worker also reads two shared files:
- `{skill_dir}/references/trace-protocol.md`: **not** a module. It is the validation method every
  module uses, and every worker reads it in full.
- `{skill_dir}/references/worker-brief.md`: the false-positive rules, confidence scoring, severity
  calibration and output format every worker follows.

**Do not Read these files yourself.** Confirm they exist with one Glob (or `ls`) of `{skill_dir}/**/*.md`,
then pass their absolute paths to the workers, which read them. Pasting their text into each
prompt would load over 20k words into this session and write them out again once per worker, for no
gain: the worker needs the full text either way.

### Step 5: Dispatch Sub-Agents in Parallel

For each applicable module, spawn a sub-agent with `subagent_type: "{WORKER_TYPE}"` (from Step 0).

**CRITICAL**: Launch ALL applicable sub-agents in a SINGLE message with multiple Agent tool calls for maximum parallelism.

**Sharding the extension module.** One agent covering all extension categories goes wide and shallow. When the extension's own source (excluding tests, `node_modules`, `dist/`) exceeds ~2,000 lines, dispatch the extension module as three agents, each reading the full module file but told to own only its shard and go deep on it:
- **extension:boundaries** — categories 3, 4, 7, 8 (external and internal messaging, token and session lifecycle, network). Walk every listener and every token read/write.
- **extension:page** — categories 5, 6, 12, 13 (content scripts, injected UI and clickjacking, untrusted page content flowing inward to extension pages, backend and LLM, privacy, MV3 lifecycle and check-then-inject races). Walk every content script and every `executeScript`.
- **extension:package** — categories 1, 2, 9, 10, 11 (manifest, CSP, web-accessible resources, remote code and the built bundle, build and release chain).
Each shard also applies the module's **Tests Expected** section to its own categories. Consolidation merges the three as one module (`extension`). Each shard still returns its own clean-coverage note, so gaps between shards are visible.

Each sub-agent prompt MUST include:
1. The system context summary (from Step 2)
2. The absolute paths of its module file, `trace-protocol.md` and `worker-brief.md`, with the
   instruction to read all three in full before doing anything else
3. The target path to scan, and the trace scope (target path + any `--trace-scope` roots)
4. The reporting threshold (from `--include-low`) and, for an extension shard, the categories it owns

**Sub-agent prompt template**:
```
You are conducting a security audit. Your module is: {MODULE_NAME}{, shard: {SHARD_NAME}, owning only categories {LIST}}

TARGET PATH (findings are reported only against files here): {target_path}
TRACE SCOPE (you may READ anything here to follow a path; do not report findings outside TARGET PATH): {target_path}{, plus each --trace-scope root, each named}
{If no --trace-scope roots were supplied and the recon found sibling components the paths may reach, add: "NOTE: the following components appear reachable from the target but were NOT supplied for tracing — treat any path into them as a [boundary] hop: {list}. Say so in the finding, per the trace protocol."}

YOUR INSTRUCTIONS: read these three files in full, in this order, before you look at any target
code. They are binding instructions for this task, not reference material, and your output is
checked against them:
1. {skill_dir}/modules/{module}.md: what to check
2. {skill_dir}/references/trace-protocol.md: how every finding is validated
3. {skill_dir}/references/worker-brief.md: false-positive rules, confidence, severity calibration, output format

TRACE PROTOCOL — this is a GATE on every finding, not documentation. Apply it before you report
anything. A candidate you have not traced is an observation, not a finding; the falsification pass
in §5 is what tells you whether it is real. Findings are reported with a `**Trace:**` field in the
format defined in §6, and your confidence score is derived from the weakest verification marker on
the chain per §3 — it is not a separate judgement.

REPORTING THRESHOLD: {If --include-low: "LOW confidence findings are included: report ALL findings regardless of confidence." Otherwise: "Only include findings with confidence >= 6 (HIGH or MEDIUM). Do NOT report LOW confidence findings."} At every threshold, findings held at LOW only by `[assumed]`/`[boundary]` hops, or left untraced, are still returned under `## Unconfirmed`, per worker-brief.md.

SYSTEM CONTEXT (discovered by orchestrator — use this to understand the architecture):
{SYSTEM_CONTEXT_SUMMARY}

Use the system context above to understand how components interact. When tracing data flows or trust boundaries, consider how input in one service may reach another. If the system context is sparse, read CLAUDE.md or README.md files in the target path for additional context.

Return only the findings, the clean-coverage note and the module summary line, in the format
worker-brief.md defines.
```

### Step 6: Consolidate Report

After all sub-agents complete, consolidate findings into a single report.

Read the report template from `{skill_dir}/templates/report.md` and fill it in with:
1. Executive summary with overall posture assessment
2. Finding summary table (counts by severity)
3. All findings grouped by severity (Critical → Informational), with module tag on each
4. Deduplicate any findings that overlap between modules (e.g., code + api might both flag the same SQL injection). When deduplicating, merge the affected files lists and keep the most detailed fix instructions. **Merge the traces too, and prefer the better-verified one** — if one module reached a hop by reading it and another assumed it, keep the `[verified]` hop and raise the merged finding's confidence accordingly. Two modules independently tracing the same path to the same conclusion is corroboration; say so on the merged finding.
5. A finding whose **Trace** is missing or does not connect source to sink is not dropped silently: send the module agent back for the trace, or report it at LOW confidence marked untraced. An untraced finding was not validated, and shipping it spends the reader's trust on something nobody checked. If it looks important, send the module agent back for the trace rather than publishing it unverified.
6. Drop any findings with MEDIUM confidence that lack a concrete exploit scenario, and any whose Exploit scenario asserts a step the Trace does not support.
7. Assign sequential IDs: C-1, H-1, M-1, L-1, I-1 (by severity)
8. All findings start with **Status:** OPEN and blank **Remediation notes:** (these get filled in during triage)
9. Preserve the **Trace**, **Affected files**, **Current controls**, **Exposure**, and implementation-specific **Fix** details from sub-agents — these are critical for actionability. Never compress a Trace to prose in consolidation; its per-hop `file:line` and status markers are the whole point.
10. Collect the module clean-coverage notes into a single **Verified Clean** section near the end of the report, grouped by area. Include the killed candidates and the fact that killed each. A future audit reads this to avoid re-deriving the same dead ends, and a reader uses it to tell silence-because-checked from silence-because-missed.
11. If any finding carries a `[boundary]` hop, add a short **Trace Coverage** note under the summary: which components the paths reached that were not available for tracing, and that supplying them (via `--trace-scope`) could raise those findings' confidence or severity. This makes the audit's own blind spots visible instead of implicit.
12. Collect every worker's `## Unconfirmed` findings, and any finding kept at LOW under rule 5, into the report's **Unconfirmed** section. They are always included, whatever the `--include-low` setting, because a finding held low only by code outside the audited scope is unverified, not disproven. Without `--include-low`, list each as one line: title, `file:line`, module, and the missing component or unfinished hop that kept it low. With `--include-low`, give each the full finding format. They are not counted in the severity tables.
13. Include a **Findings by Exposure** table (Public-facing / Internal-network-reachable / Auth-gated-internal, each broken out by severity) alongside the Findings by Module table — this surfaces whether Critical/High risk is concentrated on the internet edge or sitting on internal-only services, which changes remediation urgency even at equal severity.

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
**Exposure:** {Public-facing | Internal-network-reachable | Auth-gated-internal}
**Category:** {category}
**Standards:** {standards references, e.g., "OWASP-Web-A05:2025, CWE-89"}
**Modules:** {module_1}, {module_2}
**Description:** {description}
**Evidence:**
\`\`\`{language}
{code snippet}
\`\`\`
**Trace:** {shape} — {one-line path statement}
1. `{file}:{line}` — {what happens here} [verified]
2. `{file}:{line}` — {what happens here} [verified]
**Breaks if:** {the control that would defeat this chain, and where it was confirmed absent or insufficient}
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
    "modules_skipped": ["terraform", ...],
    "trace_scope": ["<target path>", "<additional roots supplied via --trace-scope>"],
    "trace_boundaries": ["<reachable components that were not available to trace into>"]
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
      "exposure": "Public-facing | Internal-network-reachable | Auth-gated-internal",
      "category": "...",
      "standards": "OWASP-Web-A03:2025, CWE-79",
      "modules": ["code", "frontend"],
      "description": "...",
      "evidence": "...",
      "trace": {
        "shape": "dataflow | reachability | control-failure",
        "summary": "one-line statement of the path",
        "hops": [
          { "n": 1, "location": "src/app.py:42", "what": "...", "status": "verified" },
          { "n": 2, "location": "<external component>", "what": "...", "status": "boundary" }
        ],
        "breaks_if": "...",
        "fully_verified": false
      },
      "current_controls": "...",
      "exploit_scenario": "...",
      "fix": "..."
    }
  ],
  "unconfirmed": [
    { "title": "...", "location": "src/app.py:42", "module": "api", "held_low_by": "the missing component or unfinished hop" }
  ]
}
```
`unconfirmed` is always present (empty when there are none) and is not counted in `summary` or in the `--fail-on` check.

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
