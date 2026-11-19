# Causal fixture

Shared input for the causal-graph pieces: `scripts/causal_graph.py` (its suite
is `test-fixtures/causal-graph/`) and the T2 tests of
`causal-claim-extractor`, `causal-variable-harmonizer` and
`causal-pair-searcher`. Every file follows `templates/causal-claims-spec.md`
and `templates/research-problem-profile-format-spec.md`. Everything is
synthetic: the target, the setting, the papers, their ids and numbers. Tests
run on a copy and never change these files. The parent folder is `records/`
rather than `paper_vault/` because `.gitignore` excludes that name everywhere.

Checks that need no script (from the repo root):

```
C=test-fixtures/causal
for f in $C/records/fixture-causal-20261119/claims/*.json $C/variables.json; do
  python3 -m json.tool "$f" > /dev/null || echo "bad json: $f"; done
grep -F 'reported less leisure-time' $C/records/fixture-causal-20261119/*.md   # nothing: the planted quote is absent
```

## Files

- `fixture-causal-20261119.md`: a confirmed causal profile. Target
  `Fixture outcome`; setting: adults undergoing elective fixture surgery at a
  fixture centre, outcome within 30 days. `exclude_papers` holds one entry,
  a title with an upper-case DOI that matches `2018_keane_lowe` by DOI.
  `pair_search_k: 3` and `pair_search_max_papers: 10`, so `pairs` has a real
  cut; `upstream_search_k: 4` and `upstream_search_max_papers: 6`, so
  `upstream` has one too, and `setting_terms` with a multi-word term;
  `prediction_time` at the preoperative visit. It has no `paper_vault_path`; a test copy adds one pointing at its
  scratch copy of the records.
- `records/fixture-causal-20261119/`: five paper records with identity
  headers, and `claims/` with one hand-written claims file each.
- `variables.json`: the harmonized nodes for the records once
  `2018_keane_lowe` is excluded: seven nodes, the target among them with its
  synonyms `FO` and `postoperative fixture outcome`, and `comorbidities`
  unmapped. Every node but the target has `timing: baseline` and
  `exogenous: false`, so no timing rule changes the graphs; the target has
  neither (its own tags are not used).
- `names.txt`: what `causal_graph.py names` writes for the records after
  `exclude` and `check`, on pass 1 (no `variables.json` yet). The harmonizer's
  T2 input.

## What each record tests

- `2020_ashford_bell`: prospective cohort, adjusted, setting-matched
  (grade probable). An adjusted OR on a binary cause (diabetes); a
  three-level cause (`smoking status`: never, former, current) with one OR per
  level against `never smokers`, the `former` claim's quote joining two
  fragments with `...`; a per-unit OR on a continuous cause (body mass index,
  per kg/m²); a standardized beta between two causes (physical activity →
  body mass index). Prevalences of diabetes, of every smoking level (`never
  smoked` maps through `level_map`) and of the outcome. Its reference list
  sits under `## References`. Quotes span line breaks and carry `–`, `−` and
  `²`.
- `2019_carver_dunn`: matched case-control, setting-matched (suggested). On
  the same edge as the cohort, diabetes → outcome, it reports the opposite
  direction (OR 0.7), with levels `diabetic` / `non-diabetic` that map through
  `level_map`, and the target as `FO`. A per-unit OR of leisure-time physical
  activity on `FO`. A claim on `comorbidities`, a name too vague to be one
  variable. **The planted claim**: diabetes mellitus → leisure-time physical
  activity, whose quote is not in the paper; `check` must reject it.
- `2022_ellery_finch`: randomized trial, abstract-only (established): fixture
  prophylaxis lowers the outcome, an RR. The outcome's incidence in the
  placebo arm as a prevalence, quoted from the abstract.
- `2023_garner_hale`: registry cohort, adjusted, in a setting that does not
  match (outpatient procedures, 90 days), so one grade lower (suggested); it
  draws a DAG of the target (`presents_dag: true`). Diabetes as `DM` → outcome
  (increases, agreeing with the cohort); physical activity → outcome with
  direction `none`; BMI → physical activity, the reverse of the cohort's
  physical activity → body mass index, so the two form a cycle; operative
  duration → outcome with direction `unclear` and no estimate. A diabetes
  prevalence that must not become a share, since the setting does not match.
- `2018_keane_lowe`: cross-sectional, abstract-only, setting-matched; the
  paper `exclude_papers` names. Its claims (a strong diabetes OR, body mass
  index → diabetes) and its diabetes prevalence would change the edges,
  `pairs` and the diabetes shares if it were not excluded.

## What the rules make of it

With `2018_keane_lowe` excluded, the planted claim rejected and
`variables.json` as given, the rules of `CAUSAL_GRAPH_DESIGN.md` ("Behaviour
and algorithms") give:

| Edge | Claims (grade) | Edge grade | Sign | Strength | Graph |
|---|---|---|---|---|---|
| Diabetes → Fixture outcome | cohort 2, case-control opposite 1, other-setting cohort 1 | 2: the weaker contrary claim does not downgrade | positive | medium (OR 2.1, d 0.41) | strict |
| Smoking → Fixture outcome | cohort 2, two levels against `never` | 2 | {never: negative, former: negative, current: positive} | medium (median d 0.33) | strict |
| BMI → Fixture outcome | cohort 2, per unit | 2 | positive | none: per-unit only | strict |
| Fixture prophylaxis → Fixture outcome | trial 3 | 3 | negative | small (RR 0.63, d 0.25) | strict |
| Physical activity → BMI | cohort 2, beta −0.34 | 2 | negative | medium | strict |
| Physical activity → Fixture outcome | case-control 1; a `none` claim of grade 1 conflicts | 0 | negative | none: per-unit only | full |
| Operative duration → Fixture outcome | other-setting cohort 1, `unclear` | 1 | none | none | full |
| BMI → Physical activity | other-setting cohort 1 | 1 | negative | small | dropped from the full graph: the cycle with Physical activity → BMI, lowest grade |

- Strict graph: 6 nodes, 5 edges, 4 into the target, no cycle. Full graph:
  7 nodes, 7 edges, 6 into the target, one cycle drop.
- Shares: Fixture outcome `[0.915, 0.085]` (median of 9% and 8%); Diabetes
  `[0.82, 0.18]` (the other setting's 25% and the excluded 40% are not used);
  Smoking `[0.48, 0.3, 0.22]`.
- `comorbidities`: one unmapped claim. `presents_dag`: `2023_garner_hale`.
- `pairs` with k 3: support Diabetes 3, Physical activity 3, BMI 2. Pairs:
  Diabetes–Physical activity (support 6; the rejected claim would have linked
  them) and Diabetes–BMI (5; the excluded paper would have linked them);
  Physical activity–BMI is already linked.
