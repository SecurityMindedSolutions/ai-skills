# Backend Audit Skill

Backend application architecture audit that dispatches parallel sub-agents across eight modules to check handler hygiene, service layer patterns, data access, error handling, and observability against enterprise standards.

**Scope distinction**: This audit targets the *server-side application layer* — handlers, services, business logic, data access, and tests. It complements `/audit-security` (exploitable vulnerabilities) and `/audit-frontend` (client-side architecture). There's intentional overlap in areas like error handling and security — this audit checks *patterns and best practices*, not *exploitability*.

## Modules

| Module | What It Checks |
|---|---|
| **architecture** | Handler thickness, service layer separation, dependency injection, framework coupling |
| **errors** | Error handling patterns, catch-all handlers, error propagation, user-facing error messages |
| **data-access** | Repository patterns, query safety, connection management, transaction handling |
| **data-contracts** | Request/response schemas, validation, serialization, API contract consistency |
| **code-quality** | Function length, naming conventions, dead code, complexity, DRY violations |
| **testing** | Test coverage patterns, mocking strategies, assertion quality, edge case coverage |
| **observability** | Logging patterns, structured logging, metrics, tracing, health checks |
| **security** | Auth middleware, input validation, secrets handling, CORS, rate limiting (pattern-focused) |

## Usage

```
/audit-backend                                   # All modules, current directory
/audit-backend architecture                      # Just architecture module
/audit-backend errors,data-access                # Two specific modules
/audit-backend all ./services/api                # All modules, specific path
/audit-backend testing ./cloud_functions         # One module, specific path
```

## Output

Report is written to `{target_path}/docs/audits/audit-backend-report-{YYYY-MM-DD}.md` containing:

- Overall scorecard (pass rate per module)
- All FAIL findings grouped together (highest priority)
- All WARN findings grouped together (watch items)
- Per-module summaries with prioritized recommendations

### Scoring

| Result | Meaning |
|---|---|
| **PASS** | The assertion holds. Code meets the standard. |
| **FAIL** | The assertion is violated. Includes file path, line number, and what's wrong. |
| **WARN** | Not violated but trending toward a problem. Includes what to watch. |
| **N/A** | The assertion doesn't apply to this codebase. |

### Finding Format

Each assertion includes:

- **Result** — PASS, FAIL, WARN, or N/A
- **File(s)** — File paths and line numbers
- **Evidence** — Code snippet showing the issue (for FAIL/WARN)
- **Analysis** — Why this passes, fails, or warrants a warning
- **Fix** — Implementation-ready remediation (for FAIL/WARN)

## File Structure

```
audit-backend/
├── skill.md              # Orchestrator prompt and execution logic
├── README.md             # This file
├── modules/
│   ├── architecture.md   # Handler and service layer patterns
│   ├── errors.md         # Error handling rules
│   ├── data-access.md    # Data access and query patterns
│   ├── data-contracts.md # Request/response schema rules
│   ├── code-quality.md   # Code quality and conventions
│   ├── testing.md        # Test patterns and coverage
│   ├── observability.md  # Logging, metrics, tracing rules
│   └── security.md       # Security best practice patterns
└── templates/
    └── report.md         # Consolidated report template
```

## Customization

- **Add a module** — Create a new `.md` file in `modules/` following the existing assertion format and add the module name to `skill.md`
- **Modify assertions** — Edit module files to adjust what's checked, add new assertions, or change thresholds
- **Change report format** — Edit `templates/report.md` to customize the output structure
