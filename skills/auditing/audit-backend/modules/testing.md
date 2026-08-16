# Module: Testing (TEST)

Evaluate test coverage, test quality, and whether the application architecture supports effective testing.

## Assertions

### TEST-1: Business logic is testable without mocking infrastructure
- Service/business logic functions should accept plain arguments and return plain values.
- Testing business rules should NOT require mocking HTTP frameworks, database clients, or cloud services.
- Look for: service functions that can only be tested by mocking Firestore/SQL/Redis, business validation buried inside handlers that require full request mocking.

### TEST-2: Tests exist for all CRUD operations
- Every create, read, update, and delete operation exposed via the API should have at least one test.
- Look for: API endpoints or handler functions without corresponding test cases, untested CRUD paths.

### TEST-3: Negative test cases exist
- Tests should cover error paths, not just happy paths.
- Required negative tests: invalid input (wrong types, missing fields, too long), not found (nonexistent IDs), unauthorized access (wrong user, missing auth), duplicate creation (if applicable).
- Look for: test files that only test success paths, missing tests for validation errors, missing tests for 404 cases.

### TEST-4: Auth and access control have dedicated tests
- Authentication edge cases: expired sessions, invalid tokens, missing cookies.
- Authorization edge cases: wrong user accessing another user's data, insufficient role/permissions.
- Look for: auth tests that only check "valid token works", missing tests for cross-user data access, missing role-based access tests.

### TEST-5: Test setup is clean and maintainable
- Test fixtures and mocks should be centralized (conftest.py, test helpers, factory functions).
- Each test should set up only what it needs — no giant shared state.
- Look for: repeated mock setup in every test function, copy-pasted fixture code, test files over 500 lines, fragile tests that break when unrelated code changes.

### TEST-6: Tests run independently and deterministically
- Tests should not depend on execution order or shared mutable state.
- Each test should set up its own data and clean up after itself (or use isolated fixtures).
- Look for: tests that fail when run individually but pass in suite, tests that modify shared state, tests that depend on database seeding from another test.

### TEST-7: Test assertions are specific, not just "no error"
- Tests should assert on specific return values, response shapes, and side effects.
- `assert response.status_code == 200` alone is insufficient — also check the response body.
- Look for: tests that only check status codes, tests that assert `is not None` without checking contents, tests with no assertions (just "it didn't crash").
