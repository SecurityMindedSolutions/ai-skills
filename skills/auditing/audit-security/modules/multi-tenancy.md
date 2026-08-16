# Multi-Tenancy & Tenant Isolation Review Module

Review a multi-tenant application for cross-tenant data leakage and isolation failures.

This module applies to any system where data is partitioned by a tenant boundary — call it
tenant, organization, workspace, account, team, project, or customer. The single worst failure
class in a multi-tenant SaaS is one tenant reading or mutating another tenant's data, so isolation
deserves a dedicated pass rather than a single bullet inside a generic auth review.

If the target is single-tenant (no tenant/org/workspace partitioning of data), this module is N/A —
say so and stop.

## Categories to Review

### 1. Tenant Identifier Provenance
<!-- Standards: OWASP-API1:2023, OWASP-API5:2023, CWE-639, CWE-565 -->
- The tenant a request operates on must be derived from a **trusted, server-verified source** — a
  validated session/token claim, or a path segment that a central gate then authorizes the caller
  against. It must NOT be taken, for authorization purposes, from a client-controllable field that
  nobody re-checks: request body, query string, or an arbitrary request header.
- Flag any handler that reads the tenant/org id from `request.body`, `request.json`, `request.args`,
  or a custom header (e.g. `X-Tenant-Id`) and then uses it to scope data **without** a membership/
  ownership check that the current identity belongs to that tenant.
- Flag "tenant from two sources" bugs: identity resolved from the session but the tenant taken from
  a body field, so a valid user for tenant A can pass `tenant_id=B`.
- The safe pattern: identity from the session; tenant from a validated path param; a central gate
  asserts `identity ∈ members(tenant)` before the handler runs.

### 2. Tenant-Scoped Data Access
<!-- Standards: OWASP-API1:2023, CWE-639, CWE-566 -->
- **Every** data read/write that touches tenant-owned data must include the tenant scope: a `WHERE
  tenant_id = :t` clause, an ancestor/partition key, a per-tenant collection/table, or a per-tenant
  object-store prefix. A query that omits the scope filter returns or mutates across tenants.
- Check object storage: per-tenant bucket or a tenant-prefixed key path — never a shared path where
  the only thing separating tenants is an unguessable id (that is IDOR waiting to happen).
- Check **cache keys**: any cache (in-process, Redis, CDN) keyed without the tenant in the key can
  serve tenant A's cached response to tenant B. Grep for cache `.set(`/`.get(` where the key is built
  from a resource id but not the tenant.
- Check **background jobs, exports, webhooks, and scheduled tasks**: these frequently run outside the
  request-scoped middleware and are a classic place the tenant filter gets dropped.

### 3. Centralized, Fail-Closed Enforcement
<!-- Standards: OWASP-API5:2023, CWE-862, CWE-863 -->
- Tenant membership/authorization should be enforced in **one central place** (middleware, a request
  dispatcher, a decorator applied uniformly) that a new handler cannot forget to call — not
  re-implemented per handler. Per-handler manual checks are the pattern that eventually ships a
  handler with no check at all.
- The gate must **fail closed**: unknown route/permission/tenant → deny, not allow. Flag any
  `if can_access: ... ` with no `else: deny`, or default-allow permission maps.
- If isolation rests entirely on this one gate (no secondary data-layer enforcement such as DB
  row-level security or client-SDK security rules), that is acceptable but raises the stakes — every
  handler bypassing the gate is a full cross-tenant hole. Flag any route registered without the
  standard auth/tenant middleware.

### 4. Cross-Tenant IDOR / BOLA
<!-- Standards: OWASP-API1:2023, CWE-639 -->
- For every endpoint that takes an object identifier (doc id, record id, file id), verify the lookup
  is constrained to the caller's tenant — e.g. `get(tenant_id, doc_id)` not `get(doc_id)` followed by
  an assumed-safe return. Fetching by global id and returning it without re-checking tenant ownership
  is Broken Object Level Authorization.
- "Unguessable UUID" is not an authorization control. A leaked/logged/enumerated id must still be
  rejected cross-tenant. Do not accept "the id is random" as the isolation mechanism.

### 5. Tenant / Resource Enumeration & Existence Oracles
<!-- Standards: OWASP-API1:2023, CWE-204, CWE-203 -->
- Requests for a resource in another tenant (or a non-existent tenant) should return an **identical**
  response to "not found" — same status code, same body shape, ideally similar timing. Distinct
  responses (`403` for exists-but-forbidden vs `404` for absent) leak which tenants/resources exist
  and enable enumeration of customer identifiers, slugs, or ids.
- Flag branches that return different status/body for "not authorized" vs "not found" on
  tenant-scoped or public-per-tenant resources.
- Flag sequential/guessable tenant identifiers (auto-increment ids, predictable slugs) combined with
  a distinguishable "exists" response.

### 6. Cross-Tenant Resource Sharing Boundaries
<!-- Standards: OWASP-API1:2023, CWE-668 -->
- Presigned/signed URLs must be scoped to the tenant's storage and time-boxed; a presigned URL
  pattern reachable across tenant prefixes is a leak.
- Shared infrastructure (a single search index, a single analytics table, a shared queue) must carry
  and filter on the tenant field on **every** query. Grep analytics/search queries for a missing
  tenant predicate.
- Per-tenant encryption (CMK/CMEK) or per-tenant buckets: verify no shared staging/quarantine/scratch
  location co-mingles bytes from multiple tenants, even transiently.

### 7. Injection in Tenant-Scoped Filters
<!-- Standards: OWASP-Web-A05:2025, CWE-89, CWE-943 -->
- Where a user-supplied value feeds a `LIKE`/wildcard/search filter that also carries the tenant
  predicate, verify wildcard metacharacters (`%`, `_`, and the escape char) are escaped so a crafted
  value can't broaden the match. The tenant `AND` must not be defeatable by the user-controlled term.
- Confirm the tenant predicate is a **bound parameter**, never string-interpolated alongside the
  user term.

### 8. Per-Tenant Resource Lifecycle Completeness (Create/Delete Parity)
<!-- Standards: OWASP-Web-A09:2025, CWE-459, GDPR Art.17 -->
- When a tenant/account is deleted, **every** store written during its creation must have a
  corresponding teardown. Enumerate what tenant creation writes (primary docs, subcollections,
  membership records, denormalized counters, per-tenant buckets/keys, external resources like DNS/CDN
  hostnames, analytics rows) and verify the delete path covers each. A store seeded at create but
  absent from delete silently orphans that tenant's data forever — a privacy/erasure failure.
- Parent-record deletion does **not** always cascade to subcollections/related rows (true for
  document stores like Firestore, and for any schema without `ON DELETE CASCADE`). Flag delete paths
  that assume a cascade that the datastore does not provide.
- Denormalized counters/aggregates must be corrected on delete.
- The durable safeguard is a **parity test/check**: an assertion that every per-tenant store created
  is also deleted. Flag its absence — without it, the next new per-tenant store orphans undetected.
- Note the retention carve-out: audit logs / immutable backups may be intentionally retained past
  tenant deletion. That is acceptable **if** it is a documented, time-bounded policy, not an
  overlooked store. Do not flag a clearly-intentional, aging-out audit archive as an orphan.

### 9. Client-Side Data-Layer Access Boundary
<!-- Standards: OWASP-API1:2023, OWASP-Web-A01:2025, CWE-639 -->
- If the client bundle talks to a database/storage SDK directly (Firebase/Firestore, Supabase,
  AWS Amplify/AppSync, PocketBase, etc.), the datastore's **security rules are the tenant boundary**
  and must be audited: verify rules enforce tenant/ownership scoping on every collection/path, and
  fail closed by default. A permissive/`allow read, write: if true`-style rule is a full breach.
- If data access is exclusively server-side (the client only calls your own API), verify the client
  bundle does **not** import a direct data-layer SDK. An accidental direct-DB import creates a second,
  unrules'd access path around the server-side gate. Grep the frontend for direct DB/storage SDK
  imports and flag any that appear when the architecture is meant to be server-mediated.

## Scanning Approach

1. Establish the tenant boundary term (tenant/org/workspace/account) and how a request is bound to
   it — read the auth/dispatch middleware first.
2. Enumerate routes; for each tenant-scoped route confirm the tenant id is resolved from a trusted
   source and a central gate authorizes membership before the handler.
3. Grep data-access call sites for a missing tenant predicate (queries, object paths, cache keys,
   analytics/search).
4. Trace one object-id endpoint end to end to confirm cross-tenant BOLA is prevented at the data
   layer, not just the UI.
5. Compare the tenant-create writes against the tenant-delete teardown for parity.
6. If a client-side DB SDK is used, pivot to auditing its security rules; if not, confirm the client
   has no direct DB import.

## Patterns to Grep For

```
# Tenant id taken from client-controllable sources (suspicious if used to scope data)
request\.(json|body|form|args|query)\.get\(['"](tenant|org|organization|workspace|account|company)_?id
req\.(body|query|params)\.(tenant|org|workspace|account)Id
headers?\.get\(['"]?[xX]-(tenant|org|workspace)

# Data access — check each for a tenant predicate nearby
\.where\(|WHERE |\.filter\(|\.find\(|\.query\(|collection\(|\.document\(
tenant_id|org_id|organization_id|workspace_id|account_id

# Object storage paths / buckets (tenant scoping)
bucket|blob|\.upload|putObject|getObject|storage\.|gs://|s3://

# Cache keys (check for tenant in the key)
cache\.(set|get)|redis\.(set|get)|\.setex\(|memcache|cacheKey|cache_key

# Existence oracle — different responses for forbidden vs not-found
40[13]|not_found|Forbidden|NotAuthorized|does not exist|permission denied

# LIKE / wildcard filters (check for metachar escaping)
LIKE |ILIKE | rlike|contains\(|startsWith\(|search.*%

# Deletion / lifecycle
delete_tenant|deleteAccount|delete_org|teardown|purge|cascade|ON DELETE

# Client-side direct DB SDK (server-mediated architectures should have none)
firebase/firestore|getFirestore|@supabase/supabase-js|createClient\(|aws-amplify|AppSync|pocketbase
```
