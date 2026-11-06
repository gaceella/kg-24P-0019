# SHACL note

## What the report found
I validated my graph (out/kg.ttl) against shapes.ttl. The report has 0 violations
and 11 warnings. All 11 warnings come from one check: an Organization's name
should contain a word like "university" or "institute". The hard checks (at most one
birthplace, correct types for each relation, nothing being two classes at once) all passed.

## Real errors in my data
Six of the warnings show real mistakes made by my extractor:

- **Berlin:** In the sentence "At Berlin, Franck attended lectures...", Berlin stands for the
  University of Berlin, but my extractor kept only the city name, so the span is too short (E1).
- **Hertz:** Hertz is a person (Gustav Hertz), not an employer. The sentence says Franck joined
  Hertz and other colleagues at the Kaiser Wilhelm Institute, but my rule took the word after
  "joined" as the employer (E4).
- **Solvay_Conference:** The Solvay Conference is an event, not a school. My rule treats
  "attended" as studying, so it created a wrong educatedAt triple (E4).
- **Advanced_Study:** The sentence says Einstein took up a position at the "Institute for
  Advanced Study". My extractor produced the correct full name and also a shortened copy,
  "Advanced Study", so the shortened one has a span that is too short (E1).
- **Experimental_Physics:** In "he became Professor of Experimental Physics and Director of the
  Second Institute for Experimental Physics", "Experimental Physics" is a field of study, not an
  employer. My job-title rule picked up the field as if it were a workplace (E4).
- **Polytekniske_Læreanstalt_for_Arthur_von_Hippel:** The sentence says Franck found a position
  at the Polytekniske Læreanstalt in Copenhagen *for* Arthur von Hippel, his son-in-law. The
  position was for von Hippel, not for Franck, and my extractor also attached "for Arthur von
  Hippel" to the institution's name. So both the person and the name span are wrong (E4 and E1).

## Shape too strict
Three warnings are my shape being too strict:

- **Harvard:** It is a real organisation, but its name has no word from my list such as
  "university", "institute" or "school".
- **MIT:** MIT is a real university, but its name is an abbreviation, so none of my keywords match.
- **Swiss_Patent_Office:** Einstein really worked there, so it is a real employer, but "Office"
  is not in my keyword list.

## Mixed cases
Two warnings are partly the shape's fault and partly the data's fault:

- **National_Association_for_Advancement_of_Colored_People:** It is a real organisation, so the
  name check was too strict. But the sentence says Einstein joined it and campaigned for civil
  rights, so he was a member, not an employee, and the worksAt triple is doubtful (E4). My
  extractor also dropped the word "the" from the name.
- **Telegraph_Battalion:** It is a real military unit, so the name check was too strict. But
  the sentence says Franck was called up and joined it, which is military service rather than
  ordinary employment, so worksAt is doubtful (E4). My extractor also dropped "1st" from the name.

## What a reasoner can do that SHACL cannot
A reasoner can work out new facts from the ontology. In my ontology, bornIn has range Place.
So if the graph says someone was born in X, a reasoner concludes that X is a Place, even if
nobody wrote that down. SHACL does not add facts like this. It only looks at what is there.

## What SHACL can do that a reasoner cannot
SHACL checks the data exactly as it is written and reports problems. My shape says a person has
at most one birthplace, so if a person had two different birthplaces, SHACL would report an
error. A reasoner would not, because OWL assumes the world is open: since bornIn is functional,
it would just conclude that the two places are the same thing. It does not call the data wrong.