#!/usr/bin/env python3
"""
fetch_wikidata.py - download Wikidata values for the five predicates of each
Wikipedia person and save them as eval/wikidata_<Name>.csv.

Run from the repo root:   python src/fetch_wikidata.py

Steps for each person:
  1. Ask Wikipedia for the person's Wikidata id (Q-number) from the article title.
  2. Ask the Wikidata SPARQL endpoint for P19, P69, P166, P108, P184 values.
"""
import csv
import pathlib
import time

import requests

# TODO: add your own contact to the User-Agent (Wikimedia asks for this).
HEADERS = {"User-Agent": "KRR-coursework/1.0 (student coursework; add-your-contact-here)"}
PEOPLE = ["James Chadwick", "Steven Weinberg", "Albert Einstein",
          "Ernest Lawrence", "James Franck"]
PROPS = {"P19": "bornIn", "P69": "educatedAt", "P166": "receivedAward",
         "P108": "worksAt", "P184": "doctoralAdvisor"}


def qid_for(title):
    r = requests.get("https://en.wikipedia.org/w/api.php", headers=HEADERS, timeout=30,
                     params={"action": "query", "prop": "pageprops", "ppprop": "wikibase_item",
                             "redirects": 1, "titles": title, "format": "json"})
    r.raise_for_status()
    page = next(iter(r.json()["query"]["pages"].values()))
    return page["pageprops"]["wikibase_item"]


def values_for(qid):
    values = " ".join(f'("{pid}" wdt:{pid})' for pid in PROPS)
    query = f"""
    SELECT ?pid ?val ?valLabel WHERE {{
      VALUES (?pid ?prop) {{ {values} }}
      wd:{qid} ?prop ?val .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}"""
    r = requests.get("https://query.wikidata.org/sparql", timeout=60,
                     params={"query": query, "format": "json"}, headers=HEADERS)
    r.raise_for_status()
    rows = []
    for b in r.json()["results"]["bindings"]:
        pid = b["pid"]["value"]
        rows.append({"predicate": PROPS[pid], "property": pid,
                     "value": b["valLabel"]["value"],
                     "value_id": b["val"]["value"].rsplit("/", 1)[-1]})
    return rows


if __name__ == "__main__":
    out = pathlib.Path("eval")
    out.mkdir(exist_ok=True)
    for person in PEOPLE:
        qid = qid_for(person)
        rows = values_for(qid)
        path = out / f"wikidata_{person.replace(' ', '_')}.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["person", "predicate", "property", "value", "value_id"])
            w.writeheader()
            for r in sorted(rows, key=lambda r: (r["predicate"], r["value"])):
                w.writerow({"person": person, **r})
        counts = {}
        for r in rows:
            counts[r["predicate"]] = counts.get(r["predicate"], 0) + 1
        print(f"{person} ({qid}): {len(rows)} values {counts}")
        time.sleep(1)   # be polite to the server