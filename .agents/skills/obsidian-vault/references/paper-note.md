# Paper note contract

Materialize one Markdown note per paper record using this structure. Preserve empty optional values rather than inventing facts.

```markdown
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
related_problem: <problem-profile id>
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

## Problem addressed

## Method

## Result

## Synthesis

**Why relevant** —

**What would need to change to apply it** —

**Skeptical note** —

## Code notes
```

For the current graph version, keep `related_notes` unchanged. Add only the problem wikilink required by the main skill.

