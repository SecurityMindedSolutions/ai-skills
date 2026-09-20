# Measurements

All numbers below were measured on one reference repository: a 303k-line,
1,339-file multi-tenant SaaS monorepo (Python serverless functions and a
shared library, two React + TypeScript apps, a container service, 43
Terraform files, five build configs, two GitHub workflows). A frozen archive
directory was excluded. Dates are 2026-09-19 and 2026-09-20.

## Whole tree vs a full multi-agent audit

The comparison target was a security audit that runs eight reasoning-model
sub-agents, each reading a large share of the tree and tracing every
candidate across files. Its cost was measured from the sub-agent transcripts
(every assistant message, deduplicated by message id, at list price with
cache writes at 1.25x and cache reads at 0.1x).

| | Full audit, run A | Full audit, run B | code-audit-jev (13 rules) |
|---|---|---|---|
| Wall time | 25 min | 24 min agents + orchestrator | 333 s |
| Input tokens | 136.5M | 148.5M (98% cache reads) | 28.0M |
| Cost at list | ~$90 | ~$95 | $1.18 |
| Output | 40 traced findings | 37 traced findings | 56 candidate units in 38 findings |

The two audit runs, three days apart on the same tree, agree on 7 of the 12
Medium-and-above findings of run A. That 60% is the noise floor any cheaper
method is judged against.

**Overlap.** Of run A's 40 findings, Jev scored 5 at or above the attention
line (50), 11 more in the Note band (25-49), 19 below, 5 in files it does not
judge. Of run B's 37: 2, 5, 21, 9. Lowering the attention line to 25 raises
the run-A hits to 12 while raising candidate units from 56 to 248.

**Why the misses are misses.** Run B's 37 findings by what a reader must see:

| Class | Count | Jev |
|---|---|---|
| Visible in one unit | 6 | 2 flagged, 4 Note |
| Absence of a control that lives elsewhere (no revocation, no throttle, no test step, no scan) | 12 | 6-43 |
| Relationship between two or more files (a route's capability vs its serializer; a grant reaching a resource declared elsewhere) | 11 | 10-45 |
| Lifecycle ordering across services (a delete that commits one step before another; a webhook that re-creates a deleted record) | 5 | 27-40 |
| Facts outside the tree | 3 | not judgeable |

Jev sees the first class. The rest need a reader that leaves the unit. That
is a property of the design, not the questions.

**What Jev flagged that the audit did not.** 36 of the 56 attention units.
Every one was a fact in a file the unit does not contain: a single pinned
HTTPS transport that every outbound URL passes through (12 SSRF rows), a
restricted ingress next to a public invoker (infrastructure rows), operator
scripts and platform-global collections read as tenant-isolation gaps. Each
is one sentence in `app.md` or one `--exclude`.

## Stability

Two full runs (the second with two question fixes) on 4,501 shared units:
median score difference 0.5 points, 90% of units within 2.7 points, category
agreement 90%, attention-set overlap 0.68 (the difference is CI files the fix
un-dropped).

## The cascade

Jev's 38 candidates were handed to one reasoning-model agent with the
audit's trace protocol and no access to either audit report.

| | |
|---|---|
| Wall time | 8.7 min |
| Tokens | 8.4M input-side, 12k output |
| Cost | $5.63 |
| Verdicts | 2 confirmed, 2 accepted risk, 25 false positive, 9 operator scripts |

One confirmed finding was a High (an administrative role granted by
`for_each` to every service account) that run A found and run B, at ~$95,
did not. Cascade total: about $7 and 14 minutes.

## The PR check

`--diff` mode judges only the units a change touched, on both sides of the
merge base, and reports band rises.

| | Units | Tokens | Cost | Model time |
|---|---|---|---|---|
| A PR vendoring the tool itself | 71 | 600k | $0.025 | 2 s |
| A probe PR: 17 planted defects (API handler, React component, Terraform, workflow) + 6 hard negatives | 23 | 189k | $0.008 | 2 s |

Probe result: 17/17 reported, 0 false positives, all 17 as code-scanning
alerts in the Security tab.

Three things fixed in rule files after the probe: a file whose comments say
"test fixture, never merge" is dropped as non-production (Jev believes
comments); JSX `<p>{text}</p>` read as an unescaped sink until the question
said JSX text is escaped; CSRF and IDOR gate on the "is this a request
handler" question so helpers taking an id parameter do not fire.

## Per-unit cost

| Rules | Tokens per unit (median) | Per 100 units |
|---|---|---|
| 13 | 5,115 | $0.02 |
| 22 | ~7,600 | $0.03 |

One request per unit; every rule's questions ride in it and Jev evaluates
them in parallel. Latency per request: median 421 ms, p95 550 ms.

## Mock regression set

`mock-data/sample-repo/`: 27 labelled defects across all 22 rules, 17 hard
negatives. Current: 27/27 flagged, 16/17 negatives quiet, ~375k tokens,
$0.02, 3 s.

## Limits of the measurement

One repository, one language mix, one week. The audit's own run-to-run
noise is about 40%, so single-run overlap counts over-state both hits and
misses. The reference is the audit, not ground truth. Costs are list
prices.
