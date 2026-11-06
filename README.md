# kg-24P-0019
# Knowledge graph assignment (AI3001, Assignment 1) – 24P-0019

Pipeline: text → triples → ontology and SHACL checks → RDF graph in Fuseki → SPARQL queries → scoring against Wikidata.

- Fuseki dataset: `kg-24p-0019`
- Namespace: `http://example.org/kg/24p-0019/`
- Texts: five Wikipedia articles (James Chadwick, Steven Weinberg, Albert Einstein, Ernest Lawrence, James Franck) and my private document, all in `data/raw/`.

## How to run

Local Python (3.10 or newer) or the `py` Docker service (`docker compose run --rm py python <script>`).
Install once: `pip install spacy rdflib pyshacl requests` and `python -m spacy download en_core_web_sm`.

Run from the repository root, in this order:

| Step | Command | Output |
|---|---|---|
| 1 Fetch Wikipedia text | `python src/fetch_wikipedia.py` | `data/raw/*.txt` |
| 2 Extract triples | `python src/extract.py` | `out/triples.csv`, `out/merge_report.txt` |
| 3 Build RDF graph | `python src/build_kg.py` | `out/kg.ttl` |
| 4 Validate with SHACL | `python src/validate_shacl.py` | `shacl_report.txt` |
| 5 Load and query | `docker compose up -d fuseki`, open http://localhost:3030, upload `out/kg.ttl`, run `queries/q1.rq`–`q6.rq` | `results/q1.csv`–`q6.csv` |
| 6 Wikidata values | `python src/fetch_wikidata.py` | `eval/wikidata_*.csv` |
| 7 Score | `python src/evaluate.py` (use `--tag after` for a second run) | `eval/metrics.csv` |

For a single document: `python src/extract.py --only private_document.txt --out /tmp/test.csv -v`.

**Important:** Steps 3 and 4 (graph, SHACL report, queries) were produced from the output of the
*first* extractor run, before the fixes described below. `eval/metrics.csv` and
`eval/error_analysis.md` describe that first run; `eval/metrics_after.csv` is the run after the fixes.
The current `out/triples.csv` is the post-fix output.

## How the extractor works (`src/extract.py`)

The extractor uses spaCy (`en_core_web_sm`) for sentence splitting, named entities and the
dependency parse. No relation-extraction model and no language model produces triples; every
triple comes from the hand-written rules below. All five predicate rules use the dependency parse
(the verb, its subject and its prepositional or direct object), not only text patterns.

**R1 `bornIn`:** finds the word "born", takes its subject, and follows the preposition "in" or "at"
to the place. Dates and numbers are skipped.

**R2 `educatedAt`:** looks for the verbs study, graduate, attend, educate, enrol, matriculate and
enter. The school is the object of "at", "from" or "in", or the direct object of "attend" / "enter".
When the object comes from "in" or from "attend", it must contain a school word (university,
college, institute, school ...), so "attended the Solvay Conference" is rejected. Names are
extended through "of" / "for" ("College of Science"). **R2b** also reads degrees: "received his PhD
from X".

**R3 `receivedAward`:** looks for receive, win, earn, award, share and accept with a direct object
that contains an award word (prize, medal, award, cross, honour, fellowship). The span is
extended through "in" / "of" ("Kestrel Prize in Physics").

**R4 `worksAt`:** the verb "join" with a direct object, "work / teach / lecture" with "at / for / in",
and "move / relocate / transfer" with "to". The object must look like an organisation (an
institution word or an ORG label from spaCy). Moves are ignored when the sentence is about studying
or the target is a school. **R4b** reads job titles: "professor / director / chair ... at X".

**R5 `doctoralAdvisor`:** "X's doctoral advisor was Y" (and "Y was X's doctoral advisor"),
"supervised ... PhD", and "completed his PhD under Y".

**Pronouns.** "he / she / his / her" are replaced by a person. The candidates are the people in
the same sentence, then the previous sentence (subjects first), then the document's main person.
A candidate is skipped if its known gender disagrees with the pronoun; gender comes from a small
first-name list and is learned from earlier pronouns. This is how "He later moved to Riverbend
Institute of Physics" is attached to Junaid Hashmi, not to Hira Cheema.

**Negation.** If the verb has a negation (never, not, n't ...), the statement is stored as
suppressed and is not written to `triples.csv`. The sentence "she never studied at Ashdown College of
Science" therefore gives no triple.

**Same entity, one name.** A person registry maps "Dr. Cheema" and other titles / surnames to the
full name (titles are stripped, a lone surname maps to the full name). The number of merged mentions
and the alias forms are printed and saved in `out/merge_report.txt`. On the private document there are
**2 merges** ("Dr. Cheema" → "Hira Cheema"). On the whole collection the first run made 969 merged
mentions (144 alias forms); after the fixes, 983 (152 forms).

**Provenance.** Every row of `out/triples.csv` has the columns `subject, predicate, object,
source_doc, sentence`, so each triple names its document and its sentence.

## Fixes after the first run (Step 5)

1. **Attend objects (E4):** "attended X" counts as education only if X has a school word (removes the Solvay Conference triples).
2. **Move / transfer verbs (E4):** not `worksAt` when the sentence is about study or the target is a school (removes Luitpold Gymnasium and Princeton).
3. **Alias split (E3):** "Ernest Orlando Lawrence" and "Ernest Lawrence" become one person.
4. **Nested names (E1):** "Institute for Advanced Study" no longer also gives "Advanced Study".

Results: overall precision 0.392 → 0.447, recall 0.147 → 0.154 (see `eval/metrics.csv`,
`eval/metrics_after.csv` and `eval/error_analysis.md`).

## Graph and rules

- `src/build_kg.py` turns the triples into `out/kg.ttl`. Each name becomes `kg:<Name_With_Underscores>`
  with an `rdfs:label`; each predicate is a `kg:` property. Types come from the role in a triple
  (subject → Person, bornIn object → Place, educatedAt / worksAt object → Organization,
  receivedAward object → Award, doctoralAdvisor object → Person).
- `ontology.ttl`: classes Person, Place, Organization, Award; the five properties with domain
  and range; `owl:disjointWith` between the classes; `bornIn` is functional.
- `shapes.ttl`: SHACL shapes (at most one birthplace, correct type for each relation, no entity of
  two classes, name checks for Organization and Award as warnings).
- `shacl_report.txt` and `shacl_note.md`: the pySHACL report (0 violations, 11 warnings) and my
  explanation of each warning, plus OWL versus SHACL.
- `queries/q1.rq`–`q6.rq`, `queries/answers.md`, `results/q1.csv`–`q6.csv`.

## Limits I know about

- Wikipedia's advisor information is in the infobox, which the plain-text download lacks, so
  `doctoralAdvisor` finds only the private document's advisor.
- Many Wikidata awards and employers never appear in the article text, so recall is low (about 0.15).
- Scoring uses exact text matching, so a correct triple with a differently worded name counts as a false positive.

## Sources and help

Course slides and the official documentation of spaCy, rdflib, pySHACL, Apache Jena Fuseki, Wikidata
and SPARQL. I developed this project with assistance from an AI assistant (Claude), as permitted by my
instructor. <!-- Edit or remove this sentence so it matches what your instructor agreed. -->