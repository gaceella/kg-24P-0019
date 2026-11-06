# Predictions 

## Expected triples per predicate (all 6 documents)
- bornIn: 6
- educatedAt: 21
- receivedAward: 10
- worksAt: 12
- doctoralAdvisor: 7

## Predicate with the lowest precision
Predicate: worksAt
Why: sentences like "moved to Berlin" show place  not an employer  so  rules that I defined  may extract a city as a workplace and produce wrong triples. 

## Difficulty in my private document I expect to fail on
Difficulty: “Dr. Cheema” must become Hira Cheema.
Why: these two may cause confusion because at first start from female and then Dr.Cheema is male and second name of hira not first name so that's why it cause an issue.