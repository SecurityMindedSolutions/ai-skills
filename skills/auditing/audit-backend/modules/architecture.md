# Module: Architecture (ARCH)

Evaluate whether the application follows clean architecture principles — thin handlers, service layer separation, clear boundaries between HTTP concerns and business logic, and a framework that scales without rewrites.

## Assertions

### ARCH-1: Handlers are thin — HTTP concerns only
- Handlers should extract input from the request context, delegate to a service, and return the result.
- A handler should be 3-10 lines: extract args, call service, wrap response.
- Handlers should NOT contain: database queries, entity construction, business validation, data serialization.
- Models, validation, and orchestration should live in separate files — not mixed into route handlers.
- Look for: handlers longer than 15 lines, handlers that import database clients, handlers that build entities, model definitions in handler files, validation logic inline in route handlers.

### ARCH-2: Route definitions are declarative
- Routes should be data (config arrays, decorators, or YAML), not imperative code inside the framework.
- Adding a new route should require only adding a route config entry and a handler function — zero framework changes.
- Look for: route definitions inside the service class, handler registration via imperative method calls, hardcoded route lists in the framework, switch/case on paths.

### ARCH-3: A service layer exists between handlers and data access
- Business logic should live in service modules that are callable without HTTP context.
- Services receive plain Python/JS arguments (not request objects or context dicts).
- Services return plain dicts or domain objects (not HTTP responses).
- Look for: handlers calling database clients directly, business logic inline in route handlers, no `services/` directory.

### ARCH-4: Services are reusable without HTTP context
- Service functions should be importable and callable from a CLI tool, scheduled job, or test without mocking any HTTP/framework objects.
- Handlers should receive a structured context (parsed, validated data) — not raw framework internals.
- Look for: services that import Flask, services that read from `request` objects, services that set HTTP headers, handlers calling `request.args.get()` for values that should be pre-validated.

### ARCH-5: Each layer has a single direction of dependency
- Handlers depend on services. Services depend on data access. Data access depends on the database client.
- No upward dependencies: services should not import from handlers, data access should not import from services.
- The framework layer should not statically import handler/business-logic modules — handlers should be loaded dynamically or via dependency injection.
- Look for: circular imports, services importing handler modules, data access importing service modules, framework files with `from module.xxx import` for handler code.

### ARCH-6: Business validation lives in the service layer (not handlers)
- Input validation (field presence, types) belongs at the framework/handler boundary.
- Business validation (length limits, format constraints, uniqueness checks, state transitions) belongs in services.
- Look for: business rules like `len(name) > 100` or regex checks in handler code, services that skip validation.

### ARCH-7: Response serialization is not scattered across handlers
- Entity-to-dict serialization should be defined once per domain object (in the service or a dedicated serializer).
- Handlers should not manually pick fields from database entities.
- Look for: `_serialize()` functions defined in multiple handler files, inline dict construction from entities in handlers.

### ARCH-8: Cross-cutting concerns use middleware, not inline checks
- Auth, logging, CORS, rate limiting should be handled once in the framework/middleware layer.
- These should NOT be copy-pasted into each handler.
- Look for: duplicate auth checks, CORS headers set in multiple places, logging boilerplate in handlers.

### ARCH-9: Shared utilities are extracted, not duplicated
- Helper functions used by 2+ modules should live in a shared location.
- Look for: identical or near-identical functions defined in multiple files (e.g., `_ancestor_key()`, `_build_key()`, `_format_date()`).

### ARCH-10: Framework is reusable across multiple services
- The framework should be deployable with different route configs for different services.
- Service-specific behavior should come from config, not framework code.
- Look for: service-specific logic hardcoded in the framework, imports from specific services.

### ARCH-11: Validation is declarative and composable
- Validation rules should be defined as data (schemas, configs, decorators), not imperative code per-route.
- Nested object validation should work without special-casing.
- Look for: hand-written validation in handlers, validation that doesn't support nesting or lists.

### ARCH-12: Outbound calls have timeouts and error handling
<!-- Standards: OWASP API10:2023, Enterprise Best Practices -->
- All outbound HTTP calls (to external APIs, webhooks, third-party services) should have explicit timeouts configured. A missing timeout means a single slow upstream can block the entire request indefinitely.
- External API failures should be caught and handled gracefully (retry with backoff for transient errors, degrade gracefully for non-critical calls).
- Database connection pools should have configured size limits and connection timeouts (not defaults).
- Look for: `requests.get/post()` without `timeout=`, database client creation without pool size or timeout config, external calls without try/except handling.
- Note: Flag as WARN (not FAIL) — this is a resilience best practice, not a correctness issue.

### ARCH-13: Cross-consumer operations have consistent security controls
- When the same operation is implemented across multiple entry points (web app API, public API, MCP server, webhooks), all implementations should enforce the same security controls: auth checks, CSRF, input validation, and audit logging.
- A common pattern that breaks: the primary web API has full controls (CSRF + granular auth + validation), then a public API or MCP wrapper is added later with only partial controls.
- Look for: the same core function called from multiple handlers/wrappers with different pre-checks, one consumer adding CSRF while others skip it, one consumer doing field-level validation while others pass raw input through.

### ARCH-14: Health check endpoint exists and is safe
<!-- Standards: Enterprise Best Practices, CIS -->
- The application should expose a health check endpoint (e.g., `/health`, `/_health`, `/ready`) for load balancer and orchestration use.
- Health check endpoints should NOT return sensitive information (no database connection strings, no internal state dumps, no dependency details).
- Health checks should verify the service can handle requests (not just return 200 unconditionally).
- Look for: health endpoints that return full config or dependency details, missing health endpoints entirely, health endpoints that leak internal architecture.
- Note: Flag as WARN (not FAIL) if health check exists but is too verbose. Flag as WARN if no health endpoint exists at all.
