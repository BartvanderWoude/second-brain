---
name: second-brain-pipeline
description: >
  Runs the second-brain research pipeline end to end, stages 1 through 5:
  problem intake, arXiv paper discovery, a checkpoint pause for researcher
  review, paper vault-build (structured summaries plus per-subtopic topic
  notes), and Obsidian vault materialization. Use this whenever a researcher
  wants to go from a raw problem description all the way to a populated,
  linked Obsidian vault in one flow, rather than invoking
  research-problem-intake, second-brain-paper-downloader, paper-summarizer,
  topic-summarizer, and obsidian-vault-writer separately. Does not implement PubMed/Semantic Scholar/GitHub discovery,
  code/repo vault-build, embedding cross-linking, or an experiment plan —
  those stages of the pipeline spec are not built yet.
---

# Second-brain pipeline

Act as the calling agent. This skill does no discovery or vault-writing
logic itself — it dispatches to four already-implemented pieces, in order,
and carries each stage's output forward as the next stage's input. Its only
job is getting the handoffs right and holding the checkpoint pause.

## Stage 1–2: problem intake

Delegate to the `research-problem-intake` skill (`skills/research-problem-intake/SKILL.md`)
and run its Q&A until it writes a `status: confirmed` problem-profile `.md`
file. If the researcher already has a confirmed profile file in hand (they
name/attach one, or one already exists in this session), read it directly
and skip re-running intake — but verify its `status:` field really is
`confirmed`, not `draft`, before moving on. If it's `draft`, hand it back to
`research-problem-intake` to finish rather than proceeding against an
unconfirmed profile.

Note its `id`, `paper_vault_path`, and `code_vault_path` fields — every
later stage needs these.

## Stage 3: paper discovery (arXiv)

Dispatch the `second-brain-paper-downloader` agent with the confirmed
profile's file path. It reads `paper_vault_path` itself and saves matched
papers there directly — do not pass or compute that path separately, and
do not pre-create the directory (the agent handles that).

This pipeline currently only wires up arXiv discovery. If the researcher
asks about PubMed, Semantic Scholar, or GitHub code discovery, tell them
plainly those sources aren't implemented yet rather than silently skipping
them.

## Stage 4: checkpoint — stop and wait

After the downloader reports back, relay its summary (what was saved,
skipped, or dropped) to the researcher and **stop here**. Ask explicitly
whether to proceed to vault-build with what was found, or make changes
first (remove a saved paper file, re-run discovery with adjusted terms,
etc.) — this is the pipeline's checkpoint before anything downstream
consumes the papers. Do not continue to stage 5 in the same turn; wait for
an explicit go-ahead in a follow-up message.

## Stage 5: vault build

Only after the researcher confirms:

0. **Resolve the template paths.** Two templates are needed this stage:
   `paper-page-template.md` (step 1) and `topic-note-template.md` (step 2).
   A repo-root-relative path like `templates/paper-page-template.md` only
   resolves when this skill happens to be running from a checkout of this
   repo — it does not resolve once the plugin is installed and invoked from
   an unrelated project. Resolve the `templates/` directory once, before
   dispatching anything, in this order:
   1. `${CLAUDE_PLUGIN_ROOT}/templates/`, if that variable is set.
   2. `./templates/` relative to the current working directory — the
      local-dev case (`claude --plugin-dir .` run from inside a checkout of
      this repo).
   3. `~/.claude/plugins/marketplaces/*/templates/`, keeping only a match
      whose sibling `.claude-plugin/plugin.json` names
      `second-brain-researcher` (an unrelated installed plugin could also
      ship a `templates/` folder) — the real installed-plugin case.

   Take both template paths from whichever directory resolves. If neither
   template exists there, stop and report the gap plainly rather than
   guessing a path or dispatching an agent without a valid format file.

1. **Papers.** `Glob` `<paper_vault_path>/*.md` (the saved papers
   themselves — not any `summaries/` subdirectory, which won't exist yet on
   a first run). For each one, dispatch `paper-summarizer`, passing three
   paths: the paper file, the template path resolved in step 0, and the
   confirmed problem-profile file (the new optional third input — this is
   what makes the resulting notes carry real `related_problem`/
   `matched_terms`/relevance synthesis instead of the generic
   no-profile fallback). These are independent per paper — dispatch them in
   parallel.

   On a re-run, skip papers that already have a `summaries/<name>_summary.md`
   counterpart unless the researcher asked to regenerate.

2. **Topics.** Build the keyword index **once**, here in the pipeline — the
   agents do not each re-derive it. `Glob` `<paper_vault_path>/summaries/*.md`
   and read the `keywords` block from each one (block style, one `  - slug`
   per line), inverting it into a map of keyword → the summaries carrying it.

   Then select which keywords get a topic note:
   - **every** `keywords_of_interest` entry from the confirmed profile, even
     one that matched zero papers — an empty topic note is a real signal that
     either the literature or the search terms have a gap, so don't drop it;
   - **plus** any other keyword appearing on **2 or more** papers. Keywords the
     summarizer coined that landed on a single paper are skipped: a one-paper
     topic note adds nothing over the paper note itself.

   Dispatch `topic-summarizer` once per selected keyword, passing six paths:
   the keyword slug, the matched summary paths (possibly none), the
   `paper_vault_path`, the confirmed profile, the topic-note template path
   resolved in step 0, and the output path
   `<paper_vault_path>/topics/<keyword>.md`. These are independent per
   keyword — dispatch them in parallel.

   On a re-run, skip keywords that already have a `topics/<keyword>.md` unless
   the researcher asked to regenerate. If new papers were saved since the last
   run, regenerate the topics they touch — a stale topic note that predates
   half its papers is worse than none.

3. **Vault.** Dispatch the `obsidian-vault-writer` agent with: the confirmed
   profile path, the paper collection from step 1, the topic collection
   (`Glob` `<paper_vault_path>/topics/*.md`), and an explicit vault path —
   the parent directory of `paper_vault_path` (i.e. strip the trailing
   `paper_vault/<id>/` and replace with `obsidian_vault/`), so it is never
   left to guess a default. All four inputs are required by the agent — it
   derives nothing and guesses nothing, so pass all four explicitly.

   The agent writes markdown files and nothing else. It does not need the
   Obsidian application installed, and vault-build never blocks on it. If the
   agent reports it couldn't proceed (a missing field, an unusable vault path),
   fix the named input and dispatch it again — never write the vault notes
   yourself instead.

## Report back

State the profile id, how many papers were found/summarized/vaulted, how many
topic notes were written, and the final vault path. Name any topic note that
came back with zero matching papers — that's a gap in the literature or in the
search terms, and it's the kind of thing that's easy to miss in a folder
listing. If anything failed at any stage (a summarizer call errored, a paper
had no matches to the profile's terms, etc.), name it plainly rather than
reporting a clean run.

Close by reminding the researcher which stages of the original pipeline spec
this run does not cover, so they don't assume those happened silently:
code/repo discovery and vault-build, and the experiment plan. Be precise about
cross-linking — papers are now linked to each other through shared-keyword
topic notes, but the spec's **embedding-similarity** cross-linking is still not
implemented, so don't report spec stage 6 as done.

## Finally: offer to open the vault

Not a pipeline-spec stage — the spec's stages 6 and 7 are cross-linking and the
experiment plan, neither of which is implemented. This is a convenience step
that runs once vault-build is already complete and reported, and nothing here
can turn a finished run into a failed one.

Ask the researcher whether they want to open the vault in Obsidian. If they
already asked for it to be opened earlier in this run, skip the question and go
straight to the launch attempt.

Only if they say yes, check whether Obsidian is actually present — a
platform-appropriate check (on Linux/WSL, an `obsidian` binary on `PATH` or a
Flatpak install; on Windows, the standard install locations). If it is, launch
it against the verified vault path and report any launch failure plainly
without touching the created files.

If Obsidian isn't installed, say so plainly — the vault path is already in the
report above, so they can open it themselves. **Do not offer or run an install
command** — no winget, no brew, no apt. Installing software on the researcher's
machine is out of scope for this pipeline.
