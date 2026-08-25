---
id: <slug>-<yyyymmdd>
created: <yyyy-mm-dd>
status: draft
type: paper
source: arxiv | pubmed | semantic_scholar
title:
authors: []
year:
venue:
url:
doi:
code_link:
pdf_local_path:
code_local_path:
paywalled: false
related_problem: <id of the problem-profile note this was discovered for — must have status: confirmed>
matched_terms:
  close_field: []
  generalized: []
domain:
data_modality:
task:
method:
result:
related_notes: []
---

`pdf_local_path` and `code_local_path` point inside the linked problem's `paper_vault_path`/`code_vault_path` (from the problem-profile note) — save downloads/clones there, not somewhere ad hoc, so the two vaults stay organized per problem. Leave either blank if that vault path wasn't available when this note was created.

## Problem addressed

What problem/task does this paper actually tackle, in its own terms.

## Method

Short description of the method — enough to judge fit, not a full re-explanation.

## Result

Headline result(s), with the metric and comparison point.

## Synthesis

**Why relevant** — one or two sentences on why this surfaced for the linked problem, tying back to `matched_terms`.

**What would need to change to apply it** — the concrete gap between this paper's setup and the linked problem (different modality, different scale, different reference standard, etc.).

**Skeptical note** — one honest reservation: an assumption that might not hold, a result that might not replicate, a mismatch worth double-checking before relying on this.

## Code notes

Only if a repo was cloned/tested — structure, entry point, whether it ran. Leave blank if code wasn't run yet.
