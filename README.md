# Knowledge Graph Representation – AI3001 Assignment 1 (24P-0019)

This project turns biographies into a small knowledge graph, checks the graph with an ontology and
SHACL shapes, stores it in Apache Jena Fuseki, queries it with SPARQL, and scores the extracted
facts against Wikidata.

```
text → triples → ontology + SHACL → RDF graph in Fuseki → SPARQL queries → scoring
```

- Fuseki dataset: `kg-24p-0019` (persistent TDB2)
- Namespace: `http://example.org/kg/24p-0019/`
- Texts (`data/raw/`): five Wikipedia articles (James Chadwick, Steven Weinberg, Albert Einstein,
  Ernest Lawrence, James Franck) and my private document `private_document.txt`.
- The five extracted predicates: `bornIn`, `educatedAt`, `receivedAward`, `worksAt`, `doctoralAdvisor`.

## Folder contents

| Path | Contents |
|---|---|
| `src/` | `fetch_wikipedia.py`, `extract.py`, `build_kg.py`, `validate_shacl.py`, `fetch_wikidata.py`, `evaluate.py` |
| `data/raw/` | the six input texts |
| `out/` | `triples.csv`, `merge_report.txt`, `kg.ttl` |
| `ontology.ttl`, `shapes.ttl`, `shacl_report.txt`, `shacl_note.md` | ontology, SHACL shapes, validation report and my note on it |
| `queries/`, `results/` | `q1.rq`–`q6.rq`, `answers.md`, and the results `q1.csv`–`q6.csv` |
| `eval/` | `wikidata_*.csv`, `metrics.csv`, `metrics_after.csv`, `error_analysis.md` |
| `predictions.md`, `reflection.md`, `screenshots/` | predictions, reflection, Fuseki screenshots |

## How to run

Use Python 3.10 or newer, or the `py` Docker service (`docker compose run --rm py python <script>`).
Install once:

```
pip install spacy rdflib pyshacl requests
python -m spacy download en_core_web_sm
```

Run from the repository root, in this order:

| Step | Command | Output |
|---|---|---|
| 1. Fetch Wikipedia text | `python src/fetch_wikipedia.py` | `data/raw/*.txt` |
| 2. Extract triples | `python src/extract.py` | `out/triples.csv`, `out/merge_report.txt` |
| 3. Build the RDF graph | `python src/build_kg.py` | `out/kg.ttl` |
| 4. Validate with SHACL | `python src/validate_shacl.py` | `shacl_report.txt` |
| 5. Load and query | `docker compose up -d fuseki`, open http://localhost:3030, upload `out/kg.ttl` to the dataset, run `queries/q1.rq`–`q6.rq` | `results/q1.csv`–`q6.csv` |
| 6. Get Wikidata values | `python src/fetch_wikidata.py` | `eval/wikidata_*.csv` |
| 7. Score | `python src/evaluate.py` (add `--tag after` for a second run) | `eval/metrics.csv` |

To test one document: `python src/extract.py --only private_document.txt --out /tmp/test.csv -v`.
To test a new paragraph, put it in its own folder and run
`python src/extract.py --raw <folder> --out /tmp/test.csv -v`.

**Which run each output comes from.** The graph (`out/kg.ttl`), the SHACL report and note, and the
query results come from the *first* extractor run, before the fixes listed below. `eval/metrics.csv`
and `eval/error_analysis.md` also describe that first run. `eval/metrics_after.csv` is the score after
the fixes, and the current `out/triples.csv` is the post-fix output.

## How the extractor works (`src/extract.py`)

The extractor uses spaCy (`en_core_web_sm`) for sentence splitting, named entities and the dependency
parse. No relation-extraction model and no language model produces triples: every triple comes from
the hand-written rules below. All five predicate rules use the dependency parse (the verb, its subject
and its prepositional or direct object), not only text patterns.

**R1 `bornIn`.** Finds the word "born", takes its subject, and follows the preposition "in" or "at" to
the place. Dates and numbers are skipped.

**R2 `educatedAt`.** Looks for the verbs study, graduate, attend, educate, enrol, matriculate and
enter. The school is the object of "at", "from" or "in", or the direct object of "attend" / "enter".
When the object comes from "in" or from "attend" / "enter", it must contain a school word (university,
college, institute, school, ...), so "attended the Solvay Conference" is rejected. Names are extended
through "of" / "for" ("College of Science"). **R2b** also reads degrees: "received his PhD from X".

**R3 `receivedAward`.** Looks for receive, win, earn, award, share and accept with a direct object that
contains an award word (prize, medal, award, cross, honour, fellowship). The name is extended through
"in" / "of" ("Kestrel Prize in Physics").

**R4 `worksAt`.** The verb "join" with a direct object; "work / teach / lecture" with "at / for / in";
and "move / relocate / transfer" with "to". The object must look like an organisation (an institution
word, or an ORG label from spaCy). Moves are ignored when the sentence is about studying or the target
is a school. **R4b** reads job titles: "professor / director / chair ... at X".

**R5 `doctoralAdvisor`.** "X's doctoral advisor was Y" (and "Y was X's doctoral advisor"),
"supervised ... PhD", and "completed his PhD under Y".

**Pronouns.** "he / she / his / her" are replaced by a person. The candidates are the people in the
same sentence, then the previous sentence (subjects first), then the document's main person. A candidate
is skipped if its known gender disagrees with the pronoun; gender comes from a small first-name list
and is learned from earlier pronouns. This is how "He later moved to Riverbend Institute of Physics"
is attached to Junaid Hashmi and not to Hira Cheema.

**Negation.** If the verb is negated (never, not, n't, ...), the statement is stored as suppressed and is
not written to `triples.csv`. "She never studied at Ashdown College of Science" therefore gives no triple.

**Same entity, one name.** A person registry maps titles and surnames to the full name ("Dr. Cheema" →
"Hira Cheema"). The merged mentions are counted, printed and saved in `out/merge_report.txt`. On the
private document there are **2 merges**. On the whole collection the first run made 969 merged mentions
(144 alias forms); after the fixes, 983 (152 forms).

**Provenance.** Every row of `out/triples.csv` has the columns `subject, predicate, object, source_doc,
sentence`, so each triple names its document and its sentence.

## Fixes after the first run

1. **Attend objects (E4):** "attended X" counts as education only if X has a school word (removes the Solvay Conference triples).
2. **Move / transfer verbs (E4):** not `worksAt` when the sentence is about study or the target is a school (removes Luitpold Gymnasium and Princeton University).
3. **Alias split (E3):** "Ernest Orlando Lawrence" and "Ernest Lawrence" are now one person.
4. **Nested names (E1):** "Institute for Advanced Study" no longer also produces "Advanced Study".

## Scores against Wikidata

Precision and recall over the five Wikipedia people (the private document has no Wikidata entry). Values
match when their lower-cased text is equal.

| Predicate | Precision before → after | Recall before → after |
|---|---|---|
| bornIn | 0.750 → 0.800 | 0.600 → 0.800 |
| educatedAt | 0.333 → 0.429 | 0.143 → 0.143 |
| receivedAward | 0.588 → 0.588 | 0.135 → 0.135 |
| worksAt | 0.190 → 0.222 | 0.143 → 0.143 |
| doctoralAdvisor | 0.000 → 0.000 | 0.000 → 0.000 |
| **All** | **0.392 → 0.447** | **0.147 → 0.154** |

Details are in `eval/metrics.csv`, `eval/metrics_after.csv` and `eval/error_analysis.md`.

## Graph, ontology and queries

- `src/build_kg.py` turns the triples into `out/kg.ttl`. Each name becomes `kg:<Name_With_Underscores>`
  with an `rdfs:label`, and each predicate is a `kg:` property. Types come from the role in a triple:
  subject → Person, `bornIn` object → Place, `educatedAt` / `worksAt` object → Organization,
  `receivedAward` object → Award, `doctoralAdvisor` object → Person.
- `ontology.ttl`: classes Person, Place, Organization and Award; the five properties with domain and
  range; `owl:disjointWith` between the classes; `bornIn` is functional.
- `shapes.ttl`: SHACL shapes (at most one birthplace, the right type for each relation, nothing is two
  classes at once, name checks for Organization and Award as warnings).
- `shacl_report.txt` and `shacl_note.md`: 0 violations and 11 warnings, each explained in the note, plus
  the difference between an OWL reasoner and SHACL.
- `queries/q1.rq`–`q6.rq` with `queries/answers.md`: birthplaces with OPTIONAL, triples per predicate,
  shared birthplaces, people with two birthplaces, people without `educatedAt`, and doctoral ancestors
  with a `+` property path. Q3 and Q4 return no rows, and the reasons are in `queries/answers.md`.

## Known issues

- Wikipedia gives advisors in the infobox, which the plain-text download does not contain, so
  `doctoralAdvisor` finds only the private document's advisor.
- Many Wikidata awards and employers never appear in the article text, so recall is low (about 0.15).
- Scoring uses exact text matching, so a correct triple with a differently worded name (for example
  "Nobel Prize" and "Nobel Prize in Physics") counts as a false positive.
- Some `worksAt` triples are still wrong, for example people and fields of study taken as employers.

## Sources

Course slides and the official documentation of spaCy, rdflib, pySHACL, Apache Jena Fuseki, Wikidata
and SPARQL. I developed this project with assistance from an AI assistant (Claude), as permitted by my
instructor.