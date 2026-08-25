# Obsidian vault deferred decisions

These items are intentionally outside version 1.

## Intake and identity

- Final file and `id` naming convention.
- Exact transport and syntax of a multi-paper collection.
- Whether malformed records block the whole import or only the affected paper.
- Duplicate identity rules: DOI, source identifier, canonical URL, or normalized title and year.

## Lifecycle

- Problem status values after `draft` and `confirmed`.
- Merge rules that preserve manual edits when an existing note is updated.
- Whether missing `related_projects` targets are rejected or reported.

## Graph expansion

- Paper-to-paper links based on citations, shared methods, task and modality fields, or semantic similarity.
- Automatic-link thresholds versus reviewable suggestions.
- Embedding model, indexed text, storage, and re-indexing policy.
- Whether shared problem membership is enough to imply paper similarity.
- Cross-project behavior when `cross_project_linking: true`.
- Whether graph edges should be typed and explain why two notes are related.

## Other pipeline ownership

- Discovery, ranking, paywall handling, repository cloning, code execution, and experiment planning remain separate agents.
- MCP or Obsidian UI control should be added only when file-level Markdown access no longer covers a concrete workflow.
