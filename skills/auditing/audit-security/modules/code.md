# Code Security Review Module

Review application code for security vulnerabilities. Focus on real exploitable issues, not theoretical patterns.

## Categories to Review

### 1. Injection Vulnerabilities
<!-- Standards: OWASP-Web-A05:2025, CWE-89, CWE-78, CWE-94, CWE-77 -->
- **SQL Injection**: Parameterized queries vs string interpolation/f-strings in SQL. Check for second-order injection (DB-stored values interpolated into later queries).
- **Command Injection**: `os.system`, `subprocess` with `shell=True`, `eval()`, `exec()`
- **Template Injection**: User input in template rendering (Jinja2, Handlebars, etc.)
- **LDAP/XML Injection**: If applicable to the codebase

### 2. Authentication & Authorization
<!-- Standards: OWASP-Web-A01:2025, OWASP-Web-A07:2025, OWASP-API1:2023, OWASP-API5:2023, CWE-862, CWE-863, CWE-306, CWE-639 -->
- Missing auth checks on endpoints that should require authentication
- Privilege escalation paths (can a lower-role user access higher-role functionality?)
- Session management flaws (predictable tokens, missing expiry, no invalidation)
- Multi-tenant isolation failures (queries missing `tenant_id` scoping)
- CSRF protection gaps on state-changing operations

### 3. Cryptography & Randomness
<!-- Standards: OWASP-Web-A04:2025, OWASP Proactive Controls C2 -->
- Non-cryptographic PRNG used for security values (`random` module instead of `secrets`)
- Weak hashing (MD5, SHA1 for security purposes)
- Hardcoded encryption keys or IVs
- Missing or improper TLS validation (`verify=False`)
- **Inconsistent crypto across similar flows**: If one OAuth/auth flow encrypts state and another uses plain JSON, flag the unprotected flow. Check ALL flows, not just the first one found.

### 4. Business Logic Flaws
<!-- Standards: OWASP-Web-A06:2025 -->
- Race conditions (TOCTOU: check-then-act without atomicity)
- Self-action bypasses (can a user perform actions on themselves that should be blocked?)
- State machine violations (can steps be skipped or reordered?)
- Numeric overflow/underflow in financial calculations
- Missing validation on state transitions
- **Dict merge key override**: When a dict is built from explicit fields and then merged with a user-supplied dict (e.g., `target_data.update(parameters)`), the merge can overwrite protected keys. Look for `dict.update()`, `{**dict1, **dict2}`, or `Object.assign()` where user-controlled data merges into a dict that already has security-relevant keys (user IDs, tenant IDs, target identifiers). The fix is to only add keys that don't already exist, or use an explicit allowlist.
- **Multi-consumer authorization inconsistency**: When the same authorization function is called from multiple consumers (e.g., web API, public API, MCP server, CLI), verify all consumers pass the same parameters. A centralized `authorize(action_type=...)` that checks per-resource permissions only works if every caller passes `action_type`. If one caller omits it, the granular checks are silently skipped. Trace the authorize function's conditional logic (e.g., `if action_type is not None: check_permissions()`) and verify every call site passes all required parameters.
- **Permission level mismatch on operations**: Write/destructive operations (delete, revoke, modify) should not use read-level permission checks. Look for route configs where a state-changing method (POST, PUT, DELETE) uses a read-scoped permission (e.g., `feature_role="read:*"` or `permission="view"`).

### 5. Error Handling & Information Disclosure
<!-- Standards: OWASP-Web-A10:2025, CWE-200 -->
- Internal exception details (`str(e)`, stack traces) returned to clients
- Debug endpoints or flags accessible in production
- Verbose error messages that reveal implementation details
- Logging sensitive data (passwords, tokens, PII)

### 6. SSRF & Outbound Request Safety
<!-- Standards: OWASP-API7:2023, CWE-918, OWASP Proactive Controls C10 -->
- User-controlled URLs passed to HTTP clients without validation
- Blocklist-based URL validation (bypassable with encoding tricks)
- Missing DNS resolution checks before outbound requests
- Redirect following that could reach internal services

### 7. File Operations
<!-- Standards: CWE-22 -->
- Path traversal (user input in file paths without sanitization)
- Unsafe file uploads (missing type/size validation, stored in webroot)
- Predictable temporary filenames
- Symlink following vulnerabilities

### 8. Deserialization
<!-- Standards: CWE-502, OWASP-Web-A08:2025 -->
- `pickle.loads`, `yaml.load` (without SafeLoader), `eval` on untrusted data
- JSON parsing without schema validation where structure matters for security

### 9. Unsafe Third-Party API Consumption
<!-- Standards: OWASP API10:2023 -->
- Are responses from external/third-party APIs validated or typed before use (not blindly trusted)?
- Is a timeout configured on all outbound HTTP calls (`requests.get(url, timeout=...)`)? Missing timeout = potential hang forever.
- Is error handling in place for external API failures (no crash-on-500, no unhandled exceptions)?
- Is TLS verification enabled on outbound requests (no `verify=False` in production code)?
- Are response size limits enforced when consuming external APIs (prevent memory exhaustion from oversized responses)?
- Is retry logic present for transient failures (429, 5xx) with backoff?

### 10. File Upload Security
<!-- Standards: CWE-434, OWASP Proactive Controls C3 -->
- Is file type validated via allowlist (not blocklist, not just extension — check magic bytes / MIME type)?
- Are file size limits enforced before reading the full upload into memory?
- Are uploaded files stored outside the webroot (not in a publicly accessible directory)?
- Are filenames generated randomly (not using user-supplied filenames — prevents path traversal)?
- Is Content-Type of the upload validated (not just trusted from the client)?
- Are uploaded files scanned for malware or suspicious content where applicable?
- Are temporary files cleaned up after processing?
- **Container-format confusion (magic-byte collision)**: OOXML documents (`.docx`/`.xlsx`/`.pptx`)
  and many archives (`.zip`/`.jar`/`.apk`/`.epub`) share the identical `PK\x03\x04` ZIP magic.
  Magic-byte validation alone therefore **cannot** distinguish a legitimate `.docx` from a bare ZIP
  (or a JAR) renamed to `.docx` — the renamed archive passes signature checks and gets stored as a
  trusted document, turning the app into arbitrary file hosting under an innocuous name/extension
  (and, if the content is later opened by a client that trusts the extension, a delivery vector).
  For `PK`-magic uploads, validate the **container's internal structure** (e.g. presence of
  `[Content_Types].xml` plus the format-specific subtree — `word/`, `xl/`, `ppt/` — via a
  `zipfile`/zip reader), not just the leading bytes. Flag upload validators that allowlist OOXML
  extensions but only check magic bytes.

### 11. Serverless Event-Source Injection
<!-- Standards: OWASP Serverless SAS-1, CNAS-2 -->
- Are Pub/Sub message payloads validated and decoded safely before use (not blindly parsed as trusted JSON)?
- Is GCS trigger event data (filename, bucket name) validated before use in file operations or queries?
- Are Cloud Scheduler payloads treated as potentially untrusted (validate structure and content)?
- Are event-driven function inputs treated with the same suspicion as HTTP request inputs?
- Are message attributes from event sources validated (not used directly in queries or commands)?

## Scanning Approach

1. Read architecture docs (CLAUDE.md, README.md) to understand frameworks, auth patterns, and data flows
2. Identify the auth/authorization framework and verify it's applied consistently
3. Trace data flows from user input to database queries and outbound requests
4. Check for consistency in security patterns (are some endpoints missing protections others have?)
5. Look for business logic issues that pattern matching won't catch
6. Verify cryptographic choices are appropriate

## Patterns to Grep For

```
# SQL injection
f".*SELECT|f".*INSERT|f".*UPDATE|f".*DELETE|\.format\(.*SELECT|%s.*SELECT
execute.*\+|execute.*format|execute.*f"

# Command injection
os\.system|subprocess.*shell=True|os\.popen|eval\(|exec\(

# Weak crypto/randomness
import random|random\.choice|random\.randint|random\.random|hashlib\.md5|hashlib\.sha1

# Information disclosure
str\(e\)|traceback\.print_exc|traceback\.format_exc.*return|debug=True

# SSRF
requests\.(get|post|put|delete)\(.*variable|urllib\.request\.urlopen

# Deserialization
pickle\.loads|yaml\.load\b(?!.*Loader)|marshal\.loads

# Path traversal
open\(.*\+|os\.path\.join.*request|os\.path\.join.*user

# Missing auth (look for route definitions without auth decorators/middleware)
@app\.route|@router\.|RouteConfig.*auth_level.*NONE

# TLS bypass
verify=False|CERT_NONE

# Race conditions
SELECT.*UPDATE.*separate|if.*exists.*then.*create

# Dict merge override (user data overwriting protected keys)
\.update\(|Object\.assign\(|\{\*\*.*\*\*|\{\.\.\.

# Multi-consumer auth inconsistency (same authorize function called with different params)
authorize\(|core_authorize\(

# Unsafe API consumption (missing timeout)
requests\.(get|post|put|delete|patch)\((?!.*timeout)
urllib\.request\.urlopen(?!.*timeout)
httpx\.(get|post|put|delete)\((?!.*timeout)
aiohttp\.ClientSession

# TLS bypass on outbound calls
verify=False|verify\s*=\s*False|CERT_NONE|ssl.*False

# File upload patterns
upload|file.*upload|multipart|form-data
save\(|write\(.*file|open\(.*wb
content_type|mimetype|file\.filename|secure_filename

# Serverless event sources
base64\.b64decode|pubsub_message|event\[.data.\]
cloud_event|CloudEvent|storage\.objects
trigger|event_type|cloud_scheduler
```
