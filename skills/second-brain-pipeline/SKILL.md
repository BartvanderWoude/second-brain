---
name: second-brain-pipeline
description: >
  Runs the second-brain research pipeline end to end, stages 1 through 5:
  problem intake, parallel paper discovery across arXiv and PubMed/PMC, a
  checkpoint pause for researcher review, paper vault-build (structured
  summaries plus researcher-selected topic notes), and Obsidian vault materialization. Use this whenever a researcher
  wants to go from a raw problem description — or a topic they want a
  literature review of, with no specific problem or dataset — all the way to
  a populated, linked Obsidian vault in one flow, rather than invoking
  research-problem-intake, second-brain-paper-downloader,
  second-brain-biomed-downloader, paper-summarizer, topic-summarizer, and
  obsidian-vault-writer separately. Does not implement GitHub code discovery,
  the Semantic Scholar cross-field pass, code/repo vault-build, or an
  experiment plan — those stages of the pipeline spec are not built yet.
  Paper-to-paper linking runs as a script (`scripts/link_papers.py`), with
  content similarity from SPECTER2 title+abstract embeddings, not full text.
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

Also note its `profile_type`: `problem` (a concrete problem with data) or
`topic` (a literature review with no problem behind it); a missing field means
`problem`. This skill does not branch on it — every agent below reads the
profile and handles both types itself — but the reports at stage 4 and at the
end state it, and the final report has one topic-only line.

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
is unset, or that a topic profile has no methodology terms because the
researcher declined the pass, that is a skipped enhancement, not a failed run. Say so in the stage-4
report, in one line, and carry on with the arXiv and PubMed results. Never
present a run as failed because the optional leg was skipped, and never re-run
discovery to "fix" a missing key.

### Merge before the checkpoint

The legs run blind to each other, so the same paper can arrive twice — a
preprint from arXiv and the published version from PubMed, or a cross-field hit
that is also an arXiv paper. Resolve that here,
before the researcher reviews anything:

1. `Glob` `<paper_vault_path>/*.md` for everything the legs saved. Read only
   each file's **header** — `Read` with `limit: 40`, or `head -n 40` via Bash —
   which is where the title, DOI and source ids sit. Never read a full paper
   here: they run 20–140 KB each, and this step runs in the main conversation,
   where 40 full texts would dwarf the cost of every other stage's dispatch.
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
combined summary (the profile type, what was saved per leg, which legs ran and which were
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

   The directory that holds `templates/` is the plugin root. Note it: step 3
   runs `<plugin root>/scripts/link_papers.py` from it.

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

2. **Topics.** Topic notes are meant to be a small set of entry points into
   the vault, not one note per recurring keyword — so the researcher chooses
   which ones get written. Four substeps: index, propose, select, dispatch.

   **2a. Build the keyword index once**, here in the pipeline — the agents do
   not each re-derive it. Extract the `keywords` block from every
   `<paper_vault_path>/summaries/*.md` with a single `Grep` (or `grep -A` via
   Bash) rather than reading each summary in full — the field is block style,
   one `  - slug` per line, precisely so it can be grepped. Invert the result
   into a map of keyword → the summaries carrying it.

   **2b. Propose candidates.**
   - The profile's `keywords_of_interest` are the researcher's own topics,
     confirmed at intake. Every one that has no topic note yet is **always**
     written, even one that matched zero papers — an empty topic note is a
     real signal that either the literature or the search terms have a gap.
     They are not asked about; list them once, above the picker, as "already
     included".
   - The candidates offered are every other keyword on **2 or more** papers.
     This threshold now decides only what is *offered*, not what is written.
     A keyword on a single paper is not offered: a one-paper topic note adds
     nothing over the paper note itself.
   - **Suggest merges.** Working from the slug list alone (no summary reads),
     group slugs that name the same subtopic — `survival-analysis` /
     `time-to-event-prediction`, `scleral-buckling` /
     `scleral-buckling-surgery`. The canonical slug is the profile keyword
     when the group contains one, otherwise the slug on the most papers; the
     rest become its **aliases**. A merged topic's paper list is the union of
     its members' lists. Merge only true synonyms or variants — a narrower
     concept (`dynamic-survival-prediction` under `survival-analysis`) is a
     judgment call, so prefer offering it as its own candidate. A profile
     keyword may absorb synonyms too; show such merges in the "already
     included" line so the researcher can reject them.
   - **On a re-run**, nothing from a previous selection is remembered: every
     candidate is offered again, and none is skipped or pre-rejected because
     of an earlier choice. A topic that already has a
     `<paper_vault_path>/topics/<slug>.md` is offered too, marked
     "(note exists, +N new papers)" — N being the matched summaries whose `id`
     is not in that note's `papers` frontmatter. Profile keywords that
     already have a note move into the picker as well, under their own
     "Your topics" question, so a re-run never regenerates them all
     automatically.

   **2c. The researcher selects.** This is a real pause, like the stage 4
   checkpoint: dispatch nothing until the selection is answered, and never
   auto-select. Use `AskUserQuestion` with `multiSelect: true`. It allows at
   most 4 options per question and 4 questions per call, so:
   - group the candidates into themed questions of up to 4 options each
     ("Methods", "Clinical context", "Evaluation", …), ranked by paper count
     within a theme. The question's `header` is the theme; an option's
     `label` is the canonical slug with its aliases
     (`survival-analysis (+ time-to-event-prediction)`), and its
     `description` gives the paper count, one or two paper titles, and the
     "(note exists, +N new papers)" marker where it applies;
   - with more than 16 candidates, run a second call with the rest. Never
     more than two rounds: whatever is left after 32 is named in one line
     with "reply to add any";
   - tell the researcher, in the question text, that the free-text "Other"
     field can add a keyword that wasn't offered, undo a merge ("split
     survival-analysis"), or give a focus for deepening an existing note
     ("deepen model-calibration: more on recalibration methods").

   If `AskUserQuestion` isn't available (a non-interactive run), show the
   same list numbered in chat and wait for a reply naming the numbers.

   **2d. Dispatch** `topic-summarizer` once per selected topic — the
   researcher's picks plus the profile keywords that have no note yet —
   passing six paths: the canonical keyword slug, the matched summary paths
   (the union across aliases; possibly none), the `paper_vault_path`, the
   confirmed profile, the topic-note template path resolved in step 0, and
   the output path `<paper_vault_path>/topics/<keyword>.md`. Add the optional
   inputs where they apply:
   - **aliases** — the slugs merged into this topic;
   - **existing note** — for a topic that already has a note, which puts the
     agent in deepen mode: it builds on the note rather than starting over.
     Pass the Obsidian copy `<vault>/<problem-id>/topics/<keyword>.md` when it
     exists (that copy carries the researcher's edits; `<vault>` is the path
     derived in step 4), else `<paper_vault_path>/topics/<keyword>.md`;
   - **focus** — any deepening direction the researcher gave for this topic.

   These are independent per topic — dispatch them in parallel. Keep the
   list of slugs dispatched in this run: step 4 needs it as the rebuilt
   topics.

3. **Paper-to-paper links.** Run the linker script once with Bash — no agent
   dispatch; this step involves no model:

   ```
   python3 <plugin root>/scripts/link_papers.py \
     --summaries <paper_vault_path>/summaries/ \
     --state <paper_vault_path>/.linker/
   ```

   It fetches every paper's reference list and SPECTER2 embedding from
   Semantic Scholar in one batch request, then writes three kinds of link into
   each summary's `related_notes`, with the reason for each in
   `related_basis`:
   - **direct citation**: one vault paper cites the other;
   - **shared references**: the two share 2 or more references outside the
     vault;
   - **similar content**: their title+abstract embeddings are close (cosine
     ≥ 0.90), for pairs with no citation relation at all.

   Each paper gets at most 5 citation links and 3 content links. Every link is
   written on both papers.

   Run it **after** step 1, since it reads the summaries, and **before** step 4,
   since the vault writer renders the links. It needs every paper at once, so
   it is one run, not a fan-out.

   The script tracks which entries it wrote, in `.linker/owned.json`. That is
   what makes re-runs safe:
   - Entries a researcher added by hand are never touched.
   - A regenerated summary whose id changed has its old links removed and
     re-added under the new id.
   - A re-run with nothing new changes no files and fetches nothing.

   It prints a JSON report. Relay it as it stands and do not upgrade its
   language:
   - link counts by kind;
   - `zero_edge_papers`;
   - `not_in_s2` (no links possible);
   - `no_content_links_possible` (citation links only: Semantic Scholar has no
     embedding for them);
   - `embedding_coverage`.

   Name the papers in each of those lists. An empty link list must not read as
   "nothing related exists". If `embedding_coverage` is below ~70%, say so
   prominently: content linking then covers only part of the vault.

   **If it can't run, skip the step; it never blocks the vault.** That covers:
   - `python3` missing;
   - a non-zero exit with `{"error": ...}`, for example Semantic Scholar
     rate-limiting for the whole 10-minute retry window.

   Report it in one line, suggest setting `SEMANTIC_SCHOLAR_API_KEY` if the
   cause was rate limiting, and carry on to step 4 with whatever links the
   summaries already hold. Never write links by hand instead.

4. **Vault.** Dispatch the `obsidian-vault-writer` agent with: the confirmed
   profile path, the paper collection from step 1, the topic collection
   (`Glob` `<paper_vault_path>/topics/*.md`), the repo collection (`Glob`
   `<paper_vault_path>/repos/*.md`, empty if the code leg was skipped), and an
   explicit vault path —
   the parent directory of `paper_vault_path` (i.e. strip the trailing
   `paper_vault/<id>/` and replace with `obsidian_vault/`), so it is never
   left to guess a default. All five inputs are required by the agent — it
   derives nothing and guesses nothing, so pass all five explicitly.

   Also pass the **rebuilt topics**: the slugs dispatched in step 2d this run
   (empty if none). On a re-run the agent otherwise leaves a topic note's
   content sections exactly as they are in the vault, so a new or deepened
   note would never reach it.

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

State the profile id and type, how many papers were found/summarized/vaulted, how many
topic notes and repo notes were written, and the final vault path. For topics, say how
many were offered and how many selected, split into new and deepened notes, and which
merges were applied; name the unselected slugs in one line, so the researcher knows they
still exist as paper keywords and can be picked on a later run. Name any topic note that
came back with zero matching papers — that's a gap in the literature or in the
search terms, and it's the kind of thing that's easy to miss in a folder
listing. For a topic profile, do the same for `review_questions`: name any
question that no paper summary cites. Summaries cite review questions by
position as `Q1`, `Q2`, …, so the check is one `Grep` over `summaries/` for
`\bQ[0-9]+\b`, not a re-read. An
unanswered review question is the topic-review counterpart of an empty topic
note, and it is the finding the researcher most needs. If anything failed at any stage (a summarizer call errored, a paper
had no matches to the profile's terms, etc.), name it plainly rather than
reporting a clean run.

Report the paper-to-paper links separately from the topic notes:
- the split between direct citations, shared references and similar content;
- embedding coverage;
- which papers ended with no links, and why (not in Semantic Scholar, or
  genuinely unrelated to the rest of the vault).

Close by reminding the researcher which stages of the original pipeline spec
this run does not cover, so they don't assume those happened silently: repos
were catalogued but **never cloned, run, or tested** — there is no code
vault-build and no Docker sandbox — and there is no experiment plan.

**Be precise about cross-linking**, because it is the easiest thing in this
pipeline to overstate. Papers are linked three ways:
- through shared-keyword topic notes;
- through citation links (direct citations and shared references);
- through content links.

Citation links are facts: a researcher can check "A cites B" or "A and B share
5 references". Content links are estimates, and narrower than the spec's
stage 6 in two ways:
- they compare **title and abstract only**, not full text;
- they exist only for papers Semantic Scholar knows and has an embedding for.

They are what connects two papers that solve the same problem in different
literatures with no shared bibliography, which is the case this project exists
for. So report them, with their coverage, and never present a missing content
link as evidence that no such connection exists. Report what ran, not what
the spec asked for.

## Finally: offer to open the vault

Not a pipeline-spec stage — the spec's stage 6 (cross-linking) is implemented
only in the reduced form described above, and stage 7 (the experiment plan)
not at all. This is a convenience step
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
