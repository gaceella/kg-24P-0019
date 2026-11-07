# SHACL note

## What the report found
Validating `out/kg.ttl` against `shapes.ttl` gave 0 violations and 11 warnings, all from one
check: an Organization's name should contain a word like "university" or "institute". The hard
checks (at most one birthplace, correct types, nothing in two classes at once) all passed.

## Real errors in my data (6)
- **Berlin:** stands for the University of Berlin, but my extractor kept only the city name (E1).
- **Hertz:** a person (Gustav Hertz), not an employer; my rule took the word after "joined" (E4).
- **Solvay_Conference:** an event, not a school; my rule treats "attended" as studying (E4).
- **Advanced_Study:** a shortened copy of "Institute for Advanced Study" (E1).
- **Experimental_Physics:** a field, not an employer; taken from "Professor of Experimental Physics" (E4).
- **Polytekniske_Læreanstalt_for_Arthur_von_Hippel:** the position was for von Hippel, not Franck,
  and "for Arthur von Hippel" was attached to the institution's name (E4 and E1).

## Shape too strict (3)
- **Harvard, MIT, Swiss_Patent_Office:** real employers whose names contain no word from my
  list (MIT is an abbreviation, and "Office" is not in the list).

## Mixed cases (2)
- **National_Association_for_Advancement_of_Colored_People:** a real organisation (the shape is
  too strict), but Einstein joined as a member and campaigner, not an employee, so worksAt is doubtful (E4).
- **Telegraph_Battalion:** a real military unit (the shape is too strict), but Franck was called up
  for military service, so worksAt is doubtful (E4).

## OWL reasoner versus SHACL
A reasoner can **infer new facts**: bornIn has range Place, so the place someone was born in is
concluded to be a Place even if nobody wrote that down. SHACL adds no facts; it only looks at
what is in the data.

SHACL can **check the data as written**: my shape allows at most one birthplace, so a person
with two birthplaces is reported as an error. A reasoner would not report this. Because OWL
assumes an open world and bornIn is functional, it would conclude that the two places are the
same thing, unless they were declared different. It does not call the data wrong.