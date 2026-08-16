# Module: Data Contracts (DC)

Evaluate whether the API framework enforces clear, typed contracts between layers (framework <-> handlers <-> clients).

## Assertions

### DC-1: Handler input contract is explicit and typed
- What handlers receive should be well-defined (a typed context object, named parameters, or a documented dict structure).
- Handlers should not need to guess what keys are available or do defensive `.get()` for expected data.
- Look for: handlers using `.get()` with defaults for data the framework guarantees, undocumented context keys.

### DC-2: Handler output contract is explicit
- What handlers can return should be documented: plain dicts, response objects, or specific types.
- The framework should handle all valid return types consistently.
- Look for: undocumented return value conventions, framework crashing on unexpected return types.

### DC-3: API error envelope is standardized
- All API responses (success and error) should follow a consistent JSON structure.
- Clients should be able to parse any response with the same code.
- Look for: success responses with different shapes, error responses missing expected fields.

### DC-4: Route config declares its full contract
- Each route definition should declare: method, path, handler, auth level, parameters, body schema, and allowed roles.
- Missing declarations should fail explicitly (not silently skip validation).
- Look for: routes with no parameter config that accept query params, routes with no body schema that read JSON bodies.

### DC-5: Validation errors include field-level detail
- When validation fails, the error response should identify which field failed and why.
- Generic "validation failed" messages force clients to guess what's wrong.
- Look for: validation errors without field names, generic error messages for specific field failures.

### DC-6: Type coercion is explicit and safe
- String-to-type conversion (query params, path params) should handle invalid input gracefully.
- The framework should return a clear error, not crash on `int("abc")`.
- Look for: bare `int()` / `float()` casts without try/except, type coercion that silently truncates.
