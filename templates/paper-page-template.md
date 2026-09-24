---
id: <paper filename stem, e.g. 2023_fung_john>
created: <yyyy-mm-dd>
status: draft
type: paper
source: arxiv | pubmed | pmc | europepmc | semantic_scholar
title:
authors: []
year:
venue:
url:
doi:
pmid:
code_link:
pdf_local_path:
code_local_path:
paywalled: false
full_text: full | abstract-only
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
related_basis: {}
---

`id` is the saved paper's filename stem (`2023_fung_john.md` → `2023_fung_john`), per `templates/paper-identity-spec.md` — never a slug coined from the title. The same string names the vault note and appears in every topic, repo and related-paper link to it. The identity fields — `id`, `source`, `title`, `authors`, `year`, `venue`, `url`, `doi`, `pmid`, `paywalled`, `full_text` — are copied from the saved paper file's header, which carries the source's own metadata; the body text only fills what the header leaves blank.

`pdf_local_path` is the path of the saved paper file when its `full_text` is `full`, and blank when the record is abstract-only. `code_local_path` points inside the linked problem's `code_vault_path` (from the problem-profile note) — clone there, not somewhere ad hoc, so the vaults stay organized per problem. Leave it blank until a repo is cloned.

`keywords` are the subtopics *this paper* actually covers, as lowercase kebab-case slugs (e.g. `contrastive-pretraining`). Where the paper covers a concept the linked problem profile already names in its `keywords_of_interest`, reuse that slug **verbatim** — that exact-string reuse is what lets a topic note find its papers. Keywords beyond the profile's list are expected and wanted: they describe the paper itself, not its relation to this problem, so a later project searching a different topic can still pick this paper up. Distinct from `matched_terms`, which records which of the profile's *search queries* surfaced it. Populated even when no problem profile is linked.

`related_notes` and `related_basis` are written by the pipeline's linker script (`scripts/link_papers.py`), not by the summarizer. Leave both empty (`[]` and `{}`). `related_basis` maps each linked paper's id to why it is linked: `direct-citation`, `"shared-references (N)"`, or `"similar-content (cosine)"`. A researcher may add ids to `related_notes` by hand; the script never removes those.

Write `keywords` in **block style** — one `  - slug` per line, as shown — never flow style (`keywords: [a, b, c]`). The pipeline inverts this field across every paper to build the keyword index that drives topic notes, so one canonical form matters. An empty list is written as `keywords: []`.

## Problem addressed

What problem/task does this paper actually tackle, in its own terms.

## Method

Short description of the method — enough to judge fit, not a full re-explanation.

## Key technical details

The paper's central equation(s) or objective, copied verbatim from its text as
LaTeX (`$$…$$`) with symbols defined, plus the title of the section each comes
from, so a later reader can jump straight to it. At most two or three items.
If the paper states no formulation (purely empirical or clinical work), write
one line saying so. Never reconstruct an equation from background knowledge.

## Result

Headline result(s), with the metric and comparison point.

## Synthesis

**Why relevant** — one or two sentences on why this surfaced for the linked problem, tying back to `matched_terms`. For a topic profile (`profile_type: topic`), name which of the profile's `review_questions` this paper informs, and how, citing each as `Q1`, `Q2`, … by its position in that list.

**What would need to change to apply it** — the concrete gap between this paper's setup and the linked problem (different modality, different scale, different reference standard, etc.). For a topic profile there is no setup to apply it to: say instead what this paper leaves open on the review questions it informs — the part of the question it does not settle.

**Skeptical note** — one honest reservation: an assumption that might not hold, a result that might not replicate, a mismatch worth double-checking before relying on this.

## Code notes

Only if a repo was cloned/tested — structure, entry point, whether it ran. Leave blank if code wasn't run yet.
