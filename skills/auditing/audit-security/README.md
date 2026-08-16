# Security Audit Skill

Comprehensive security audit that dispatches parallel sub-agents across security domains to find exploitable vulnerabilities.

## Modules

| Module | What It Scans |
|---|---|
| **code** | Injection (SQL, command, template), auth/authz gaps, weak crypto, business logic flaws, SSRF, deserialization, path traversal, file-upload + container-format confusion |
| **api** | Endpoint auth levels, input validation, mass assignment, data exposure, CORS, rate limiting, HTTP security headers, unauthenticated content-publication gating, anti-automation/CAPTCHA-enforce, email-action link safety |
| **frontend** | XSS (`dangerouslySetInnerHTML`, DOM sinks), client-side storage of secrets, postMessage without origin checks, CSP issues |
| **multi-tenancy** | Tenant-isolation: tenant-id provenance, tenant-scoped data access, central fail-closed enforcement, cross-tenant BOLA/IDOR, tenant enumeration oracles, cross-tenant resource sharing, create/delete parity, client-DB-SDK boundary (runs only when the app is multi-tenant) |
| **secrets** | Hardcoded credentials, committed `.env` files, cloud provider keys (AWS/GCP/Azure), git history leaks, CI/CD secret exposure |
| **dependencies** | Known CVEs via `pip-audit`/`npm audit`, unpinned versions, supply chain risks, dependency confusion, container base image issues |
| **terraform** | IAM wildcards, open security groups, missing encryption at rest/transit, public exposure, forwarded-host/origin isolation, app-level security-event alerting, missing logging, state management |

Each module includes false-positive suppression rules (e.g., test files, React auto-escaping, env vars as trusted input) and confidence scoring to reduce noise.

## Usage

```
/audit-security                              # All modules, current directory
/audit-security code                         # Just the code module
/audit-security code,secrets                 # Two specific modules
/audit-security all ./src                    # All modules, specific path
/audit-security terraform ./infra            # One module, specific path
/audit-security --include-low                # Include low-confidence findings
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
