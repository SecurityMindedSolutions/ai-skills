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
- Missing auth checks on endpoints that should require authentication. If the framework is **opt-in** for auth (a guard/middleware/dependency must be explicitly applied, so there is no "public" marker to grep for and the bug is the ABSENCE of one), enumerate routes and their effective guard chains using the method in `api.md` §1b rather than relying on a marker grep.
- Privilege escalation paths (can a lower-role user access higher-role functionality?)
- Session management flaws (predictable tokens, missing expiry, no invalidation) — see the api module's section 1c for the dedicated revocation-propagation-via-cache check, which applies to any credential/session validity cache regardless of whether it lives in an "API" layer or general application code
- Multi-tenant isolation failures (queries missing `tenant_id` scoping)
- Fail-open authorization on a missing associated record (deleted vs. explicitly deactivated) — see the api module's section 1d; this pattern shows up anywhere a lookup-then-branch authorization check exists, not just in HTTP handlers
- CSRF protection gaps on state-changing operations, including a route registered as `GET` whose handler body itself performs a mutation — see the api module's CSRF section (9) for why this specifically evades framework CSRF middleware
- Privileged/sensitive data served via a raw "get everything" accessor when a filtered/scoped equivalent exists in the same codebase — see the api module's section 3b

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
- Destructive/disruptive actions whose severity is being discounted because "something self-heals it" (a reconciliation job, a scheduled resync, a TTL) — see the api module's section 5b before accepting that as a real mitigation; it only holds if the trigger itself can't be looped faster than the repair cycle
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
- **Proxy/forwarder endpoints that build an outbound URL by string-concatenating a caller-supplied "path"-like value onto a fixed base host** (any language/HTTP client — this is a language-agnostic pattern, not just Python `requests`/`urllib`): `${BASE_HOST}${param}`, `baseUrl + req.query.path`, `new URL(param, base)` whose result is used without asserting `.host`/`.origin` still equals the intended host afterward. This is a common shape for logging/telemetry/webhook/ingest proxy endpoints and is exploitable via URL userinfo/authority injection (`@evil.com`, `//evil.com`) even when the param is nominally "just a path" — run the dedicated section 6b rubric on every such endpoint, and see the SSRF false-positive rule for how to tell a real path-only case from this.

### 6b. Trusted-Prefix / Base-Host String Concatenation SSRF (Proxy & Forwarder Endpoints — dedicated check, do not skip)
<!-- Standards: OWASP-API7:2023, CWE-918 -->
Applies to any endpoint whose job is to relay/forward a caller's request to a fixed
upstream destination (log/metrics ingestion proxies, webhook relays, file/image fetch
proxies, "call this API for me" endpoints, redirect handlers) in ANY language/framework.
This is a distinct, deliberate check — separate from generic SSRF pattern-grepping —
because the vulnerable shape reliably escapes keyword search (it isn't about an
unvalidated *full* URL; it's about a supposedly-safe *path fragment* being trusted).

1. Find every outbound HTTP/RPC call in the codebase (client library call: e.g.,
   `axios`/`fetch`/`http.request` in JS/TS, `requests`/`httpx`/`urllib` in Python,
   `net/http` in Go, `HttpClient`/`RestTemplate`/`WebClient` in Java, `Net::HTTP` in Ruby).
2. For each such call, find where its URL argument was constructed. Walk backwards
   through variable assignments to the ultimate source(s).
3. Ask: does ANY caller-controlled input (query param, header, path param, request
   body field, or upstream webhook payload field) reach that URL string — even
   partially, even if it's meant to be "just a path" or "just an identifier"?
4. If yes, determine HOW it was combined with any hardcoded/trusted base value
   (a constant/env var that looks like a host — names containing HOST/BASE/ORIGIN/
   UPSTREAM/TARGET/INTAKE/ENDPOINT):
   - **UNSAFE, no further test needed**: plain string concatenation or
     template-literal/f-string joining (`BASE + input`, `` `${BASE}${input}` ``,
     Python f-string/`%`/`.format`, Go `fmt.Sprintf`), OR passing the raw input as
     a full/absolute URL to the client without first checking it resolves to the
     intended host. This is the common case and is unsafe outright — you do not
     need a URL-parsing helper to be present to reach this verdict.
   - **UNSAFE even when a URL-parsing helper IS used** (`new URL(input, base)`
     and similar), unless the code THEN asserts the resulting
     `.host`/`.hostname`/`.origin`/`.authority` still equals the intended
     constant AFTER parsing — parsing alone is not validation; authority-injection
     tricks can still smuggle a different host through unless that equality
     check exists.
   - **SAFE**: the input is validated with an anchored allowlist/regex requiring a
     single leading `/`, rejecting `@`, rejecting a second leading `/`
     (protocol-relative), rejecting `:` before any `/`, rejecting backslashes, AND
     independently re-parsed to confirm host equality — or the input is not used
     to build the destination at all (e.g. only used to select from a fixed
     enum/allowlist of pre-built URLs).
5. If unsafe, the following are the three distinct shapes an attacker-supplied
   value takes to prove host takeover, regardless of the field's declared
   purpose or the vendor SDK's documented "shape" for that field:
   - **Userinfo injection**: a leading `@` — the intended host becomes a
     basic-auth username and the attacker's host follows it
     (`TRUSTED_HOST` + `@evil.example/x` → connects to `evil.example`).
   - **Protocol-relative injection**: a leading `//`, or an embedded `://`
     scheme prefix, overriding the authority outright.
   - **Boundary/domain-splice injection**: this applies specifically when the
     trusted constant and the input are concatenated with NO enforced
     separator between them (i.e. nothing guarantees the joined string has a
     `/` right after the trusted host). Here even an input with no special
     characters at all — e.g. `.evil.example/x` — splices onto the end of the
     trusted host to produce a single attacker-controlled string
     (`https://trusted-host.example.evil.example/x`) that resolves to a host
     the attacker controls. Always check whether the concatenation site
     enforces a separator; if it doesn't, this shape applies even when `@`
     and `//` are both rejected elsewhere.
6. This bug does not require any keyword like "forward" or "proxy" in the field
   or file name — check ALL outbound-URL construction sites the same way, but
   treat any file whose whole purpose is relaying a request (name contains
   proxy/forward/relay/webhook-passthrough/ingest) as highest priority since
   caller-controlled destination fragments are most common there.
7. Also check: is a timeout/size-limit set on the outbound call, and does the
   *service itself* (not merely headers forwarded verbatim from the inbound
   request) attach a secret/credential it holds to the outbound call — an API
   key, service token, or basic-auth value read from its own config/env/secret
   store? Caller-supplied headers being passed through (e.g. the inbound
   request's own `content-type`/`accept`/`user-agent`) do NOT count here, since
   they carry nothing the service is trying to protect. If a service-held
   secret IS attached AND the destination can be redirected per the above,
   that's a credential-exfiltration amplifier, not just an availability issue —
   call this out explicitly and raise severity.
8. Trace what the resulting request method is limited to (e.g., hardcoded `POST`) — this bounds which internal routes are reachable if the SSRF pivots inward, and is worth noting in the exploit scenario.
9. Explicitly reason about pivot potential: could the forwarder be redirected at an internal-only hostname/IP (cluster-internal service, cloud metadata endpoint `169.254.169.254`, a private CIDR)? If the endpoint is itself internet-facing, this turns an internal-only weakness elsewhere into an internet-reachable one — flag that chain explicitly and let it drive severity up, even if you haven't verified the internal target is itself vulnerable.

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

### 12. Deletion Integrity — Data Silently Not Removed, or Removed More/Less Than Intended (dedicated check, do not skip)
<!-- Standards: OWASP-Web-A04:2025, CWE-459, CWE-703 -->

Applies to any code path whose job is to permanently remove data — a user/tenant
"delete my data" or retention/compliance flow, a credential/enrollment revoke
flow, a cache/cleanup step, or a destructive maintenance script/migration — in
ANY language/framework. This is a distinct, deliberate
check because a deletion path that *looks* successful (no exception thrown, a
success log line, HTTP 200) can still have left the data recoverable or never
actually removed it, and this reliably escapes generic error-handling review
because the code technically "handles" the response — it just doesn't act on
what that response says.

1. Find every call site that deletes data, across every storage type the
   codebase touches — relational and document databases, key-value/wide-column
   stores, object/blob storage, caches, search/vector indexes, message queues,
   file systems, and third-party APIs that hold data on the app's behalf:
   single-item deletes (a `deleteObject`/`deleteItem`/`remove`-style SDK call,
   ORM `.destroy()`/`.delete()`, `unlink`/`rm`), bulk/batch deletes (a
   multi-key `deleteObjects`-style call, a batch-write API carrying delete
   requests, `deleteMany`/`bulkDelete`, index/collection-wide purges), and raw
   `DELETE FROM`/`TRUNCATE`/`DROP` statements (including inside migrations).
2. For each, check whether the call's result is a **bulk/batch response with
   per-item partial-failure semantics** — many "delete N things" APIs return a
   success status even when some items in the batch failed to delete, and
   report those failures only in a field on the response (an `Errors` list, an
   `Unprocessed*` set, an `Unsuccessful*`/`Failed*` list, a per-item status
   array, a `deletedCount` lower than the requested count). If the code never
   reads that field and acts on it (retry, raise, alert), a partial failure is
   silently reported as a full success. This is NOT the same finding as "no
   try/catch" — the call can be perfectly exception-safe and still have this
   gap, because the client library doesn't throw for a partial batch failure.
   When you don't know a given SDK's response shape, look it up rather than
   assuming it throws.
3. Check whether a delete's return value or thrown error is actually
   propagated to the caller, or whether it's caught, logged, and swallowed
   while the caller proceeds as if it succeeded (`.catch(() => void 0)`,
   `.catch(err => logger.warn(err))` with no rethrow, a helper function that
   returns `false`/`None` on failure that its caller never checks). Trace the
   full call chain, not just the immediate function — the immediate function
   may correctly throw while an outer wrapper (a `Promise.all(...).catch(...)`
   around a batch of pages, a queue consumer's top-level handler) is what
   actually absorbs it.
4. If the delete targets a store that can retain prior versions or soft-delete
   (versioned object/blob storage, databases with point-in-time or time-travel
   reads, soft-delete/trash retention, snapshots, replicas, backups), check
   whether that retention is **actually enabled on the destination** (check
   IaC for that bucket/table/database if available in-repo; otherwise flag as
   needing infra confirmation rather than asserting). If it is, a plain delete
   call that doesn't target the specific version (e.g., no version identifier
   on a versioned-bucket delete) only writes a tombstone/delete marker — the
   prior bytes are still physically present and retrievable through the
   store's versioned-read API. For any deletion described as satisfying a
   retention, compliance, or "right to be forgotten" requirement, this is a
   real gap between "looks deleted" and "is actually gone," and is worth
   flagging even without IaC access to confirm, provided you say so
   explicitly as unconfirmed.
5. Check ordering and atomicity across multi-step or multi-backend deletes
   (e.g., delete-from-blob-storage-then-delete-from-database,
   delete-from-database-then-evict-cache, delete-from-primary-store-and-
   secondary-index-in-parallel). If there's no transaction, outbox pattern, or
   compensating rollback, ask: what state does the system end up in if step 1
   succeeds and step 2 fails? Which is worse — an orphaned object nobody
   points to any more, or a live reference to something already deleted?
   Either can be the wrong answer depending on the domain (retention/
   compliance deletion should prefer "data gone" over "record consistent";
   general application cleanup often prefers the reverse) — don't assume the
   ordering doesn't matter.
6. Check any idempotency/short-circuit guard on a delete/cleanup routine ("if
   the row is already gone, return early / no-op"). Ask: if this routine is
   retried after a PARTIAL external failure (e.g., a downstream commit
   actually succeeded but the caller never received confirmation and
   retries), does the guard's early-return skip cleanup steps that hadn't run
   yet on the first attempt? A guard keyed on "is the primary record gone" can
   wrongly signal "fully done" when only that one step of a multi-step
   cleanup actually completed.
7. Check for a **silent zero-match no-op**: a delete-by-prefix, delete-by-
   query, or delete-by-filter operation that matches zero items just
   logs/returns success with no cross-check against an expected count (e.g.,
   "we expected to find and remove N items for this key, we found 0 — that's
   suspicious, not clean"). A wrong or drifted key/prefix/filter can make a
   real deletion silently do nothing while looking identical to "there was
   nothing to delete."
8. For destructive `DELETE`/`TRUNCATE` statements, especially inside a schema
   migration or maintenance script run automatically against live data: is
   the WHERE clause scoped to only the intended rows (by id, by a reviewed
   drop-list/CTE), or does it delete broadly (`WHERE id != <one-hardcoded-
   id>`, no WHERE at all) with no transaction wrapper, no dry-run, and no way
   to restore via the paired down-migration/rollback? A migration that
   includes a bulk delete as a side effect of an unrelated schema change
   (e.g., "add a column" also silently truncating a table) is a red flag
   regardless of whether the delete was intentional — it needs the same
   scrutiny as a standalone destructive script, because migrations typically
   run unattended against every environment including production.
9. Config that determines *what* gets deleted — a bucket name, table name, or
   key prefix built from a template string and an env var — read once at
   process/module start rather than resolved per call: if that config is
   wrong, missing, or drifts, does the delete call fail loudly (good) or
   quietly target/match nothing (bad, ties back to #7)?

None of this requires the word "delete" to be nearby — deletion-adjacent
language includes unenroll, revoke, forget, purge, retention, expire,
GC/garbage-collect, cleanup, evict, truncate, and compact.

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

# SSRF (Python)
requests\.(get|post|put|delete)\(.*variable|urllib\.request\.urlopen

# SSRF (Node/TS) — outbound HTTP clients fed a built-up URL
axios\.(get|post|put|delete|patch)\(|fetch\(|http\.request\(|https\.request\(

# SSRF (Go/Java/Ruby/other) — outbound HTTP clients, check the URL argument's provenance
http\.Get\(|http\.Post\(|HttpClient|Net::HTTP|RestTemplate|WebClient

# SSRF — the URL-construction pattern itself, independent of client/language (grep the sink's URL argument backwards to find one of these)
\$\{[A-Za-z_]*HOST[A-Za-z_]*\}\$\{|\+\s*req\.(query|params|body)|new URL\(.*,\s*(req\.|param|input)
forward.*param|proxy.*url.*param|targetUrl\s*=
# SSRF — trusted base-host constants/env vars whose concatenation sites must be checked per section 6b
[A-Z_]*(HOST|BASE|ORIGIN|UPSTREAM|TARGET|INTAKE|ENDPOINT)[A-Z_]*\s*[:=]

# Deserialization
pickle\.loads|yaml\.load\b(?!.*Loader)|marshal\.loads

# Path traversal
open\(.*\+|os\.path\.join.*request|os\.path\.join.*user

# Missing auth, opt-out frameworks (an explicit public/none marker to find)
@app\.route|@router\.|RouteConfig.*auth_level.*NONE

# Missing auth, opt-in frameworks (nothing to grep for — the bug is the ABSENCE of a guard).
# Grep the guards that ARE used somewhere, then diff that set against every route registration (see api.md 1b).
UseGuards\(|@PreAuthorize|@Secured|permission_classes|login_required|Depends\(.*[Aa]uth|before_action.*authenticate|APP_GUARD

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

# Credential/session revocation caching (see api module 1c)
LRUCache|NodeCache|lru_cache|memoize|CACHE_TTL|cacheTtl
revoke|revoked|deactivate|invalidat.*cache

# Fail-open on missing record (see api module 1d)
\.active\b|is_active|isActive|status.*active

# Self-heal/reconciliation vs. rate limiting (see api module 5b)
resync|reconcil|self.?heal|cron.*(recreate|resync|repair)
ratelimit|rate.limit|throttl

# Deletion integrity (see section 12) — delete call sites, any store/SDK/language
[Dd]elete(Objects?|Items?|Many|All|Batch|Bulk|Vectors?|Documents?|Blobs?|Records?|Entries)\b|delete_(objects?|items?|many|batch|bulk|blobs?)\(|[Bb]atch[Ww]rite|bulk_?[Dd]elete|purge\(|\.destroy\(|deleteMany\(|\bunlink\(|rm -rf
DELETE FROM|TRUNCATE|DROP TABLE
# Delete failures swallowed
\.catch\(\s*\(\)\s*=>\s*(void 0|undefined|\{\})\)|\.catch\((console|logger)\.(warn|error|log)\)|except\s*:\s*pass|except .*:\s*pass|rescue\s*(=>|$)|_ = .*[Dd]elete
# Partial-failure fields on batch responses — grep the DELETE call sites above and confirm one of these is read afterward
\.Errors\b|Unprocessed[A-Za-z]*|Unsuccessful[A-Za-z]*|Failed(Items|Keys|Ids|Entries)|deletedCount|deleted_count
# Versioned/soft-delete stores — a delete with no version target only writes a tombstone
[Vv]ersioning|versioned|version_?[Ii]d|soft_?delete|deleted_at|deletedAt|tombstone|delete_?marker
# Destructive statements inside migrations/maintenance scripts (scope + transaction + down-migration)
(migrat|migration|seed|maint|cleanup|script).*(DELETE FROM|TRUNCATE|DROP)
# Deletion-adjacent language that never says "delete"
unenroll|revoke|forget|purge|retention|expire|garbage.?collect|\bgc\b|cleanup|evict|compact
```
