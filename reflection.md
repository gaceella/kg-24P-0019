# Reflection

**Predictions versus results.** Before the first run I predicted 6 bornIn, 21 educatedAt,
10 receivedAward, 12 worksAt and 7 doctoralAdvisor triples. The run gave 8, 12, 26, 33 and 1.
I overestimated education and advisor triples and underestimated awards and employers.
Wikipedia states many awards and jobs in full sentences, but gives most advisors only in the
infobox, which the plain-text download does not contain. The one advisor sentence in Weinberg's
text ("under the supervision of Sam Treiman") was missed by my rules, so only one advisor triple
(from the private document) was found.

**Lowest precision.** I predicted worksAt would have the lowest precision, and I was right:
0.19 in the baseline. Verbs such as "joined" and "moved to" are used for clubs, military units,
schools and people, not only employers (for example Franck "joined Hertz", Einstein joined the
NAACP).

**Private document.** I expected the alias "Dr. Cheema" to be my hardest case, and I wrongly
thought the title might make it look like a different person. It was not a problem: "Dr." is
only a title and "Cheema" is her surname, so the names were merged. All seven expected triples
were found, "He" went to Junaid Hashmi, and the negated sentence about Ashdown College was
suppressed. The alias problem appeared instead in the Wikipedia text, where "Ernest Orlando
Lawrence" and "Ernest Lawrence" were two separate nodes, so Lawrence's birthplace was attached
to the second node. Fixing that raised bornIn recall from 0.60 to 0.80.

**Fixes.** Four small fixes raised overall precision from 0.39 to 0.45. Recall stayed near 0.15
because most Wikidata awards and employers never appear in the article text at all.

**Open-world idea.** The sentence "received a National Research Council fellowship" produced
the triple (Ernest Lawrence, receivedAward, National Research Council fellowship). Wikidata does
not list it, so the scorer counted it as a false positive. But the text says it, so it is
probably true. Not being in Wikidata does not make the triple false, only unconfirmed. The same
applies to my empty queries Q3 and Q4: no shared or double birthplaces in my graph does not mean
none exist in reality, only that my extractor found none.