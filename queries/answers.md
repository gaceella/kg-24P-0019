# Query answers

## Q3 – people who share a birthplace
Q3 returns no rows. Each birthplace in my graph belongs to only one person (see Q1),
so there are no pairs. This only means no pair was extracted, not that no two of these
people were really born in the same place.

## Q4 – people with two or more birthplaces
Q4 returns no rows. Every person has at most one birthplace in my graph, which matches the
SHACL result of zero violations for the "at most one birthplace" check.

## Q5 – people with no educatedAt triple
Q5 lists the people who have no educatedAt triple in my graph. This can show which people
my extractor found no education for. It cannot prove that these people never studied
anywhere: the extractor may have missed the sentence, or the text may not mention it. Under
the open-world idea, "not in the graph" does not mean "false".

## Q6 – doctoral ancestors
Q6 follows doctoralAdvisor any number of steps back. My data has only one advisor triple:
Hira Cheema's advisor is Junaid Hashmi. Junaid Hashmi has no advisor in the data, so the
chain stops after one step and Q6 returns only that one pair. The Wikipedia articles gave no
doctoralAdvisor triples, so there is no longer chain. This does not mean the people have no
advisors in real life, only that my graph contains none.