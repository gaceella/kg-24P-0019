#!/usr/bin/env python3
"""
validate_shacl.py - validate out/kg.ttl against shapes.ttl with pySHACL and
save the human-readable report to shacl_report.txt.

Run from the repo root:
    python src/validate_shacl.py
"""
import argparse
import pathlib

from pyshacl import validate
from rdflib import Graph


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="out/kg.ttl")
    ap.add_argument("--shapes", default="shapes.ttl")
    ap.add_argument("--ontology", default="ontology.ttl")
    ap.add_argument("--report", default="shacl_report.txt")
    args = ap.parse_args()

    data = Graph().parse(args.data, format="turtle")
    shapes = Graph().parse(args.shapes, format="turtle")
    onto = Graph().parse(args.ontology, format="turtle")

    conforms, _, text = validate(
        data, shacl_graph=shapes, ont_graph=onto,
        inference="none", abort_on_first=False, meta_shacl=False,
        advanced=True, debug=False)

    pathlib.Path(args.report).write_text(text, encoding="utf-8")
    print("conforms:", conforms)
    print(f"report written to {args.report}")
    print("violations (and warnings) in report:", text.count("Constraint Violation"))
    print("  of which severity Violation:", text.count("Severity: sh:Violation"))
    print("  of which severity Warning:  ", text.count("Severity: sh:Warning"))


if __name__ == "__main__":
    main()