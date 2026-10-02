# Worker brief: audit-security

Every module worker reads this file in full after its module file and `trace-protocol.md`. It is part of the worker's instructions, not background reading: the false-positive rules, confidence scoring, severity calibration and output format below are binding. The orchestrator relies on the output format exactly as written when it consolidates.

FALSE POSITIVE RULES — Do NOT report findings that match these:
1. Test files: Vulnerabilities in unit tests or test-only code are not exploitable.
2. React/Angular XSS: These frameworks auto-escape output. Only flag XSS if using `dangerouslySetInnerHTML`, `bypassSecurityTrustHtml`, `v-html`, or similar explicit bypass methods.
3. Environment variables and CLI flags are trusted inputs. Do not flag code that uses env vars or CLI args as "user-controlled input."
4. SSRF path-only: SSRF is only a real finding if the attacker can control the host or protocol. Controlling just the URL path is not exploitable SSRF — **but** only apply this exemption when the code demonstrably treats the input as a path: it's captured as a distinct path segment by a router (not concatenated into an existing base URL), or, if concatenated, the value is validated/parsed first to reject anything that isn't a bare path (reject a leading scheme, `//`, `@`, backslash, and require the result to start with `/`). A value that is concatenated directly onto a base URL string with no such validation is NOT path-only — URL parsers (browsers, `axios`/`fetch`/`urllib`/etc.) reinterpret a leading `@` or `//` in that position as a new host/authority, so "just the path" is actually host control. Apply the same host-confusion scrutiny here as you would to an open-redirect or OAuth `redirect_uri` check — it's the same underlying defect (untrusted string reaches a URL-consuming sink without real parsing/allowlisting), whether the sink is a browser navigation or a server-side outbound request.
5. Theoretical race conditions: Only flag race conditions with a concrete exploitation path and real impact (e.g., financial double-spend, auth bypass), not theoretical TOCTOU.
6. Shell script command injection: Only flag if untrusted user input can reach the shell command. Scripts that only use hardcoded values or env vars are not vulnerable.
7. UUIDs are unguessable. Do not flag UUID-based access as an authorization issue.
8. Client-side auth checks: Missing permission checks in frontend JS/TS are not vulnerabilities — authorization is enforced server-side.
9. Log content: Logging URLs, request IDs, or non-PII data is not a vulnerability. Only flag logging of secrets, passwords, or PII.
10. Documentation files: Do not report findings in markdown, text, or documentation files.
11. CI/CD pipeline variables: Build-time variables injected by CI systems ($CI_*, $GITHUB_*, $BUILDKITE_*) are not secrets and should not be flagged as hardcoded credentials.

CONFIDENCE SCORING — derived from the trace, per trace-protocol §3. Do not score on impression:
- HIGH (8-10): Every hop on the chain is `[verified]`. You walked the whole path and read each step.
- MEDIUM (6-7): The chain holds but carries at least one `[inferred]`, `[assumed]`, or `[boundary]`
  hop on the authorization, reachability, or input-control segment. This is the ceiling for any
  finding whose path leaves the trace scope.
- LOW (1-5): Two or more `[assumed]` hops, or the source or sink itself is unverified.

If the falsification pass BREAKS the chain, the candidate is dropped entirely rather than
downgraded — and recorded in your clean-coverage note per trace-protocol §7, so the next run does
not re-derive it.

REPORTING THRESHOLD: your task prompt states it. Default is to report only findings with confidence >= 6 (HIGH or MEDIUM) and drop LOW; when the prompt says LOW findings are included, report all of them.

SEVERITY CALIBRATION — Testing "Bounded"/"Mitigating" Claims:
Before writing anything into **Current controls** that would lower a finding's
severity (a claim that impact is "bounded," "self-healing," "low-probability,"
or "requires an already-privileged caller"), stress-test the claim itself:
- If the claim rests on a time window (a cache TTL, a reconciliation/resync
  interval, a token expiry) — could the attacker simply repeat the triggering
  action faster than that window, making the "bounded" impact actually
  unbounded/indefinite? Check whether the trigger has its own rate limit or
  auth gate before accepting the bound as real.
- If the claim rests on "the caller must already hold valid credentials" —
  does holding those credentials grant only ordinary access, or does the
  finding itself grant something beyond what those credentials should allow
  (privilege escalation, cross-tenant access, disabling a security control)?
  A precondition of "authenticated" does not make a privilege-escalation or
  cross-tenant finding low severity.
- Write the mitigating claim AND the stress-test result into **Current
  controls** explicitly (e.g., "resyncs every 15 min, but the reset endpoint
  has no rate limit, so a looping caller defeats this bound — treated as
  unbounded/indefinite, not one-shot"). A downgrade that isn't tested this way
  is a guess, not an assessment.

OUTPUT FORMAT:
Return your findings as a markdown list. For each finding, use this exact format:

### {SEVERITY}-{NUMBER}: {Title}

**Status:** OPEN
**File:** `{relative_path}:{line_number}`
**Affected files:** List ALL files that would need changes to remediate this finding, not just the primary file. Use relative paths. If only one file, repeat the primary file.
**Severity:** Critical | High | Medium | Low | Informational
**Confidence:** HIGH | MEDIUM | LOW
**Exposure:** {How this finding is actually reachable, independent of severity — one of: "Public-facing" (reachable from the open internet with no network-level gate), "Internal-network-reachable" (requires being on the VPC/mesh/internal network already, but no further credentials), "Auth-gated-internal" (requires both internal network access AND a valid credential/session). Base this on real deployment evidence (ingress/ALB scheme, security group rules, service mesh config) discovered in Step 2, not on assumption from the repo's name or docs. This is a distinct axis from Severity — an Internal-network-reachable finding can still be Critical if its impact is severe; the field exists so prioritization can weigh "how bad" and "how reachable" separately instead of one field trying to encode both.}
**Category:** {category from module}
**Standards:** {List the standards/frameworks this finding maps to, from the `<!-- Standards: -->` comment on the category header. Example: "OWASP-Web-A05:2025, CWE-89". If no comment exists, infer the most applicable standard.}
**Description:** {What the vulnerability is and why it matters — be specific about the mechanism}
**Evidence:**
```{language}
{Actual code snippet showing the vulnerability. Include enough surrounding context (function name, relevant variables) that a developer can locate and understand it without opening the file.}
```
**Trace:** {REQUIRED. The validated path, in the format defined in trace-protocol §6: the shape
(dataflow | reachability | control-failure), a one-line statement of the path, then one numbered
hop per step — each with `file:line` and a `[verified]` / `[inferred]` / `[assumed]` / `[boundary]`
marker — followed by a `**Breaks if:**` line naming the control that would defeat the chain and
where you confirmed it is absent or insufficient. Hop count equals real path length; a
same-line source and sink is a one-hop trace. Evidence shows WHERE the defect is; Trace shows THAT
it is reachable, and is what makes the finding checkable by someone who did not do the work.}
**Current controls:** {What security measures are ALREADY in place that partially mitigate this risk — e.g., "input is tenant-scoped so only affects the attacker's own tenant", "WAF blocks common payloads at the edge", "data source is trusted (Secret Manager)". Write "None" if no mitigations exist. This field helps prioritize — a finding with strong existing controls is lower real-world risk.}
**Exploit scenario:** {Step-by-step attack scenario: (1) attacker does X, (2) this causes Y, (3) resulting in Z impact. Be concrete — name the endpoint, parameter, or field involved. This is the Trace told as a story and MUST NOT contain a step the Trace does not support — if it does, either the trace is incomplete (go finish it) or the step is speculation (cut it). Start from the weakest principal for which the path holds, and state it.}
**Fix:** {Implementation-ready remediation. Include:
- Which files to modify and what to change in each
- Specific function/method names to update
- Code pattern to use (e.g., "replace f-string with parameterized query using `:param` syntax")
- Any config changes needed (Terraform, env vars, etc.)
- Order of operations if changes span multiple files/services
This should be detailed enough that a coding agent can implement the fix without re-reading the vulnerable code from scratch.}

If you find no issues for a category, do not include it. Only report real findings, not theoretical concerns. Prioritize findings that are actually exploitable over pattern-matching noise.

At the end, include BOTH of the following:

1. A clean-coverage note — a short section listing what you checked and cleared, especially any
   candidate the falsification pass killed and the specific fact that killed it (a global control
   that supplies the missing guard, an upstream type constraint, a package that is never loaded).
   State it as "checked X, holds because Y", not as an absence. This is what distinguishes "the
   audit did not look" from "the audit looked and it holds", and it stops the next run
   re-investigating the same dead end.
2. The summary count:
**{MODULE_NAME} Module Summary**: X Critical, X High, X Medium, X Low, X Informational
