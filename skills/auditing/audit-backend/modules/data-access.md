# Module: Data Access (DA)

Evaluate whether the application manages database interactions cleanly — consistent patterns, no duplication, proper client management, and safe query construction.

## Assertions

### DA-1: Database client instantiation is centralized
- There should be one function/factory for creating or retrieving the database client.
- Client reuse should follow the platform's best practices (e.g., GCP Cloud Functions should use a global singleton for warm invocations; serverless containers should use connection pooling).
- Look for: `Client()` constructors called in multiple places, database clients created per-request unnecessarily.

### DA-2: Data access helpers are defined once, not per-module
- Common patterns like building ancestor/parent keys, constructing entity keys, or formatting timestamps should be defined in one shared module.
- Look for: identical helper functions (`_ancestor_key`, `_build_key`, `_get_parent`) defined in multiple handler or service files.

### DA-3: Entity serialization is centralized per domain object
- Each domain object (category, todo, user, etc.) should have one serialization function that converts a database entity to an API-safe dict.
- Look for: `_serialize()` defined in multiple files with different field lists, inline `{"id": entity.id, "name": entity["name"]}` construction scattered across handlers.

### DA-4: Queries use parameterized inputs, never string interpolation
- All database queries must use parameterized queries, prepared statements, or the ORM's built-in escaping.
- This applies to SQL, Datastore GQL, Firestore queries, and any query language.
- Look for: f-strings or `.format()` in query construction, string concatenation for filters or keys built from user input.

### DA-5: Write operations are atomic where required
- Operations that update multiple related entities should use transactions or batch writes.
- Partial failures should not leave the database in an inconsistent state.
- Look for: multi-entity updates without transactions, reorder operations that update items one at a time, delete operations that don't clean up related entities.

### DA-6: Read operations are efficient
- List operations should use appropriate query filters and limits, not fetch-all-then-filter.
- Related data should be fetched in batch, not N+1 style.
- Look for: fetching all entities then filtering in Python/JS, loops that make one query per item, missing query limits on unbounded collections.

### DA-7: Database entities don't leak into API responses
- Raw database entities (with internal fields like `_kind`, `__class__`, ORM metadata) should never be returned directly in API responses.
- All entities should pass through serialization before reaching the response.
- Look for: entities returned directly from handlers, JSON serialization of ORM objects without explicit field selection.

### DA-8: Resource deletion has parity with creation (no orphaned stores)
- When a top-level owner is deleted (account, tenant, organization, workspace, user), every store that was written during its **creation** must have a corresponding **teardown**: primary records, subcollections/related rows, membership/join records, denormalized counters, per-owner buckets/keys, and externally-provisioned resources (DNS/CDN hostnames, external API objects).
- Parent-record deletion does not always cascade — document stores (Firestore, etc.) and schemas without `ON DELETE CASCADE` require explicit deletion of children. A store seeded at create but missing from delete orphans that owner's data indefinitely (a privacy/erasure defect).
- The durable safeguard is a parity check/test asserting every create-time store is covered by delete. Look for: a `create_*`/`delete_*` service pair where the delete path omits stores the create path writes; deletion code that assumes a cascade the datastore doesn't provide; the absence of any test enforcing create/delete parity.
- Intentional, documented, time-bounded retention (audit logs, immutable backups) is acceptable and should not be flagged as an orphan.
