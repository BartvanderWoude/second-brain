---
id: sarcopenia-ct-embedding-20260825
created: 2026-08-25
status: draft
type: paper
source: arxiv
title: Fast Sarcopenia Segmentation via Lightweight 3D CT Embeddings
authors: [Jane Q. Researcher, Alex T. Collaborator]
year: 2025
venue: MICCAI 2025 Workshop on Body Composition Imaging
url: https://arxiv.org/abs/2501.12345
doi: 10.1234/miccai.2025.00042
code_link: https://github.com/example-lab/sarcopenia-embed
paywalled: false
related_problem: ""
matched_terms:
  close_field: []
  generalized: []
domain: medical imaging / radiology (sarcopenia / body composition assessment)
data_modality: single-slice abdominal CT (L3 vertebral level)
task: skeletal muscle cross-sectional area segmentation for sarcopenia screening
method: contrastive-pretrained lightweight 3D convolutional encoder + compact segmentation head
result: Dice 0.91 vs. 0.92 for a 5x larger baseline, 8x faster on CPU (0.4s vs 3.2s/slice), n=412 single-site test set
related_notes: []
---

## Problem addressed

Sarcopenia (age-related loss of skeletal muscle mass) is typically assessed via
manual or semi-automated segmentation of the L3 vertebral CT slice. Existing
deep-learning approaches for this task rely on large 3D encoders that are
impractical to deploy in low-resource clinical settings. The paper targets a
lightweight, CPU-deployable alternative for skeletal muscle segmentation aimed
at sarcopenia screening in resource-constrained settings.

## Method

A compact 3D encoder is trained on L3-level abdominal CT slices with a
contrastive pretraining objective, then paired with a lightweight segmentation
head fine-tuned on annotated masks. The encoder has roughly 1/5th the
parameters of comparable 3D U-Net baselines, enabling CPU-only inference.

## Result

On a held-out test set of 412 scans from a single-site retrospective cohort,
the method achieves a Dice score of 0.91 for skeletal muscle segmentation,
matching a 5x larger baseline model (Dice 0.92) while running 8x faster on
CPU (0.4s vs. 3.2s per slice).

## Synthesis

**Why relevant** — *(No linked problem profile provided — general assessment
only.)* This is of general interest for any application needing fast,
low-resource skeletal muscle segmentation from abdominal CT, since it
achieves near-parity accuracy with a much larger model at a fraction of the
compute cost.

**What would need to change to apply it** — *(No linked problem profile
provided — general assessment only.)* Based on the paper's own scope, applying
this elsewhere would need to account for: validation limited to a single-site,
single-scanner cohort; no evaluation on pathological or severely atrophied
muscle presentations; and no demonstrated generalization to multi-site or
multi-scanner data.

**Skeptical note** — The reported Dice parity with the larger baseline rests
on a single-site, relatively homogeneous cohort (412 scans); it's unclear
whether the lightweight encoder's accuracy holds up on more heterogeneous,
multi-scanner data or on atrophied/pathological muscle, where segmentation
boundaries are less distinct and the authors explicitly did not evaluate.

## Code notes

