# Auditing

Codebase review, one skill per layer.

All three dispatch parallel sub-agents, one per module, and consolidate their findings
into a single report. They overlap deliberately: the security audit asks whether
something is *exploitable*, while the frontend and backend audits ask whether the
*pattern* is sound. Every report lands in `{target_path}/docs/audits/`.

To add a module to any of them, drop a new `.md` file in that skill's `modules/`
following the existing format and add the module name to its `SKILL.md`. To change
the report layout, edit the skill's `templates/report.md`. The scoring scale and the
format each module worker returns live in `references/worker-brief.md`.

### Lighter workers (optional)

Each module runs in its own sub-agent. By default that is Claude Code's
`general-purpose` agent, which starts with every tool your session has (MCP servers
included), the full default system prompt and your CLAUDE.md files, once per module.

Each audit ships `agents/ai-skills-readonly.md`, a worker definition with only Read,
Grep, Glob and Bash, no CLAUDE.md and a short system prompt. The first time an audit
runs without it installed, it offers to copy it to `~/.claude/agents/` and shows you the
file first. Pick **Don't ask again** to stop the offer. It takes effect from your next
session. To install it by hand:

```bash
mkdir -p ~/.claude/agents
cp ~/.claude/skills/audit-security/agents/ai-skills-readonly.md ~/.claude/agents/
```

All three audits share the same file. Read-only is enforced by the tool list for file
edits, but Bash is unrestricted so the scanners can run; the "never modify the target"
rule for Bash is an instruction, not a sandbox.

The orchestrator also passes each worker the *paths* of its module and brief rather than
pasting their text, so the main session never loads every module's checks.

---

## `/audit-security`

Finds exploitable vulnerabilities, with every finding gated on a walked path that
proves it is reachable.

### Modules

| Module | What it scans |
|---|---|
| **code** | Injection (SQL, command, template), auth/authz gaps, weak crypto, business logic flaws, SSRF, deserialization, path traversal, file-upload and container-format confusion, deletion integrity (partial batch failures, swallowed delete errors, versioned/soft-delete stores, destructive migrations) |
| **api** | Endpoint auth levels, credential/session revocation propagation through auth caches, fail-open authorization on a missing associated record, input validation, mass assignment, data exposure, filtered-vs-unfiltered accessor bypass, CORS, rate limiting (including self-healing claims tested against a looping trigger), HTTP security headers, CSRF incl. mutating GET routes, unauthenticated content-publication gating, anti-automation/CAPTCHA-enforce, email-action link safety |
| **frontend** | XSS (`dangerouslySetInnerHTML`, DOM sinks), client-side storage of secrets, postMessage without origin checks, CSP issues |
| **extension** | Browser extensions (Chrome, Firefox, Edge and Safari; runs when a `manifest.json` has `manifest_version`), with every category mapped to OWASP ASVS 5.0 and the release chain to NIST SSDF and SLSA: permission and host scope, extension CSP, `externally_connectable` and message sender validation, confused-deputy content-script messages, content scripts in hostile pages (DOM skimming, closed shadow root leaks, clobbering), token storage (`storage.local`/`session`/`sync`, access level), page content flowing into extension pages and LLMs, remote code and the shipped bundle (rebuilt and hash-diffed), MV3 lifecycle and check-then-inject races, DOM-based extension clickjacking, hidden text and invisible Unicode reaching LLMs, release chain (dev UI or wording in prod builds, extension id consistency across store, app and backend, store uploads that refuse a manifest `key`, a frozen version defeating a min-version kill switch, sideloaded package integrity, release gates that pin only some manifest fields, live branch-rule drift), privacy and store policy conformance (a data-flow inventory compared against the privacy policy, store listing and in-product disclosures, Chrome Limited Use, Firefox `data_collection_permissions` and AMO source upload, Safari privacy details), plus a "Store readiness notes" section in the report. Runs as three parallel agents on extensions over ~2,000 lines |
| **multi-tenancy** | Tenant-id provenance, tenant-scoped data access, central fail-closed enforcement, cross-tenant BOLA/IDOR, tenant enumeration oracles, cross-tenant resource sharing, create/delete parity, client-DB-SDK boundary (runs only when the app is multi-tenant) |
| **secrets** | Hardcoded credentials, committed `.env` files, cloud provider keys (AWS/GCP/Azure), git history leaks, CI/CD secret exposure |
| **dependencies** | Known CVEs via `pip-audit`/`npm audit`, unpinned versions, supply chain risks, dependency confusion, container base image issues |
| **terraform** | IAM wildcards, open security groups, missing encryption at rest/transit, public exposure, forwarded-host/origin isolation, app-level security-event alerting, missing logging, state management |

Each module carries false-positive suppression rules (test files, React auto-escaping,
env vars as trusted input) and confidence scoring to reduce noise.

### Trace validation

Every finding must carry a **Trace**: the walked path that proves the defect is
reachable, defined in
[`audit-security/references/trace-protocol.md`](audit-security/references/trace-protocol.md)
and applied identically by all modules.

Pattern matching finds candidate lines. Most false positives are real code on an
*unreachable* path: a dangerous sink whose input is constrained upstream, a missing
guard on a route nothing routes to, an over-broad permission on an identity nothing
assumes, a vulnerable package that never loads. Those look identical to true positives
at the line level, so the skill treats walking the path as a **gate** rather than as
documentation:

- **Three trace shapes** cover every finding type: *dataflow* (untrusted source to
  sink), *reachability* (weakest principal to capability), and *control-failure* (a
  control that exists but cannot do its job, such as fail-open defaults, guards
  applied to the wrong object, checks that cannot fail).
- **Every hop cites `file:line`** and is marked `[verified]` (read directly),
  `[inferred]` (derived from something read), `[assumed]` (not checkable), or
  `[boundary]` (path left the available code).
- **Confidence is derived from the weakest marker**, not scored by impression. All
  hops verified gives HIGH; anything assumed or out of scope on the
  auth/reachability segment is capped at MEDIUM.
- **A mandatory `Breaks if:` line** names the control that would refute the finding
  and where it was confirmed absent. A candidate whose chain breaks under that check
  is *dropped*, not downgraded, and is recorded under **Verified Clean** so future
  runs do not re-derive it.

**Cross-repository tracing.** When a path leaves the target tree, into a sibling repo,
shared library, or companion service, pass those roots with `--trace-scope` and they
become readable for tracing (they are still never scanned for findings of their own).
Without them the hop is marked `[boundary]`, the assumption made about it is stated in
the weakening direction, confidence is capped, and the report's **Trace Coverage**
section names what was missing. That way a low-confidence finding caused by absent
code stays distinguishable from one caused by weak evidence.

### Usage

```
/audit-security                              # All modules, current directory
/audit-security code                         # Just the code module
/audit-security code,secrets                 # Two specific modules
/audit-security all ./src                    # All modules, specific path
/audit-security terraform ./infra            # One module, specific path
/audit-security extension ./extension        # Browser extension module only
/audit-security --include-low                # Include low-confidence findings
/audit-security api ./svc --trace-scope ../shared-lib,../gateway   # Follow call paths into sibling repos
/audit-security code ./src --include-low     # Combine all options
```

### Output

Written to `{target_path}/docs/audits/audit-security-report-{YYYY-MM-DD}.md`:
an executive summary with overall risk posture, finding counts by severity and
module, then each finding with severity, confidence, evidence, existing mitigations,
a step-by-step exploit scenario, and implementation-ready fix instructions.

| Severity | Meaning |
|---|---|
| **Critical** | Actively exploitable with high impact |
| **High** | Exploitable with significant impact |
| **Medium** | Exploitable under specific conditions |
| **Low** | Minor issue or limited impact |
| **Informational** | Best practice recommendation |

Confidence is **HIGH** (8-10) for a clear vulnerability with a concrete attack path,
**MEDIUM** (6-7) for a suspicious pattern likely exploitable under specific conditions,
and **LOW** (1-5) for a theoretical concern. Low is excluded by default; pass
`--include-low` to see everything.

Each finding carries its file and line number, all affected files rather than just the
primary one, an **Exposure** rating (public-facing, internal-network-reachable, or
auth-gated-internal) kept separate from severity so reachability and impact can be
weighed independently, the current controls already in place, a concrete exploit
scenario, and the specific files, functions and code patterns to change.

Findings start as `OPEN` and move to `IN PROGRESS`, `RESOLVED`, or `ACCEPTED RISK`.
Resolved findings get strikethrough titles so they are easy to scan past in rendered
Markdown.

---

## `/audit-frontend`

Reviews client-side architecture against enterprise standards.

### Modules

| Module | What it checks |
|---|---|
| **design-tokens** | CSS variable usage, theme consistency, hardcoded values, dark mode strategy, spacing/color systems |
| **components** | Component structure, prop patterns, reusability, composition, shared component usage |
| **accessibility** | ARIA attributes, keyboard navigation, focus management, color contrast, screen reader support |
| **performance** | Bundle size, lazy loading, image optimization, render performance, caching strategies |
| **code-quality** | TypeScript strictness, linting, naming conventions, file organization, dead code |
| **security** | XSS vectors, client-side secret storage, CSP, postMessage handling, third-party script risks |
| **seo-meta** | Meta tags, Open Graph, structured data, canonical URLs, sitemap |

### Usage

```
/audit-frontend                              # All modules, current directory
/audit-frontend components                   # Just components module
/audit-frontend accessibility,performance    # Two specific modules
/audit-frontend all ./src                    # All modules, specific path
/audit-frontend design-tokens ./app          # One module, specific path
```

### Output

Written to `{target_path}/docs/audits/audit-frontend-report-{YYYY-MM-DD}.md`:
an executive summary, a scorecard table counting results by module, all findings
grouped by module with file paths and line numbers, and prioritized recommendations.

| Rating | Meaning |
|---|---|
| **PASS** | Meets enterprise standards. No action needed. |
| **NEEDS IMPROVEMENT** | Partially meets standards. Specific improvements identified. |
| **FAIL** | Does not meet standards. Critical issues that should be fixed. |

Each finding lists the key files examined, what was found with paths and line numbers,
and specific actionable fixes for anything not rated PASS.

---

## `/audit-backend`

Reviews the server-side application layer: framework, middleware, handlers, services,
business logic, data access, and tests.

### Modules

| Module | What it checks |
|---|---|
| **architecture** | Handler thickness, service layer separation, dependency injection, framework coupling |
| **errors** | Error handling patterns, catch-all handlers, error propagation, user-facing error messages |
| **data-access** | Repository patterns, query safety, connection management, transaction handling, delete verification and destructive-migration scoping |
| **data-contracts** | Request/response schemas, validation, serialization, API contract consistency |
| **code-quality** | Function length, naming conventions, dead code, complexity, DRY violations |
| **testing** | Test coverage patterns, mocking strategies, assertion quality, edge case coverage |
| **observability** | Logging patterns, structured logging, metrics, tracing, health checks |
| **security** | Auth middleware, input validation, secrets handling, CORS, rate limiting (pattern-focused) |

### Usage

```
/audit-backend                                   # All modules, current directory
/audit-backend architecture                      # Just architecture module
/audit-backend errors,data-access                # Two specific modules
/audit-backend all ./services/api                # All modules, specific path
/audit-backend testing ./cloud_functions         # One module, specific path
```

### Output

Written to `{target_path}/docs/audits/audit-backend-report-{YYYY-MM-DD}.md`:
an overall scorecard with a pass rate per module, all FAIL findings grouped together
as the highest priority, all WARN findings grouped as watch items, then per-module
summaries with prioritized recommendations.

| Result | Meaning |
|---|---|
| **PASS** | The assertion holds. Code meets the standard. |
| **FAIL** | The assertion is violated. Includes file path, line number, and what is wrong. |
| **WARN** | Not violated but trending toward a problem. Includes what to watch. |
| **N/A** | The assertion does not apply to this codebase. |

Each assertion reports its result, the files and line numbers involved, a code snippet
as evidence, an analysis of why it passes or fails, and implementation-ready
remediation for anything not passing.
