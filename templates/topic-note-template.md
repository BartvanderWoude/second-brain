---
id: <keyword-slug>
created: <yyyy-mm-dd>
status: draft
type: topic
keyword: <keyword-slug>
aliases: []
related_problem: <id of the problem-profile note this topic was built for>
paper_count: <number of papers carrying this keyword>
papers: []
---

One note per subtopic, built from the papers whose `keywords` include this
note's `keyword`. `id` and `keyword` are the same kebab-case slug that appears
in the papers — that exact string is what links the two. `papers` lists the
paper-note ids this synthesis drew on, in the same order as the `## Papers`
section. `aliases` lists other slugs merged into this topic because they name
the same subtopic; a paper carrying an alias belongs to this note too. Write it
block style, one `  - slug` per line, or `aliases: []` when there are none.
Obsidian reads `aliases` natively, so searching an old slug finds this note.

## Summary

What this subtopic is, and what the collected papers establish about it.
A few sentences — this is a map, not a review article.

## Across the papers

Where the papers agree, where they disagree or use incompatible setups, and
what's conspicuously missing. This is the section that has to earn the note's
existence: synthesize across the papers rather than recapping them one by one,
since each paper already has its own note.

## Core technical details

The load-bearing technical content, taken from the papers' own text: the key
equations, objectives or losses, update rules, and any assumption or
hyperparameter the result hinges on. Write equations in LaTeX as `$$…$$` blocks
and define their symbols. Attribute each item with a wikilink to the paper it
comes from. Where papers formulate the same thing differently, put the
formulations side by side and say what differs, since that comparison is the
synthesis. Every equation is copied from a paper, never reconstructed from
background knowledge. If the papers carry no such content (purely empirical or
clinical work), say so in one line.

## Relevance to the problem

How this subtopic bears on the linked problem — its `observed_failure_mode`,
`current_approach`, or `data_modality`. For a topic profile
(`profile_type: topic`), how it bears on the `review_questions` instead: which
ones it answers, how far, and what stays open. If it genuinely doesn't bear on
the problem or the questions, say so plainly rather than manufacturing a
connection.

## Papers

Wikilinks to the paper notes this topic draws on, as
`[[<problem-id>/papers/<paper-id>|<paper title>]]` — a full path from the
Obsidian vault root, whose top level holds problem folders. Use each paper's
own `id` frontmatter field rather than its filename: the same ids listed in
`papers` above, in the same order.
