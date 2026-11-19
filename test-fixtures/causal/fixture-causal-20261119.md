---
id: fixture-causal-20261119
created: 2026-11-19
status: confirmed
profile_type: topic
domain: fixture surgery
task: predict the fixture outcome within 30 days of elective fixture surgery
causal_target: Fixture outcome
causal_setting: adults undergoing elective fixture surgery at a fixture centre; outcome within 30 days
prediction_time: at the preoperative visit, before fixture surgery
exclude_papers:
  - "Fixture risk factors in a cross-sectional survey — 10.9999/FIXTURE.2018.005"
pair_search_k: 3
pair_search_max_papers: 10
upstream_search_k: 4
upstream_search_max_papers: 6
setting_terms:
  - fixture surgery
  - surgical
  - postoperative
review_scope: >-
  IN: studies reporting causes, risk factors or predictors of the fixture
  outcome after fixture surgery or in adjacent settings, with an effect
  estimate or an explicit causal claim; studies reporting effects among those
  factors. OUT: prediction-model papers that report only performance.
review_purpose: Build a literature-derived causal graph of the fixture outcome, to compare with an expert-built graph.
review_questions:
  - What causes the fixture outcome in adults undergoing elective fixture surgery at a fixture centre?
  - How do those causes affect each other?
  - How large are the effects, and how common are the causes in this setting?
core_questions: [1]
seed_papers: []
date_window_years: 10
recall_probes:
  - '("fixture outcome*"[tiab]) AND ("fixture surgery"[tiab] OR "fixture procedure*"[tiab]) AND ("risk factor*"[tiab] OR predictor*[tiab] OR "odds ratio"[tiab])'
close_field_terms:
  - fixture outcome fixture surgery risk factors
  - predictors of fixture outcome after fixture surgery
  - Mendelian randomization fixture outcome
  - fixture outcome meta-analysis risk factors
generalized_methodology_terms:
  - fixture outcome after outpatient fixture procedures
  - fixture outcome after any surgery risk factors
keywords_of_interest: []
---

Fixture causal profile for the causal-graph scripts and agents. Synthetic: the
target, the setting and every paper in `records/` are made up.
