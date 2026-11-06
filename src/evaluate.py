#!/usr/bin/env python3
"""
evaluate.py - compare out/triples.csv with the Wikidata exports (eval/wikidata_*.csv).

Run from the repo root:
    python src/evaluate.py                 # writes eval/metrics.csv and the FP/FN lists
    python src/evaluate.py --tag after     # same, but names the files *_after.csv

Rules used (state these in your README / error analysis):
  * Only triples whose subject is exactly one of the five Wikipedia people are scored.
    (Triples for other people, or for an alias such as 'Ernest Orlando Lawrence', are
    therefore not counted - an alias split shows up as missing triples = false negatives.)
  * Two values match when their lower-cased text is equal after removing a leading
    'the ' and extra spaces. Exact matching is strict on purpose.
  * TP = extracted and in Wikidata; FP = extracted, not in Wikidata;
    FN = in Wikidata, not extracted.
  * Duplicate triples (same subject, predicate, object) count once.
"""
import argparse
import csv
import glob
import pathlib
import re
from collections import defaultdict

PREDICATES = ["bornIn", "educatedAt", "receivedAward", "worksAt", "doctoralAdvisor"]
FP_POSITIONS = [8, 11, 17, 20]      # from ASSIGNMENT_SHEET.md
FN_POSITIONS = [12, 14, 19, 20]


def norm(s):
    s = re.sub(r"\s+", " ", s.strip().lower())
    return re.sub(r"^the ", "", s)


def pick(sorted_list, positions):
    """1-based positions with wrap-around: position mod length (counting from 1)."""
    n = len(sorted_list)
    if n == 0:
        return []
    out = []
    for p in positions:
        idx = ((p - 1) % n)          # p=n+1 wraps to the first item
        out.append((p, idx + 1, sorted_list[idx]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--triples", default="out/triples.csv")
    ap.add_argument("--eval-dir", default="eval")
    ap.add_argument("--tag", default="", help="suffix for output files, e.g. 'after'")
    args = ap.parse_args()
    suffix = f"_{args.tag}" if args.tag else ""
    ev = pathlib.Path(args.eval_dir)

    # Wikidata: person -> predicate -> {normalised value: original value}
    gold, people = defaultdict(lambda: defaultdict(dict)), []
    for f in sorted(glob.glob(str(ev / "wikidata_*.csv"))):
        for row in csv.DictReader(open(f, encoding="utf-8")):
            if row["person"] not in people:
                people.append(row["person"])
            gold[row["person"]][row["predicate"]][norm(row["value"])] = row["value"]
    if not people:
        raise SystemExit(f"no wikidata_*.csv files found in {ev}")

    # Extracted triples for those people (deduplicated), with a sample sentence.
    ext, sentence_of = defaultdict(lambda: defaultdict(dict)), {}
    for row in csv.DictReader(open(args.triples, encoding="utf-8")):
        s, p, o = row["subject"], row["predicate"], row["object"]
        if s in people and p in PREDICATES:
            ext[s][p].setdefault(norm(o), o)
            sentence_of.setdefault((s, p, norm(o)), (row["source_doc"], row["sentence"]))

    stats = {p: {"TP": 0, "FP": 0, "FN": 0} for p in PREDICATES}
    fps, fns = [], []
    for person in people:
        for p in PREDICATES:
            e, g = ext[person][p], gold[person][p]
            for key, val in e.items():
                if key in g:
                    stats[p]["TP"] += 1
                else:
                    stats[p]["FP"] += 1
                    doc, sent = sentence_of[(person, p, key)]
                    fps.append((person, p, val, doc, sent))
            for key, val in g.items():
                if key not in e:
                    stats[p]["FN"] += 1
                    fns.append((person, p, val, "", ""))
    fps.sort(key=lambda t: t[:3])
    fns.sort(key=lambda t: t[:3])

    # metrics.csv
    def prf(tp, fp, fn):
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        return round(pr, 3), round(rc, 3)

    metrics_path = ev / f"metrics{suffix}.csv"
    with metrics_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["predicate", "TP", "FP", "FN", "precision", "recall"])
        tot = {"TP": 0, "FP": 0, "FN": 0}
        for p in PREDICATES:
            s = stats[p]
            w.writerow([p, s["TP"], s["FP"], s["FN"], *prf(s["TP"], s["FP"], s["FN"])])
            for k in tot:
                tot[k] += s[k]
        w.writerow(["ALL", tot["TP"], tot["FP"], tot["FN"], *prf(tot["TP"], tot["FP"], tot["FN"])])

    # sorted FP / FN lists
    for name, rows in (("false_positives", fps), ("false_negatives", fns)):
        with (ev / f"{name}{suffix}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["position", "subject", "predicate", "object", "source_doc", "sentence"])
            for i, r in enumerate(rows, 1):
                w.writerow([i, *r])

    print(open(metrics_path).read())
    print(f"false positives: {len(fps)}, false negatives: {len(fns)}")
    print("\n== items to analyse (positions from your sheet, with wrap-around) ==")
    for label, lst, positions in (("FALSE POSITIVES", fps, FP_POSITIONS),
                                  ("FALSE NEGATIVES", fns, FN_POSITIONS)):
        print(f"\n{label}")
        for pos, idx, item in pick(lst, positions):
            note = f" (wrapped to {idx})" if idx != pos else ""
            print(f"  position {pos}{note}: ({item[0]}, {item[1]}, {item[2]})")
            if item[4]:
                print(f"      sentence: {item[4]}")


if __name__ == "__main__":
    main()