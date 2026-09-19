"""Every constant a reviewer needs to see in one place.

TypeSafe's own guidance: the questions and thresholds are the part of a Jev
integration humans should review, so they live here and nowhere else. The
scoring code in analyze.py only combines what is defined in this file.

Two rules shape the questions:

1. Jev is literal. Each question names the state field it is about
   (`job_description`, `resume`) and states the exact condition. Anything
   that needs interpretation is split into two questions and combined in code.
2. Jev is not a calculator. Counting, overlap ratios and similarity math are
   done in lexical.py. Jev only answers the semantic questions code cannot.
"""

MODEL = "jev-latest"

# The state sent with every request. Keys are referenced by name in the
# questions below, per the "reference specific fields" guidance.
STATE_KEYS = ("job_description", "resume")

# --------------------------------------------------------------------------
# Jev questions. One request per resume, all questions fan out in parallel.
# --------------------------------------------------------------------------
QUESTIONS = {
    "phrasing_mirror": {
        "type": "score",
        "instructions": (
            "How much of the wording in `resume` is copied or lightly reworded "
            "from `job_description`? Judge sentence structure and phrasing, not "
            "whether the same skills are mentioned."
        ),
        "criteria": [
            "Written independently. Shares only common industry terms that any "
            "candidate in this field would use.",
            "A few requirement phrases from `job_description` appear in `resume` "
            "with the wording changed.",
            "Several phrases from `job_description` appear in `resume` nearly "
            "verbatim.",
            "Large parts of `resume` are `job_description` phrases repeated back "
            "with minimal change.",
        ],
    },
    "requirement_echo": {
        "type": "score",
        "instructions": (
            "How completely does `resume` claim experience with each requirement "
            "listed in `job_description`, including the niche or unusual ones?"
        ),
        "criteria": [
            "Claims few of the listed requirements.",
            "Claims the core requirements but not the niche ones.",
            "Claims nearly every listed requirement, including niche ones.",
            "Claims every listed requirement, in the same grouping or order that "
            "`job_description` lists them.",
        ],
    },
    "concrete_specifics": {
        "type": "score",
        "instructions": (
            "How much concrete, checkable detail does `resume` contain that could "
            "not have been written from `job_description` alone? Look for named "
            "employers, dates, named systems, numbers, and outcomes."
        ),
        "criteria": [
            "Only generic responsibility statements and buzzwords.",
            "A few specifics such as employer names and dates, but the "
            "responsibilities themselves are generic.",
            "Named employers, dates, and some quantified outcomes or named "
            "projects.",
            "Rich, specific detail throughout: named systems, numbers, outcomes "
            "and context that is unique to this candidate.",
        ],
    },
    "generic_template": {
        "type": "noul",
        "instructions": (
            "Does `resume` read like generic template text that could describe "
            "almost any candidate for this role?"
        ),
        "criteria": {
            "true": "Interchangeable bullets with no detail tied to a specific "
                    "employer, project or outcome.",
            "false": "Bullets are tied to specific employers, projects or "
                     "outcomes.",
        },
    },
    "career_consistency": {
        "type": "noul",
        "instructions": (
            "Are the skills claimed in `resume` plausible given the roles, "
            "employers, seniority and dates it lists?"
        ),
        "criteria": {
            "true": "The claimed skills line up with the roles and seniority.",
            "false": "It claims skills or seniority the listed roles would not "
                     "plausibly provide.",
        },
    },
    "posting_language_leak": {
        "type": "noul",
        "instructions": (
            "Does `resume` contain language that belongs in a job posting rather "
            "than a resume, such as 'the ideal candidate', 'you will', 'we are "
            "looking for', 'must have', or requirement-style bullets?"
        ),
        "criteria": {
            "true": "Posting-style phrasing appears in `resume`.",
            "false": "`resume` is written entirely in the first person or as a "
                     "candidate's own history.",
        },
    },
}

# --------------------------------------------------------------------------
# Composite scoring. All weights within a group sum to 1.0.
# --------------------------------------------------------------------------

# Lexical signals, computed in code. Each is already normalized to 0..1.
LEXICAL_WEIGHTS = {
    "phrase_overlap": 0.35,      # share of JD 4-grams found verbatim in resume
    "longest_span": 0.20,        # longest shared word run, capped by LONGEST_SPAN_CAP
    "order_echo": 0.15,          # do matched JD terms appear in JD order?
    "tfidf_cosine": 0.15,        # bag-of-words similarity within the pool
    "keyword_coverage": 0.15,    # low weight on purpose: fit is not fraud
}
LONGEST_SPAN_CAP = 12            # a 12+ word verbatim run scores 1.0

# Semantic signals from Jev. Scores are divided by their top level index so
# each lands in 0..1. "Inverted" signals are subtracted from 1 before weighting.
SEMANTIC_WEIGHTS = {
    "phrasing_mirror": 0.40,
    "requirement_echo": 0.10,    # low weight on purpose, same reason as above
    "concrete_specifics": 0.25,  # inverted: more specifics means less suspicion
    "generic_template": 0.125,
    "posting_language_leak": 0.125,
}
INVERTED_SIGNALS = {"concrete_specifics"}

# How the two groups combine into the 0..100 mirror score.
GROUP_WEIGHTS = {"lexical": 0.5, "semantic": 0.5}

# A mirror score at or above this marks the row for human review on its own.
# There are deliberately no "high/medium/low" buckets: the tool reports how
# closely a file tracks the posting, it does not grade the candidate.
REVIEW_SCORE = 40

# A resume this many standard deviations above the batch mean is marked as a
# pool outlier regardless of bucket. Only meaningful with 5+ resumes.
POOL_OUTLIER_Z = 1.5
POOL_MIN_SIZE = 5

# "Needs human review" is true when ANY of these fire. It is deliberately
# generous: the column exists so nobody sorts by score and stops reading.
REVIEW_TRIGGERS = {
    "score": True,                     # mirror_score >= REVIEW_SCORE
    "pool_outlier": True,              # z-score past POOL_OUTLIER_Z in a batch of POOL_MIN_SIZE+
    "any_code_evidence": True,         # at least one evidence bullet from evidence.py
    "posting_language_leak": 0.5,      # Jev noul at or above this
    "generic_template": 0.5,           # Jev noul at or above this
    "career_consistency_below": 0.5,   # Jev noul below this
    "llm_flag": True,                  # the optional LLM answered "review: yes"
}

# Jev context budget is 32k tokens for state plus the longest question. We cap
# each text well under that so a long CV plus a long JD always fits.
MAX_CHARS_PER_DOC = 24_000

# Pricing for the cost line in the summary. Output tokens are free.
USD_PER_MILLION_INPUT_TOKENS = 0.042
