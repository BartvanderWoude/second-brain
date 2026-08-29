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
keywords:
  - <kebab-case-slug>
domain:
data_modality:
task:
method:
result:
related_notes: []
---

`pdf_local_path` and `code_local_path` point inside the linked problem's `paper_vault_path`/`code_vault_path` (from the problem-profile note) — save downloads/clones there, not somewhere ad hoc, so the two vaults stay organized per problem. Leave either blank if that vault path wasn't available when this note was created.

`keywords` are the subtopics *this paper* actually covers, as lowercase kebab-case slugs (e.g. `contrastive-pretraining`). Where the paper covers a concept the linked problem profile already names in its `keywords_of_interest`, reuse that slug **verbatim** — that exact-string reuse is what lets a topic note find its papers. Keywords beyond the profile's list are expected and wanted: they describe the paper itself, not its relation to this problem, so a later project searching a different topic can still pick this paper up. Distinct from `matched_terms`, which records which of the profile's *search queries* surfaced it. Populated even when no problem profile is linked.

Write `keywords` in **block style** — one `  - slug` per line, as shown — never flow style (`keywords: [a, b, c]`). The pipeline inverts this field across every paper to build the keyword index that drives topic notes, so one canonical form matters. An empty list is written as `keywords: []`.

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
