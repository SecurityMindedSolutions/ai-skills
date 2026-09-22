"""Turn run.py results into something a person reads.

    python3 report.py results.json [--sort QID] [--low 0.8] [--csv out.csv] [--top N]

Prints markdown:
  1. a per-item table (one column per question, choice/score columns show the
     answer plus confidence),
  2. the distribution of every choice / score question,
  3. the low-confidence items (any choice/score under --low), because those are
     where the ambiguity is in the DATA and usually the interesting part,
  4. if items carried `expect`, the agreement rate and every disagreement with
     the probability Jev gave the expected label.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import pathlib


def cell(ans: dict, qid: str) -> str:
    v = ans.get(qid)
    if v is None:
        return "-"
    conf = ans.get(f"{qid}_conf")
    if f"{qid}_level" in ans:
        return f"{ans[f'{qid}_level']} ({v}, c={conf})"
    if conf is not None:
        return f"{v} ({conf:.2f})"
    return f"{v:.2f}" if isinstance(v, float) else str(v)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--sort", default="", help="question id to sort by (choice: by confidence asc; noul/score: value desc)")
    ap.add_argument("--low", type=float, default=0.8, help="confidence threshold for the low-confidence section")
    ap.add_argument("--low-q", default="", help="comma-separated question ids to include in the low-confidence section (default: all)")
    ap.add_argument("--csv", default="", help="also write a flat CSV")
    ap.add_argument("--top", type=int, default=0, help="only print the first N rows of the item table")
    args = ap.parse_args()

    data = json.loads(pathlib.Path(args.results).read_text())
    meta, results = data["meta"], data["results"]
    qids = meta["questions"]
    ok = [r for r in results if not r.get("error")]
    errs = [r for r in results if r.get("error")]

    def kind(qid: str) -> str:
        a = next((r["answers"] for r in ok if qid in r["answers"]), {})
        if f"{qid}_level" in a:
            return "score"
        if f"{qid}_conf" in a:
            return "choice"
        return "noul"

    if args.sort and args.sort in qids:
        k = kind(args.sort)
        if k == "choice":
            ok.sort(key=lambda r: r["answers"].get(f"{args.sort}_conf", 0))
        else:
            ok.sort(key=lambda r: -(r["answers"].get(args.sort) or 0))

    print(f"## Jev run: {meta['items']} items, {len(qids)} questions, model {meta['model']}, "
          f"{meta['input_tokens']:,} input tokens, {meta['wall_seconds']}s, {len(errs)} errors\n")

    rows = ok[: args.top] if args.top else ok
    print("| id | " + " | ".join(qids) + " |")
    print("|---|" + "---|" * len(qids))
    for r in rows:
        print(f"| {r['id']} | " + " | ".join(cell(r["answers"], q) for q in qids) + " |")
    if args.top and len(ok) > args.top:
        print(f"\n({len(ok) - args.top} more rows in {args.results})")

    print("\n### Distributions")
    for q in qids:
        k = kind(q)
        if k == "noul":
            vals = [r["answers"][q] for r in ok if q in r["answers"]]
            yes = sum(1 for v in vals if v > 0.5)
            print(f"- **{q}** (noul): {yes}/{len(vals)} > 0.5; mean p = {sum(vals)/max(len(vals),1):.2f}")
        else:
            key = f"{q}_level" if k == "score" else q
            c = collections.Counter(r["answers"].get(key) for r in ok)
            print(f"- **{q}** ({k}): " + ", ".join(f"{lab} {n}" for lab, n in c.most_common()))

    low = []
    low_qids = [q for q in args.low_q.split(",") if q] or qids
    for r in ok:
        for q in low_qids:
            conf = r["answers"].get(f"{q}_conf")
            if conf is not None and conf < args.low:
                probs = r["answers"].get(f"{q}_probs", {})
                top = sorted(probs.items(), key=lambda kv: -kv[1])[:3]
                low.append((conf, r["id"], q, top))
    if low:
        print(f"\n### Low confidence (< {args.low}), {len(low)} answers, least confident first")
        for conf, rid, q, top in sorted(low):
            print(f"- `{rid}` **{q}** c={conf:.2f}: " + ", ".join(f"{lab} {p:.2f}" for lab, p in top))

    with_expect = [r for r in ok if r.get("expect")]
    if with_expect:
        print("\n### Agreement with expected labels")
        for q in qids:
            pairs = [(r, r["expect"][q]) for r in with_expect if q in r["expect"]]
            if not pairs:
                continue
            k = kind(q)
            key = f"{q}_level" if k == "score" else q
            def same(r, e):
                v = r["answers"].get(key)
                if k == "noul" and isinstance(v, (int, float)):  # noul answers are p(true), expect is a bool
                    return (v > 0.5) == (str(e).lower() == "true")
                return v == e
            agree = [(r, e) for r, e in pairs if same(r, e)]
            print(f"\n**{q}**: {len(agree)}/{len(pairs)} agree")
            dis = [(r, e) for r, e in pairs if not same(r, e)]
            if dis:
                print("\n| id | Jev | p(Jev) | expected | p(expected) |")
                print("|---|---|---|---|---|")
                for r, e in sorted(dis, key=lambda re: -re[0]["answers"].get(f"{q}_conf", 0)):
                    a = r["answers"]
                    probs = a.get(f"{q}_probs", {})
                    print(f"| {r['id']} | {a.get(key)} | {a.get(f'{q}_conf', 0):.2f} | {e} | {probs.get(e, 0):.2f} |")

    if errs:
        print(f"\n### Errors ({len(errs)})")
        for r in errs:
            print(f"- `{r['id']}`: {r['error'][:200]}")

    if args.csv:
        cols = ["id"] + [k for k in sorted({k for r in ok for k in r["answers"]}) if not k.endswith("_probs")]
        cols += [f"expect_{q}" for q in qids if any(q in r.get("expect", {}) for r in ok)]
        with open(args.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r in ok:
                row = {"id": r["id"], **r["answers"], **{f"expect_{q}": v for q, v in r.get("expect", {}).items()}}
                w.writerow(row)
        print(f"\nCSV: {args.csv}")


if __name__ == "__main__":
    main()
