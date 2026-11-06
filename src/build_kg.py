#!/usr/bin/env python3
"""
build_kg.py - turn out/triples.csv into an RDF graph (out/kg.ttl) with rdflib.

Run from the repo root:
    python src/build_kg.py
    python src/build_kg.py --triples out/triples.csv --out out/kg.ttl

Modelling choices (explain these in your README):
  * Every entity gets a URI in your namespace: kg:Albert_Einstein.
    The original name is kept as rdfs:label.
  * Predicates become properties: kg:bornIn, kg:educatedAt, kg:receivedAward,
    kg:worksAt, kg:doctoralAdvisor.
  * Classes are guessed from the ROLE an entity plays in a triple:
        subject of any triple, or object of doctoralAdvisor -> kg:Person
        object of bornIn                                    -> kg:Place
        object of educatedAt / worksAt                      -> kg:Organization
        object of receivedAward                             -> kg:Award
    If one name plays two roles (e.g. 'Berlin' as a birthplace and as a
    school) it gets two classes - the ontology's disjointWith statements
    and your SHACL shapes will then flag it. That is a useful finding.
  * Provenance (source_doc, sentence) stays in triples.csv; the graph itself
    holds only the facts.
"""
import argparse
import csv
import pathlib
import re
from urllib.parse import quote

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS

NS = Namespace("http://example.org/kg/24p-0019/")

PREDICATES = {"bornIn", "educatedAt", "receivedAward", "worksAt", "doctoralAdvisor"}

# predicate -> class of the OBJECT
OBJECT_CLASS = {
    "bornIn": NS.Place,
    "educatedAt": NS.Organization,
    "worksAt": NS.Organization,
    "receivedAward": NS.Award,
    "doctoralAdvisor": NS.Person,
}


def uri_for(name):
    """'Albert Einstein' -> kg:Albert_Einstein (safe for use in a URI)."""
    slug = re.sub(r"\s+", "_", name.strip())
    return URIRef(NS[quote(slug, safe="_.-~")])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--triples", default="out/triples.csv")
    ap.add_argument("--out", default="out/kg.ttl")
    args = ap.parse_args()

    g = Graph()
    g.bind("kg", NS)
    g.bind("rdfs", RDFS)

    n_rows = 0
    with open(args.triples, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            s, p, o = row["subject"], row["predicate"], row["object"]
            if p not in PREDICATES or not s or not o:
                continue
            n_rows += 1
            s_uri, o_uri = uri_for(s), uri_for(o)
            g.add((s_uri, NS[p], o_uri))
            g.add((s_uri, RDFS.label, Literal(s)))
            g.add((o_uri, RDFS.label, Literal(o)))
            g.add((s_uri, RDF.type, NS.Person))
            g.add((o_uri, RDF.type, OBJECT_CLASS[p]))

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(out), format="turtle")

    fact_count = sum(1 for _, p, _ in g if str(p).startswith(str(NS)) and
                     str(p)[len(str(NS)):] in PREDICATES)
    print(f"read {n_rows} rows from {args.triples}")
    print(f"graph has {len(g)} triples in total, {fact_count} of them facts "
          f"(duplicates in the CSV collapse into one triple)")
    print(f"written to {out}")


if __name__ == "__main__":
    main()