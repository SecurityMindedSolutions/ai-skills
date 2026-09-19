# Methodology

Why each signal exists, what it is good at, and what fools it. Read this before
changing a weight in `scripts/questions.py`.

## The problem, stated carefully

A recruiter opens fifty resumes for one posting and a dozen of them read like
the posting. Some of those people genuinely have the stack: a platform engineer
who has run EKS, Terraform and ArgoCD for six years will mention EKS, Terraform
and ArgoCD. Others pasted the posting into a chatbot and asked for a resume.
The two look alike on a keyword scan, and keyword scans are what most applicant
tracking systems do.

The distinguishing features are not *which* words appear but *how*:

- **Verbatim reuse.** People describe their own work in their own words. A
  four-word phrase from the posting appearing unchanged in a resume is unusual;
  a whole sentence is rare; nine bullets in the posting's order is not
  something a person does by accident.
- **Specificity.** Lived experience comes with names, numbers and mess: 14 AWS
  accounts, a 3h40m outage, a migration that was painful. Text generated from a
  posting has nothing to draw those from, so it stays generic or invents round
  numbers.
- **Register.** Postings are written *to* an applicant ("you will", "the ideal
  candidate", "must have"). Resumes are written *by* one. Leaked posting
  register is a strong tell.

So the method scores wording and specificity only. It deliberately does not
rate the candidate's fit or qualifications: coverage of the posting's keywords
enters the score at a low weight as a mirroring signal, and nothing in the
output grades the person.

## Layer 1: statistics in code

Jev's documentation is blunt that the model should not count or do arithmetic.
Everything that is a count or a ratio is computed here. All are 0..1.

| Signal | What it measures | Weight | Notes |
|---|---|---|---|
| `phrase_overlap` | Share of the JD's distinct 4-grams (with 2+ content words) that appear verbatim in the resume | 0.35 | The workhorse. Human resumes in the mock set score 0.000-0.005; verbatim copies 0.26-0.36; a synonym-swapped paraphrase 0.05. |
| `longest_span` | Longest run of consecutive shared words, capped at 12 | 0.20 | Humans top out around 4 ("soc 2 type ii"). The evidence bullet quotes the run so a reviewer can find it. |
| `order_echo` | Spearman correlation between the order matched terms first appear in the JD and in the resume | 0.15 | Catches paraphrases that keep the posting's structure. Needs 8+ shared terms or it reports 0. |
| `tfidf_cosine` | Cosine similarity of TF-IDF unigram+bigram vectors, IDF fit on this batch | 0.15 | Batch-relative: terms every resume shares (the stack) are down-weighted automatically. |
| `keyword_coverage` | Share of JD content words present anywhere in the resume | 0.15 | A genuine match covers keywords too, so this is weighted low on purpose. |

Two more are computed for the evidence bullets and the sheet but not weighted:
`verbatim_sentences` (JD sentences that appear with only case and punctuation
changed) and `acronym_coverage` (share of the JD's all-caps tokens, with `SLOs`
normalized to `SLO`, present in the resume).

## Layer 2: judgments from Jev

One request per resume, state `{"job_description": ..., "resume": ...}`, six
questions evaluated in parallel. Each names the state field it is about, states
the condition literally, and puts boundary cases in the criteria, following the
TypeSafe guidance on literal reading. Scores are 0..N-1 across ordered levels and
are divided by N-1 here; Nouls are probabilities.

| Question | Type | Weight | What it adds over the statistics |
|---|---|---|---|
| `phrasing_mirror` | Score, 4 levels | 0.40 | Catches reworded copies the 4-gram overlap misses. Mock paraphrase: 2.81/3 with `phrase_overlap` only 0.05. |
| `requirement_echo` | Score, 4 levels | 0.10 | Coverage including niche items and posting order. Low weight because a genuine match covers requirements too. |
| `concrete_specifics` | Score, 4 levels, inverted | 0.25 | Named employers, dates, systems, numbers, outcomes. Human mock resumes: 2.85-3.0. Generated ones: 0.7-1.0. |
| `generic_template` | Noul | 0.125 | Interchangeable bullets. Correlates with specifics but asked separately, per the guidance not to hide two judgments in one question. |
| `posting_language_leak` | Noul | 0.125 | "You will", "the ideal candidate". Near 0 for every human mock resume; 0.56-0.99 where the leak was planted. |
| `career_consistency` | Noul | 0 (review flag only) | Claimed skills plausible for the listed roles. Not weighted into the score because a mismatch is a different problem from mirroring; it flags for review instead. |

## Combining

`mirror_score = 100 * (0.5 * lexical + 0.5 * semantic)`. There are no
high/medium/low buckets; a single `REVIEW_SCORE` (40) feeds the review flag. A
z-score against the batch is reported and a resume 1.5 standard deviations
above the batch mean in a batch of five or more is marked a batch outlier.

The equal split is deliberate. The lexical half is transparent and reproducible
without any model; the semantic half catches what it misses. When the two
disagree the sheet shows both, and the evidence bullets show what the lexical
half saw.

## Needs human review

YES when any of these fire: mirror score at or above `REVIEW_SCORE`, batch
outlier, any evidence bullet, `posting_language_leak` >= 0.5, `generic_template` >= 0.5,
`career_consistency` < 0.5, or the notes ended in `review: yes`. It is generous
on purpose. In the mock batch it flags a genuinely strong human match on
acronym coverage alone, and that is fine: the reviewer reads it, sees a low
mirror score and a note saying the wording is the candidate's own, and moves
on in thirty seconds. The column's job is to make
sure nobody sorts by score and stops reading.

## Results on the mock set

13 resumes, 8 human (two very close matches, one keyword-padded skills
section, two off-target) and 5 generated in different styles.

| Group | Mirror score range | Notes |
|---|---|---|
| Generated, verbatim | 67-69 | 7, 2 and 1 verbatim JD sentences; all JD acronyms present |
| Generated, paraphrased | ~52 | Lexical half only 34; the semantic half carried it |
| Generated, polished with metrics | ~47 | Specifics judge gave 2.99 on invented round numbers. Still flagged for review; the notes carry the case |
| Human, keyword-padded skills | ~25 | Not flagged |
| Human, very close match | 14-16 | One flagged for review on acronym coverage alone |
| Human, moderate or weak match | 3-14 | |

Mean score: generated 60, human 12. Pairwise AUC 1.0, which says nothing
beyond "the mock set is separable" and should not be quoted as a result. Real
data will be messier: hybrid resumes (human history, model-polished bullets),
candidates who tailor honestly and heavily, non-native English, and postings
that are themselves generic. Re-tune thresholds on labelled real data before
trusting any bucket boundary.

## Known failure modes

- **Invented specifics.** A generator told to add metrics produces plausible
  names and round numbers. The specifics judge cannot verify them; only a human
  or a reference check can. The evidence and notes surface "all metrics are
  round" style observations for exactly this case.
- **Generic postings.** If the JD is boilerplate, everyone's `phrase_overlap`
  rises and the batch z-score becomes the more useful column.
- **Honest heavy tailoring.** Career coaches tell people to mirror the posting.
  A human who does this diligently will be flagged. That is why the output is a
  review list and not a decision.
- **Short or scanned PDFs.** Under 40 extracted words the file is reported as an
  error rather than scored. OCR is out of scope.
- **Non-English.** Jev is English-first. The lexical half still works; treat
  the semantic half with more caution.

## Candidate datasets for real evaluation

No public dataset pairs job descriptions with resumes *and* labels them as
human-written or generated, which is why this ships with synthetic data. When
real data is available, or to build a labelled set:

- The 2,245 human-written LiveCareer resumes used in "AI Self-preferencing in
  Algorithmic Hiring" (arXiv 2509.00462) predate wide LLM adoption and were
  paired with Upwork postings; the paper's construction of LLM-generated
  counterparts is a template for building a labelled set.
- `datasetmaster/resumes` on Hugging Face (MIT, ~4,800 structured tech
  resumes, mixed real and synthetic without labels) is usable as a human-ish
  pool once a posting is chosen.
- Any set of real resumes received *before* a posting was public, paired with
  that posting, is a clean human baseline for a given role.

Run with `--labels` to get mean score per label, precision and recall of the
review flag, and pairwise AUC.
