---
id: fixture-vault-20260924
created: 2026-09-24
status: confirmed
profile_type: problem
domain: clinical prediction
data_modality: tabular EHR, single centre
cohort_description: 400 patients, 12% events
task: time-to-event prediction of recurrence
reference_standard: recurrence confirmed at follow-up visit
current_approach: Cox model on 8 predictors
observed_failure_mode: poor calibration in the high-risk decile
close_field_terms:
  - recurrence prediction
generalized_methodology_terms:
  - survival model calibration
keywords_of_interest:
  - survival-analysis
  - calibration
cross_project_linking: false
paper_vault_path: /tmp/fixture/paper_vault/fixture-vault-20260924/
---

# Fixture problem

A small problem profile for the vault-build fixture.

## Papers

- [[papers/2021_smith_jones|Calibration of Clinical Risk Scores]]
- [[papers/2022_wu_chen|Time-to-Event Learning / A Review of (Deep) Methods]]
- [[papers/2023_lee_park|Deep Survival Models for Recurrence]]

## Topics

- [[topics/calibration]]
- [[topics/survival-analysis]]

## Repos

- [[repos/acme-survkit]]

## My notes

Researcher's own notes on the problem.
