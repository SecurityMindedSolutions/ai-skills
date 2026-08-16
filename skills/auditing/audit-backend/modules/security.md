# Module: Security (SEC)

Evaluate basic security practices in the application layer. This is NOT a full security audit (use `/audit-security` for that). This checks that the application follows secure coding patterns as a matter of routine.

## Assertions

### SEC-1: Auth is enforced before handler execution
- The framework should authenticate and authorize requests before dispatching to handlers.
- Handlers should never need to check auth themselves (unless for fine-grained logic).
- Look for: auth checks inside handlers, handlers that could be called without auth.

### SEC-2: RBAC is a separate check from authentication
- Authentication (who are you?) and authorization (what can you do?) should be distinct steps.
- A single "auth" function that mixes both is harder to reason about and test.
- Look for: role checks inside the authentication function, or auth that silently grants access.

### SEC-3: All user input is validated before use
- Every field from request bodies, query parameters, and path parameters should be validated for type, length, and format before being used in business logic or database queries.
- Validation should happen at the framework boundary (schema validation) or service entry point — not deep inside business logic.
- Look for: user input used without validation, missing length limits on string fields, integer fields without range checks.

### SEC-4: Data access is scoped to the authenticated user and tenant
- Every database query that reads or modifies user/tenant data should include the appropriate scope filter (e.g., ancestor key, `WHERE user_id`/`WHERE tenant_id`, partition key).
- No handler or service should be able to accidentally access another user's — or in a multi-tenant app, another tenant's — data by omitting the scope filter.
- In a multi-tenant system, the tenant scope must be derived from a trusted server-side source (validated session claim, or a path param that a central gate authorizes membership against) — never from a client-controllable body/query/header field used without a membership check. Enforcement should be centralized (middleware) so a new handler cannot forget it, not re-implemented per handler.
- Look for: queries that don't include user/tenant scoping, admin endpoints that allow user/tenant ID override without authorization checks, tenant id read from a request body/header for scoping, IDOR/BOLA-susceptible patterns, routes registered without the standard auth/tenant middleware. (For a deep multi-tenant isolation pass, use `/audit-security`'s `multi-tenancy` module.)

### SEC-5: Session tokens are hashed before storage
- Raw session tokens should never be stored in a database.
- The framework should hash tokens (SHA256 or better) before persistence.
- Look for: raw tokens in database writes, token storage without hashing.

### SEC-6: Secrets are never hardcoded
- API keys, database credentials, OAuth secrets, and encryption keys must come from environment variables or a secret manager.
- No secrets in source code, config files committed to git, or default values.
- Look for: hardcoded strings that look like keys/secrets, default values for secret parameters, `.env` files committed to git.

### SEC-7: Error responses don't leak internal details
- Client-facing error messages should be user-friendly and safe.
- Stack traces, file paths, SQL/query errors, and internal state should only appear in server-side logs.
- Look for: `str(e)` in response bodies, traceback in HTTP responses, database error messages forwarded to clients.

### SEC-8: Dependencies are pinned and auditable
- All dependencies should have pinned versions (not `>=` ranges in production).
- A lock file should exist (`requirements.txt` with pinned versions, `package-lock.json`, `uv.lock`).
- Look for: unpinned dependencies (`flask>=2.0`), missing lock files, dependencies only specified in setup.py without a lock.

### SEC-9: File and resource operations are bounded
<!-- Standards: CWE-770, OWASP API4:2023, OWASP Serverless SAS-8 -->
- Any operation that processes user data should have explicit limits: max file size, max list length, max query results, max string length.
- Unbounded operations can be exploited for DoS or financial exhaustion (billing attacks in serverless).
- **Pagination enforcement**: Every list endpoint should enforce a maximum `page_size` or `limit` (e.g., cap at 100-500). If the client doesn't provide a limit, a default should be applied. Reject unreasonable values (e.g., `page_size=999999`).
- **Request body size limits**: The framework or middleware should enforce a maximum request body size. Large payloads without limits can exhaust memory.
- **Query result caps**: Database queries should include `LIMIT` clauses. Unbounded `SELECT *` queries on large tables are both a performance and security risk.
- **Bulk operation limits**: Endpoints that accept arrays/lists of items for bulk create/update/delete should enforce a maximum item count per request.
- **String field length limits**: All user-provided string fields should have explicit maximum length validation (not just DB column width).
- Look for: list endpoints without pagination or limits, bulk operations without max item counts, string fields without length limits in validation, missing `LIMIT` on SQL queries, missing request body size middleware.

### SEC-10: CORS, cookies, and headers follow secure defaults
- CORS should allowlist specific origins, not use `*` with credentials.
- Cookies should default to `Secure`, `HttpOnly`, `SameSite=Lax`.
- Security headers should be applied uniformly (framework-level, not per-handler).
- Look for: `Access-Control-Allow-Origin: *`, cookies without `HttpOnly`, missing `SameSite`, security headers set in some responses but not others.

### SEC-11: No runtime environment sniffing
- The framework should not inspect request headers (referrer, IP, hostname) to determine environment behavior.
- Environment config should come from env vars or config files at startup time.
- Look for: `if "localhost" in referrer`, IP-based environment detection, hostname checks.

### SEC-12: Authorization is consistent across all consumers
- When the same operation is exposed through multiple entry points (web API, public API, MCP server, CLI, background jobs), all consumers must enforce the same authorization checks.
- A centralized `authorize()` function only works if every caller passes the same parameters. If one caller omits an optional parameter (e.g., `action_type`, `resource_id`), conditional authorization logic may be silently skipped.
- Trace each authorize call site and compare the parameters passed. Flag any caller that omits parameters other callers include.
- Look for: the same `authorize()` function called with different parameter sets across files, conditional checks gated by `if param is not None` where some callers don't pass that param.

### SEC-13: Dict merges don't override protected keys
- When building a dict from explicit/validated fields and then merging user-supplied data (e.g., `target_data.update(parameters)`), the merge can silently overwrite security-relevant keys like user identifiers, tenant IDs, or target references.
- Look for: `dict.update()`, `{**dict1, **dict2}`, or `Object.assign()` where user-controlled data is merged into a dict that already contains keys set from validated/trusted sources.
- The fix is to only add keys that don't already exist (`if k not in target: target[k] = v`), or use an explicit allowlist of which keys `parameters` may set.

### SEC-14: Permission levels match operation severity
- Write/destructive operations (delete, revoke, modify, suspend) should use write-level permission checks, not read-level.
- Look for: route configs where a POST/PUT/DELETE method uses a read-scoped permission or feature role (e.g., `feature_role="read:*"`, `permission="view"`, `scope="read"`).
