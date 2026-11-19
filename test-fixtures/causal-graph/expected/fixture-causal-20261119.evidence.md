# Causal graph evidence: fixture-causal-20261119

- Target: Fixture outcome
- Setting: adults undergoing elective fixture surgery at a fixture centre; outcome within 30 days
- Assembled: 2026-11-19
- Papers: 4 with a claims file, 13 kept claims; 1 excluded
- Strict graph: `fixture-causal-20261119.dag.yaml`, edges graded probable or better: 6 nodes, 5 edges
- Full graph: `fixture-causal-20261119.full.dag.yaml`, every supported edge: 7 nodes, 7 edges

Grades: established (3) for an RCT, a Mendelian randomization study, or a meta-analysis of those and cohorts; probable (2) for an adjusted cohort; suggested (1) for a case-control, cross-sectional or unadjusted cohort study; speculative (0) for the rest. A claim from outside the setting counts one grade lower; an edge counts one grade lower when contrary or no-effect claims reach its best grade.

## Nodes

### Fixture outcome (target)

- In: strict, full
- Aliases: FO, postoperative fixture outcome
- Type: categorical; levels: no, yes
- Shares: [0.915, 0.085] from yes: median of 0.09 (2020_ashford_bell), 0.08 (2022_ellery_finch); no: the complement
- Description: The fixture outcome within 30 days of elective fixture surgery.

### BMI

- In: strict, full
- Aliases: body mass index
- Type: continuous; unit: kg/m²
- Description: Body mass index before surgery.

### Diabetes

- In: strict, full
- Aliases: diabetes mellitus, DM
- Type: categorical; levels: no, yes
- Shares: [0.82, 0.18] from yes: 0.18 (2020_ashford_bell); no: the complement
  - not used: yes 0.25 (2023_garner_hale, other setting)
- Description: A diagnosis of diabetes mellitus before surgery.

### Fixture prophylaxis

- In: strict, full
- Aliases: none
- Type: categorical; levels: no, yes
- Description: Fixture prophylaxis given around surgery.

### Operative duration

- In: full
- Aliases: none
- Type: continuous; unit: minutes
- Description: The duration of the operation.

### Physical activity

- In: strict, full
- Aliases: leisure-time physical activity
- Type: continuous; unit: MET-hours per week
- Description: Habitual physical activity.
- Measurement: One paper recorded leisure-time physical activity in hours per week instead of MET-hours.

### Smoking

- In: strict, full
- Aliases: smoking status
- Type: categorical; levels: never, former, current
- Shares: [0.48, 0.3, 0.22] from never: 0.48 (2020_ashford_bell); former: 0.3 (2020_ashford_bell); current: 0.22 (2020_ashford_bell)
- Description: Smoking status before surgery.

## Edges

### BMI → Fixture outcome

- In: strict and full
- Grade: probable (2): best claim 2020_ashford_bell (cohort, adjusted, same setting)
- Conflict: none
- Sign: positive, from 1 claim at grade 2
- Strength: none: per-unit estimate only
- Evidence: PMID:99000101
- Note: probable; 1 cohort; 1 paper; no conflict; no strength (per-unit estimate only)
- Claims:
  - 2020_ashford_bell (PMID:99000101; cohort, adjusted, same setting; grade 2; supports): body mass index increases fixture outcome [yes]; OR 1.05 (95% CI 1.02 to 1.08), per unit; adjusted. "Each 1 kg/m² increase in body mass index raised the odds of the fixture outcome (adjusted OR 1.05 per kg/m², 95% CI 1.02–1.08)" (Results)

### Diabetes → Fixture outcome

- In: strict and full
- Grade: probable (2): best claim 2020_ashford_bell (cohort, adjusted, same setting)
- Conflict: none; weaker contrary claims: 2019_carver_dunn (grade 1, decreases)
- Sign: positive, from 1 claim at grade 2
- Strength: medium: d 0.41 from 1 OR (2020_ashford_bell OR 2.1: d 0.41)
- Evidence: PMID:99000101, PMID:99000104
- Note: probable; 2 cohort; 2 papers, 1 outside the setting; no conflict (weaker contrary evidence from 1 paper); strength from 1 OR (d 0.41)
- Claims:
  - 2020_ashford_bell (PMID:99000101; cohort, adjusted, same setting; grade 2; supports): diabetes [yes vs no] increases fixture outcome [yes]; OR 2.1 (95% CI 1.4 to 3.2), per category; adjusted. "diabetes was independently associated with the fixture outcome (adjusted OR 2.1, 95% CI 1.4–3.2)" (Results)
  - 2019_carver_dunn (PMID:99000102; case-control, same setting; grade 1; contrary): diabetes mellitus [diabetic vs non-diabetic] decreases FO [yes]; OR 0.7 (95% CI 0.5 to 0.98), per category; adjusted. "Diabetes mellitus was less common among cases than controls (adjusted OR 0.7, 95% CI 0.5–0.98)" (Results)
  - 2023_garner_hale (PMID:99000104; cohort, adjusted, other setting; grade 1; supports): DM [yes vs no] increases fixture outcome [yes]; OR 1.6 (95% CI 1.2 to 2.1), per category; adjusted. "DM was associated with the fixture outcome (adjusted OR 1.6, 95% CI 1.2–2.1)" (Results)

### Fixture prophylaxis → Fixture outcome

- In: strict and full
- Grade: established (3): best claim 2022_ellery_finch (rct, same setting)
- Conflict: none
- Sign: negative, from 1 claim at grade 3
- Strength: small: d 0.25 from 1 RR; RR read as an OR (2022_ellery_finch RR 0.63: d 0.25)
- Evidence: PMID:99000103
- Note: established; 1 rct; 1 paper; no conflict; strength from 1 RR (d 0.25; RR read as an OR)
- Claims:
  - 2022_ellery_finch (PMID:99000103; rct, same setting; grade 3; supports): fixture prophylaxis [prophylaxis vs placebo] decreases postoperative fixture outcome [yes]; RR 0.63 (95% CI 0.47 to 0.83), per category; unadjusted. "Fixture prophylaxis reduced the risk of the postoperative fixture outcome (RR 0.63, 95% CI 0.47–0.83)" (Abstract)

### Operative duration → Fixture outcome

- In: full only
- Grade: suggested (1): best claim 2023_garner_hale (cohort, adjusted, other setting)
- Conflict: none
- Sign: none: no claim gives a direction
- Strength: none: no estimate
- Evidence: PMID:99000104
- Note: suggested; 1 cohort; 1 paper, 1 outside the setting; no conflict; no strength (no estimate)
- Claims:
  - 2023_garner_hale (PMID:99000104; cohort, adjusted, other setting; grade 1; supports): operative duration affects (direction unclear) fixture outcome [yes]; adjusted. "Operative duration was a significant predictor of the fixture outcome (p = 0.01)" (Results)

### Physical activity → Fixture outcome

- In: full only
- Grade: speculative (0): best claims suggested (1), one lower on a conflict
- Conflict: 2023_garner_hale reports no effect (grade 1)
- Sign: negative, from 1 claim at grade 1
- Strength: none: per-unit estimate only
- Evidence: PMID:99000102
- Note: speculative; 1 case-control; 1 paper; conflict, one grade lower; no strength (per-unit estimate only)
- Claims:
  - 2019_carver_dunn (PMID:99000102; case-control, same setting; grade 1; supports): leisure-time physical activity decreases FO [yes]; OR 0.92 (95% CI 0.86 to 0.98), per unit; adjusted. "Each additional hour per week of leisure-time physical activity was associated with lower odds of FO (adjusted OR 0.92, 95% CI 0.86–0.98)" (Results)
  - 2023_garner_hale (PMID:99000104; cohort, adjusted, other setting; grade 1; no effect): physical activity has no effect on fixture outcome [yes]; OR 0.95 (95% CI 0.7 to 1.3); adjusted. "Physical activity was not associated with the fixture outcome (adjusted OR 0.95, 95% CI 0.70–1.30)" (Results)

### Smoking → Fixture outcome

- In: strict and full
- Grade: probable (2): best claim 2020_ashford_bell (cohort, adjusted, same setting)
- Conflict: none
- Sign: {never: negative, former: negative, current: positive}, per level of Smoking, from 2 claims at grade 2, against reference never (log scale): never 0, former 0.34, current 0.88; centred on their mean 0.4
- Strength: medium: median d 0.33 from 2 ORs (2020_ashford_bell OR 2.4: d 0.48, 2020_ashford_bell OR 1.4: d 0.19)
- Evidence: PMID:99000101
- Note: probable; 1 cohort; 1 paper; no conflict; strength from 2 ORs (median d 0.33)
- Claims:
  - 2020_ashford_bell (PMID:99000101; cohort, adjusted, same setting; grade 2; supports): smoking status [current smokers vs never smokers] increases fixture outcome [yes]; OR 2.4 (95% CI 1.5 to 3.8), per category; adjusted. "Compared with never smokers, current smokers had higher odds of the fixture outcome (adjusted OR 2.4, 95% CI 1.5–3.8)" (Results)
  - 2020_ashford_bell (PMID:99000101; cohort, adjusted, same setting; grade 2; supports): smoking status [former smokers vs never smokers] increases fixture outcome [yes]; OR 1.4 (95% CI 1.1 to 1.8), per category; adjusted. "Compared with never smokers, current smokers had higher odds of the fixture outcome ... Former smokers also had higher odds (adjusted OR 1.4, 95% CI 1.1–1.8)" (Results)

### Physical activity → BMI

- In: strict and full
- Grade: probable (2): best claim 2020_ashford_bell (cohort, adjusted, same setting)
- Conflict: none
- Sign: negative, from 1 claim at grade 2
- Strength: medium: d 0.34 from 1 standardized beta (2020_ashford_bell beta_std -0.34: d 0.34)
- Evidence: PMID:99000101
- Note: probable; 1 cohort; 1 paper; no conflict; strength from 1 standardized beta (d 0.34)
- Claims:
  - 2020_ashford_bell (PMID:99000101; cohort, adjusted, same setting; grade 2; supports): physical activity decreases body mass index; beta_std -0.34 (95% CI -0.42 to -0.26), per SD; adjusted. "A one-SD higher physical activity was associated with a lower body mass index (standardized beta −0.34, 95% CI −0.42 to −0.26)" (Results)

## Dropped

### Below the strict threshold

- Operative duration → Fixture outcome: suggested (1), below probable
- Physical activity → Fixture outcome: speculative (0), below probable
- BMI → Physical activity: suggested (1), below probable; also dropped from the full graph (cycle)

### Leading nowhere near the target

None.

### Cycles

- full graph: BMI → Physical activity dropped from the cycle BMI → Physical activity → BMI: the worst-supported edge (suggested (1), 1 supporting paper)

#### BMI → Physical activity

- In: neither graph (cycle)
- Grade: suggested (1): best claim 2023_garner_hale (cohort, adjusted, other setting)
- Conflict: none
- Sign: negative, from 1 claim at grade 1
- Strength: small: d 0.21 from 1 standardized beta (2023_garner_hale beta_std -0.21: d 0.21)
- Evidence: PMID:99000104
- Note: suggested; 1 cohort; 1 paper, 1 outside the setting; no conflict; strength from 1 standardized beta (d 0.21)
- Claims:
  - 2023_garner_hale (PMID:99000104; cohort, adjusted, other setting; grade 1; supports): BMI decreases physical activity; beta_std -0.21 (95% CI -0.27 to -0.15), per SD; adjusted. "a higher BMI predicted lower subsequent physical activity (standardized beta −0.21, 95% CI −0.27 to −0.15)" (Results)

## Not used

### Unmapped names

- comorbidities: 1 claim

### Claims of no effect on pairs without an edge

None.

### Quote-check rejections

- 2019_carver_dunn: 1 (1 claim: quote not found)

### Excluded papers

- 2018_keane_lowe: Fixture risk factors in a cross-sectional survey (PMID:99000105)

### Papers that draw a DAG of the target

- 2023_garner_hale: Causal pathways to the fixture outcome after outpatient fixture procedures: a registry cohort (PMID:99000104). If it is the source of the expert graph, add it to exclude_papers and assemble again.
