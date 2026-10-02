# Worker brief: audit-backend

Every module worker reads this file in full after its module file. It is part of the worker's instructions, not background reading: the scale and output format below are binding, and the orchestrator relies on the output format exactly as written when it consolidates.

SCORING:
For each assertion in your module, evaluate the codebase and assign one of:
- PASS: The assertion holds. Code meets the standard.
- FAIL: The assertion is violated. Include file path, line number, and what's wrong.
- WARN: Not violated but trending toward a problem. Include what to watch.
- N/A: The assertion doesn't apply to this codebase.

OUTPUT FORMAT:
Return your findings as markdown. For each assertion:

### {MODULE_PREFIX}-{NUMBER}: {Assertion title}

**Result:** PASS | FAIL | WARN | N/A
**File(s):** `{relative_path}:{line_number}` (or "N/A")
**Evidence:**
```{language}
{Actual code snippet if FAIL or WARN. Show enough context to understand the issue.}
```
**Analysis:** {Why this passes, fails, or warrants a warning. Be specific — reference actual code patterns, not abstract principles.}
**Fix:** {If FAIL or WARN: implementation-ready remediation. Which files, what to change, code pattern to use. If PASS: omit this field.}

At the end, include:
**{MODULE_NAME} Summary**: X PASS, X FAIL, X WARN, X N/A
