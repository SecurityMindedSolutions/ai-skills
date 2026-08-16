# API Security Review Module

Review API endpoints, route configurations, and request handling for security vulnerabilities.

## Categories to Review

### 1. Authentication & Authorization at Endpoint Level
<!-- Standards: OWASP-API1:2023, OWASP-API2:2023, OWASP-API5:2023, CWE-862, CWE-306 -->
- Endpoints with missing or incorrect auth level (e.g., `AuthLevel.NONE` on state-changing operations)
- Inconsistent auth requirements across similar endpoints
- API key validation gaps (deleted/expired entities still authenticated)
- Token validation timing (check before or after other processing?)

### 2. Input Validation & Mass Assignment
<!-- Standards: OWASP-API3:2023, CWE-20, CWE-915 -->
- Missing parameter validation on route definitions
- Type coercion issues (string vs int, list vs single value)
- Missing length/size limits on input fields
- Regex denial of service (ReDoS) in validation patterns
- Mass assignment: API accepts more fields than intended, allowing users to set `role`, `is_admin`, `tenant_id`, etc. Check for patterns like `**request.json`, `Object.assign(model, req.body)`, `{...req.body}`, or ORM `.create(req.body)` without field filtering

### 3. Data Exposure
<!-- Standards: OWASP-API3:2023, CWE-200 -->
- Endpoints returning more data than the client needs
- Internal IDs, stack traces, or system info in error responses
- Sensitive fields not excluded from API responses (passwords, hashes, internal flags)
- Pagination without limits (can caller request unbounded result sets?)

### 4. CORS & Cross-Origin
<!-- Standards: OWASP-API8:2023, OWASP-Web-A02:2025 -->
- Wildcard CORS origins in production
- CORS bypass via Host header manipulation
- Missing CORS on endpoints that need it
- Credentials allowed with wildcard origins

### 5. Rate Limiting & Resource Exhaustion
<!-- Standards: OWASP-API4:2023, CWE-770, OWASP Serverless SAS-8 -->
- Endpoints without rate limiting that should have it (auth, signup, password reset)
- Missing pagination limits (can request page_size=999999?)
- Expensive operations without throttling (report generation, exports, bulk operations)
- File upload size limits

### 6. HTTP Security
<!-- Standards: OWASP-API8:2023, OWASP Proactive Controls C8, NIST-CSF PR.DS -->
- Missing security headers (HSTS, X-Content-Type-Options, X-Frame-Options, CSP)
- Insecure cookie attributes (missing Secure, HttpOnly, SameSite)
- HTTP methods not properly restricted (OPTIONS, TRACE, DELETE where not needed)
- Cache headers exposing sensitive data

### 7. Error Handling
<!-- Standards: OWASP-Web-A10:2025, CWE-200 -->
- Different error responses for "not found" vs "not authorized" (enables enumeration)
- Stack traces or internal exception details in error responses
- Inconsistent error format across endpoints
- Error responses that leak database schema or query structure

### 8. Business Logic at API Level
<!-- Standards: OWASP-API6:2023, OWASP-Web-A06:2025, CWE-352 -->
- Missing CSRF on state-changing endpoints
- Idempotency issues on non-idempotent operations
- Race conditions between concurrent API calls
- Bulk operation abuse (can delete/modify more than intended?)

### 9. CSRF Protection
<!-- Standards: CWE-352, OWASP Proactive Controls C8 -->
- Do state-changing endpoints (POST/PUT/DELETE/PATCH) have CSRF protection?
- Is `SameSite` cookie attribute set on session cookies (`Lax` or `Strict`, not `None` without justification)?
- Is Origin or Referer header validated on state-changing requests?
- Is there a double-submit cookie pattern, synchronizer token pattern, or framework-provided CSRF middleware?
- Are CSRF protections applied uniformly (not missing on some state-changing routes)?
- If the API is token-based (Bearer/API key in header), CSRF may not apply — verify auth mechanism before flagging.
- **Cross-layer CSRF flow validation**: When the backend validates CSRF tokens, verify the full flow works end-to-end: (1) the CSRF action name is in the generation endpoint's allowlist, (2) the frontend actually requests and sends the token, and (3) the backend validates it. A broken link in any of these three steps means CSRF is either silently failing or silently bypassed. Check both the backend validation code AND the frontend service/fetch calls for each protected endpoint.

### 10. API Inventory & Lifecycle
<!-- Standards: OWASP API9:2023 -->
- Are there debug or internal endpoints exposed without authentication (`/debug`, `/test`, `/internal`, `/_health` with sensitive data)?
- Are there deprecated or legacy API versions still accessible (e.g., `/v1/` alongside `/v2/`)?
- Do all registered routes appear in API documentation or route config (no shadow endpoints)?
- Are there endpoints that accept requests but are undocumented or unused?
- Are there admin/management endpoints accessible from the public API surface?

### 11. Content-Type & HTTP Method Enforcement
<!-- Standards: OWASP API8:2023, Enterprise Best Practices -->
- Is the `Content-Type` header validated on incoming requests (reject unexpected types)?
- Are HTTP methods properly restricted per route (no wildcard/catch-all method handlers)?
- Are request bodies rejected on methods that shouldn't have them (GET, HEAD, DELETE)?
- Is `Accept` header validated where response format matters?
- Are `OPTIONS` and `TRACE` methods disabled or restricted?

### 12. OAuth / SSO Flow Security
<!-- Standards: OWASP-Web-A07:2025, OWASP-API2:2023, CWE-352, CWE-601 -->
- **State parameter integrity**: OAuth state must be encrypted (AES-GCM) or HMAC-signed — not plain JSON, UUID, or base64-encoded cleartext. Plain state allows tampering, CSRF bypass, and information disclosure.
- **State contents**: State should not contain sensitive config (internal URLs, cookie settings, infrastructure details, tenant architecture). Only include the minimum needed (redirect path, CSRF nonce).
- **CSRF in state**: State must include a server-validated CSRF nonce — a random value nobody checks server-side is not CSRF protection. Best practice: dual nonce (one in encrypted state + one in HttpOnly cookie, compared with `hmac.compare_digest` on callback).
- **State expiry**: State must include a timestamp validated on callback (10 minutes max).
- **Callback validation order**: Callback must validate state BEFORE processing the authorization code or any other parameters.
- **Redirect URI validation**: Callback redirect targets must be validated against an allowlist — never redirect to a user-controlled URL from the state parameter without validation.
- **Authorization code handling**: Code must be exchanged server-side (never exposed to frontend), used exactly once, and exchanged promptly.
- **Token storage**: Access/refresh tokens stored server-side (session or DB). If tokens must reach the client, use HttpOnly Secure cookies — never localStorage/sessionStorage for auth tokens.
- **ID token validation**: If using OIDC, verify signature, issuer (`iss`), audience (`aud`), and expiry (`exp`) — don't just trust the claims.
- **Consistency across flows**: If the app has multiple OAuth flows (login, integration, linking), ALL must use the same security level. A single unprotected flow is a vulnerability even if others are hardened.
- **Logout completeness**: Logout must invalidate server-side session, clear auth cookies, and (if applicable) revoke tokens with the identity provider.

### 13. Unauthenticated Content-Publication Surfaces
<!-- Standards: OWASP-API1:2023, OWASP-API3:2023, OWASP-Web-A01:2025, CWE-639, CWE-200 -->
Applies to any app that serves per-owner content to the public with no auth (status pages, public
profiles, published documents, share links, a per-tenant "trust"/marketing page). These endpoints
are deliberately `AuthLevel.NONE`, so the usual "public endpoint = suspicious" heuristic is wrong —
instead audit the **content-gating logic** that decides what an anonymous caller may see:
- **Publish-state gating**: every public read must gate on an explicit server-owned "published/
  visible/active" flag before returning owner content. Flag a public handler that returns content
  without checking a publish/visibility state — it exposes drafts.
- **Draft/preview access**: a preview or draft view (`?preview=true`, `/draft/…`) must require an
  authenticated, authorized session (ownership/membership), never a bare query flag. Flag preview
  bypasses gated only by a client-supplied parameter.
- **Response field allowlist, not record pass-through**: the public payload must be assembled from an
  **explicit allowlist** of safe fields, never a whole record/document spread. A pass-through
  (`return {**doc}`, `return record`, `res.json(record)`, `return service.get(...)`) risks leaking
  internal fields — webhook URLs, recipient lists, signing secrets, internal flags — the moment any
  such field is added to the record. Flag public serializers that return a full record instead of
  picking named fields.
  - **Be exhaustive, not sampled.** First enumerate **every** unauthenticated response path in the
    codebase — grep all route configs for `AuthLevel.NONE`/unauthenticated routes across **all**
    functions (not just the obvious public one), list each handler, and classify each return. A
    leak in a public handler you never opened is the common miss; the pass is only as good as its
    coverage of the full public surface.
  - **Trace nested sub-objects one level down.** A handler that allowlists the top level can still
    embed a raw sub-object that carries internal fields (`return {"page": page}`,
    `return {"layout": layout}`, `return enrich_x(record)`). Follow the **service function** that
    produced each embedded object and check what fields it stamps — not just the outer dict.
  - **Sensitive-field taxonomy** (any of these reaching an anonymous caller is a leak, not just
    "secrets"): any field ending `_email`/containing `email`; actor identity (`created_by*`,
    `updated_by*`, `*_by`, user IDs/UIDs); audit/bookkeeping metadata (internal `updated_at`,
    `changed_from_defaults`, revision/version fields); webhook URLs / tokens / signing keys /
    recipient lists; internal-only flags or config not needed to render; plan/billing/cost internals.
    Admin **email addresses** are a common real leak (usable for targeted phishing/enumeration) — do
    not dismiss them as "not a secret."
  - **Regression guard, not just a scan**: an audit is point-in-time; the durable control is a
    repo-committed test/lint asserting the taxonomy fields are **absent** from every public response
    (generalize the single-endpoint version many codebases already have). Recommend adding one where
    it's missing — flag the *absence of a guard*, not only the current leaks.
- **Server-owned gating flags**: whether an item is gated/public must be computed from the item's
  own server-stored attributes, never from a client-supplied flag in the request (a layout/display
  hint from the client must not decide access).
- **Existence oracle**: unknown owner, unpublished owner, missing item, disabled section, failed
  preview, AND validation/error paths should all return the **same** not-found response (see §7) so
  the public surface isn't an enumeration oracle. Distinct status codes or bodies (403-vs-404,
  a distinguishable error shape, a validation message echoing internal field names) leak which
  owners/resources exist. Enumerate every branch of each public handler and confirm they converge on
  one uniform response.

### 14. Anti-Automation on Public Endpoints
<!-- Standards: OWASP-API4:2023, OWASP-API6:2023, CWE-799, CWE-770 -->
- Public unauthenticated write endpoints (signup, waitlist, contact, access-request, comment,
  invite) must have anti-automation controls: rate limiting and/or CAPTCHA/attestation.
- **CAPTCHA must be in enforce mode, not observe/monitor mode.** A CAPTCHA integration that computes
  a score but lets the request proceed regardless (`ENFORCE=false`, score logged but not acted on,
  a sentinel default that fail-opens) provides no protection. Flag CAPTCHA/risk checks whose default
  or configured behavior is fail-open (proceed on unassessed/low score).
- Verify public read endpoints that expose per-owner content have some throttle, or explicitly note
  the enumeration/scraping exposure if none exists.

### 15. Email-Action & Verification-Link Safety
<!-- Standards: OWASP-Web-A01:2025, OWASP-API2:2023, CWE-352, CWE-640, CWE-294 -->
- **A link (GET) must never perform a state change.** Email clients, link scanners, and browser
  prefetch fetch every URL in a message automatically — an action link that acts on GET (verify,
  reset, enroll, revert, unsubscribe-that-mutates) will fire without the user clicking. State
  changes must require an explicit user-initiated `POST`/form submit from an interstitial page.
- **No validity oracle on the action page**: valid, invalid, expired, and nonexistent action codes
  should render an indistinguishable page (the page loads; only the explicit submit reveals outcome),
  so the link isn't a token-probing oracle.
- **One-time tokens** (email oobCodes, magic links, MFA/step-up session handles, password-reset
  tokens): stored **hashed** (never raw), **single-use** (hard-deleted/invalidated on consume), and
  **TTL-bounded**. Flag raw-token storage, tokens reusable after consumption, or missing expiry.
- **Redirect targets** derived from the request (a forwarded host, a `next`/`callback` param) must be
  validated against an allowlist before being used to build the emailed link or the post-action
  redirect (open-redirect / link-spoofing).

## Scanning Approach

1. Read architecture docs to understand the API framework, auth middleware, and route structure
2. Map all route definitions and their auth levels — flag any suspicious NONE/public endpoints
3. Check each endpoint's input validation against what the handler actually uses
4. Verify response payloads don't include unnecessary internal data
5. Check error handling consistency across all endpoints
6. Look for endpoints that bypass the framework's built-in protections
7. Trace all OAuth/SSO flows end-to-end: login initiation → redirect → callback → session creation → logout. Check each step for the protections listed in section 9.

## Patterns to Grep For

```
# Route definitions
RouteConfig|@app\.route|@router\.|app\.(get|post|put|delete|patch)

# Auth levels
AuthLevel\.NONE|auth_level.*none|authenticate.*false|@login_not_required

# CORS
Access-Control-Allow-Origin|\*|cors.*origin

# Error leaks
str\(e\)|traceback|stack_trace|\.message.*error|detail.*exception

# Missing validation
request\.args\.get|request\.form\.get|request\.json\.get|params\[

# Mass assignment
\*\*request\.(json|form)|\.update\(\*\*|Object\.assign\(.*req\.body|\{\.\.\.req\.body
Model\.(create|update)\(req\.body|\.create\(\*\*request

# Security headers
X-Frame-Options|X-Content-Type|Strict-Transport|Content-Security-Policy

# Cookie security
set_cookie|Set-Cookie|secure.*false|httponly.*false|samesite.*none

# Pagination
limit.*request|page_size.*request|offset.*request|LIMIT.*:

# OAuth state (check for unencrypted/unsigned state)
json\.dumps.*state|state.*json\.dumps|state.*uuid|state\s*=\s*\{
create_oauth_state|encrypt.*state|decrypt.*state|oauth.*state
prepare_request_uri|authorization_url|authorize_redirect

# OAuth tokens
localStorage\.setItem.*(token|access|refresh|auth)
sessionStorage\.setItem.*(token|access|refresh|auth)
id_token|access_token|refresh_token

# OAuth callback handling
/callback|/oauth|/auth.*code|authorization_code

# CSRF patterns
csrf|CSRF|_csrf|xsrf|XSRF
SameSite|samesite|same_site
double.submit|synchronizer.token|anti.forgery

# API inventory / debug endpoints
/debug|/test|/internal|/_admin|/swagger|/openapi|/graphql
/api-docs|/api/v1|/api/v2|/health.*detail|/metrics|/status

# Content-Type enforcement
Content-Type|content.type|content_type
method.*\*|methods.*=.*\["

# Public content-publication surfaces (check gating + field allowlist)
published|is_published|visibility|is_public|draft|preview|show_in_nav|path_routing
return\s*\{\*\*|res\.json\(\s*\w+\s*\)|jsonify\(\s*\w+\)|return\s+doc\b|\.to_dict\(\)

# Anti-automation / CAPTCHA enforce vs observe
recaptcha|captcha|hcaptcha|turnstile|createAssessment|risk.?score
ENFORCE|enforce.*false|observe|monitor.?mode|fail.?open

# Email-action / verification-link safety (GET must not mutate)
oobCode|oob_code|action.*code|magic.?link|verify.*link|reset.*token|/auth/action
token_urlsafe|secrets\.token|sha256.*token|single.?use|expires_at|ttl
```
