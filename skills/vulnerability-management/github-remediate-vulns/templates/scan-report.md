# Vulnerability Scan Report

**Organization**: {ORG}
**Date**: {DATE}
**Scope**: {SCOPE_DESCRIPTION}
**Severity Filter**: {SEVERITY_FILTER}
**Mode**: {MODE_A_B_C}

---

## Summary

| Alert Type | Total | Auto-Fix | Assisted-Fix | Manual |
|------------|-------|----------|--------------|--------|
| Dependabot | {DEP_TOTAL} | {DEP_AUTO} | {DEP_ASSISTED} | {DEP_MANUAL} |
| Code Scanning | {CS_TOTAL} | {CS_AUTO} | {CS_ASSISTED} | {CS_MANUAL} |
| Secret Scanning | {SS_TOTAL} | {SS_AUTO} | {SS_ASSISTED} | {SS_MANUAL} |
| **Total** | **{TOTAL}** | **{AUTO_TOTAL}** | **{ASSISTED_TOTAL}** | **{MANUAL_TOTAL}** |

### Repos Scanned

| Repo | Dependabot | Code Scanning | Secret Scanning | Status |
|------|-----------|---------------|-----------------|--------|
{REPO_ROWS}

### Repos Skipped

{SKIPPED_REPOS_TABLE_OR_NONE}

---

## Auto-Fix Items

These will be applied automatically with test validation. Failed tests trigger automatic revert.

{For each repo with auto-fix items:}

### {org}/{repo}

| # | Package/Rule | Current | Patched | Severity | CVE/CWE |
|---|-------------|---------|---------|----------|---------|
{AUTO_FIX_ROWS}

---

## Assisted-Fix Items

These will be attempted but need extra review. Reasons: major version bumps, code changes, or no test suite.

{For each repo with assisted-fix items:}

### {org}/{repo}

| # | Package/Rule | Current | Patched | Severity | CVE/CWE | Reason |
|---|-------------|---------|---------|----------|---------|--------|
{ASSISTED_FIX_ROWS}

---

## Manual Items

These cannot be auto-fixed. Guidance provided below.

{For each repo with manual items:}

### {org}/{repo}

{For each manual item:}

**{alert_type} #{number}**: {title}
- **Severity**: {severity}
- **Package/Rule**: {package_or_rule}
- **Reason**: {why it's manual - no patch available | unknown rule | secret scanning | etc.}
- **Guidance**: {what the user should do}

---

## Recommended Actions

1. **Approve auto-fixes** - {N} items can be safely bumped with test validation
2. **Review assisted-fixes** - {N} items need human review (major bumps or code changes)
3. **Address manual items** - {N} items need manual intervention
4. **Dismiss false positives** - Mark any non-applicable alerts for dismissal

### Options

- **Approve all** - Apply auto-fix + assisted-fix items
- **Approve auto-fix only** - Only apply auto-fixes
- **Approve per-repo** - Select specific repos
- **Dismiss alerts** - Specify alert numbers to dismiss as false positives
- **Skip** - No changes (this scan report is still useful for tracking)

