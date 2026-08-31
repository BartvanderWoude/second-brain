---
name: second-brain-pipeline
description: >
  Runs the second-brain research pipeline end to end, stages 1 through 5:
  problem intake, parallel paper discovery across arXiv and PubMed/PMC, a
  checkpoint pause for researcher review, paper vault-build (structured
  summaries plus per-subtopic topic notes), and Obsidian vault materialization. Use this whenever a researcher
  wants to go from a raw problem description all the way to a populated,
  linked Obsidian vault in one flow, rather than invoking
  research-problem-intake, second-brain-paper-downloader,
  second-brain-biomed-downloader, paper-summarizer, topic-summarizer, and
  obsidian-vault-writer separately. Does not implement GitHub code discovery,
  the Semantic Scholar cross-field pass, code/repo vault-build, embedding
  cross-linking, or an experiment plan — those stages of the pipeline spec are
  not built yet.
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

## Stage 3: discovery

Dispatch all three discovery agents **in parallel**, each with the confirmed
profile's file path and nothing else. Each reads `paper_vault_path` itself
and save into it directly — do not pass or compute that path separately, and do
not pre-create the directory (the agents handle that).

- `second-brain-paper-downloader` — the arXiv leg.
- `second-brain-biomed-downloader` — the PubMed/PMC/Europe PMC leg.
- `second-brain-crossfield-searcher` — the cross-field methodology pass, over
  paper bodies via Asta. **Dispatch it unconditionally**; do not pre-check for a
  key yourself. The agent's own first step is a one-line key check that returns
  in seconds, and centralizing that check in the agent is what keeps this skill
  from having to know about anyone's credentials.

**The legs are independent — one failing never discards another's results.** In
particular, the cross-field pass is *additive*: if it reports that `ASTA_API_KEY`
is unset, that is a skipped enhancement, not a failed run. Say so in the stage-4
report, in one line, and carry on with the arXiv and PubMed results. Never
present a run as failed because the optional leg was skipped, and never re-run
discovery to "fix" a missing key.

### Merge before the checkpoint

The legs run blind to each other, so the same paper can arrive twice — a
preprint from arXiv and the published version from PubMed, or a cross-field hit
that is also an arXiv paper. Resolve that here,
before the researcher reviews anything:

1. `Glob` `<paper_vault_path>/*.md` for everything the legs saved.
2. Apply the key ladder in `templates/paper-identity-spec.md` — DOI, then
   source-native id, then normalized title. A normalized-title match with
   different DOIs is the preprint/published pair, not a collision.
3. Keep **one** file per paper, preferring the copy with usable full text, then
   the published version. Delete the redundant file rather than leaving both:
   two files for one paper double-count it in every topic note downstream.

Report what was merged. A silent merge looks like a paper went missing.

### Then the code leg — after the paper legs, still before the checkpoint

Dispatch `second-brain-code-finder` with the confirmed profile path, **once the
three paper legs have returned and the merge above is done**. It is not a fourth
parallel leg, and the reason is a real dependency rather than caution: its
highest-precision source is the repos named *inside the saved papers*, so it
needs those files on disk. Started in parallel it would find an empty vault and
silently degrade to topic search alone — the weakest half of what it does.

It still runs before the checkpoint, so repos and papers are approved together
in one review.

Note what does *not* exist yet at this point: `summaries/` is written at stage 5,
so the `code_link` field is unavailable on a first run and the agent works from
the full texts. That is the richer source anyway. On a re-run where summaries
already exist, it uses both.

The agent reads GitHub through the API only — it never clones, downloads, or
executes anything, and `code_vault_path` is still empty when it finishes. That
is what makes it safe to run *before* the checkpoint at all. If it reports that
`gh` is missing or unauthenticated, that is a skipped enhancement exactly like a
missing Asta key: report it in one line and carry on.


## Stage 4: checkpoint — stop and wait

After every discovery leg has reported and the merge above is done, relay a
combined summary (what was saved per leg, which legs ran and which were
skipped, what was merged as duplicates, what was skipped, dropped, or saved
abstract-only because it is paywalled, and which repositories were found) to the
researcher and **stop here**.

If the biomedical leg returned a **needs-manual-download** list — papers that
resolved neither open-access nor via the Sci-Hub rung — present it verbatim,
with title, DOI and PMID per paper. This is the one point in the run where the
researcher can drop those files into `paper_vault_path` by hand; once
vault-build starts, an absent full text silently becomes an abstract-only note.
Do not fold that list into the general "skipped" tally, and do not proceed past
it without an explicit decision.

Report the repositories as their own section, not folded into the paper counts:
how many came from the papers versus from topic search, and — named individually
— any with **no license**. That last one is the finding most likely to change
what the researcher does with a repo, and the checkpoint is where it is still
cheap to act on. State that nothing was cloned and `code_vault_path` is empty,
so its emptiness reads as intended rather than as a step that failed.

Ask explicitly
whether to proceed to vault-build with what was found, add the missing papers
manually first, or make other changes (remove a saved paper file, re-run
discovery with adjusted terms, etc.) — this is the pipeline's checkpoint before anything downstream
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

3. **Similarity edges.** Dispatch `similarity-linker` once, passing three
   paths: the summaries directory (`<paper_vault_path>/summaries/`), the
   `paper_vault_path`, and the confirmed profile. It adds paper-to-paper
   `related_notes` edges built from the citation graph, so papers link directly
   rather than only through shared-keyword topic notes.

   Run it **after** step 1, since it reads the summaries, and **before** step 4,
   since the vault writer renders the edges it produces. It is a single
   dispatch, not a fan-out — it needs to see every paper at once to find shared
   references between them.

   This step is **not** the spec's stage 6. Citation-based linking is a
   different mechanism from embedding similarity: it is factual and
   interpretable, but it cannot connect two papers that solve the same problem
   in different literatures with no shared bibliography. Relay the agent's
   report as it stands and do not upgrade its language.

   If it reports a missing `ASTA_API_KEY`, that is a partial result, not a
   failure: arXiv papers still get edges via the keyless citation graph, and
   only non-arXiv papers go unlinked. Carry on to step 4.

   **On a re-run, tell it which summaries were regenerated.** Paper ids are a
   title slug plus the date the summary was written, so regenerating a summary
   on a later day changes its id and silently breaks every edge pointing at it.
   If step 1 regenerated anything, say so in the dispatch so the linker
   recomputes those edges rather than leaving dead links behind.

4. **Vault.** Dispatch the `obsidian-vault-writer` agent with: the confirmed
   profile path, the paper collection from step 1, the topic collection
   (`Glob` `<paper_vault_path>/topics/*.md`), the repo collection (`Glob`
   `<paper_vault_path>/repos/*.md`, empty if the code leg was skipped), and an
   explicit vault path —
   the parent directory of `paper_vault_path` (i.e. strip the trailing
   `paper_vault/<id>/` and replace with `obsidian_vault/`), so it is never
   left to guess a default. All five inputs are required by the agent — it
   derives nothing and guesses nothing, so pass all five explicitly.

   The agent writes markdown files and nothing else. It does not need the
   Obsidian application installed, and vault-build never blocks on it. On a
   re-run it merges rather than overwriting — it regenerates only the link,
   citation and related sections it owns and preserves anything the researcher
   added to a note — so tell them that their annotations survive, and that
   hand-edits made *inside* a generated section are the one exception. If the
   agent reports it couldn't proceed (a missing field, an unusable vault path),
   fix the named input and dispatch it again — never write the vault notes
   yourself instead.

## Report back

State the profile id, how many papers were found/summarized/vaulted, how many
topic notes and repo notes were written, and the final vault path. Name any topic note that
came back with zero matching papers — that's a gap in the literature or in the
search terms, and it's the kind of thing that's easy to miss in a folder
listing. If anything failed at any stage (a summarizer call errored, a paper
had no matches to the profile's terms, etc.), name it plainly rather than
reporting a clean run.

Report the paper-to-paper edges separately from the topic notes: how many
`related_notes` edges were written, the split between direct citations and
bibliographic couplings, and how many papers ended with none.

Close by reminding the researcher which stages of the original pipeline spec
this run does not cover, so they don't assume those happened silently: repos
were catalogued but **never cloned, run, or tested** — there is no code
vault-build and no Docker sandbox — and there is no experiment plan.

**Be precise about cross-linking**, because it is now the easiest thing in this
pipeline to overstate. Papers are linked to each other two ways — through
shared-keyword topic notes, and through citation-graph edges in
`related_notes`. Neither is the spec's stage 6, which specifies
**embedding-similarity** linking, and that remains unimplemented. The
distinction is not pedantic: citation edges cannot connect two papers that solve
the same problem in different literatures with no shared bibliography, and that
cross-field case is the entire motivation for this project. Report what ran, not
what the spec asked for.

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
