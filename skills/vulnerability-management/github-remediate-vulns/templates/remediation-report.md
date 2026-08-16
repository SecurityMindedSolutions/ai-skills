# Vulnerability Remediation Report

**Organization**: {ORG}
**Date**: {DATE}
**Scope**: {SCOPE_DESCRIPTION}

---

## Summary

| Category | Count |
|----------|-------|
| Successfully fixed | {FIXED_COUNT} |
| Failed (reverted) | {FAILED_COUNT} |
| Manual (report only) | {MANUAL_COUNT} |
| Dismissed | {DISMISSED_COUNT} |
| **Total processed** | **{TOTAL}** |

---

## Successfully Fixed

{For each repo with fixes:}

### {org}/{repo}

**Branch**: `remediate/vulns-{DATE}`
**PR**: {PR_URL or "not yet created"}

| Package/Rule | Old | New | CVE/CWE | Severity | Type |
|-------------|-----|-----|---------|----------|------|
{FIXED_ROWS}

**Test results**: All tests passing after fixes applied.

---

## Failed (Reverted)

These fixes were attempted but caused test failures. Changes were reverted.

{For each repo with failures:}

### {org}/{repo}

| Package/Rule | Attempted | CVE/CWE | Failure Reason |
|-------------|-----------|---------|----------------|
{FAILED_ROWS}

**Recommended next steps**:
{Per-failure guidance - e.g., "Flask 3.x requires app factory pattern changes. See migration guide: ..."}

---

## Manual Items

These require human intervention. Guidance below.

{For each repo with manual items:}

### {org}/{repo}

{For each manual item:}

**{type} #{number}**: {title}
- **Severity**: {severity}
- **Guidance**: {specific instructions}
{If secret scanning: include rotation checklist from secret-scanning module}

---

## Dismissed Alerts

{If any alerts were dismissed:}

| Repo | Alert # | Type | Reason | Comment |
|------|---------|------|--------|---------|
{DISMISSED_ROWS}

---

## Branches & PRs

| Repo | Branch | PR | CI Status |
|------|--------|----|-----------|
{BRANCH_PR_ROWS}

---

## Next Steps

1. {If PRs created: "Review and merge the PRs listed above"}
2. {If failed fixes: "Address {N} failed fixes manually - see failure details above"}
3. {If manual items: "Triage {N} manual items - especially {N} secret scanning alerts"}
4. {If secrets found: "Rotate exposed secrets immediately - see rotation checklists above"}
5. Run `/github-remediate-vulns --dry-run` periodically to track new alerts

