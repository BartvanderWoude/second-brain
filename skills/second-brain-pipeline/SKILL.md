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
  second-brain-biomed-downloader, paper-summarizer and topic-summarizer
  separately. Does not implement code/repo vault-build (cloning, running) or
  an experiment plan — those stages of the pipeline spec are not built yet.
  The deterministic steps run as scripts: `scripts/stage_prep.py` (duplicate
  merge, fan-out planning, keyword index, topic digests),
  `scripts/link_papers.py` (paper-to-paper links, content similarity from
  SPECTER2 title+abstract embeddings, not full text),
  `scripts/fetch_fulltext.py` (full text), `scripts/build_vault.py` (the
  Obsidian vault) and `scripts/check_vault.py` (records and links).
---

# Second-brain pipeline

Act as the calling agent. This skill does no discovery or vault-writing
logic itself — it dispatches agents and runs scripts, in order, and carries
each stage's output forward as the next stage's input. Its only job is getting
the handoffs right and holding the checkpoint pause.

**Keep this conversation lean.** Every turn here re-reads the whole
conversation, and a 42-paper run takes over a hundred of them, so anything
pasted in here is paid for again on every later turn. Read the scripts' compact
reports, never paper files, summaries or topic notes. Give each agent only its
step's prompt template, filled in; its definition carries the instructions.
Dispatch every fan-out in **waves**:

- All `Agent` calls of a wave go in **one message**, each with
  `run_in_background: false`, so the wave comes back in one turn rather than
  one per agent.
- A wave holds at most the concurrent-subagent cap read before stage 3
  (`$CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`, 20 when unset): Claude Code
  refuses a call past it rather than queueing it. Start the next wave only
  once the previous one has returned.

Agents reply `OK <path>` or `FAIL <reason>` plus a few anomaly lines; carry
those to the report.

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

## Before stage 3: resolve the plugin root

The plugin's `templates/` and `scripts/` directories are needed from here on —
the fetcher at stage 3, the templates, linker and checker at stage 5. A
repo-root-relative path like `templates/paper-page-template.md` only resolves
when this skill happens to be running from a checkout of this repo — it does
not resolve once the plugin is installed and invoked from an unrelated project.
Resolve the plugin root once, now, in this order:

1. `${CLAUDE_PLUGIN_ROOT}`, if that variable is set.
2. The current working directory, if it has `templates/` and `scripts/` — the
   local-dev case (`claude --plugin-dir .` run from inside a checkout of this
   repo).
3. `~/.claude/plugins/marketplaces/*/`, keeping only a match whose
   `.claude-plugin/plugin.json` names `second-brain-researcher` (an unrelated
   installed plugin could also ship a `templates/` folder) — the real
   installed-plugin case.

In the same Bash call, read the wave size:
`echo ${CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS:-20}`.

Note `<plugin root>/scripts/fetch_fulltext.py` for stage 3. If no root
resolves, discovery still runs — dispatch the legs without the fetcher path;
they then save abstract-only records and say so — but say it in the stage-4
report, since it is the cause of every abstract-only paper that run.

## Stage 3: discovery

Dispatch all three discovery agents as **one wave**, each with the confirmed
profile's file path and the fetcher path
`<plugin root>/scripts/fetch_fulltext.py` — nothing else. Each reads
`paper_vault_path` itself and save into it directly — do not pass or compute that path separately, and do
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
that is also an arXiv paper. Resolve that here, before the researcher reviews
anything, with one Bash call — no header reads in this conversation:

```
python3 <plugin root>/scripts/stage_prep.py merge <paper_vault_path>
```

It applies the key ladder in `templates/paper-identity-spec.md` and keeps
**one** file per paper — the one that already has a summary (a re-run), else
the one with usable full text, else the published version — under its own
name, adding the other copies' sources and missing ids to its header. The
other copies move to `<paper_vault_path>/.merged/`, which no later stage
reads; left in place, they would double-count the paper in every topic note.

Its JSON report lists each merge (`kept`, `removed`, the matching key, what
was added to the header), `possible_duplicates` it did not merge (same title,
different ids — the researcher's call), and the stage-4 coverage figures. Report what was merged: a silent merge looks like a paper
went missing. Keep the report's coverage block for stage 4.

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

State **full-text coverage** as numbers, from the merge report rather than
from the legs' prose: `full_text` gives `full` versus `abstract-only`,
`by_source` splits them by leg, `extraction_warnings` names the records whose
extracted text is known to be damaged, and `no_header` any record a leg saved
without its identity header. Name `possible_duplicates` too, for the
researcher to decide. A vault whose clinical core is abstracts caps the quality of
everything downstream, and this is the last point where that is cheap to fix.

If the biomedical leg returned a **needs-manual-download** list — papers that
resolved neither open-access nor via the Sci-Hub rung — present it verbatim,
with title, DOI and PMID per paper. This is the one point in the run where the
researcher can supply those files by hand; once vault-build starts, an absent
full text silently becomes an abstract-only note. Do not fold that list into
the general "skipped" tally, and do not proceed past it without an explicit
decision.

Tell the researcher how to supply one: save the PDF as
`<paper_vault_path>/<id>.pdf`, next to the record `<id>.md` of the same name.
When they say they have, run for each such PDF (`--from-pdf` takes one record
at a time):

```
python3 <plugin root>/scripts/fetch_fulltext.py --source manual \
  --record <paper_vault_path>/<id>.md --from-pdf <paper_vault_path>/<id>.pdf
```

It validates the file, converts it and upgrades the record in place. Delete the
PDF once the report says `full_text: full` — the vault holds Markdown, not PDFs.
If the report says the file is not a PDF (a browser often saves a publisher's
HTML page under a `.pdf` name), tell the researcher that rather than deleting
anything.

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

0. **Take the template paths** from the plugin root resolved before stage 3.
   Two templates are needed this stage:
   `<plugin root>/templates/paper-page-template.md` (step 1) and
   `<plugin root>/templates/topic-note-template.md` (step 2). If
   the root did not resolve then, try the same three places again now. If
   either template does not exist, stop and report the gap plainly rather than
   guessing a path or dispatching an agent without a valid format file.

1. **Papers.** Plan the fan-out with one Bash call (add `--regenerate` only if
   the researcher asked to regenerate; without it, papers that already have a
   `summaries/<id>_summary.md` are skipped):

   ```
   python3 <plugin root>/scripts/stage_prep.py summaries <paper_vault_path>
   ```

   Its `dispatches` give each long full text a dispatch of its own, with
   `read_until` at the line before its references, and batch the rest up to 8
   per dispatch. Dispatch `paper-summarizer` once per entry, in waves, with
   this prompt:

   ```
   papers:
   - <paper_vault_path>/<id>.md (read_until: <N>)
   - <paper_vault_path>/<id>.md
   format: <plugin root>/templates/paper-page-template.md
   problem profile: <confirmed profile path>
   ```

   The problem profile is what makes each summary carry real
   `related_problem`/`matched_terms`/relevance synthesis instead of the
   generic no-profile fallback. Carry every `FAIL` line into the final report.

2. **Topics.** Topic notes are meant to be a small set of entry points into
   the vault, not one note per recurring keyword — so the researcher chooses
   which ones get written. Four substeps: index, propose, select, dispatch.

   **2a. Build the keyword index once**, here in the pipeline — the agents do
   not each re-derive it — with one Bash call:

   ```
   python3 <plugin root>/scripts/stage_prep.py keywords <paper_vault_path> \
     --profile <confirmed profile path>
   ```

   One line per slug: its paper count, two paper titles, and "(note exists,
   +N new)" when a topic note exists with N matched papers not yet in it.
   Profile keywords come first, then every keyword on 2 or more papers; the
   single-paper slugs follow on one line, as merge material only. Keep its
   last two lines, the profile keywords on no paper and the review questions
   no summary cites, for the final report.

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
     including the single-paper slugs, group slugs that name the same subtopic — `survival-analysis` /
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
     "(note exists, +N new papers)" as the index prints it. Profile keywords that
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

   **2d. Dispatch.** The selected topics are the researcher's picks plus the
   profile keywords that have no note yet. First write one digest per topic
   (every summary carrying the slug or an alias, in one file) with a single
   Bash call; `<slug>:<alias>,…` gives a merged topic its aliases:

   ```
   python3 <plugin root>/scripts/stage_prep.py digest <paper_vault_path> \
     --topic <slug> --topic <slug>:<alias>,<alias> ...
   ```

   The report gives each topic's paper count; a topic with 0 papers still
   gets its note. Then dispatch `topic-summarizer` once per selected topic, in
   waves, with this prompt:

   ```
   keyword: <slug>
   aliases: <alias>, <alias>
   digest: <paper_vault_path>/.digests/<slug>.md
   paper vault path: <paper_vault_path>
   problem profile: <confirmed profile path>
   format: <plugin root>/templates/topic-note-template.md
   output: <paper_vault_path>/topics/<slug>.md
   output exists: <true | false>
   existing note: <path>
   focus: <the researcher's direction>
   ```

   `aliases` only for a merged topic; `output exists` is true when the index
   marked the slug "(note exists …)". `existing note` only for a topic that
   already has a note, which puts the agent in deepen mode: it builds on the
   note rather than starting over. Pass the Obsidian copy
   `<vault>/topics/<slug>.md` when it exists (that copy carries the
   researcher's edits; `<vault>` is the problem's vault, derived in step 4),
   else `<paper_vault_path>/topics/<slug>.md`. `focus` only when the
   researcher gave a deepening direction for this topic.

   Keep the list of slugs dispatched in this run: step 4 needs it as the
   rebuilt topics.

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
   since vault-build renders the links. It needs every paper at once, so
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

3b. **Check the records** before they reach the vault — one Bash call, no
   model:

   ```
   python3 <plugin root>/scripts/check_vault.py records <paper_vault_path> --fix
   ```

   It checks that every paper file has its identity header and that the header
   `id` is the filename stem; that every summary's `id` is its paper's id; that
   every wikilink in the summaries, topic notes and repo notes resolves inside
   the problem's vault layout (`papers/<id>`, `topics/<slug>`, `repos/<id>`,
   `<problem-id>`) and that none carries a `<problem-id>/` prefix; and that
   every id in a topic's `papers` or a repo's `related_papers` is a real
   paper. `--fix` repairs only the two mechanical defects — tool-call markup
   an agent leaked at the end of a file, and stray side files such as
   `*.tmp` — and reports each one. It never changes a link or an id.

   Relay its JSON report: what it fixed, then each error by file. Errors do not
   block step 4, but they go into the final report by name. **Never repair a
   link or an id by hand, and never by matching titles** — ids are fixed at
   download so that nothing has to match titles, and a mismatch is a bug in the
   agent that wrote it. Its warnings — summaries with no resolvable identifier,
   "full texts" that are not, extraction warnings — go in the report too.

4. **Vault.** One Bash call — no agent; this step involves no model:

   ```
   python3 <plugin root>/scripts/build_vault.py --profile <confirmed profile path> \
     --records <paper_vault_path> --vault <root>/obsidian_vault/<id>/ \
     --rebuilt-topics <slug>,<slug>
   ```

   `--vault` is the problem's own Obsidian vault, the folder the researcher
   opens: strip the trailing `paper_vault/<id>/` from `paper_vault_path` and
   append `obsidian_vault/<id>/`. `--rebuilt-topics` is the slugs dispatched in
   step 2d (leave it out if none); on a re-run a topic note's content sections
   are otherwise kept as they are, so a new or deepened note would never reach
   the vault.

   On a re-run it merges rather than overwriting: it regenerates only the
   link, citation and related sections it owns and preserves everything the
   researcher added or edited. Tell the researcher their annotations survive,
   and that hand-edits made *inside* a generated section are the one
   exception.

   Relay from its JSON report: notes created and `merged`; `citations.missing`
   (arXiv papers left without a citation); `dropped_unknown_ids` (ids that
   match no paper, dropped rather than re-targeted by title: an upstream bug
   to name); and `papers_without_summary`. If it exits 2 with `{"error": …}`,
   fix the named input and run it again — never write the vault notes yourself.

5. **Check the vault's links** — one more Bash call:

   ```
   python3 <plugin root>/scripts/check_vault.py vault <vault>
   ```

   It resolves every wikilink in the vault against the vault root, exactly as
   Obsidian will, and lists each dead one with the note it sits in. Expect
   zero. Report any it finds by name; do not edit the notes to fix them.

## Report back

State the profile id and type, how many papers were found/summarized/vaulted, how many
topic notes and repo notes were written, and the final vault path. For topics, say how
many were offered and how many selected, split into new and deepened notes, and which
merges were applied; name the unselected slugs in one line, so the researcher knows they
still exist as paper keywords and can be picked on a later run. Name any topic note that
came back with zero matching papers — that's a gap in the literature or in the
search terms, and it's the kind of thing that's easy to miss in a folder
listing. For a topic profile, do the same for `review_questions`: name any
question that no paper summary cites — the keyword index from step 2a already
printed them. An unanswered review question is the topic-review counterpart of an empty topic
note, and it is the finding the researcher most needs. If anything failed at any stage (a summarizer call errored, a paper
had no matches to the profile's terms, etc.), name it plainly rather than
reporting a clean run.

Report both `check_vault.py` results: the record errors from step 3b and the
dead-link count from step 5, with each dead link named. A clean run says "0 dead
links" in so many words.

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
it against the problem's vault, `<root>/obsidian_vault/<id>/` — the folder
whose links step 5 checked, not its parent `obsidian_vault/` — and report any
launch failure plainly without touching the created files.

If Obsidian isn't installed, say so plainly — the vault path is already in the
report above, so they can open it themselves. **Do not offer or run an install
command** — no winget, no brew, no apt. Installing software on the researcher's
machine is out of scope for this pipeline.
