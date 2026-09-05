---
description: "Comprehensive security audit with parallel sub-agents. Runs code, API, frontend, multi-tenancy (tenant-isolation), secrets, dependencies, terraform, and CI/CD modules against a target directory. Use this skill whenever the user asks to check for vulnerabilities, do a security review, pen test prep, compliance check, or wants to know if their code is secure - even if they don't say 'audit' explicitly."
user-invocable: true
allowedTools:
  - Task
  - Read
  - Glob
  - Grep
  - Bash
metadata:
  summary: "Finds exploitable vulnerabilities across code, APIs, frontend, tenancy, secrets, dependencies, Terraform and CI/CD"
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
/audit-security api ./svc --trace-scope ../shared-lib,../gateway → trace call paths into sibling repos
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

Also read `{skill_dir}/references/trace-protocol.md`. It is **not** a module — it is the shared
validation method every module uses, and its full text is passed to every sub-agent.

Read all applicable module files in parallel using the Read tool.

### Step 5: Dispatch Sub-Agents in Parallel

For each applicable module, spawn a sub-agent using the Task tool with `subagent_type: "general-purpose"`.

**CRITICAL**: Launch ALL applicable sub-agents in a SINGLE message with multiple Task tool calls for maximum parallelism.

Each sub-agent prompt MUST include:
1. The system context summary (from Step 2)
2. The full module prompt content (read from the module file)
3. **The full text of `references/trace-protocol.md`** — every module validates findings the same way, so this is passed verbatim to every sub-agent, not summarized
4. The target path to scan, and the trace scope (target path + any `--trace-scope` roots)
5. The standardized output format

**Sub-agent prompt template**:
```
You are conducting a security audit. Your module is: {MODULE_NAME}

TARGET PATH (findings are reported only against files here): {target_path}
TRACE SCOPE (you may READ anything here to follow a path; do not report findings outside TARGET PATH): {target_path}{, plus each --trace-scope root, each named}
{If no --trace-scope roots were supplied and the recon found sibling components the paths may reach, add: "NOTE: the following components appear reachable from the target but were NOT supplied for tracing — treat any path into them as a [boundary] hop: {list}. Say so in the finding, per the trace protocol."}

SYSTEM CONTEXT (discovered by orchestrator — use this to understand the architecture):
{SYSTEM_CONTEXT_SUMMARY}

Use the system context above to understand how components interact. When tracing data flows or trust boundaries, consider how input in one service may reach another. If the system context is sparse, read CLAUDE.md or README.md files in the target path for additional context.

{MODULE_PROMPT_CONTENT}

TRACE PROTOCOL — this is a GATE on every finding, not documentation. Read it in full and apply it
before you report anything. A candidate you have not traced is an observation, not a finding; the
falsification pass in §5 is what tells you whether it is real. Findings are reported with a
`**Trace:**` field in the format defined in §6, and your confidence score is derived from the
weakest verification marker on the chain per §3 — it is not a separate judgement.

{TRACE_PROTOCOL_CONTENT}

FALSE POSITIVE RULES — Do NOT report findings that match these:
1. Test files: Vulnerabilities in unit tests or test-only code are not exploitable.
2. React/Angular XSS: These frameworks auto-escape output. Only flag XSS if using `dangerouslySetInnerHTML`, `bypassSecurityTrustHtml`, `v-html`, or similar explicit bypass methods.
3. Environment variables and CLI flags are trusted inputs. Do not flag code that uses env vars or CLI args as "user-controlled input."
4. SSRF path-only: SSRF is only a real finding if the attacker can control the host or protocol. Controlling just the URL path is not exploitable SSRF — **but** only apply this exemption when the code demonstrably treats the input as a path: it's captured as a distinct path segment by a router (not concatenated into an existing base URL), or, if concatenated, the value is validated/parsed first to reject anything that isn't a bare path (reject a leading scheme, `//`, `@`, backslash, and require the result to start with `/`). A value that is concatenated directly onto a base URL string with no such validation is NOT path-only — URL parsers (browsers, `axios`/`fetch`/`urllib`/etc.) reinterpret a leading `@` or `//` in that position as a new host/authority, so "just the path" is actually host control. Apply the same host-confusion scrutiny here as you would to an open-redirect or OAuth `redirect_uri` check — it's the same underlying defect (untrusted string reaches a URL-consuming sink without real parsing/allowlisting), whether the sink is a browser navigation or a server-side outbound request.
5. Theoretical race conditions: Only flag race conditions with a concrete exploitation path and real impact (e.g., financial double-spend, auth bypass), not theoretical TOCTOU.
6. Shell script command injection: Only flag if untrusted user input can reach the shell command. Scripts that only use hardcoded values or env vars are not vulnerable.
7. UUIDs are unguessable. Do not flag UUID-based access as an authorization issue.
8. Client-side auth checks: Missing permission checks in frontend JS/TS are not vulnerabilities — authorization is enforced server-side.
9. Log content: Logging URLs, request IDs, or non-PII data is not a vulnerability. Only flag logging of secrets, passwords, or PII.
10. Documentation files: Do not report findings in markdown, text, or documentation files.
11. CI/CD pipeline variables: Build-time variables injected by CI systems ($CI_*, $GITHUB_*, $BUILDKITE_*) are not secrets and should not be flagged as hardcoded credentials.

CONFIDENCE SCORING — derived from the trace, per trace-protocol §3. Do not score on impression:
- HIGH (8-10): Every hop on the chain is `[verified]`. You walked the whole path and read each step.
- MEDIUM (6-7): The chain holds but carries at least one `[inferred]`, `[assumed]`, or `[boundary]`
  hop on the authorization, reachability, or input-control segment. This is the ceiling for any
  finding whose path leaves the trace scope.
- LOW (1-5): Two or more `[assumed]` hops, or the source or sink itself is unverified.

If the falsification pass BREAKS the chain, the candidate is dropped entirely rather than
downgraded — and recorded in your clean-coverage note per trace-protocol §7, so the next run does
not re-derive it.

{If --include-low: "Include ALL findings regardless of confidence." Otherwise: "Only include findings with confidence >= 6 (HIGH or MEDIUM). Do NOT report LOW confidence findings."}

SEVERITY CALIBRATION — Testing "Bounded"/"Mitigating" Claims:
Before writing anything into **Current controls** that would lower a finding's
severity (a claim that impact is "bounded," "self-healing," "low-probability,"
or "requires an already-privileged caller"), stress-test the claim itself:
- If the claim rests on a time window (a cache TTL, a reconciliation/resync
  interval, a token expiry) — could the attacker simply repeat the triggering
  action faster than that window, making the "bounded" impact actually
  unbounded/indefinite? Check whether the trigger has its own rate limit or
  auth gate before accepting the bound as real.
- If the claim rests on "the caller must already hold valid credentials" —
  does holding those credentials grant only ordinary access, or does the
  finding itself grant something beyond what those credentials should allow
  (privilege escalation, cross-tenant access, disabling a security control)?
  A precondition of "authenticated" does not make a privilege-escalation or
  cross-tenant finding low severity.
- Write the mitigating claim AND the stress-test result into **Current
  controls** explicitly (e.g., "resyncs every 15 min, but the reset endpoint
  has no rate limit, so a looping caller defeats this bound — treated as
  unbounded/indefinite, not one-shot"). A downgrade that isn't tested this way
  is a guess, not an assessment.

OUTPUT FORMAT:
Return your findings as a markdown list. For each finding, use this exact format:

### {SEVERITY}-{NUMBER}: {Title}

**Status:** OPEN
**File:** `{relative_path}:{line_number}`
**Affected files:** List ALL files that would need changes to remediate this finding, not just the primary file. Use relative paths. If only one file, repeat the primary file.
**Severity:** Critical | High | Medium | Low | Informational
**Confidence:** HIGH | MEDIUM | LOW
**Exposure:** {How this finding is actually reachable, independent of severity — one of: "Public-facing" (reachable from the open internet with no network-level gate), "Internal-network-reachable" (requires being on the VPC/mesh/internal network already, but no further credentials), "Auth-gated-internal" (requires both internal network access AND a valid credential/session). Base this on real deployment evidence (ingress/ALB scheme, security group rules, service mesh config) discovered in Step 2, not on assumption from the repo's name or docs. This is a distinct axis from Severity — an Internal-network-reachable finding can still be Critical if its impact is severe; the field exists so prioritization can weigh "how bad" and "how reachable" separately instead of one field trying to encode both.}
**Category:** {category from module}
**Standards:** {List the standards/frameworks this finding maps to, from the `<!-- Standards: -->` comment on the category header. Example: "OWASP-Web-A05:2025, CWE-89". If no comment exists, infer the most applicable standard.}
**Description:** {What the vulnerability is and why it matters — be specific about the mechanism}
**Evidence:**
```{language}
{Actual code snippet showing the vulnerability. Include enough surrounding context (function name, relevant variables) that a developer can locate and understand it without opening the file.}
```
**Trace:** {REQUIRED. The validated path, in the format defined in trace-protocol §6: the shape
(dataflow | reachability | control-failure), a one-line statement of the path, then one numbered
hop per step — each with `file:line` and a `[verified]` / `[inferred]` / `[assumed]` / `[boundary]`
marker — followed by a `**Breaks if:**` line naming the control that would defeat the chain and
where you confirmed it is absent or insufficient. Hop count equals real path length; a
same-line source and sink is a one-hop trace. Evidence shows WHERE the defect is; Trace shows THAT
it is reachable, and is what makes the finding checkable by someone who did not do the work.}
**Current controls:** {What security measures are ALREADY in place that partially mitigate this risk — e.g., "input is tenant-scoped so only affects the attacker's own tenant", "WAF blocks common payloads at the edge", "data source is trusted (Secret Manager)". Write "None" if no mitigations exist. This field helps prioritize — a finding with strong existing controls is lower real-world risk.}
**Exploit scenario:** {Step-by-step attack scenario: (1) attacker does X, (2) this causes Y, (3) resulting in Z impact. Be concrete — name the endpoint, parameter, or field involved. This is the Trace told as a story and MUST NOT contain a step the Trace does not support — if it does, either the trace is incomplete (go finish it) or the step is speculation (cut it). Start from the weakest principal for which the path holds, and state it.}
**Fix:** {Implementation-ready remediation. Include:
- Which files to modify and what to change in each
- Specific function/method names to update
- Code pattern to use (e.g., "replace f-string with parameterized query using `:param` syntax")
- Any config changes needed (Terraform, env vars, etc.)
- Order of operations if changes span multiple files/services
This should be detailed enough that a coding agent can implement the fix without re-reading the vulnerable code from scratch.}

If you find no issues for a category, do not include it. Only report real findings, not theoretical concerns. Prioritize findings that are actually exploitable over pattern-matching noise.

At the end, include BOTH of the following:

1. A clean-coverage note — a short section listing what you checked and cleared, especially any
   candidate the falsification pass killed and the specific fact that killed it (a global control
   that supplies the missing guard, an upstream type constraint, a package that is never loaded).
   State it as "checked X, holds because Y", not as an absence. This is what distinguishes "the
   audit did not look" from "the audit looked and it holds", and it stops the next run
   re-investigating the same dead end.
2. The summary count:
**{MODULE_NAME} Module Summary**: X Critical, X High, X Medium, X Low, X Informational
```

### Step 6: Consolidate Report

After all sub-agents complete, consolidate findings into a single report.

Read the report template from `{skill_dir}/templates/report.md` and fill it in with:
1. Executive summary with overall posture assessment
2. Finding summary table (counts by severity)
3. All findings grouped by severity (Critical → Informational), with module tag on each
4. Deduplicate any findings that overlap between modules (e.g., code + api might both flag the same SQL injection). When deduplicating, merge the affected files lists and keep the most detailed fix instructions. **Merge the traces too, and prefer the better-verified one** — if one module reached a hop by reading it and another assumed it, keep the `[verified]` hop and raise the merged finding's confidence accordingly. Two modules independently tracing the same path to the same conclusion is corroboration; say so on the merged finding.
5. Drop any finding whose **Trace** is missing, or whose Trace does not actually connect its stated source to its stated sink. An untraced finding was not validated, and shipping it spends the reader's trust on something nobody checked. If it looks important, send the module agent back for the trace rather than publishing it unverified.
6. Drop any findings with MEDIUM confidence that lack a concrete exploit scenario, and any whose Exploit scenario asserts a step the Trace does not support.
7. Assign sequential IDs: C-1, H-1, M-1, L-1, I-1 (by severity)
8. All findings start with **Status:** OPEN and blank **Remediation notes:** (these get filled in during triage)
9. Preserve the **Trace**, **Affected files**, **Current controls**, **Exposure**, and implementation-specific **Fix** details from sub-agents — these are critical for actionability. Never compress a Trace to prose in consolidation; its per-hop `file:line` and status markers are the whole point.
10. Collect the module clean-coverage notes into a single **Verified Clean** section near the end of the report, grouped by area. Include the killed candidates and the fact that killed each. A future audit reads this to avoid re-deriving the same dead ends, and a reader uses it to tell silence-because-checked from silence-because-missed.
11. If any finding carries a `[boundary]` hop, add a short **Trace Coverage** note under the summary: which components the paths reached that were not available for tracing, and that supplying them (via `--trace-scope`) could raise those findings' confidence or severity. This makes the audit's own blind spots visible instead of implicit.
12. Include a **Findings by Exposure** table (Public-facing / Internal-network-reachable / Auth-gated-internal, each broken out by severity) alongside the Findings by Module table — this surfaces whether Critical/High risk is concentrated on the internet edge or sitting on internal-only services, which changes remediation urgency even at equal severity.

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
