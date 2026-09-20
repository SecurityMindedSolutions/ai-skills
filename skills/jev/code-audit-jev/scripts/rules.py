"""The rule set: everything the runner knows about what to look for comes
from `rules/*.toml`, loaded here. The runner itself knows nothing about any
category.

    rs = load(["/path/to/rules", "/repo/.jev-rules"])   # later dirs override by id
    sig = rs.scan(code, start_line)                        # regex facts per unit
    answers = client.evaluate(state, rs.questions)         # one Jev request
    verdict = rs.judge(answers, sig, role)                 # score, band, category

A rule file declares: `id`, `title`, `class` (its option in the class choice),
`[questions.<id>]` (yes/no Nouls: instructions, true, false), `[signals.<name>]`
(label + regex patterns), `[vector]` (all = multiplied, none = multiplied as
1 - p) and optionally `[floor]` (a code fact plus a question answer that makes
the unit attention regardless of score). `_core.toml` holds the model, the
scoring constants, the class choice wording, the severity scale, the shared
questions (mitigation, not-production) and the generic source/guard signals.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

BUILTIN_RULES_DIR = Path(__file__).resolve().parent.parent / "rules"


@dataclass
class Rule:
    id: str
    title: str
    class_text: str
    questions: dict           # qid -> {"instructions", "true", "false"}
    signals: dict             # name -> {"label", "patterns": [compiled]}
    vector_all: list
    vector_none: list
    floor: dict | None
    source: str


@dataclass
class RuleSet:
    core: dict
    rules: dict = field(default_factory=dict)   # id -> Rule
    core_signals: dict = field(default_factory=dict)

    # --- what Jev is asked -------------------------------------------------
    @property
    def model(self) -> str:
        return self.core["model"]["name"]

    @property
    def scoring(self) -> dict:
        return self.core["scoring"]

    @property
    def bands(self) -> list:
        return [(int(b[0]), str(b[1])) for b in self.scoring["bands"]]

    @property
    def classes(self) -> dict:
        out = {"none": self.core["choice"]["none"]}
        out.update({r.id: r.class_text for r in self.rules.values()})
        out["other_security_defect"] = self.core["choice"]["other"]
        return out

    @property
    def severity_levels(self) -> list[str]:
        return [l.split(".")[0].strip() for l in self.core["severity"]["levels"]]

    @property
    def questions(self) -> dict:
        """The request's `questions` map: one Choice, one Noul per declared
        question (rule and core), one Score."""
        qs = {"issue_class": {"type": "choice", "instructions": self.core["choice"]["instructions"], "criteria": self.classes}}
        for r in self.rules.values():
            for qid, spec in r.questions.items():
                qs[qid] = _noul(spec)
        for qid, spec in self.core.get("questions", {}).items():
            qs[qid] = _noul(spec)
        qs["severity"] = {"type": "score", "instructions": self.core["severity"]["instructions"], "criteria": list(self.core["severity"]["levels"])}
        return qs

    # --- code facts --------------------------------------------------------
    def scan(self, code: str, start_line: int = 1) -> dict:
        """{group: {signal_name: 'label (line N)'}} for every signal that fired;
        rule signals are grouped under the rule id, core signals under 'context'."""
        out: dict = {}
        for r in self.rules.values():
            hits = _scan_group(r.signals, code, start_line)
            if hits:
                out[r.id] = hits
        hits = _scan_group(self.core_signals, code, start_line)
        if hits:
            out["context"] = hits
        return out

    @staticmethod
    def security_relevant(sig: dict) -> bool:
        return any(g != "context" for g in sig) or "context" in sig

    @staticmethod
    def flat(sig: dict) -> list[str]:
        return [f"{g}.{n}" for g, hits in sig.items() for n in hits]

    # --- composition -------------------------------------------------------
    def vectors(self, s: dict) -> dict[str, float]:
        out = {}
        for r in self.rules.values():
            p = 1.0
            for qid in r.vector_all:
                p *= s[qid]
            for qid in r.vector_none:
                p *= 1 - s[qid]
            out[r.id] = round(p, 3)
        return out

    def score(self, s: dict, vectors: dict) -> float:
        c = self.scoring
        strongest = max(vectors.values()) if vectors else 0.0
        raw = c["w_severity"] * s["severity"] / (len(self.severity_levels) - 1) + c["w_vector"] * strongest * (1 - c["mitigation_discount"] * s["mitigation_in_unit"])
        return round(100 * min(1.0, raw), 1)

    def band(self, score: float) -> str:
        name = self.bands[0][1]
        for floor, label in self.bands:
            if score >= floor:
                name = label
        return name

    def judge(self, answers: dict, sig: dict, role: str) -> dict:
        s = self.flatten_answers(answers)
        c = self.scoring
        vectors = self.vectors(s)
        reasons: list[str] = []
        if role == "test" or s["not_production_code"] >= c["drop_not_production"]:
            return {"category": "dropped", "score": 0.0, "band": self.bands[0][1], "attention": False,
                    "reasons": [f"not production code ({s['not_production_code']})"], "answers": s, "vectors": vectors, "signals_fired": []}
        score = self.score(s, vectors)
        strongest = max(vectors, key=vectors.get) if vectors else "none"
        category = s["issue_class"]
        if category in vectors and vectors[category] < c["choice_min_own_vector"] and s["issue_class_confidence"] < 0.9:
            reasons.append(f"choice {category} contradicted by its own vector {vectors[category]}")
            category = "none"
        if category == "none" or s["issue_class_confidence"] < c["choice_min_confidence"]:
            if score >= c["attention_score"] and vectors.get(strongest, 0) >= c.get("fallback_min_vector", 0.5):
                category = strongest
                reasons.append(f"choice was {s['issue_class']} ({s['issue_class_confidence']}); strongest vector {strongest} {vectors.get(strongest)}")
            else:
                category = "none"
        attention = score >= c["attention_score"] and category != "none"
        for r in self.rules.values():
            f = r.floor
            if not f:
                continue
            hit = sig.get(r.id, {}).get(f["signal"], "")
            qid = r.vector_all[0] if r.vector_all else None
            if hit and any(lbl in hit for lbl in f.get("labels", [])) and qid and s[qid] >= f["min"]:
                attention, category = True, r.id
                score = max(score, float(c["attention_score"]))
                reasons.append(f"code floor ({r.id}): {hit} and Jev agrees ({s[qid]})")
        fired = [qid for qid, v in sorted(self.rule_question_answers(s).items(), key=lambda kv: -kv[1]) if v >= c["signal_threshold"]]
        return {"category": category, "score": score, "band": self.band(score), "attention": attention,
                "reasons": reasons, "answers": s, "vectors": vectors, "signals_fired": fired}

    def rule_question_answers(self, s: dict) -> dict:
        """Only the questions whose 'true' means a defect (the ones in a rule's
        `all` list), for the Signals column."""
        out = {}
        for r in self.rules.values():
            for qid in r.vector_all:
                out[qid] = s[qid]
        return out

    def flatten_answers(self, answers: dict) -> dict:
        s: dict = {}
        for key, spec in self.questions.items():
            a = answers[key]
            if spec["type"] == "noul":
                s[key] = round(a["noul"], 3)
            elif spec["type"] == "score":
                s[key] = round(a["score"], 2)
                s[f"{key}_confidence"] = round(a["confidence"], 3)
                probs = {int(k): round(v, 3) for k, v in a["probabilities"].items()}
                top = max(probs, key=probs.get)
                s[f"{key}_level"] = self.severity_levels[top]
                s[f"{key}_level_p"] = probs[top]
                s[f"{key}_probabilities"] = probs
            elif spec["type"] == "choice":
                s[key] = a["choice"]
                s[f"{key}_confidence"] = round(a["confidence"], 3)
                s[f"{key}_probabilities"] = {k: round(v, 3) for k, v in a.get("probabilities", {}).items()}
        return s


def _noul(spec: dict) -> dict:
    return {"type": "noul", "instructions": spec["instructions"], "criteria": {"true": spec["true"], "false": spec["false"]}}


def _compile_signals(table: dict) -> dict:
    out = {}
    for name, spec in table.items():
        out[name] = {"label": spec.get("label", name.replace("_", " ")),
                     "patterns": [re.compile(p, re.M) for p in spec.get("patterns", [])]}
    return out


def _scan_group(signals: dict, code: str, start_line: int) -> dict:
    hits = {}
    for name, spec in signals.items():
        for rx in spec["patterns"]:
            m = rx.search(code)
            if m:
                hits[name] = f"{spec['label']} (line {start_line + code.count(chr(10), 0, m.start())})"
                break
    return hits


def load(dirs: list[str | Path] | None = None) -> RuleSet:
    """Built-in rules first, then each extra directory in order; a file with an
    existing `id` replaces that rule, `_core.toml` in an extra dir is merged
    over the built-in core (top-level tables replaced whole)."""
    dirs = [BUILTIN_RULES_DIR] + [Path(d) for d in (dirs or [])]
    core: dict = {}
    rules: dict = {}
    for d in dirs:
        d = Path(d).expanduser()
        if not d.is_dir():
            raise SystemExit(f"rules directory not found: {d}")
        core_file = d / "_core.toml"
        if core_file.is_file():
            loaded = tomllib.loads(core_file.read_text(encoding="utf-8"))
            core.update(loaded) if core else core.update(loaded)
        for f in sorted(d.glob("*.toml")):
            if f.name.startswith("_"):
                continue
            t = tomllib.loads(f.read_text(encoding="utf-8"))
            rid = t.get("id") or f.stem
            rules[rid] = Rule(id=rid, title=t.get("title", rid), class_text=t["class"],
                              questions=t.get("questions", {}), signals=_compile_signals(t.get("signals", {})),
                              vector_all=list(t.get("vector", {}).get("all", [])), vector_none=list(t.get("vector", {}).get("none", [])),
                              floor=t.get("floor"), source=str(f))
    if not core:
        raise SystemExit("no _core.toml found in any rules directory")
    rs = RuleSet(core=core, rules=rules, core_signals=_compile_signals(core.get("signals", {})))
    _validate(rs)
    return rs


def _validate(rs: RuleSet) -> None:
    qids = set(rs.questions)
    for r in rs.rules.values():
        for qid in r.vector_all + r.vector_none:
            if qid not in qids:
                raise SystemExit(f"rule {r.id} ({r.source}): vector names unknown question {qid}")
        if not r.vector_all:
            raise SystemExit(f"rule {r.id}: [vector] all must name at least one question")
        if r.floor and r.floor.get("signal") not in r.signals:
            raise SystemExit(f"rule {r.id}: floor names unknown signal {r.floor.get('signal')}")
    for must in ("mitigation_in_unit", "not_production_code"):
        if must not in rs.core.get("questions", {}):
            raise SystemExit(f"_core.toml must declare [questions.{must}]")


if __name__ == "__main__":
    import json
    import sys
    rs = load(sys.argv[1:])
    print(f"{len(rs.rules)} rules, {len(rs.questions)} questions per request, "
          f"{sum(len(r.signals) for r in rs.rules.values()) + len(rs.core_signals)} signal groups")
    for r in rs.rules.values():
        print(f"  {r.id:24} questions={list(r.questions)} signals={list(r.signals)} vector=all{r.vector_all} none{r.vector_none}{' floor' if r.floor else ''}")
    print(json.dumps({k: v["type"] for k, v in rs.questions.items()}))
