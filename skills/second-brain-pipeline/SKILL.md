---
name: second-brain-pipeline
description: >
  Runs the second-brain research pipeline end to end: problem or topic intake,
  paper and code discovery (arXiv, PubMed, cross-field, citation chasing,
  GitHub), a checkpoint for the researcher's review, then summaries,
  researcher-selected topic notes, paper links and a linked Obsidian vault. Use
  it when a researcher wants to go from a research problem, or a topic to
  review, to a populated vault in one flow. Also runs stages 3–5 of a topic
  deep-dive handed over by second-brain-topic-deep-dive.
---

# Second-brain pipeline

Act as the calling agent. This skill dispatches agents and runs scripts in
order, carries each stage's output into the next, and holds the checkpoint
pause. It does no discovery or writing itself.

**Keep this conversation lean.** Every turn here re-reads the whole
conversation, so read the scripts' compact reports, never paper files,
summaries or notes. Give each agent only its step's prompt template, filled
in. Dispatch every fan-out in **waves**:

- all `Agent` calls of a wave in **one message**, each with
  `run_in_background: false`;
- at most the concurrent-subagent cap per wave (read before stage 3); a call
  past it is refused, not queued. Start the next wave once the previous one
  has returned.

Agents reply `OK <path>` or `FAIL <reason>` plus a few anomaly lines; carry
those to the report.

## Stage 1–2: problem intake

Run the `research-problem-intake` skill until it writes a `status: confirmed`
profile. If the researcher already has a profile, read it: a `draft` goes back
to intake to finish. Note its `id`, `paper_vault_path` and `profile_type`
(missing means `problem`); the agents handle both types themselves, and the
reports state it.

**A topic profile needs `core_questions`** (`[]` counts as answered). If a
confirmed topic profile lacks the field, hand it to intake to ask that one
question, as for a `draft`.

**A profile with `deep_dive_of` is a topic deep-dive.** Resolve the plugin
root (next section), then read
`<plugin root>/skills/second-brain-pipeline/deep-dive.md`: its differences
override the stages below.

## Before stage 3: resolve the plugin root

The plugin's `templates/` and `scripts/` are needed from here on, by absolute
path. Resolve the root once, and read the wave size, with this Bash call as
written. It takes the first folder whose `.claude-plugin/plugin.json` names
this plugin, from: `$CLAUDE_PLUGIN_ROOT`; the working directory (development
with `claude --plugin-dir .`); the installed copy; a marketplace clone.

```bash
python3 - <<'EOF'
import glob, json, os
def ours(d):
    try: return json.load(open(os.path.join(d, ".claude-plugin", "plugin.json")))["name"] == "second-brain-researcher"
    except Exception: return False
p = os.path.expanduser("~/.claude/plugins")
dirs = [os.environ.get("CLAUDE_PLUGIN_ROOT", ""), os.getcwd()]
try: dirs += [e["installPath"] for k, v in json.load(open(p + "/installed_plugins.json"))["plugins"].items()
              if k.startswith("second-brain-researcher@") for e in v]
except Exception: pass
dirs += sorted(glob.glob(p + "/marketplaces/*/"))
print("plugin root:", next((os.path.normpath(d) for d in dirs if d and ours(d)), "NOT FOUND"))
print("wave size:", os.environ.get("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", "20"))
EOF
```

On `NOT FOUND`, stop and tell the researcher the plugin's files could not be
found.

## Stage 3: discovery

Dispatch the three discovery legs as **one wave**, each with this prompt and
nothing else (the `find_papers` line for the biomedical leg only):

```
profile: <confirmed profile path>
identity spec: <plugin root>/templates/paper-identity-spec.md
fetcher: <plugin root>/scripts/fetch_fulltext.py
find_papers: <plugin root>/scripts/find_papers.py
```

- `second-brain-paper-downloader`: arXiv.
- `second-brain-biomed-downloader`: PubMed, PMC, Europe PMC.
- `second-brain-crossfield-searcher`: methods from adjacent fields, via Asta.
  Dispatch it **unconditionally**; it checks its own key.

Each leg reads `paper_vault_path` from the profile and creates it. The legs are
independent: one failing never discards another's results. A leg that reports
a skip (no `ASTA_API_KEY`, no methodology terms, no `gh`) is an optional leg
skipped, not a failed run: one line in the stage-4 report. Never re-run
discovery to fix a missing key.

### Then core coverage: the citation chaser

Once the three legs have returned, dispatch `second-brain-citation-chaser`:

```
profile: <confirmed profile path>
find_papers: <plugin root>/scripts/find_papers.py
```

It chases citations from the core papers the legs saved, so it runs after
them. It replies `OK` with the core question, seeds, probes (drafted ones
marked), candidates and additions per round, why it stopped, OpenAlex gaps,
and a **needs-manual-download** list; keep all of it for stage 4.
`OK core coverage skipped: …` (no core question) is one line in the report.

### Merge before the checkpoint

The legs cannot see each other's writes, so one paper can arrive twice.
Resolve that with one Bash call:

```
python3 <plugin root>/scripts/stage_prep.py merge <paper_vault_path>
```

It keeps one file per paper and moves the other copies to `.merged/`. Report
each merge (a silent one looks like a paper went missing) and its
`possible_duplicates`, which are the researcher's call. Keep its coverage block
for stage 4.

### Then the code leg

Once the merge is done, dispatch `second-brain-code-finder`:

```
profile: <confirmed profile path>
format: <plugin root>/templates/repo-note-template.md
```

It mines the saved papers for repos, so it runs after them, and before the
checkpoint, so repos and papers are reviewed together. It uses the GitHub API
only and never clones anything.

## Stage 4: checkpoint — stop and wait

Relay one combined summary to the researcher and **stop**:

- the profile type; what each leg saved, with the core question's count
  separate; which legs ran and which were skipped; each leg's zero-hit and
  too-broad queries; what was merged; what was skipped, dropped, or left
  abstract-only.
- **Full-text coverage as numbers**, from the merge report: `full_text` (full
  versus abstract-only), `by_source`, `extraction_warnings`, `no_header`, and
  `possible_duplicates`. Abstract-only papers cap the quality of everything
  downstream, and this is the last cheap point to fix them.
- **needs-manual-download**, from the biomedical leg and the chaser, verbatim
  as one list with title, DOI and PMID; mark the chaser's as core papers. Never
  fold it into the skipped tally, and never proceed past it without an
  explicit decision. To supply one, the researcher saves the PDF as
  `<paper_vault_path>/<id>.pdf`; when they say so, run for each:

  ```
  python3 <plugin root>/scripts/fetch_fulltext.py --source manual \
    --record <paper_vault_path>/<id>.md --from-pdf <paper_vault_path>/<id>.pdf
  ```

  Delete the PDF once the report says `full_text: full`. If it says the file is
  not a PDF (a browser often saves a publisher's HTML page as `.pdf`), tell the
  researcher and delete nothing.
- **Core coverage**, as its own section: the core question, seeds, the probes
  (drafted ones marked, so the researcher can add them to `recall_probes`),
  candidates and additions per round, the total added by title, and why it
  stopped. Name OpenAlex's gaps and any `seed_papers` not in the vault. If the
  chaser hit its 40-paper guard or 4-round cap, say so prominently: narrowing
  `core_questions` is the researcher's call.
- **Repositories**, as their own section: how many from papers and how many
  from search, each one with **no license** by name, and that nothing was
  cloned and `code_vault_path` is empty by design.

Ask whether to proceed to the vault build, add missing papers first, or change
something (remove a paper, re-run discovery with other terms). Do not continue
to stage 5 in the same turn: wait for an explicit go-ahead.

## Stage 5: vault build

Only after the researcher confirms. If this conversation has no plugin root
yet (a resumed run), resolve it first as above. If a template or script path
below does not exist, stop and report it; never guess a path.

1. **Papers.** Plan the fan-out (add `--regenerate` only if the researcher
   asked to regenerate existing summaries):

   ```
   python3 <plugin root>/scripts/stage_prep.py summaries <paper_vault_path>
   ```

   Dispatch `paper-summarizer` once per entry of its `dispatches`, in waves:

   ```
   papers:
   - <paper_vault_path>/<id>.md (read_until: <N>)
   - <paper_vault_path>/<id>.md
   format: <plugin root>/templates/paper-page-template.md
   problem profile: <confirmed profile path>
   ```

   Carry every `FAIL` line into the final report.

2. **Topics.** The researcher chooses which topic notes get written.

   **2a. Index**, once:

   ```
   python3 <plugin root>/scripts/stage_prep.py keywords <paper_vault_path> \
     --profile <confirmed profile path>
   ```

   One line per slug: paper count, two titles, and "(note exists, +N new)".
   Profile keywords first, then every keyword on 2 or more papers, then the
   single-paper slugs on one line, as merge material only. Keep its last two
   lines (profile keywords on no paper, review questions no summary cites) for
   the final report.

   **2b. Propose.**
   - Every profile keyword without a topic note is **always** written, even
     with zero papers (an empty note shows a gap). List them once above the
     picker as "already included"; do not ask about them.
   - Offer every other keyword on **2 or more** papers.
   - **Suggest merges** from the slug list alone, single-paper slugs included:
     group slugs naming the same subtopic (`survival-analysis` /
     `time-to-event-prediction`). The canonical slug is the profile keyword if
     the group has one, else the slug on most papers; the rest become its
     **aliases**. Merge only true synonyms; offer a narrower concept as its
     own candidate. Show a profile keyword's merges in the "already included"
     line so the researcher can reject them.
   - **On a re-run** nothing from an earlier selection is remembered: every
     candidate is offered again, existing notes marked "(note exists, +N new
     papers)". Profile keywords that already have a note go into the picker
     under their own "Your topics" question.

   **2c. The researcher selects.** A real pause: dispatch nothing until
   answered, never auto-select. Use `AskUserQuestion` with
   `multiSelect: true` (at most 4 options per question, 4 questions per call):
   - themed questions ("Methods", "Clinical context", …) ranked by paper
     count; `header` the theme; an option's `label` the canonical slug with
     its aliases (`survival-analysis (+ time-to-event-prediction)`), its
     `description` the paper count, one or two titles, and the "(note exists
     …)" marker;
   - over 16 candidates, a second call with the rest; whatever is left after
     32 is named in one line with "reply to add any";
   - say in the question text that "Other" can add a keyword, undo a merge
     ("split survival-analysis") or give a focus for deepening ("deepen
     model-calibration: more on recalibration methods").

   Without `AskUserQuestion`, show the list numbered in chat and wait for the
   numbers.

   **2d. Dispatch.** The selected topics plus the profile keywords with no
   note. Write their digests in one call:

   ```
   python3 <plugin root>/scripts/stage_prep.py digest <paper_vault_path> \
     --topic <slug> --topic <slug>:<alias>,<alias> ...
   ```

   Then dispatch `topic-summarizer` once per topic, in waves:

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

   `aliases` only for a merged topic; `output exists` true when the index
   marked the slug "(note exists …)". `existing note` only when a note exists:
   the Obsidian copy `<vault>/topics/<slug>.md` if there is one (it carries
   the researcher's edits; `<vault>` as in step 4), else the paper-vault copy.
   `focus` only when the researcher gave one. Keep the dispatched slugs for
   step 4.

3. **Paper-to-paper links.** One Bash call, after step 1:

   ```
   python3 <plugin root>/scripts/link_papers.py \
     --summaries <paper_vault_path>/summaries/ \
     --state <paper_vault_path>/.linker/
   ```

   It writes citation and content links into each summary's `related_notes`,
   and never touches entries a researcher added. Relay its JSON report as it
   stands: link counts by kind, and by name the papers in `zero_edge_papers`,
   `not_in_s2` and `no_content_links_possible`, plus `embedding_coverage`
   (below ~70%: say so prominently). An empty link list is not evidence that
   nothing is related.

   If it cannot run (no `python3`, or exit 2 with `{"error": …}`, e.g.
   Semantic Scholar rate-limiting for its whole retry window), skip it in one
   line, suggest `SEMANTIC_SCHOLAR_API_KEY` if rate limiting was the cause,
   and go on. Never write links by hand.

   **3b. Check the records:**

   ```
   python3 <plugin root>/scripts/check_vault.py records <paper_vault_path> --fix
   ```

   It checks headers, ids and links, and `--fix` repairs only leaked tool-call
   markup and stray side files. Relay what it fixed and each error by file;
   errors do not block step 4 but go in the final report, with its warnings.
   **Never repair a link or an id by hand, and never by matching titles.**

4. **Vault.** One Bash call:

   ```
   python3 <plugin root>/scripts/build_vault.py --profile <confirmed profile path> \
     --records <paper_vault_path> --vault <vault> --rebuilt-topics <slug>,<slug>
   ```

   `<vault>` is the problem's Obsidian vault: `paper_vault_path` with its
   trailing `paper_vault/<id>/` replaced by `obsidian_vault/<id>/`.
   `--rebuilt-topics` is the slugs dispatched in step 2d (omit if none);
   without it, a rebuilt note's content would not reach the vault. On a re-run
   it replaces only the sections it owns: tell the researcher their
   annotations survive, except edits made inside a generated section.

   Relay notes created and `merged`, `citations.missing`,
   `dropped_unknown_ids` (an upstream bug to name) and
   `papers_without_summary`. On exit 2 with `{"error": …}`, fix the named input
   and run it again; never write vault notes yourself.

5. **Check the vault's links:**

   ```
   python3 <plugin root>/scripts/check_vault.py vault <vault>
   ```

   Expect zero dead links. Report any by name; do not edit notes to fix them.

## Report back

- The profile id and type; papers found, summarized and in the vault; topic
  and repo notes written; the vault path.
- Topics: how many offered and selected, new versus deepened, the merges
  applied, and the unselected slugs in one line (they can be picked on a later
  run). Name every topic note with zero papers, and on a topic profile every
  review question no summary cites: these gaps are the findings most easily
  missed.
- Core coverage in one line: the core question, papers added over how many
  rounds, and why it stopped, or why it was skipped.
- Both `check_vault.py` results: record errors, and the dead-link count with
  each one named ("0 dead links" when clean).
- Paper links: the split between direct citations, shared references and
  similar content; embedding coverage; and the papers left without links, and
  why.
- Anything that failed at any stage, plainly.

Then say what this run did not do: repos were catalogued but **never cloned,
run or tested**, and there is no experiment plan.

**Be precise about cross-linking.** Papers are linked through shared-keyword
topic notes, citation links and content links. Citation links are checkable
facts. Content links are estimates from **title and abstract only**, and exist
only for papers Semantic Scholar has an embedding for: never present a missing
content link as evidence that two papers are unrelated.

## Finally: offer to open the vault

Ask whether to open the vault in Obsidian (skip the question if they already
asked for it). Only on yes, check that Obsidian is installed (Linux/WSL: an
`obsidian` binary on `PATH` or a Flatpak install; Windows: the standard
install locations) and launch it on `<vault>`, the problem's folder, not its
parent. Report a launch failure plainly and touch no files. If Obsidian is not
installed, say so; the vault path is in the report. **Never offer or run an
install command.** Nothing here can turn a finished run into a failed one.
