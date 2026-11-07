# Error analysis

All items below come from the **baseline** run (before my fixes). The sorted lists are in
`eval/false_positives.csv` and `eval/false_negatives.csv`. Positions are the ones on my
assignment sheet: false positives 8, 11, 17, 20 and false negatives 12, 14, 19, 20.

## False positives

### FP position 8: (Ernest Lawrence, educatedAt, Solvay Conference)
Sentence: "At Cockcroft's invitation, Lawrence attended the 1933 Solvay Conference in Belgium."
Error code: **E4** (wrong relation)
Why: The Solvay Conference is an event, not a school. My education rule treats the verb
"attend" plus an object as studying, whatever the object is.
Fix: Count "attended X" as education only if X contains a school word such as university,
college or school. **Applied as fix 1.** It removed this triple and the same mistake for Einstein.

### FP position 11: (Ernest Lawrence, receivedAward, National Research Council fellowship)
Sentence: "He was elected a member of Sigma Xi, and, on Swann's recommendation, received a
National Research Council fellowship."
Error code: **E6** (source gap)
Why: The sentence really says Lawrence received the fellowship, so my triple is probably
correct. Wikidata does not list it as an award, so the scorer counts it as a false positive.
Fix: No code change. The extractor is right here. A better reference source, or a manual
check against another biography, would show it as a true positive.

### FP position 17: (James Chadwick, receivedAward, Nobel Prize)
Sentence: "He ran into withering skepticism from the Cavendish Laboratory's James Chadwick, the
physicist who had discovered the neutron in 1932, for which he was awarded the Nobel Prize in 1935."
Error code: **E1** (wrong span)
Why: Chadwick did win the Nobel Prize in Physics, so the fact is right. The sentence only says
"Nobel Prize", while Wikidata says "Nobel Prize in Physics", and my scorer matches text exactly,
so it counts as a mismatch.
Fix: Make the scorer accept a match when one name starts with the other, or use the award
context to complete the name. **Not applied.** It would change how matching works, not the extractor.

### FP position 20: (James Franck, educatedAt, Berlin)
Sentence: "At Berlin, Franck attended lectures by Max Planck and Emil Warburg."
Error code: **E1** (wrong span)
Why: Here "Berlin" stands for the University of Berlin, but the extractor kept only the city
name, so it does not match Wikidata's name for the university.
Fix: Require a school word in the object for the "at" pattern too, or expand a bare city after
"At" to "University of <city>". **Not applied.**

## False negatives

### FN positions 12, 14, 19 and 20: four Einstein awards
Items:
- (Albert Einstein, receivedAward, Gold Medal of the Royal Astronomical Society)
- (Albert Einstein, receivedAward, Honorary Fellow of the Royal Society Te Apārangi)
- (Albert Einstein, receivedAward, New Jersey Hall of Fame)
- (Albert Einstein, receivedAward, Pour le Mérite for Sciences and Arts order)

Sentence: none. I searched `data/raw/Albert_Einstein.txt` with grep and none of these awards
appears in the text.
Error code: **E7** (other)
Why: Wikidata lists these awards, but the Wikipedia article text never mentions them, so there
was no sentence for any text-based extractor to read. The missing facts are a gap between the
text and Wikidata, not a bug in my rules.
Fix: No code fix is possible. A longer source (for example the awards table of the article, or
another document) would be needed. This is why `receivedAward` recall is only 0.135.

## Before and after the fixes

I made four fixes in `src/extract.py`:
1. **Attend / enter objects (E4):** "attended X" counts as education only if X has a school word.
2. **Move / transfer verbs (E4):** "moved/transferred to X" is not `worksAt` when the sentence
   is about study (PhD, dissertation) or X is a school.
3. **Alias split (E3):** "Ernest Orlando Lawrence" and "Ernest Lawrence" are one person.
4. **Nested names (E1):** "Institute for Advanced Study" no longer also gives "Advanced Study".

| Predicate | Precision before | Precision after | Recall before | Recall after |
|---|---|---|---|---|
| bornIn | 0.750 | 0.800 | 0.600 | 0.800 |
| educatedAt | 0.333 | 0.429 | 0.143 | 0.143 |
| receivedAward | 0.588 | 0.588 | 0.135 | 0.135 |
| worksAt | 0.190 | 0.222 | 0.143 | 0.143 |
| doctoralAdvisor | 0.000 | 0.000 | 0.000 | 0.000 |
| **All** | **0.392** | **0.447** | **0.147** | **0.154** |

Overall false positives fell from 31 to 26 and true positives rose from 20 to 21.
The Solvay Conference fix removed two `educatedAt` false positives, the move/transfer fix
removed `Luitpold Gymnasium` and `Princeton University` from `worksAt`, the nested-name fix
removed `Advanced Study`, and the alias fix attached Lawrence's birthplace to the right person,
which raised `bornIn` recall from 0.60 to 0.80. (The four fixes together account for the
change; I did not score each fix on its own.)

## What the scores cannot show
- **doctoralAdvisor (0 found, 8 in Wikidata):** most advisors appear only in the Wikipedia
  infobox, which the plain-text download leaves out. One advisor sentence was in my data
  (Weinberg completed his dissertation "under the supervision of Sam Treiman"), but my rule
  for "under" did not capture it, because the name sits inside "the supervision of ...", and
  my rule expects a person directly after "under".
- **Wikidata is not perfect:** some of my false positives are correct facts that Wikidata
  lacks or words differently (E6), for example the Research Council fellowship above.
- Wikidata had values for all five people, so no person had to be left out of the scores.