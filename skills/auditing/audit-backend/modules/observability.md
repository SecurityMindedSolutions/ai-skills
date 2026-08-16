# Module: Observability (OBS)

Evaluate whether the application produces logs and metadata sufficient for debugging, monitoring, and alerting in production.

## Assertions

### OBS-1: Logging uses structured format (JSON) for production
- Production logs should be structured JSON for machine parsing by cloud log aggregators (Cloud Logging, CloudWatch, Datadog).
- Each log entry should include at minimum: severity/level, message, timestamp.
- Look for: plain text log formatting in production config, `print()` statements, f-string logging without structured fields.

### OBS-2: Request ID is propagated through all layers
- A unique request ID should be generated at request entry and included in every log line for that request.
- The ID should be available to framework code, handlers, services, and data access layers.
- Look for: request ID generated but only used in framework-level logs, services that log without request context, handler logs missing request ID.

### OBS-3: Request ID is returned to the client
- The request ID should be included in response headers (e.g., `X-Request-Id`) or the response body.
- This allows users/frontend to reference specific requests in bug reports.
- Look for: request ID generated but never sent back to the client.

### OBS-4: Auth events are logged with security context
- Successful logins, failed auth attempts, session creation/destruction, and permission denials should be logged.
- Logs should include: user identifier, action, outcome, and IP address where available.
- Look for: silent auth failures, login events without user context, missing permission denial logs.

### OBS-5: Success and failure paths both log method, path, duration, and user context
- Minimum fields per request log: HTTP method, path, duration (ms), user identifier (or "anonymous").
- These should appear in both success and error log lines.
- Look for: error paths with less detail than success paths, missing duration in error logs.

### OBS-6: Error logs include sufficient debugging context
- Error logs should include: the error type, message, relevant entity IDs, user context, and request ID.
- Stack traces should appear in server logs (not client responses).
- Look for: error logs with only a message and no context, `logger.error(str(e))` without additional fields, errors logged without the triggering request context.

### OBS-7: Business operations are logged at appropriate levels
- Create/update/delete operations should log at INFO level with entity type and ID.
- Validation failures should log at WARNING level.
- Unexpected errors should log at ERROR level.
- Look for: all logs at the same level, missing audit trail for data mutations, verbose DEBUG logging left on in production config.

### OBS-8: No sensitive data in logs
- Logs must NOT contain: passwords, session tokens, API keys, PII beyond user identifiers.
- Hashed or masked values are acceptable for debugging (e.g., last 4 chars of a token).
- Look for: full session tokens in log lines, request bodies logged without field filtering, OAuth tokens or secrets in debug logs.
