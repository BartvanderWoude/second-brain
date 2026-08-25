# Fast Sarcopenia Segmentation via Lightweight 3D CT Embeddings

**Authors:** Jane Q. Researcher, Alex T. Collaborator
**Year:** 2025
**Venue:** MICCAI 2025 Workshop on Body Composition Imaging
**arXiv:** https://arxiv.org/abs/2501.12345
**DOI:** 10.1234/miccai.2025.00042
**Code:** https://github.com/example-lab/sarcopenia-embed

## Abstract

We propose a lightweight 3D convolutional embedding model for segmenting
skeletal muscle cross-sectional area from single-slice abdominal CT, aimed
at sarcopenia screening in resource-constrained settings. Our approach
combines a contrastive pretraining objective with a compact segmentation
head, enabling accurate muscle delineation without the computational cost
of full 3D volumetric models.

## 1. Introduction

Sarcopenia — age-related loss of skeletal muscle mass — is commonly assessed
via manual or semi-automated segmentation of the L3 vertebral CT slice.
Existing deep learning approaches for this task rely on large 3D encoders
that are impractical to deploy in low-resource clinical settings. We address
this gap with a lightweight embedding-based approach.

## 2. Method

We train a compact 3D encoder on L3-level abdominal CT slices using a
contrastive pretraining objective, followed by a lightweight segmentation
head fine-tuned on annotated masks. The encoder has roughly 1/5th the
parameters of comparable 3D U-Net baselines, enabling CPU-only inference.

## 3. Results

On a held-out test set of 412 scans drawn from a single-site retrospective
cohort, our method achieves a Dice score of 0.91 for skeletal muscle
segmentation, matching a 5x larger baseline model (Dice 0.92) while running
8x faster on CPU (0.4s vs. 3.2s per slice).

## 4. Discussion

Limitations include validation on a single-site cohort with a relatively
homogeneous patient population, and no evaluation on pathological or
severely atrophied muscle presentations, where segmentation boundaries may
be less distinct. Generalization to multi-site or multi-scanner data remains
untested.
