---
id: <owner>-<name>
created: <yyyy-mm-dd>
status: draft
type: repo
full_name: <owner/name>
url: https://github.com/<owner>/<name>
homepage:
license: <SPDX key, or "none" — see below>
stars: <number>
language:
last_pushed: <yyyy-mm-dd>
archived: false
provenance: <official-implementation | reimplementation | dependency-or-dataset | search-hit>
related_problem: <id of the problem-profile note this repo was discovered for>
related_papers: []
keywords:
  - <kebab-case-slug>
---

One note per repository. `id` is the `owner/name` pair with the slash replaced
by a hyphen, lowercased — that pair is the repo's identity, so a fork and its
upstream are different ids and the same repo found twice is one id.

`license` is written as the SPDX key GitHub reports (`mit`, `apache-2.0`,
`gpl-3.0`), or the literal string **`none`** when GitHub reports no license.
`none` is not a missing value — it is a finding, and the one most likely to
matter later: code with no license grants no reuse rights, however good it is.

`provenance` records *how this repo was found*, which is usually more
informative than its star count:

- `official-implementation` — linked from a paper in this vault. The
  authoritative code for that paper's results.
- `reimplementation` — a third-party implementation of a method from the
  literature. Often more usable than the original, and often subtly different.
- `dependency-or-dataset` — a library, dataset loader, or benchmark referenced
  by the papers rather than being their contribution.
- `search-hit` — surfaced by topic search with no paper linkage. Lowest
  confidence; the note should justify why it survived screening.

`related_papers` lists the paper-note ids that reference this repo, matching the
`## Papers` section. Empty for a pure `search-hit`.

`keywords` uses the same vocabulary as the paper notes — reuse the linked
problem's `keywords_of_interest` slugs verbatim where they apply, so a repo and
the papers about the same subtopic land on the same topic note.

## What it is

What the repository actually contains and what it is for, in the researcher's
terms rather than the README's marketing. One short paragraph. If it is the
implementation of a specific paper, say which.

## Structure

The shape of the codebase, from its file tree: where the model definition
lives, where training and evaluation live, where configs and data loaders live.
Describe the organization and what it implies — a single flat script directory
and a packaged module with tests are very different things to inherit. Do not
paste the file listing; the point is the reading of it.

## Entry points

The command a researcher would actually run, named concretely: the training
entry (`train.py`, `main.py`, a console script), how it is configured (CLI
flags, a YAML config, hardcoded constants), and any evaluation or inference
entry. If no runnable entry point exists — a library, or a code dump with no
driver — say that plainly, because it changes what the repo is good for.

## Reproducibility signals

What the tree says about whether this can actually be run: dependency
declaration (`requirements.txt`, `environment.yml`, `pyproject.toml`), whether
versions are pinned, a `Dockerfile`, tests, and whether pretrained weights are
shipped or linked. This is the section that predicts effort, so be concrete
about what is present and what is absent.

## Relevance to the problem

Why this repo bears on the linked problem — its `observed_failure_mode`,
`current_approach`, or `data_modality` — and, concretely, **what would have to
change to use it here**: different modality, different input dimensionality,
different supervision, different reference standard. Same bar as the paper
notes: if you cannot name the gap, the repo is not actually a candidate. For a
topic profile (`profile_type: topic`) there is no problem to fit it to: say
which `review_questions` the code bears on — typically as the reference
implementation of a method the review covers — and how complete it is as one.

## Caveats

Honest reservations, each one a fact rather than a worry: no license, archived,
last commit years old, no tests, a single squashed commit with no history, an
open issue reporting the results do not reproduce. Leave blank only if there
genuinely are none.

## Papers

Wikilinks to the paper notes that reference this repo, as
`[[<problem-id>/papers/<paper-id>|<paper title>]]` — a full path from the
Obsidian vault root. Use each paper's own `id` frontmatter field rather than its
filename: the same ids listed in `related_papers` above.
