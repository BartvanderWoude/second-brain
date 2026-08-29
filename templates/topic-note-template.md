---
id: <keyword-slug>
created: <yyyy-mm-dd>
status: draft
type: topic
keyword: <keyword-slug>
related_problem: <id of the problem-profile note this topic was built for>
paper_count: <number of papers carrying this keyword>
papers: []
---

One note per subtopic, built from the papers whose `keywords` include this
note's `keyword`. `id` and `keyword` are the same kebab-case slug that appears
in the papers — that exact string is what links the two. `papers` lists the
paper-note ids this synthesis drew on, in the same order as the `## Papers`
section.

## Summary

What this subtopic is, and what the collected papers establish about it.
A few sentences — this is a map, not a review article.

## Across the papers

Where the papers agree, where they disagree or use incompatible setups, and
what's conspicuously missing. This is the section that has to earn the note's
existence: synthesize across the papers rather than recapping them one by one,
since each paper already has its own note.

## Relevance to the problem

How this subtopic bears on the linked problem — its `observed_failure_mode`,
`current_approach`, or `data_modality`. If it genuinely doesn't bear on the
problem, say so plainly rather than manufacturing a connection.

## Papers

Wikilinks to the paper notes this topic draws on, as
`[[<problem-id>/papers/<paper-id>|<paper title>]]` — a full path from the
Obsidian vault root, whose top level holds problem folders. Use each paper's
own `id` frontmatter field rather than its filename: the same ids listed in
`papers` above, in the same order.
