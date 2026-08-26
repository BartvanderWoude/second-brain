# arxiv-paper-downloader

Finds and downloads relevant arXiv papers for a research problem/domain
described in an input markdown file, saving them as markdown into that
project's `papers/` folder.

## What it does

Given a research-problem file, the skill:

1. Ensures the `arxiv` MCP server is configured (installing it
   project-locally on first use, then stopping so the session can be
   restarted to pick up the new tools).
2. Derives several distinct search queries covering the problem's
   sub-asks, and searches arXiv for each, biased toward the last 3 years
   (with a small allowance for landmark/foundational papers outside that
   window when the problem calls for them).
3. Screens candidates for relevance using their full abstracts, actively
   checking each one against the problem file's stated exclusions/out-of-
   scope sections, not just topical similarity.
4. Deduplicates and caps the selection at 20 papers, spreading the slate
   across the problem's distinct sub-asks rather than pure similarity
   ranking.
5. Skips papers already saved from a prior run (matched by normalized
   title), so re-runs are idempotent.
6. Downloads and saves each remaining paper's full extraction, verifying
   the saved file is a plausible size rather than truncated or empty.

## Input

The path to an `.md` file describing a research problem/domain, with:

- a required `path:` field in its YAML frontmatter — the target project
  folder papers are saved under (created if it doesn't exist yet)
- frontmatter body and prose describing the research problem, domain, and
  relevant keywords/subfields/methods, used to guide search — including
  any section that rules topics out of scope

If `path:` is absent, empty, or malformed, the skill stops and reports
that rather than guessing a location.

## Output

No summary, index, or report file is written — the saved paper markdown
files are the only output, saved to `<path>/papers/` and named
`YEAR_firstauthor_secondauthor.md` (or `YEAR_firstauthor.md` for a single
author), with a numeric suffix only on a genuine same-name collision
between different papers.

The skill's final reply (not a file) lists what was saved, what was
skipped as already present, what was dropped at the 20-paper cap, what
failed to download, and which picks (if any) were landmark papers pulled
from outside the normal date window.
