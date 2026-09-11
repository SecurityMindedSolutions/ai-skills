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

### DA-9: Delete operations verify completion and propagate partial failure
- Applies to every store the app deletes from: relational/document databases, key-value stores, object/blob storage, caches, search/vector indexes, queues, file systems, and third-party APIs holding data on the app's behalf.
- Bulk/batch delete APIs (multi-key object deletes, batch-write calls carrying delete requests, cache multi-key eviction, `deleteMany`, third-party bulk-delete SDKs) can return a success-level response while silently failing on some items. The per-item failure/unprocessed field on that response (`Errors`, `Unprocessed*`, `Unsuccessful*`/`Failed*`, a per-item status array, a `deletedCount` lower than requested) must be read and acted on — retried, raised, or alerted — not merely present in the SDK's typed response and ignored. When the SDK's response shape isn't known, look it up rather than assuming it throws.
- A delete helper that returns `false`/`None`/an error object on failure must have every caller check that return value; a caller that logs "deleted" unconditionally after calling it is a bug regardless of whether the helper itself is correct.
- A delete-by-prefix/query/filter that matches zero items should not be indistinguishable from a successful delete: if the caller expected N items, zero matches is a signal (wrong key, drifted prefix, misconfigured target), not a clean no-op.
- If the destination retains prior versions (versioned buckets, soft-delete, snapshots, time-travel reads), a delete that doesn't target the specific version only writes a tombstone; data described as removed for retention/compliance purposes is still recoverable. Confirm via IaC where possible, otherwise flag as unconfirmed.
- Look for: `.catch(() => void 0)` / `.catch(logger.warn)` or bare `except: pass` around a delete call, a `Promise.all(...).catch(logger.error)` wrapping a batch of independent delete operations (this converts a per-page failure into an overall silent success), delete helper functions whose boolean/error return value isn't checked at any call site, batch delete results whose failure field is never referenced, delete-by-filter routines with no expected-count cross-check.

### DA-10: Multi-step and destructive-migration deletes are scoped, ordered deliberately, and reversible
- A deletion that spans more than one backend or more than one step (blob + database row, database row + cache entry, primary store + secondary index, local record + third-party resource) should either be transactional, use an outbox/compensating pattern, or have an explicit, documented choice of which step runs first and why — not an accidental ordering with no consideration of what state a failure between steps leaves behind. Retention/compliance deletes should generally prefer "data gone, record inconsistent" over the reverse; general cleanup often prefers the opposite. Either way it must be a decision, not an accident.
- Idempotency/early-return guards on cleanup routines ("record already gone, skip") must not skip the remaining steps of a multi-step cleanup when a retry follows a partial failure.
- Schema migrations and maintenance scripts that contain a `DELETE`/`TRUNCATE`/`DROP` — especially ones bundled into an otherwise-unrelated schema change — must scope the WHERE clause narrowly (by id or a reviewed drop-list, not a broad negative or absent WHERE), and the paired down-migration should restore the data or, at minimum, the migration should call out explicitly that it's irreversible before it ships. A destructive statement that runs unattended across every environment carries the same blast radius as a standalone maintenance script and should be reviewed with the same rigor.
- Look for: `DELETE FROM` inside a migration file with no matching data-restore in its down-migration, destructive scripts/migrations with no transaction wrapper (`BEGIN`/`COMMIT` or ORM transaction) around delete+dependent-write pairs, no dry-run or row-count sanity check before a bulk delete executes, delete-then-reinsert sequences that lose data if interrupted between the two.
