# Trace Protocol

**A finding is a claim about a path, not about a line.** Pattern-matching finds candidate lines.
Only walking the path decides whether the candidate is real. This file defines how to walk it,
how to write it down, and what to do when it cannot be walked.

It is language-, framework-, and platform-agnostic. Every module uses it. Nothing in it assumes a
particular stack, cloud, repository layout, or number of services.

---

## 1. Why this is a gate, not paperwork

Most false positives in a security audit are not misread code. They are **real code on an
unreachable path**: a dangerous sink whose input is constrained upstream, a missing guard on a
route nothing routes to, an over-broad permission on an identity nothing assumes, a vulnerable
package that never loads. Each of those looks identical to a true positive at the line level and
is distinguished only by following the path.

So the trace does three jobs at once:

1. **Validation.** Walking the path is how you find out the finding is wrong.
2. **Evidence.** The written trace is what lets a reviewer check your conclusion without redoing
   the work.
3. **Calibration.** Which hops you could and could not verify *is* the confidence score. It is
   not a separate judgement.

A finding reported without a trace has not been validated, only observed.

---

## 2. The three trace shapes

Pick the one that matches the claim. Most findings are exactly one; a few need two (e.g. an
injection reachable only from an unauthenticated route: trace A for the injection, trace B for the
reachability).

### A. Dataflow trace — "untrusted input reaches a dangerous operation"

For injection, XSS, SSRF, path traversal, deserialization, template injection, open redirect,
log/argument injection, mass assignment.

```
SOURCE  → [BOUNDARY …] → [PROPAGATION …] → SINK
```

- **Source** — where the value enters from outside the trust boundary: request field, header,
  cookie, path segment, uploaded file, queue message, webhook body, a record previously written
  by a user (second-order), a response from an external service.
- **Boundary** — anything that validates, escapes, parses, allowlists, type-constrains, or
  otherwise could stop the value. **Every boundary you pass must be read and shown to be
  insufficient.** "There is no validation" is a claim requiring the same proof as any other: say
  where you looked.
- **Propagation** — each frame the value crosses: assignment, function call, serialization,
  storage write-then-read, message publish-then-consume, template interpolation.
- **Sink** — the operation whose behaviour the value changes: query execution, command spawn,
  file open, outbound request, rendered markup, deserializer, redirect.

### B. Reachability trace — "a principal can reach a capability"

For missing/insufficient authorization, exposed resources, over-broad privilege, credential
exposure, network misconfiguration, CI/CD abuse paths, vulnerable dependencies.

```
PRINCIPAL → [ACCESS PATH …] → [PRIVILEGE …] → CAPABILITY
```

- **Principal** — who is at the start, stated in terms of what they already have: anonymous;
  any authenticated user; a user of one tenant/org; a low-privilege role; anyone who can open a
  pull request; anyone who can publish to a package registry; a process on a shared host.
  **Name the weakest principal for which the path holds** — that is the finding's real precondition.
- **Access path** — each hop that gets them from there to the component: a public DNS name, a
  route/listener/ingress rule, an unauthenticated endpoint, a job trigger, an injected build step,
  a package installed at build time.
- **Privilege** — what the component holds that the principal inherits on reaching it: a role
  binding, a policy attachment, an ambient credential, a token in the environment, a mounted
  secret.
- **Capability** — what they can then do, stated as an action on a resource, not as an adjective.
  "Read every record in store X" beats "excessive access."

For a dependency finding, the reachability trace is what separates Critical from noise: is the
vulnerable code **loaded**, **called**, and **reachable with attacker-influenced input**? Check
and say which of the three you established.

### C. Control-failure trace — "a control exists but cannot do its job"

For fail-open defaults, guards that are never applied, guards that cannot fail, checks on the wrong
value, ordering bugs, and documented-but-unenforced controls. This shape matters because the
line-level evidence looks *correct* — the bug is in the relationship between the control and what
it is supposed to gate.

```
CONTROL → [WHAT IT ACTUALLY EVALUATES] → [THE GAP] → WHAT PASSES THROUGH
```

Show, with file:line: where the control is defined, what it reads, what it is applied to, and the
concrete input for which it returns "allow" when it should return "deny". If the control is
unreachable, applied to a different object than the one at risk, keyed on a field that is absent
in the dangerous case, or short-circuits before the dangerous case, that is the gap — name it.

**Common shapes, all of which have looked like working controls in real audits:** a default value
that is the permissive one when a field is missing; a check that runs only for methods/verbs/types
the dangerous case is not; a validator applied to a normalized copy while the raw value reaches the
sink; a guard whose name implies authentication but whose body checks something else; a control
declared in documentation, schema, or config but never consumed by executing code.

---

## 3. Verification status — mandatory per hop

Every hop carries exactly one marker. This is the honesty mechanism and the input to confidence.

| Marker | Means | Required alongside |
|---|---|---|
| `[verified]` | You opened this file at this line and it does what you say. | nothing |
| `[inferred]` | Not read directly; derived from something you *did* read — a config, a route table, a generated binding, a framework convention this codebase demonstrably uses elsewhere. | name what you read instead |
| `[assumed]` | You could not check it. | say why, in four words or fewer |
| `[boundary]` | The path leaves the audited scope here. | name the destination component |

Rules:

- **Never mark a hop `[verified]` you did not read.** The entire value of this protocol is that
  `[verified]` means something.
- A trace whose **source or sink** is not `[verified]` is not a finding yet. Go read them.
- An `[assumed]` or `[boundary]` hop **anywhere on the authorization, reachability, or
  input-control segment caps the finding at MEDIUM confidence**, regardless of how obvious it
  seems. HIGH confidence means you walked it.
- Two or more `[assumed]` hops caps the finding at LOW confidence, which under default settings
  means it is not reported at all.

---

## 4. Scope, and what to do at its edge

The **audited scope** is the target path plus any additional roots supplied to the audit. Within
scope, follow the path — across directories, across services, across languages, into shared
libraries.

**Third-party and vendored code is in scope for reading.** Modules tell you to exclude dependency
directories from *scanning* (to avoid reporting findings inside them); that exclusion does not
apply to *tracing*. If the question is whether a library's escaping function actually escapes, whether
a router applies a middleware globally, or whether a client reinterprets a string as a host, open
the installed source and read it. Cite it like any other hop and mark it `[verified]`.

**When the path leaves the audited scope** — a call to another team's service, a component in a
repository that was not supplied, an external API, a managed platform behaviour:

1. Mark the hop `[boundary]` and name the destination concretely.
2. State the assumption you are making about it, explicitly, as an assumption:
   *"assumes the receiving service does not re-validate"* or *"assumes it does."*
3. **Choose the assumption that makes the finding weaker, not stronger.** If you cannot see
   whether something downstream validates, you may not claim it does not.
4. Apply the confidence cap from §3.
5. Say in the **Fix** whether resolving the boundary would change the severity, so a reader who
   *does* have that component knows the finding is worth re-checking with it in hand.

If additional roots were supplied and the destination lives in one of them, it is **not** a
boundary — follow it, and prefix the citation with that root's name so the reader knows which tree
each hop is in.

Boundaries are a normal result, not a failure. A trace that stops honestly at an edge is more
useful than one that guesses past it.

---

## 5. The falsification pass — do this before writing anything

For each hop, ask: **what single thing, if it existed, would break this chain?** Then go look for
that thing. This is the step that removes pattern-match noise, and it is the step most often
skipped.

Prompts that reliably find the breaker:

- Is there a global or framework-level control applied to everything, so the absence of a local one
  proves nothing?
- Is the value's **type** already constrained upstream — parsed to a number, matched against an
  enum, bound to a schema, deserialized into a fixed shape?
- Is the source actually attacker-controlled, or is it configuration, a build-time constant, an
  internally-generated identifier, or a value the system itself wrote?
- Does the sink actually do the dangerous thing with *this* argument position, or is the value
  placed somewhere inert?
- Is there a control **in a different layer** — network, gateway, proxy, platform policy, database
  permission — that this code-level reading cannot see? Look for it before claiming it is absent.
- Is the dangerous path reachable in the deployed configuration, or only under a flag, a mode, or
  an environment that is never enabled?
- For an inconsistency finding ("A does this, B doesn't"): read both. The difference may be
  deliberate and correct, and the reason may be in a comment on the line you did not open.

**If the falsification pass breaks the chain, the finding is dropped, not downgraded.** Record it
in the module's clean-coverage note (§7) so the next run does not re-derive it.

---

## 6. Writing the trace

A `**Trace:**` field is required on every finding. Format:

```
**Trace:** <shape: dataflow | reachability | control-failure> — <one-line statement of the path>
1. `relative/path/file.ext:LINE` — what happens here [verified]
2. `relative/path/other.ext:LINE` — what happens here [verified]
3. `<external component>` — assumption being made [boundary]
4. `relative/path/sink.ext:LINE` — the dangerous operation [verified]
**Breaks if:** <the control that would defeat this chain, and where you confirmed it is absent or insufficient>
```

Requirements:

- **Every hop cites `file:line`** except `[boundary]` hops, which name a component instead.
- **Hop count equals path length.** If source and sink are the same line, the trace is one hop —
  write one hop. Do not pad. If the real path is longer than about eight hops, keep the source,
  the sink, every boundary/guard hop, and every scope crossing; compress consecutive
  pass-through frames into a single hop noting how many were collapsed.
- **`Breaks if:` is mandatory.** It is the falsification pass, written down. It states what would
  make the finding wrong and reports that you checked. A finding whose author cannot name what
  would refute it has not tested it.
- Keep each hop to one line. The prose explanation belongs in **Description**; the narrative
  belongs in **Exploit scenario**; the trace is the skeleton both hang on.

**The Exploit scenario must be consistent with the trace.** It is the same path told as a story.
If the scenario contains a step the trace does not, the trace is incomplete — fix it, or cut the
step. This consistency check catches scenarios that quietly assume capabilities never established.

---

## 7. Recording what you cleared

When the falsification pass kills a candidate that a reasonable reviewer would also have suspected
— a dangerous-looking sink that turns out to be safe, a missing guard that a global control
supplies, a vulnerable package that is never loaded — add one line to the module's clean-coverage
note: **what you checked, and the fact that established it.**

This is not padding. It is the difference between "the audit did not mention X" and "the audit
checked X and it holds," and it stops the same false positive being re-derived and re-investigated
on every future run.

---

## 8. Worked shapes

Illustrative only — the file paths, languages, and component names are placeholders.

**Dataflow, complete, high confidence:**
```
**Trace:** dataflow — a request body field reaches a query executed as a string
1. `src/handlers/search.ext:34` — `term` read from the request body, no schema constraint [verified]
2. `src/handlers/search.ext:41` — passed unchanged to `buildFilter(term)` [verified]
3. `src/data/filters.ext:88` — interpolated into a WHERE fragment via string concatenation [verified]
4. `src/data/client.ext:120` — fragment executed as a raw statement, no parameter binding [verified]
**Breaks if:** an upstream schema or type coercion constrained `term` — checked the route
definition at `src/routes.ext:210`, which declares no body schema for this route, and the shared
validation middleware at `src/middleware/validate.ext:15`, which is applied per-route and is not
applied here.
```

**Reachability, with a boundary, capped at MEDIUM:**
```
**Trace:** reachability — anonymous caller reaches an identity with resource-creation privilege
1. `deploy/service.yaml:22` — service exposed with no authentication on its listener [verified]
2. `src/api/jobs.ext:56` — the create-job route applies no guard; global guard absent, confirmed at
   `src/app.ext:40` [verified]
3. `src/api/jobs.ext:73` — caller-supplied image reference passed to the orchestration client [verified]
4. `<orchestration control plane>` — assumes it does not re-authorize the caller [boundary]
5. `deploy/rbac.yaml:14` — the identity's role permits creating workloads cluster-wide [verified]
**Breaks if:** the control plane independently authorized the original caller rather than the
service identity — not verifiable from the supplied scope; confidence capped at MEDIUM for this
reason. Supplying the platform configuration would settle it and could raise severity.
```

**Control-failure, one hop plus the gap:**
```
**Trace:** control-failure — the gate's default is the permissive value, so records missing the
field are treated as public
1. `src/access/rules.ext:104` — `is_restricted()` reads the field with a default of "unrestricted" [verified]
2. `src/handlers/fetch.ext:322` — the public read path calls it and serves the object when false [verified]
3. `src/handlers/fetch.ext:97` — the authenticated path calls a *different* resolver that defaults
   to "restricted" for the same field — the two disagree on the same record [verified]
**Breaks if:** no record can exist without the field — checked the write path at
`src/access/store.ext:526`, which always populates it, and the import path at
`tools/import.ext:44`, which does not.
```

---

## 9. Checklist

- [ ] Trace shape chosen and stated
- [ ] Source and sink both `[verified]`
- [ ] Every boundary/guard on the path read, not assumed absent
- [ ] Every hop carries `file:line` and a status marker
- [ ] Scope crossings marked `[boundary]` with the assumption stated in the weakening direction
- [ ] Falsification pass done; `Breaks if:` written
- [ ] Confidence reflects the weakest marker on the chain
- [ ] Exploit scenario contains no step absent from the trace
- [ ] Killed candidates recorded in clean coverage
