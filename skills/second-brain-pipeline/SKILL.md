---
name: second-brain-pipeline
description: >
  Runs the second-brain research pipeline end to end, stages 1 through 5:
  problem intake, arXiv paper discovery, a checkpoint pause for researcher
  review, paper vault-build (structured summaries), and Obsidian vault
  materialization. Use this whenever a researcher wants to go from a raw
  problem description all the way to a populated, linked Obsidian vault in
  one flow, rather than invoking research-problem-intake,
  second-brain-paper-downloader, paper-summarizer, and obsidian-vault
  separately. Does not implement PubMed/Semantic Scholar/GitHub discovery,
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

0. **Resolve the template path.** A repo-root-relative path like
   `templates/paper-page-template.md` only resolves when this skill happens
   to be running from a checkout of this repo — it does not resolve once
   the plugin is installed and invoked from an unrelated project. Resolve
   the absolute path once, before dispatching any paper, in this order:
   1. `${CLAUDE_PLUGIN_ROOT}/templates/paper-page-template.md`, if that
      variable is set.
   2. `./templates/paper-page-template.md` relative to the current working
      directory — the local-dev case (`claude --plugin-dir .` run from
      inside a checkout of this repo).
   3. `~/.claude/plugins/marketplaces/*/templates/paper-page-template.md`,
      keeping only a match whose sibling `.claude-plugin/plugin.json` names
      `second-brain-researcher` (an unrelated installed plugin could also
      ship a `templates/` folder) — the real installed-plugin case.

   If none of these resolve to an existing file, stop and report the gap
   plainly rather than guessing a path or dispatching `paper-summarizer`
   without a valid format file.

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

2. **Vault.** `Glob` `<paper_vault_path>/summaries/*.md` for the records
   just written. Dispatch the `obsidian-vault` skill with: the confirmed
   profile path, that paper collection, and an explicit vault path —
   the parent directory of `paper_vault_path` (i.e. strip the trailing
   `paper_vault/<id>/` and replace with `obsidian_vault/`), so it is never
   left to guess a default.

## Report back

State the profile id, how many papers were found/summarized/vaulted, and
the final vault path. If anything failed at any stage (a summarizer call
errored, a paper had no matches to the profile's terms, etc.), name it
plainly rather than reporting a clean run. Close by reminding the
researcher which stages of the original pipeline spec this run does not
cover (code/repo discovery and vault-build, cross-linking, experiment
plan) so they don't assume those happened silently.
