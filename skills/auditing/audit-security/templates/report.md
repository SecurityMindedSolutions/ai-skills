# Security Audit Report

**Target**: {TARGET_PATH}
**Date**: {DATE}
**Modules Run**: {MODULES_RUN}
**Modules Skipped**: {MODULES_SKIPPED}

---

## Executive Summary

{EXECUTIVE_SUMMARY}

**Overall Risk**: {OVERALL_RISK} (Critical / High / Medium / Low / Minimal)

## Finding Summary

| Severity | Count |
|----------|-------|
| Critical | {CRITICAL_COUNT} |
| High | {HIGH_COUNT} |
| Medium | {MEDIUM_COUNT} |
| Low | {LOW_COUNT} |
| Informational | {INFO_COUNT} |
| **Total** | **{TOTAL_COUNT}** |

### Findings by Module

| Module | Critical | High | Medium | Low | Info |
|--------|----------|------|--------|-----|------|
{MODULE_BREAKDOWN_ROWS}

---

## Critical Findings

{CRITICAL_FINDINGS}

## High Findings

{HIGH_FINDINGS}

## Medium Findings

{MEDIUM_FINDINGS}

## Low Findings

{LOW_FINDINGS}

## Informational Findings

{INFO_FINDINGS}

---

## Methodology

This audit was conducted using automated security analysis with the following modules:

- **Code**: Application code review for injection, auth, crypto, business logic, SSRF, and deserialization vulnerabilities
- **API**: Endpoint authentication, input validation, data exposure, CORS, rate limiting, and error handling
- **Frontend**: XSS, DOM manipulation, client-side storage, CSP, and React-specific security issues
- **Secrets**: Hardcoded credentials, environment variable exposure, git history, cloud provider keys, and CI/CD secrets
- **Dependencies**: Known CVEs, outdated packages, version pinning, supply chain risks, and container base images
- **Terraform**: IAM policies, network security, encryption, public exposure, logging, and state management

Each module was executed as an independent sub-agent that read architecture documentation, scanned relevant files, and applied both pattern-based and contextual analysis. Findings were deduplicated and consolidated across modules.

## Finding Format Reference

Each finding uses this format:

- **Status**: OPEN (default for new findings)
- **File**: Primary source file and line number where the vulnerability is most visible
- **Affected files**: All files that need changes to remediate (not just the primary one)
- **Severity**: Critical / High / Medium / Low / Informational
- **Confidence**: HIGH (clear exploit path) or MEDIUM (exploitable under specific conditions)
- **Category**: Vulnerability category from the scanning module
- **Modules**: Which audit module(s) flagged this finding
- **Description**: What the vulnerability is and why it matters
- **Evidence**: Code snippet or pattern demonstrating the issue
- **Current controls**: What mitigations already exist (helps assess real-world risk and avoid duplicate work)
- **Exploit scenario**: How an attacker would exploit this in practice
- **Fix**: Specific, implementable remediation steps including file paths, function names, and code patterns — enough detail for an engineer or coding agent to implement without re-investigating the issue
- **Remediation notes**: Blank on creation — filled during triage with status updates, decisions, and implementation details

### Status Values

Findings progress through these statuses during triage:

| Status | Meaning |
|--------|---------|
| OPEN | Not yet triaged or remediation not started |
| IN PROGRESS | Remediation underway — see remediation notes for details |
| RESOLVED | Fix implemented and deployed |
| ACCEPTED RISK | Risk acknowledged, no fix planned — see remediation notes for rationale |

Findings with LOW confidence (< 6/10) are excluded from this report unless `--include-low` was specified.
