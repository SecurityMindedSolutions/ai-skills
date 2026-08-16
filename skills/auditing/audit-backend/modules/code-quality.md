# Module: Code Quality (CQ)

Evaluate code maintainability, readability, and adherence to clean code principles. This is about day-to-day code health, not architecture (which ARCH covers).

## Assertions

### CQ-1: Functions stay under 50 lines
- No single function should exceed ~50 lines of logic (excluding docstrings, blank lines, and imports).
- Long functions indicate multiple responsibilities that should be extracted.
- Look for: functions over 50 lines in handler, service, and utility code. Count actual logic lines.

### CQ-2: No duplicated code blocks across modules
- Code blocks of 5+ lines that appear in multiple files should be extracted to shared utilities.
- Near-duplicates (same logic, different variable names) count as duplicates.
- Look for: identical or near-identical functions, repeated patterns like error response construction, duplicate entity-building code.

### CQ-3: Naming is consistent and descriptive
- Functions, variables, and modules should follow the language's conventions (snake_case for Python, camelCase for JS/TS).
- Names should describe what they do, not how they do it (`get_active_todos` not `query_datastore_for_todos`).
- Private/internal functions should be prefixed consistently (`_` in Python).
- Look for: mixed naming conventions, single-letter variables outside loops, misleading names.

### CQ-4: No dead code or commented-out code
- Unused functions, unreachable branches, and commented-out code blocks should be removed.
- Version control preserves history — there's no need to keep commented-out code.
- Look for: functions that are never called, `if False:` blocks, large blocks of commented-out code, unused imports.

### CQ-5: Magic numbers and strings are constants
- Repeated literal values (status codes, field lengths, config values) should be named constants.
- Look for: `100` as a name length limit used in multiple places, hardcoded strings like `"VALIDATION_ERROR"` repeated across files, color codes or regex patterns inline.

### CQ-6: Imports are clean and organized
- Imports should be organized by convention (stdlib, third-party, local).
- No wildcard imports (`from module import *`).
- No unused imports.
- Look for: `import *`, unused imports, circular import workarounds (imports inside functions for non-performance reasons).

### CQ-7: Configuration and env vars are not scattered
- All configuration (env vars, defaults, feature flags) should be read in one config module.
- Handler and service code should import config values, not read `os.environ` directly.
- Look for: `os.environ.get()` or `os.getenv()` outside config/settings modules, hardcoded values that should be configurable.

### CQ-8: No global mutable state modified at request time
- Module-level variables, singletons, or class attributes should not be mutated during request handling.
- Request-scoped data should be stored in per-request objects (context dicts, thread-locals, or request objects).
- Look for: global dicts/lists appended to during requests, class-level caches modified without locks.

### CQ-9: No isinstance chains that should be dispatch maps
- Long `isinstance` or `if/elif` chains for type-based dispatch are a code smell past 3-4 types.
- These should be replaced with dict-based dispatch or polymorphism.
- Look for: `isinstance` chains in error handling, response processing, or validation.
- Note: Flag as WARN (not FAIL) if 4 or fewer types — it's a watch item, not a violation.

### CQ-10: No string-based type systems
- Type checking should use Python types, enums, or type annotations — not string comparisons.
- Look for: `if type == "str"`, `if config.type == "int"` — these should be enum values or type objects.
- Note: If the string-based system is contained to one module and works consistently, flag as WARN.

### CQ-11: No magic return values that control framework behavior
- Handlers returning special keys (e.g., `{"session_token": ..., "clear_session": True}`) to trigger framework-level side effects (cookie setting, session clearing) is an implicit contract.
- This isn't necessarily wrong for small systems, but should be documented and the keys should be constants.
- Look for: undocumented magic keys in handler return values, keys that are `.pop()`ed before serialization.
