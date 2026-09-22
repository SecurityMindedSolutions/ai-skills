"""Field check: run jev-email-analysis over a REAL labelled dataset and measure it.

Dataset (--dataset): list of {"id", "state"} (e.g. from a mail-log export; keep it outside this
skill - it is real mail). Labels (--labels): {id: {"category", "accept": [...], "ambiguous": bool,
"ok_verdicts": [...]}} - `accept` lists every category a careful human would also accept;
`ok_verdicts` lists verdicts that are acceptable even for a harmless label (e.g. "suspicious" for
scammy lead-list spam).

Metrics (ambiguous items excluded from all but the listing):
  strict   - predicted category == primary label
  lenient  - predicted category in accept
  false alarms - label accepts only harmless categories, but verdict suspicious/malicious (minus ok_verdicts)
  misses       - labelled as a threat category, but verdict benign or spam
Also a confusion table (label -> predicted) and, with --baseline, what changed vs a previous run.

Usage: field_check.py --dataset d.json --labels l.json --out run.json [--baseline prev.json] [--show 25]
"""
import argparse, collections, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from analyze import SPAM, api_key, judge_all, normalize, org_context  # noqa: E402

HARMLESS = {"legitimate_business"} | SPAM


def score(results: dict, labels: dict) -> dict:
    s = collections.Counter(); conf = collections.Counter(); fa, miss, wrong = [], [], []
    for i, r in results.items():
        lab = labels.get(i)
        if not lab or lab.get("ambiguous") or not r.get("answers"):
            continue
        cat, v = r["answers"].get("category"), r.get("verdict")
        s["n"] += 1; s["strict"] += cat == lab["category"]; s["lenient"] += cat in lab["accept"]
        conf[(lab["category"], cat)] += 1
        if cat not in lab["accept"]:
            wrong.append(i)
        harmless_ok = set(lab["accept"]) <= HARMLESS          # label accepts no threat reading at all
        if harmless_ok and v in ("suspicious", "malicious") and v not in lab.get("ok_verdicts", []):
            fa.append(i)
        if lab["category"] not in HARMLESS and v in ("benign", "spam"):
            miss.append(i)
    n = max(s["n"], 1)
    return {"n": s["n"], "strict": s["strict"] / n, "lenient": s["lenient"] / n,
            "false_alarms": fa, "misses": miss, "wrong": wrong,
            "confusion": {f"{a} -> {b}": c for (a, b), c in conf.most_common() if a != b}}


def show(title: str, ids: list, results: dict, labels: dict, states: dict, limit: int):
    print(f"\n{title} ({len(ids)})")
    for i in ids[:limit]:
        a = results[i]["answers"]; st = states[i]
        print(f"  {i} {results[i]['verdict']:10} {a['category'][:20]:20} ({a['category_conf']:.2f}) "
              f"want {labels[i]['category'][:20]:20} | {st['sender'][:34]:34} | {st.get('subject', '')[:50]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True); ap.add_argument("--labels", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True); ap.add_argument("--baseline", type=Path)
    ap.add_argument("--show", type=int, default=25)
    ap.add_argument("--org-name"); ap.add_argument("--own-domains")
    a = ap.parse_args()
    key = api_key()
    if not key:
        sys.exit("no TypeSafe credentials")
    items = normalize(json.loads(a.dataset.read_text())); labels = json.loads(a.labels.read_text())
    states = {i["id"]: i["state"] for i in items}
    ctx = org_context(a.org_name, a.own_domains.split(",") if a.own_domains else None)
    results = {r["id"]: r for r in judge_all(items, key, ctx)}
    m = score(results, labels)
    a.out.write_text(json.dumps({"metrics": m, "results": list(results.values())}, indent=1))
    print(f"n={m['n']}  strict {m['strict']:.1%}  lenient {m['lenient']:.1%}  "
          f"false alarms {len(m['false_alarms'])}  misses {len(m['misses'])}  "
          f"errors {sum('error' in r for r in results.values())}")
    print("confusion (label -> predicted):", json.dumps(m["confusion"], indent=1))
    show("FALSE ALARMS", m["false_alarms"], results, labels, states, a.show)
    show("MISSES", m["misses"], results, labels, states, a.show)
    show("OTHER WRONG CATEGORY", [i for i in m["wrong"] if i not in m["false_alarms"] + m["misses"]], results, labels, states, a.show)
    if a.baseline and a.baseline.exists():
        b = json.loads(a.baseline.read_text())["metrics"]
        print(f"\nvs baseline: strict {b['strict']:.1%} -> {m['strict']:.1%}, lenient {b['lenient']:.1%} -> {m['lenient']:.1%}, "
              f"false alarms {len(b['false_alarms'])} -> {len(m['false_alarms'])}, misses {len(b['misses'])} -> {len(m['misses'])}")
        print("  newly wrong:", sorted(set(m["wrong"]) - set(b["wrong"])), " newly right:", sorted(set(b["wrong"]) - set(m["wrong"])))


if __name__ == "__main__":
    main()
