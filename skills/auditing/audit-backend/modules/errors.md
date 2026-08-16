# Module: Error Handling (ERR)

Evaluate whether the application uses the framework's error handling consistently, returns correct HTTP status codes, handles errors safely across all code paths, and avoids inline error response construction.

## Assertions

### ERR-1: Handlers raise framework exceptions, not return error dicts
- The framework provides an exception hierarchy (e.g., `ValidationError`, `AuthenticationError`, `NotFoundError`). Handlers should use it.
- Handlers should NOT return `{"success": False, "error": {...}}` dicts — this bypasses the framework's centralized error formatting, logging, and HTTP status code mapping.
- Look for: `return {"success": False` in handler code, error dicts constructed inline.

### ERR-2: All exceptions are caught and return structured JSON
- No request should result in an unhandled exception or raw stack trace to the client.
- The framework should have a catch-all that wraps unexpected errors in a standard error envelope.
- Look for: missing catch-all in the request handler, handlers that can throw uncaught exceptions.

### ERR-3: HTTP status codes are semantically correct
- Validation errors → 400. Not found → 404. Auth failures → 401/403. Server errors → 500.
- Errors should NOT return HTTP 200 with `success: false` — this breaks monitoring, load balancers, and HTTP-aware tooling.
- Look for: error responses that don't set a non-200 status code, framework errors returning 200.

### ERR-4: The exception hierarchy covers all application error cases
- The framework should have distinct exception types for: validation, not found, authentication, authorization/forbidden, conflict/duplicate.
- If handlers need an error type that doesn't exist, the hierarchy has a gap.
- Framework errors should be distinct from handler errors — enabling different logging levels and monitoring alerts.
- Look for: handlers returning error dicts because no matching exception type exists, generic `Exception` raises for domain-specific errors, all errors treated the same way.

### ERR-5: Error messages are user-facing quality
- Error messages should be clear, actionable, and safe (no internal details).
- "Name must be 1-100 characters" is good. "KeyError: 'name'" is not.
- Look for: raw exception messages exposed to clients, generic "Something went wrong" for known error cases, error messages containing file paths or stack frames.

### ERR-6: Error response format is consistent across all code paths
- Every error response (framework-generated and handler-generated) should have the same JSON shape.
- CORS headers must be added to error responses — without them, the browser blocks the error and the frontend can't read it.
- Look for: framework errors with one shape and handler errors with a different shape, missing fields in some error responses, error paths that skip CORS header addition.

### ERR-7: Request duration is logged for both success and failure paths
- Request timing should be captured regardless of outcome (success, auth failure, validation error, 500).
- This is critical for latency monitoring and alerting.
- Look for: duration calculation only in the success path, missing timing in exception handlers.

### ERR-8: Errors in async/background operations are logged, not swallowed
- If the application does any async work (background tasks, fire-and-forget API calls, optimistic updates), failures must be logged.
- Look for: bare `except: pass`, `try/except` blocks that catch and ignore errors, missing error logging in background operations.
