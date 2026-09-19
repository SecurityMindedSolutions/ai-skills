# resume-mirror-eval

## Disclaimer: research proof of concept, not a hiring tool

This skill was built to test whether a methodology works: measuring how
closely a resume's *wording* tracks a job description using TypeSafe's Jev
decision model plus plain text statistics. It is published so others can look
at the approach, run it on the fictional data in `mock-data/`, and improve it.

**It does not and cannot determine whether a person used AI to write their
resume.** A candidate whose experience genuinely matches a role will score
above the average of the batch. Its output is a list of resumes a human should
read first, with the reasons spelled out. It is not a ranking, not a filter,
and not evidence of anything about a candidate. The first column of every
result is "Needs human review", and that is exactly what it means.

**The use of automated tools in hiring is regulated.** Depending on where you
and your applicants are, that may include the EU AI Act (employment is a
high-risk use), New York City Local Law 144 (bias audits and notice for
automated employment decision tools), the Illinois Artificial Intelligence
Video Interview Act and the 2026 amendment to the Illinois Human Rights Act,
Colorado SB 24-205, and US EEOC guidance on algorithmic tools under Title VII
and the ADA. Requirements commonly include candidate notice, independent bias
auditing, record-keeping, and a human decision-maker.

**If you use this, or anything derived from it, on real applicants, you are
solely responsible for complying with every law and regulation that applies to
you, and you should consult your own legal counsel before doing so.** The
author offers it for research and education only, as is, without warranty of
any kind, and accepts no responsibility for how it is used.

All data in `mock-data/` is fictional. The company, the candidates, their
employers and their histories were invented for this demonstration. Any
resemblance to a real person or employer is coincidental.

---

- How the skill works, how an agent runs it, and every flag: [`SKILL.md`](SKILL.md)
- Usage, output format, cost and time, and results on the mock set: [`../README.md`](../README.md)
- Why each signal exists and what fools it: [`references/methodology.md`](references/methodology.md)
- Every question, weight and threshold: [`scripts/questions.py`](scripts/questions.py)
