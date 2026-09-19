# Mock data

Everything in this folder is synthetic and exists only so the skill can be
demonstrated without pointing it at real people. The company, the candidates,
their employers, contact details and career histories are invented. Any
resemblance to a real person or employer is coincidental.

- `job-description.md` - one fictional Senior Platform Engineer posting.
- `resumes/` - 13 fictional resumes in .md, .docx and .pdf form.
- `labels.csv` - how each resume was written, so a run can be scored.

## How the resumes were constructed

| Label | Count | How it was written |
|---|---|---|
| `human` | 8 | Written as a person would: own phrasing, specific employers, dates and numbers. Fit to the posting ranges from strong (two are deliberately very close matches) to weak (a frontend developer and a data analyst). One is a human who padded a skills section with posting keywords. |
| `ai_tailored` | 5 | Written the way a generative tool produces a resume from a posting: requirements restated as experience, posting order preserved, generic or absent specifics, and in one case posting language ("the ideal candidate") left in. |

The two very close human matches (`dana_whitfield`, `marcus_chen`) are the point
of the exercise. A candidate who genuinely has the stack will cover the
requirements. The methodology has to score them lower than the generated ones
on wording and specificity while still reporting their fit as high.

## Scoring a run

```bash
uv run ../scripts/analyze.py --jd job-description.md --resumes resumes --labels labels.csv
```

The summary line reports mean score per label, precision and recall of the
"flagged" (high or moderate) bucket, and a pairwise AUC.
