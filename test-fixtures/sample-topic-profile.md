---
id: ssl-pretraining-ct-review-20260924
created: 2026-09-24
status: confirmed
profile_type: topic
domain: medical imaging / computed tomography
review_purpose: Deciding whether self-supervised pretraining for CT is mature enough to adopt as a default backbone strategy in upcoming projects.
review_scope: Self-supervised pretraining (contrastive, masked-image modelling, self-distillation) of encoders on CT volumes or slices, evaluated on downstream CT tasks. Out of scope - supervised-only transfer from ImageNet, MRI/X-ray-only work, and vision-language pretraining.
review_questions:
  - Which self-supervised objectives have been applied to CT, and how do they compare on downstream tasks?
  - How much unlabeled CT is needed before pretraining beats supervised ImageNet transfer?
  - Do CT-pretrained encoders transfer across scanners, sites and anatomical regions?
seed_papers:
  - "Models Genesis (Zhou et al., 2019)"
date_window_years: 0
close_field_terms:
  - self-supervised pretraining CT
  - contrastive learning computed tomography
  - masked image modeling CT volumes
  - foundation model CT
generalized_methodology_terms: []
keywords_of_interest:
  - contrastive-pretraining
  - masked-image-modeling
  - self-distillation
  - data-scaling
  - domain-shift
  - abdominal-ct
  - chest-ct
cross_project_linking: false
related_projects: []
paper_vault_path:
code_vault_path:
---

A literature review of self-supervised pretraining for CT, with no specific dataset or failure behind it. The aim is to judge whether it is mature enough to adopt as the default way to get a CT backbone, which comes down to how the main objectives compare, how much unlabeled data they need, and whether they hold up across sites and body regions. The cross-field pass was declined at intake, and there is no date limit so that early work such as Models Genesis is in reach.
