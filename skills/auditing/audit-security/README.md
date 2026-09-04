# Security Audit Skill

Comprehensive security audit that dispatches parallel sub-agents across security domains to find exploitable vulnerabilities.

## Modules

| Module | What It Scans |
|---|---|
| **code** | Injection (SQL, command, template), auth/authz gaps, weak crypto, business logic flaws, SSRF, deserialization, path traversal, file-upload + container-format confusion |
| **api** | Endpoint auth levels, credential/session revocation propagation through auth caches, fail-open authorization on a missing associated record, input validation, mass assignment, data exposure, filtered-vs-unfiltered accessor bypass, CORS, rate limiting (including self-healing claims tested against a looping trigger), HTTP security headers, CSRF incl. mutating GET routes, unauthenticated content-publication gating, anti-automation/CAPTCHA-enforce, email-action link safety |
| **frontend** | XSS (`dangerouslySetInnerHTML`, DOM sinks), client-side storage of secrets, postMessage without origin checks, CSP issues |
| **multi-tenancy** | Tenant-isolation: tenant-id provenance, tenant-scoped data access, central fail-closed enforcement, cross-tenant BOLA/IDOR, tenant enumeration oracles, cross-tenant resource sharing, create/delete parity, client-DB-SDK boundary (runs only when the app is multi-tenant) |
| **secrets** | Hardcoded credentials, committed `.env` files, cloud provider keys (AWS/GCP/Azure), git history leaks, CI/CD secret exposure |
| **dependencies** | Known CVEs via `pip-audit`/`npm audit`, unpinned versions, supply chain risks, dependency confusion, container base image issues |
| **terraform** | IAM wildcards, open security groups, missing encryption at rest/transit, public exposure, forwarded-host/origin isolation, app-level security-event alerting, missing logging, state management |

Each module includes false-positive suppression rules (e.g., test files, React auto-escaping, env vars as trusted input) and confidence scoring to reduce noise.

## Trace validation

Every finding must carry a **Trace**: the walked path that proves the defect is reachable, defined
in [`references/trace-protocol.md`](./references/trace-protocol.md) and applied identically by all
modules.

Pattern matching finds candidate lines. Most false positives are real code on an *unreachable*
path — a dangerous sink whose input is constrained upstream, a missing guard on a route nothing
routes to, an over-broad permission on an identity nothing assumes, a vulnerable package that never
loads. Those look identical to true positives at the line level, so the skill treats walking the
path as a **gate** rather than as documentation:

- **Three trace shapes** cover every finding type: *dataflow* (untrusted source → sink), *reachability*
  (weakest principal → capability), and *control-failure* (a control that exists but cannot do its
  job — fail-open defaults, guards applied to the wrong object, checks that cannot fail).
- **Every hop cites `file:line`** and is marked `[verified]` (read directly), `[inferred]` (derived
  from something read), `[assumed]` (not checkable), or `[boundary]` (path left the available code).
- **Confidence is derived from the weakest marker**, not scored by impression. All hops verified →
  HIGH; anything assumed or out of scope on the auth/reachability segment → capped at MEDIUM.
- **A mandatory `Breaks if:` line** names the control that would refute the finding and where it was
  confirmed absent. A candidate whose chain breaks under that check is *dropped*, not downgraded,
  and is recorded under **Verified Clean** so future runs don't re-derive it.

**Cross-repository tracing.** When a path leaves the target tree — into a sibling repo, shared
library, or companion service — pass those roots with `--trace-scope` and they become readable for
tracing (they are still never scanned for findings of their own). Without them the hop is marked
`[boundary]`, the assumption made about it is stated in the weakening direction, confidence is
capped, and the report's **Trace Coverage** section names what was missing — so a low-confidence
finding caused by absent code is distinguishable from one caused by weak evidence.

## Usage

```
/audit-security                              # All modules, current directory
/audit-security code                         # Just the code module
/audit-security code,secrets                 # Two specific modules
/audit-security all ./src                    # All modules, specific path
/audit-security terraform ./infra            # One module, specific path
/audit-security --include-low                # Include low-confidence findings
/audit-security api ./svc --trace-scope ../shared-lib,../gateway   # Follow call paths into sibling repos
/audit-security code ./src --include-low     # Combine all options
```

## Output

Report is written to `{target_path}/docs/audits/audit-security-report-{YYYY-MM-DD}.md` containing:

- Executive summary with overall risk posture
- Finding counts by severity and module
- Each finding with: severity, confidence, evidence (code snippets), existing mitigations, step-by-step exploit scenario, and implementation-ready fix instructions

### Finding Severity Levels

| Severity | Meaning |
|---|---|
| **Critical** | Actively exploitable with high impact |
| **High** | Exploitable with significant impact |
| **Medium** | Exploitable under specific conditions |
| **Low** | Minor issue or limited impact |
| **Informational** | Best practice recommendation |

### Confidence Scoring

- **HIGH** (8-10): Clear vulnerability with concrete attack path
- **MEDIUM** (6-7): Suspicious pattern, likely exploitable under specific conditions
- **LOW** (1-5): Theoretical concern — excluded by default, include with `--include-low`

### Finding Format

Every finding includes enough detail to act on immediately:

- **File & line number** — Where the vulnerability lives
- **Affected files** — All files that need changes, not just the primary one
- **Exposure** — Public-facing, Internal-network-reachable, or Auth-gated-internal — kept separate from Severity so reachability and impact can be weighed independently
- **Current controls** — Existing mitigations already in place
- **Exploit scenario** — Concrete step-by-step attack path
- **Fix** — Specific files, functions, and code patterns to change

### Triage Workflow

Findings start as `OPEN` and can be updated to:

| Status | Meaning |
|---|---|
| `OPEN` | Not yet triaged |
| `IN PROGRESS` | Remediation underway |
| `RESOLVED` | Fix implemented |
| `ACCEPTED RISK` | Risk acknowledged, no fix planned |

Resolved findings get strikethrough titles for visual scanning in rendered Markdown.

## File Structure

```
audit-security/
├── SKILL.md              # Orchestrator prompt and execution logic
├── README.md             # This file
├── modules/
│   ├── code.md           # Application code review rules
│   ├── api.md            # API endpoint security rules
│   ├── frontend.md       # Client-side security rules
│   ├── multi-tenancy.md  # Tenant-isolation rules (multi-tenant apps)
│   ├── secrets.md        # Credential and secret scanning rules
│   ├── dependencies.md   # Dependency and supply chain rules
│   └── terraform.md      # Infrastructure-as-code rules
└── templates/
    └── report.md         # Consolidated report template
```

## Customization

- **Add a module** — Create a new `.md` file in `modules/` following the existing format and add the module name to `SKILL.md`
- **Adjust false-positive rules** — Edit the false-positive suppression rules in `SKILL.md`
- **Change confidence threshold** — By default, only HIGH and MEDIUM confidence findings are reported. Use `--include-low` to see everything
