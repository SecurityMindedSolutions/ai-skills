"""Run a Jev spec: the same questions over one or many items, in parallel.

    python3 run.py spec.json results.json [--dry-run] [--limit N] [--concurrency N]

Spec shape (see references/spec-format.md):
    {
      "model": "jev-latest",                  # optional
      "concurrency": 6,                       # optional
      "questions": {qid: {type, instructions, criteria}},
      "context": {...},                       # optional, merged into every item's state as "context"
      "items": [{"id": "...", "state": {...}, "expect": {qid: label}}]
    }

Writes results.json:
    {"meta": {...}, "results": [{"id", "answers": {qid: flat}, "expect", "input_tokens", "latency_ms", "error"?}]}

Answers are flattened per primitive so report.py and ad-hoc code can read them
without knowing the wire shape:
    noul   -> {qid: p_true}
    choice -> {qid: option, qid_conf: confidence, qid_probs: {option: p}}
    score  -> {qid: expected_value, qid_conf, qid_level: top label, qid_probs: {label: p}}
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from jev import JevClient, load_api_key  # noqa: E402

# Measured on jev-latest 2026-09-20: prompts over ~6k input tokens per call
# start getting truncated or rejected. Warn, do not block.
SOFT_TOKEN_CAP = 6000


def flatten(answers: dict, questions: dict) -> dict:
    flat: dict = {}
    for qid, spec in questions.items():
        a = answers[qid]
        kind = spec["type"]
        if kind == "noul":
            flat[qid] = round(a["noul"], 3)
        elif kind == "choice":
            flat[qid] = a["choice"]
            flat[f"{qid}_conf"] = round(a["confidence"], 3)
            flat[f"{qid}_probs"] = {k: round(v, 3) for k, v in a.get("probabilities", {}).items()}
        elif kind == "score":
            probs = {int(k): round(v, 3) for k, v in a.get("probabilities", {}).items()}
            legend = {int(k): v for k, v in a.get("legend", {}).items()} or dict(enumerate(spec["criteria"]))
            top = max(probs, key=probs.get) if probs else None
            flat[qid] = round(a["score"], 3)
            flat[f"{qid}_conf"] = round(a["confidence"], 3)
            flat[f"{qid}_level"] = legend.get(top) if top is not None else None
            flat[f"{qid}_probs"] = {legend.get(k, str(k)): v for k, v in probs.items()}
    return flat


def estimate_tokens(obj) -> int:
    return len(json.dumps(obj)) // 4


def validate(spec: dict) -> list[str]:
    problems = []
    qs = spec.get("questions") or {}
    if not qs:
        problems.append("spec.questions is empty")
    for qid, q in qs.items():
        t = q.get("type")
        if t not in ("noul", "choice", "score"):
            problems.append(f"{qid}: type must be noul|choice|score, got {t!r}")
        if not q.get("instructions"):
            problems.append(f"{qid}: instructions missing")
        if t == "choice" and not (isinstance(q.get("criteria"), dict) and 2 <= len(q["criteria"]) <= 255):
            problems.append(f"{qid}: choice needs a criteria dict of 2..255 options")
        if t == "score" and not (isinstance(q.get("criteria"), list) and 2 <= len(q["criteria"]) <= 10):
            problems.append(f"{qid}: score needs a criteria list of 2..10 ordered levels")
        if t == "noul" and q.get("criteria") is not None and set(q["criteria"]) != {"true", "false"}:
            problems.append(f"{qid}: noul criteria, when given, must have exactly 'true' and 'false'")
    items = spec.get("items") or []
    if not items:
        problems.append("spec.items is empty")
    ids = [it.get("id") for it in items]
    if len(set(ids)) != len(ids) or any(i is None for i in ids):
        problems.append("every item needs a unique 'id'")
    for it in items:
        for qid, label in (it.get("expect") or {}).items():
            q = qs.get(qid)
            if q and q["type"] == "choice" and label not in q["criteria"]:
                problems.append(f"{it.get('id')}: expect[{qid}]={label!r} is not one of the choice options")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("out")
    ap.add_argument("--dry-run", action="store_true", help="validate + estimate tokens, no API calls")
    ap.add_argument("--limit", type=int, default=0, help="run only the first N items")
    ap.add_argument("--concurrency", type=int, default=0)
    args = ap.parse_args()

    spec = json.loads(pathlib.Path(args.spec).read_text())
    problems = validate(spec)
    if problems:
        print("spec problems:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 2

    questions = spec["questions"]
    context = spec.get("context")
    items = spec["items"][: args.limit] if args.limit else spec["items"]
    model = spec.get("model", "jev-latest")
    concurrency = args.concurrency or spec.get("concurrency", 6)

    def state_for(item: dict) -> dict:
        st = item["state"]
        if context is not None:
            st = {"context": context, "item": st} if not isinstance(st, dict) else {"context": context, **st}
        return st

    est = [estimate_tokens({"state": state_for(it), "questions": questions}) for it in items]
    big = [(it["id"], e) for it, e in zip(items, est) if e > SOFT_TOKEN_CAP]
    print(f"{len(items)} items x {len(questions)} questions, ~{sum(est):,} input tokens estimated", file=sys.stderr)
    if big:
        print(f"WARNING {len(big)} items exceed ~{SOFT_TOKEN_CAP} tokens (truncate their state): "
              + ", ".join(f"{i}={e}" for i, e in big[:8]), file=sys.stderr)
    if args.dry_run:
        return 0

    client = JevClient(load_api_key(), model)

    def one(item: dict) -> dict:
        t0 = time.time()
        base = {"id": item["id"], "expect": item.get("expect") or {}}
        try:
            resp = client.evaluate(state_for(item), questions)
        except Exception as err:  # noqa: BLE001
            return base | {"error": str(err)[:400], "answers": {}, "input_tokens": 0, "latency_ms": 0}
        return base | {"answers": flatten(resp["answers"], questions),
                       "input_tokens": resp["usage"]["input_tokens"],
                       "latency_ms": int((time.time() - t0) * 1000),
                       "model": resp.get("model", model)}

    results = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        for r in ex.map(one, items):
            results.append(r)
            tag = "ERR " if r.get("error") else "ok  "
            print(f"{tag}{r['id']}", file=sys.stderr, flush=True)

    errors = [r for r in results if r.get("error")]
    meta = {"spec": str(args.spec), "model": model, "items": len(results), "errors": len(errors),
            "questions": list(questions), "input_tokens": sum(r["input_tokens"] for r in results),
            "wall_seconds": round(time.time() - t0, 1)}
    pathlib.Path(args.out).write_text(json.dumps({"meta": meta, "results": results}, indent=1))
    print(f"done: {meta['items']} items, {meta['errors']} errors, {meta['input_tokens']:,} input tokens, "
          f"{meta['wall_seconds']}s -> {args.out}", file=sys.stderr)
    if errors:
        print("first error: " + errors[0]["error"], file=sys.stderr)
    return 1 if errors and len(errors) == len(results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
