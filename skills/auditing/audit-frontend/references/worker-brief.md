# Worker brief: audit-frontend

Every module worker reads this file in full after its module file. It is part of the worker's instructions, not background reading: the scale and output format below are binding, and the orchestrator relies on the output format exactly as written when it consolidates.

RATING SCALE:
For each category in your module, rate as:
- PASS: Meets enterprise standards. No action needed.
- NEEDS IMPROVEMENT: Partially meets standards. Specific improvements identified.
- FAIL: Does not meet standards. Critical issues that should be fixed.

OUTPUT FORMAT:
Return your findings as markdown. For each category, use this exact format:

### {CATEGORY_NAME}

**Rating:** PASS | NEEDS IMPROVEMENT | FAIL
**Files examined:** List key files you checked
**Findings:**
{What you found — be specific with file paths and line numbers}

**Recommendations:**
{If NEEDS IMPROVEMENT or FAIL — specific, actionable fixes with file paths and code patterns. Each recommendation should be implementable without ambiguity.}

At the end, include a summary:
**{MODULE_NAME} Module Summary**: X PASS, X NEEDS IMPROVEMENT, X FAIL
