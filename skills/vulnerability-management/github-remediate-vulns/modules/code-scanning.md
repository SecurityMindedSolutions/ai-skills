# Code Scanning Alert Remediation Module

Apply fixes for CodeQL and other SAST findings with known remediation patterns. Conservative approach: only attempt fixes for well-understood rules. Unknown rules go to MANUAL.

## Alert Structure

Code scanning alerts from the GitHub API include:

```
alert.rule.id                    → e.g., "py/incomplete-url-substring-sanitization"
alert.rule.description           → human-readable description
alert.rule.severity              → "error", "warning", "note"
alert.rule.security_severity_level → "critical", "high", "medium", "low"
alert.tool.name                  → "CodeQL" or other tool
alert.most_recent_instance.location.path     → file path
alert.most_recent_instance.location.start_line → line number
alert.most_recent_instance.location.end_line   → end line
alert.most_recent_instance.message.text      → description of the specific instance
```

## Classification Logic

**ASSISTED-FIX** if the rule ID matches a known fix pattern (see below).
All code scanning fixes are ASSISTED (not AUTO) because code changes carry higher risk than version bumps and need human review.

**MANUAL** if:
- Rule ID is not in the known patterns list
- The code context is too complex to safely auto-fix
- The fix would require architectural changes

## Known Fix Patterns

### `py/incomplete-url-substring-sanitization`
**Problem**: Using string operations (`.startswith()`, `in`, `.find()`) to validate URLs.
**Risk**: Attacker can bypass with crafted URLs (e.g., `evil.com/good.com`).

**Fix pattern**:
```python
# BEFORE (vulnerable)
if url.startswith("https://example.com"):
    # or: if "example.com" in url:
    allow(url)

# AFTER (fixed)
from urllib.parse import urlparse
parsed = urlparse(url)
if parsed.scheme == "https" and parsed.netloc == "example.com":
    allow(url)
```

**Steps**:
1. Read 50 lines of context around the flagged line
2. Identify the URL variable and the string check being performed
3. Add `from urllib.parse import urlparse` if not already imported
4. Replace the string check with proper URL parsing
5. Preserve the original logic (what happens on match/no-match)

### `py/weak-sensitive-data-hashing`
**Problem**: Using MD5 or SHA-1 to hash sensitive data (passwords, tokens, PII).
**Risk**: These algorithms are cryptographically broken for security purposes.

**Fix pattern**:
```python
# BEFORE (vulnerable)
import hashlib
hashed = hashlib.md5(password.encode()).hexdigest()
# or: hashlib.sha1(data.encode()).hexdigest()

# AFTER (for passwords - use bcrypt)
import bcrypt
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

# AFTER (for data integrity/fingerprinting - use SHA-256)
import hashlib
hashed = hashlib.sha256(data.encode()).hexdigest()
```

**Steps**:
1. Read the context to determine what is being hashed
2. If hashing passwords: replace with bcrypt (add to requirements if needed)
3. If hashing for integrity/fingerprinting: replace with SHA-256
4. If hashing for non-security purposes (checksums, cache keys): classify as MANUAL with note
5. Check if the hash output is stored/compared anywhere - update those too

### `py/sql-injection`
**Problem**: Building SQL queries with string formatting/concatenation.
**Risk**: Attacker can inject arbitrary SQL.

**Fix pattern**:
```python
# BEFORE (vulnerable)
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
# or: cursor.execute("SELECT * FROM users WHERE id = " + user_id)
# or: cursor.execute("SELECT * FROM users WHERE id = %s" % user_id)

# AFTER (parameterized)
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
# or for named params:
cursor.execute("SELECT * FROM users WHERE id = :id", {"id": user_id})
```

**Steps**:
1. Read the full function containing the flagged line
2. Identify all variables interpolated into the query
3. Replace with parameterized query syntax appropriate for the DB library
4. For SQLAlchemy: use `text()` with `:param` syntax
5. For psycopg2/MySQLdb: use `%s` positional params
6. For sqlite3: use `?` positional params

### `js/xss`
**Problem**: Inserting user-controlled data into the DOM without encoding.
**Risk**: Cross-site scripting - attacker can execute arbitrary JavaScript.

**Fix pattern**:
```javascript
// BEFORE (vulnerable)
element.innerHTML = userInput;
document.write(userInput);

// AFTER (textContent for plain text)
element.textContent = userInput;

// AFTER (DOMPurify for HTML)
import DOMPurify from 'dompurify';
element.innerHTML = DOMPurify.sanitize(userInput);
```

**Steps**:
1. Read surrounding context to understand what the user input is
2. If plain text output: replace `innerHTML` with `textContent`
3. If HTML output is intentional: add DOMPurify sanitization
4. Check for React `dangerouslySetInnerHTML` - wrap value in DOMPurify
5. If the pattern is complex (template engines, SSR), classify as MANUAL

### `py/command-injection`
**Problem**: Passing user input to shell commands via `os.system()`, `subprocess.call()` with `shell=True`.
**Risk**: Attacker can inject arbitrary OS commands.

**Fix pattern**:
```python
# BEFORE (vulnerable)
import os
os.system(f"ls {user_path}")
# or: subprocess.call(f"git clone {repo_url}", shell=True)

# AFTER (list args, no shell)
import subprocess
subprocess.run(["ls", user_path], check=True)
# or: subprocess.run(["git", "clone", repo_url], check=True)
```

**Steps**:
1. Read the full function to understand the command being built
2. Replace `os.system()` or `shell=True` subprocess calls with list-arg subprocess
3. Split the command into proper list elements
4. Remove `shell=True`
5. If the command genuinely needs shell features (pipes, redirects), classify as MANUAL

### `js/sql-injection`
**Problem**: Building SQL queries with string concatenation or template literals.
**Risk**: Attacker can inject arbitrary SQL through user-controlled values.

**Fix pattern**:
```javascript
// BEFORE (vulnerable)
const query = `SELECT * FROM users WHERE id = ${userId}`;
db.query(query);
// or: db.query("SELECT * FROM users WHERE id = " + userId);

// AFTER (parameterized - pg/mysql2)
db.query("SELECT * FROM users WHERE id = $1", [userId]);
// or for mysql2:
db.query("SELECT * FROM users WHERE id = ?", [userId]);

// AFTER (Knex.js)
knex("users").where("id", userId);

// AFTER (Prisma - already safe by default, but raw queries need params)
prisma.$queryRaw`SELECT * FROM users WHERE id = ${userId}`;
```

**Steps**:
1. Read the full function containing the flagged line
2. Identify the DB library (pg, mysql2, sqlite3, knex, sequelize, prisma)
3. Replace string interpolation with parameterized queries using the library's syntax
4. For `pg`: use `$1, $2` positional params
5. For `mysql2`/`sqlite3`: use `?` positional params
6. For ORMs with raw queries: use the ORM's parameterized raw query method

### `js/path-injection`
**Problem**: User input used in file system paths without sanitization.
**Risk**: Attacker can traverse directories to read/write arbitrary files.

**Fix pattern**:
```javascript
// BEFORE (vulnerable)
const filePath = path.join(uploadDir, req.params.filename);
fs.readFile(filePath);

// AFTER (validated)
const path = require("path");
const safeName = path.basename(req.params.filename); // strips directory traversal
const filePath = path.join(uploadDir, safeName);
const resolved = path.resolve(filePath);
if (!resolved.startsWith(path.resolve(uploadDir))) {
  throw new Error("Path traversal detected");
}
fs.readFile(resolved);
```

**Steps**:
1. Read context to find where user input enters the path construction
2. Add `path.basename()` to strip directory components from user input
3. Add a `path.resolve()` + `startsWith()` guard to ensure the final path stays within the intended directory
4. If the code needs subdirectories from user input, classify as MANUAL (more complex validation needed)

### `js/code-injection`
**Problem**: User input passed to `eval()`, `Function()`, `setTimeout(string)`, or `vm.runInNewContext()`.
**Risk**: Attacker can execute arbitrary JavaScript in the server context.

**Fix pattern**:
```javascript
// BEFORE (vulnerable)
eval(userExpression);
new Function("return " + userInput)();
setTimeout(userCode, 1000);

// AFTER (safe alternatives depend on use case)
// For JSON parsing: use JSON.parse()
JSON.parse(userInput);
// For math expressions: use a safe expression parser like expr-eval
const { Parser } = require("expr-eval");
new Parser().evaluate(userExpression);
// For setTimeout: use function reference
setTimeout(() => { /* safe logic */ }, 1000);
```

**Steps**:
1. Read context to understand what the eval/Function is doing
2. If parsing JSON: replace with `JSON.parse()`
3. If evaluating math: add `expr-eval` dependency and use its parser
4. If evaluating user-defined logic: classify as MANUAL (requires architectural redesign)
5. For `setTimeout`/`setInterval` with string args: convert to arrow function

### `go/sql-injection`
**Problem**: SQL queries built with `fmt.Sprintf` or string concatenation.
**Risk**: Attacker can inject arbitrary SQL.

**Fix pattern**:
```go
// BEFORE (vulnerable)
query := fmt.Sprintf("SELECT * FROM users WHERE id = '%s'", userID)
db.Query(query)

// AFTER (parameterized)
db.Query("SELECT * FROM users WHERE id = $1", userID) // PostgreSQL
db.Query("SELECT * FROM users WHERE id = ?", userID)  // MySQL
```

**Steps**:
1. Read the full function containing the flagged line
2. Identify the database driver (lib/pq for Postgres, go-sql-driver/mysql, mattn/go-sqlite3)
3. Replace `fmt.Sprintf` query building with parameterized queries
4. For PostgreSQL: use `$1, $2` positional params
5. For MySQL/SQLite: use `?` positional params
6. If using an ORM (GORM, sqlx): use the ORM's parameterized methods

### `go/path-injection`
**Problem**: User input used in file paths without validation.
**Risk**: Directory traversal to read/write arbitrary files.

**Fix pattern**:
```go
// BEFORE (vulnerable)
filePath := filepath.Join(baseDir, userInput)
data, err := os.ReadFile(filePath)

// AFTER (validated)
filePath := filepath.Join(baseDir, filepath.Base(userInput))
absPath, err := filepath.Abs(filePath)
if err != nil || !strings.HasPrefix(absPath, filepath.Clean(baseDir)) {
    return fmt.Errorf("invalid path")
}
data, err := os.ReadFile(absPath)
```

**Steps**:
1. Add `filepath.Base()` to strip directory components from user input
2. Resolve to absolute path and verify it stays under the base directory
3. Add `strings` import if not present
4. If the code needs subdirectories from user input, classify as MANUAL

### `go/command-injection`
**Problem**: User input passed to `exec.Command` with shell invocation.
**Risk**: Attacker can inject OS commands.

**Fix pattern**:
```go
// BEFORE (vulnerable)
cmd := exec.Command("sh", "-c", "git clone " + repoURL)

// AFTER (list args, no shell)
cmd := exec.Command("git", "clone", repoURL)
```

**Steps**:
1. Read the full function to understand the command
2. Replace `sh -c` invocations with direct command + argument list
3. If the command genuinely needs shell features (pipes, globbing), classify as MANUAL

## Remediation Process

### 1. Read context

For each alert, read 50 lines of context around the flagged location:
- Use Read tool with the file path from the alert
- Calculate offset: `max(1, start_line - 25)` and limit: `50`
- Understand the surrounding code structure

### 2. Match fix pattern

Compare the `rule.id` against known patterns above. If no match, classify as MANUAL immediately.

### 3. Apply fix

Follow the specific steps for the matched pattern. Key principles:
- **Minimal changes**: Only modify what's necessary. Don't refactor surrounding code.
- **Preserve behavior**: The fix should not change program behavior except to close the vulnerability.
- **Import management**: Add imports at the top of the file if needed. Don't duplicate existing imports.
- **Add dependencies if needed**: If the fix requires a new package (e.g., bcrypt, DOMPurify), add it to the manifest file.

### 4. Run tests

Run the repo's test suite. If tests fail:
- Revert ALL changes for this alert
- Record the failure reason
- Classify as FAILED

### 5. Handle test files

If the flagged code is in a test file (path contains `test_`, `_test.`, `tests/`, `__tests__/`, `.spec.`, `.test.`):
- The fix may be less critical (test code isn't production)
- Still apply the fix if straightforward
- Note in the report that this is test-only code
- Consider recommending dismissal with reason "used in tests"

## Unknown Rules

For any `rule.id` not listed above, classify as MANUAL and include:
- The rule ID and description
- The file and line number
- A snippet of the flagged code
- A link to the CodeQL rule documentation (if available): `https://codeql.github.com/codeql-query-help/{language}/{rule-id}/`

## Output Format

Return results as structured data:

```
FIXED:
- {repo}: {rule_id} in {file}:{line} - {description of fix applied}

FAILED (reverted):
- {repo}: {rule_id} in {file}:{line} - {test failure reason}

SKIPPED (manual):
- {repo}: {rule_id} in {file}:{line} - {reason: unknown rule | complex pattern | architectural change needed}
```
