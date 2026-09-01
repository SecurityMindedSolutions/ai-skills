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

## Verified Clean

What was checked and found sound, including candidates that were investigated and ruled out with
the fact that ruled them out. Recorded so a reader can tell silence-because-checked from
silence-because-missed, and so a future audit does not re-derive the same dead ends.

{VERIFIED_CLEAN}

## Trace Coverage

Every finding above was validated by following its path from source to sink (or principal to
capability) with each hop cited. Where a path left the code available to this audit, the finding
says so and its confidence is capped accordingly.

{TRACE_COVERAGE}

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

**Every finding was validated by tracing, not by pattern match alone.** A candidate line only becomes a finding once the path around it has been walked: for a dataflow issue, from the untrusted source through every boundary and propagation frame to the sink; for a reachability issue, from the weakest principal that can reach it through each access and privilege hop to the capability; for a control failure, from the control's definition to the concrete input it wrongly admits. Each hop is cited with `file:line` and marked as verified (read directly), inferred (derived from something read), assumed (not checkable) or boundary (path left the available code). Confidence is derived from the weakest marker on the chain rather than scored by impression, and each finding carries a `Breaks if:` line naming the control that would refute it and where that control was confirmed absent or insufficient. Candidates whose chain broke under that check were dropped rather than downgraded, and are listed under Verified Clean.

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
- **Evidence**: Code snippet or pattern demonstrating the issue — shows *where* the defect is
- **Trace**: The validated path proving the defect is *reachable* — one numbered hop per step, each with `file:line` and a `[verified]` / `[inferred]` / `[assumed]` / `[boundary]` marker, closing with `Breaks if:` (the control that would defeat the chain, and where it was confirmed absent or insufficient). This is what lets a reviewer check the conclusion without redoing the investigation, and what makes the audit's own uncertainty legible
- **Current controls**: What mitigations already exist (helps assess real-world risk and avoid duplicate work)
- **Exploit scenario**: How an attacker would exploit this in practice — the same path as the Trace, told as a story, and containing no step the Trace does not support
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
