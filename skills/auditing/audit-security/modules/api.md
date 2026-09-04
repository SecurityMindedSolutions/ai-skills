# API Security Review Module

Review API endpoints, route configurations, and request handling for security vulnerabilities.

## Categories to Review

### 1. Authentication & Authorization at Endpoint Level
<!-- Standards: OWASP-API1:2023, OWASP-API2:2023, OWASP-API5:2023, CWE-862, CWE-306 -->
- Endpoints with missing or incorrect auth level (e.g., `AuthLevel.NONE` on state-changing operations)
- Inconsistent auth requirements across similar endpoints
- API key validation gaps (deleted/expired entities still authenticated)
- Token validation timing (check before or after other processing?)

**1b. Missing Authentication on Opt-In-Auth Frameworks (Silent-by-Default Unauthenticated Routes — dedicated check, do not skip)**
<!-- Standards: OWASP-API2:2023, CWE-306, CWE-862 -->
The bullets above assume an *opt-out* framework, where an explicit marker
(`AuthLevel.NONE`, `@login_not_required`) declares a route public and you can
grep for that marker. Many modern frameworks are the opposite: auth is
OPT-IN per route, and there is no marker to grep for — the vulnerability is
the ABSENCE of one. Examples: NestJS `@UseGuards(...)` / a global `APP_GUARD`
provider, Express/Koa middleware chains, Spring Security
`@PreAuthorize`/`@Secured`/security-filter-chain config, FastAPI
`Depends(get_current_user)`, Django `permission_classes`/`@login_required`,
Rails `before_action :authenticate!`. A route with none of these applied is
unauthenticated by default. Treat this as a separate pass from the marker-grep
above — you must enumerate the positive set, not search for a negative flag:

1. Identify the framework(s) in use and, for each, identify EVERY mechanism
   this specific codebase uses anywhere to gate a route (grep the whole repo
   for guard/middleware/dependency names actually used at least once — don't
   assume framework defaults, use what THIS codebase does elsewhere). A
   guard/middleware only counts here if it verifies the CALLER'S identity or
   credentials (a token, session, API key, signature, mTLS cert). Something
   merely named "guard" that gates a route on an environment flag, feature
   flag, or request-shape check (e.g. a docs-exposure toggle) is not an auth
   mechanism and must not be treated as one just because of its name — read
   its body, not just its name, before deciding it counts.
2. Enumerate every route/handler (controller method, router registration, view
   function) in the module(s) under review — every HTTP verb, not just POST.
3. For each route, determine its FULL effective middleware/guard/dependency
   chain: method-level decorator/dependency, controller/class-level decorator,
   module-level provider, AND global application-level guard/middleware
   (checked once for the whole app — a global guard means individual routes
   need no local decorator, so confirm whether a global one exists before
   concluding a route is unguarded).
4. Flag any route where that chain contains NONE of the auth mechanisms
   identified in step 1, AND the route does any of: creates/deletes/mutates a
   resource, triggers a side effect outside the request (spawns a
   process/job/container, sends a message, calls another internal service with
   elevated credentials, writes to storage), or returns data scoped to a
   specific caller/tenant. A plain unauthenticated GET that discloses internal
   operational/system state (job status, infra metadata, other users' records)
   still belongs in this bullet even in a single-tenant service with no
   explicit tenant model — "no tenant concept exists" is not the same as "no
   confidentiality boundary exists"; flag it, at lower confidence if it's
   read-only, especially when unauthenticated mutating routes sit right next
   to it (their presence signals the read route was never behind an intended
   auth boundary either).
5. Do not suppress a finding just because NO other route in the repo is
   protected either — "the whole service has no auth anywhere" is not a
   mitigating factor, it is the finding (arguably a higher-severity one, since
   it means the entire API surface, not just one endpoint, is exposed). Only
   treat missing-auth as expected/non-finding when the route is genuinely
   meant to be public (health checks, static assets, truly public read
   endpoints) — a route that creates infrastructure, runs code, or has any
   side effect is never in that category regardless of what other routes in
   the repo do.
6. Cross-check documentation against enforcement: if the API's docs/OpenAPI/
   Swagger setup DECLARES a security scheme (API key, bearer token, OAuth) —
   via `addApiKey`/`addBearerAuth`/`SecurityRequirement`/`@ApiSecurity`/OpenAPI
   `securitySchemes` — search the entire codebase for anywhere that scheme is
   actually CONSUMED by a real guard/middleware/dependency check. If the
   documented scheme is never wired into any enforcement code, that is "auth
   theater": it makes the API look protected in its own documentation/Swagger
   UI while every route remains open, and callers/reviewers relying on the
   docs will be misled. This holds regardless of whether the doc config
   applies the scheme per-operation (`@ApiSecurity`/`security:` on individual
   routes) or only registers it globally (`components.securitySchemes`/
   `addApiKey` with no per-route annotation) — an unenforced scheme is auth
   theater either way, and an unapplied one is if anything worse (it isn't
   even wired into the docs, let alone the code). Flag this as one
   repo/API-wide finding, and reference it as amplifying context in every
   unauthenticated dangerous-route finding in the same service — it turns "an
   attacker would have to know this route is open" into "the service's own
   docs imply it's protected, but nothing actually checks."

**1c. Credential/Session Revocation Propagation (dedicated check — do not skip)**
<!-- Standards: OWASP-Web-A07:2025, CWE-613, CWE-639 -->
Authentication is frequently split across a live check ("is this credential valid
right now") and a cached/memoized check ("was this credential valid recently"),
and the cached path is where revocation silently fails. This applies to API
gateway authorizers, Lambda/serverless authorizer caches, in-process memoization
(`lru-cache`, `node-cache`, `functools.lru_cache`, a plain module-level dict/Map
with a TTL), and any framework's own token-introspection cache.

1. Find every place a credential/token/session/API-key validity result is cached
   — grep for cache constructs (`new LRUCache`, `NodeCache`, `@lru_cache`,
   `memoize`, a dict/Map keyed by token/credential id) anywhere near
   authentication/authorization code, and any explicit `*_CACHE_TTL`,
   `cacheTtl`, `authorizerResultTtlInSeconds`, or similar TTL configuration.
2. For each one found, check whether there is an ACTIVE invalidation path —
   does a revoke/deactivate/logout operation anywhere in the codebase publish
   an event, call a cache-eviction function, or otherwise reach into that cache
   to remove the now-invalid entry? Or does the entry only leave the cache when
   its TTL naturally expires?
3. If there is no active invalidation, this is a finding: the credential
   continues to authenticate for up to the TTL window after an operator
   believes they've revoked it. Severity should scale with the TTL length and
   with how central the cached check is (e.g., a shared API-gateway authorizer
   used by every route in the fleet is worse than a single service's local
   session cache) — but even a short TTL is a real, reportable gap, not a
   false positive; note the bounded window explicitly in **Current controls**
   so triage can weigh it accurately rather than treating "it expires
   eventually" as equivalent to "properly invalidated."
4. If the same credential/token type has MORE THAN ONE independent cache or
   validation path in the codebase (e.g., a gateway-level authorizer cache AND
   a separate introspection-endpoint cache), check each one separately — one
   being fixed does not mean the other is, and the presence of multiple
   uncoordinated caches for the same credential type is itself worth calling
   out as compounding exposure.

**1d. Fail-Open on a Missing Associated Record (dedicated check — do not skip)**
<!-- Standards: OWASP-Web-A01:2025, CWE-862, CWE-863 -->
A common and easy-to-miss authorization defect: code that loads a secondary
record to determine whether the caller is allowed to proceed (an `Account`,
`Tenant`, `Membership`, `Subscription`, `Profile` — anything looked up by
foreign key from the authenticated principal) correctly rejects when that
record is found and marked inactive/disabled/revoked, but has no explicit
branch for "the record was not found at all" — and a missing record silently
falls through as if the check passed.

1. For every authorization/entitlement check that does a lookup-then-branch
   (`if (record) { if (!record.active) reject() }` or equivalent in any
   language), explicitly ask: what happens when the lookup returns null/None/
   not-found? Is there an `else` (or equivalent) that rejects, or does control
   flow simply continue past the whole block?
2. This is especially dangerous immediately after data lifecycle changes: an
   offboarding/deprovisioning process that DELETES the backing record (instead
   of setting an inactive flag) will silently re-open access through any check
   shaped like this, even though the intent was clearly to remove access.
3. Treat this as a distinct pattern from ordinary null-pointer bugs — it is a
   security control that has three possible states (allowed / explicitly
   denied / absent) collapsed into two (checked / not-checked), where the
   collapse happens to favor the attacker. A code review or type-checker
   won't flag it because the code doesn't crash; it just does nothing.

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

**3b. Filtered vs. Unfiltered Accessor Bypass (dedicated check — do not skip)**
<!-- Standards: OWASP-API3:2023, CWE-200, CWE-862 -->
Codebases that handle privileged/sensitive collections (role or permission
definitions, tenant lists, PII-bearing records) frequently have TWO accessors
for the same underlying data: a scoped/filtered one meant for
external-facing use (`getVisibleRoles()`, `getScopedUsers()`,
`listPublicFields()`) and a raw/complete one meant for internal use
(`getAllRoles()`, `findAll()`, a direct repository/ORM call with no
projection). The vulnerability is a route or handler that calls the raw
accessor when it should call the filtered one.

1. Grep for accessor pairs that share a stem but differ by a scoping
   qualifier: `getAll*` vs `getVisible*`/`getScoped*`/`getPermitted*`,
   `findAll()` vs a repository method that takes a scope/tenant/role
   argument, a serializer/DTO that excludes fields vs. returning the raw
   entity/model directly.
2. Where both exist, check every caller of the raw/unfiltered one: is it only
   used internally (another service-layer computation, a background job), or
   does its result flow into an HTTP response? Any response-bound call to the
   unfiltered accessor is a bypass of whatever filtering the codebase clearly
   intended to apply somewhere.
3. Also check the response's cacheability (`Cache-Control`, CDN/edge cache
   config) when the data returned is privileged — a `public`/long-lived cache
   directive on an endpoint that discloses internal or restricted data
   amplifies the exposure (shared caches, CDNs, browser history) beyond the
   single request that triggered it, and is worth calling out explicitly as
   an amplifying factor even if the caching itself is a separate root cause.

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

**5b. Self-Healing / Bounded-Impact Claims Must Be Tested Against Rate Limiting (dedicated check — do not skip)**
<!-- Standards: CWE-770, CWE-799 -->
A destructive or disruptive action (delete-all, reset, bulk-teardown) is
sometimes judged lower severity because *something else* in the system
automatically repairs the damage on a schedule — a reconciliation job, a
background resync, a cache that eventually repopulates. That reasoning is
only valid if the destructive trigger itself cannot be repeated faster than
the repair cycle. Before accepting "it self-heals" or "the impact is bounded"
as a mitigating **Current control** for any destructive/disruptive endpoint:
1. Identify the repair/reconciliation interval (e.g., "resyncs every 15-30
   minutes").
2. Check whether the triggering endpoint has a rate limit, auth requirement,
   or any other friction that would stop a caller from simply looping the
   request faster than that interval.
3. If it has none, the "bounded" framing is false — a scripted/looping caller
   converts a single bounded incident into an indefinite, sustained outage at
   the caller's discretion. Report the finding's severity and exploit scenario
   accordingly (treat it as unbounded/indefinite denial of service, not a
   one-shot gap), and say explicitly in **Current controls** that the
   self-healing mechanism does not mitigate a repeated/looping trigger.
4. This reasoning applies independent of and in addition to any auth finding
   on the same endpoint — even if the endpoint also lacks authentication
   entirely, call out the missing-rate-limit dimension separately, since
   fixing auth alone (without also rate-limiting) would still leave the
   looping-trigger DoS available to any legitimate-but-compromised caller.

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
- **GET routes that perform a mutation are a CSRF/prefetch risk that framework CSRF middleware typically does NOT cover.** Standard CSRF protections (SameSite cookies, CSRF tokens, Origin/Referer checks) are conventionally applied only to POST/PUT/DELETE/PATCH — a route registered as `GET` whose handler body actually creates, deletes, or mutates state bypasses that protection entirely, and is trivially triggerable cross-site via a plain `<img>`/`<link>` tag, browser link-prefetch, or a victim simply opening a malicious link, with no token or special request needed. When enumerating routes for this section, don't assume "state-changing" means "non-GET" — read the handler body of every GET route, not just its declared verb, and flag any that mutates.
- **Cross-layer CSRF flow validation**: When the backend validates CSRF tokens, verify the full flow works end-to-end: (1) the CSRF action name is in the generation endpoint's allowlist, (2) the frontend actually requests and sends the token, and (3) the backend validates it. A broken link in any of these three steps means CSRF is either silently failing or silently bypassed. Check both the backend validation code AND the frontend service/fetch calls for each protected endpoint.

### 10. API Inventory & Lifecycle
<!-- Standards: OWASP API9:2023 -->
- Are there debug or internal endpoints exposed without authentication (`/debug`, `/test`, `/internal`, `/_health` with sensitive data)?
- Are there deprecated or legacy API versions still accessible (e.g., `/v1/` alongside `/v2/`)?
- Do all registered routes appear in API documentation or route config (no shadow endpoints)?
- Are there endpoints that accept requests but are undocumented or unused?
- Are there admin/management endpoints accessible from the public API surface?
- **Does a docs/spec-exposure guard cover every machine-readable variant the framework serves, not just the human-facing UI route?** Frameworks that auto-generate an interactive doc UI (Swagger UI, Redoc) also serve the underlying JSON/YAML spec on separate routes, and it's common to lock down the UI route while leaving the spec route open — check ALL of them together, not just the one that renders a page: NestJS/Swagger (`/api`, `/api-json`, `/api-yaml`), plain OpenAPI (`/swagger.json`, `/openapi.json`, `/v3/api-docs`, `/v2/api-docs`), Redoc, GraphQL introspection (`/graphql` with introspection enabled). An exposed machine-readable spec is a force-multiplier, not just its own informational finding: it hands an attacker the exact list of which routes require no auth (via each operation's declared `security` requirement), collapsing the recon phase of every other unauthenticated-endpoint finding in this report. If you find one, cross-reference it against every other unauthenticated-endpoint finding this pass produced and note the amplification explicitly in each one's exploit scenario — it materially changes "an attacker would have to guess this path" into "the attacker's own server told them this path exists and needs no token."

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
2. Map all route definitions and their auth levels — flag any suspicious NONE/public endpoints. If the framework is opt-in for auth (no explicit "public" marker exists at all), run the 1b enumeration instead of relying on a marker grep.
3. Check each endpoint's input validation against what the handler actually uses
4. Verify response payloads don't include unnecessary internal data
5. Check error handling consistency across all endpoints
6. Look for endpoints that bypass the framework's built-in protections
7. Trace all OAuth/SSO flows end-to-end: login initiation → redirect → callback → session creation → logout. Check each step for the protections listed in section 9.

## Patterns to Grep For

```
# Route definitions
RouteConfig|@app\.route|@router\.|app\.(get|post|put|delete|patch)

# Auth levels (opt-out frameworks — an explicit public marker exists)
AuthLevel\.NONE|auth_level.*none|authenticate.*false|@login_not_required

# Auth guards/middleware actually present (opt-in frameworks — build the positive set, then diff against routes)
UseGuards\(|@PreAuthorize|@Secured|permission_classes|login_required|Depends\(.*[Aa]uth|before_action.*authenticate|APP_GUARD

# Route registrations to diff against the guard set above (see section 1b)
@(Get|Post|Put|Delete|Patch)\(|@app\.route|router\.(get|post|put|delete)|@RequestMapping|@RestController

# Declared-but-maybe-unenforced security schemes ("auth theater" — confirm each is consumed by a real check)
addApiKey\(|addBearerAuth\(|SecurityRequirement|@ApiSecurity|securitySchemes

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

# Credential/session revocation caching (1c — check each hit for active invalidation on revoke)
LRUCache|NodeCache|lru_cache|memoize|CACHE_TTL|cacheTtl|authorizerResultTtlInSeconds
revoke|revoked|deactivate|invalidat.*cache|cache.*invalidat

# Fail-open on missing record (1d — read surrounding branches, not just the grep hit)
if\s*\(\s*(account|record|membership|tenant|profile|subscription)\s*\)|if\s+\w+\s+is\s+not\s+None
\.active\b|is_active|isActive|status.*active

# Filtered vs unfiltered accessor bypass (3b)
getAll[A-Z]\w*\(|findAll\(|getVisible[A-Z]\w*\(|getScoped[A-Z]\w*\(|getPermitted[A-Z]\w*\(
Cache-Control.*public|cache-control.*public

# GET routes with mutating handler bodies (CSRF section)
@(Get|get)\(.*\).*\n.*(delete|update|create|reset|destroy|remove)
router\.get\(.*(delete|update|create|reset)

# Self-heal / reconciliation claims to weigh against rate limiting (5b)
resync|reconcil|self.?heal|scheduleTasks|ScheduleTasks|cron.*(recreate|resync|repair)
ratelimit|rate.limit|throttl
```
