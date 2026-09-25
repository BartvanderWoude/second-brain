# Topic deep-dive: how the pipeline differs

A profile with `deep_dive_of` set is a **topic deep-dive**: a literature
search for one topic note (`topic_note`) of an existing vault, written by
`research-problem-intake` for `second-brain-topic-deep-dive`. Run SKILL.md's
stages with the differences below; everything this file does not mention runs
as written there.

Two profiles are in play, and which one a step gets is most of what differs:

- the **deep-dive profile** drives discovery: the three paper legs and the
  citation chaser;
- the **vault profile** (`vault_profile`) goes to everything that writes vault
  content: `paper-summarizer`, `stage_prep.py` and `build_vault.py`, which
  refuses any other profile;
- `topic-summarizer` gets both.

Below, `<pv>` is `paper_vault_path` (the two profiles share it), `<dd>` the
deep-dive profile's `id`, `<slug>` its `topic_note`, `<aliases>` its
`topic_aliases` comma-joined (drop the `:<aliases>` part when there are none),
and `<vault>` the vault's Obsidian folder, `<root>/obsidian_vault/<vault id>/`.

## Stage 1–2

The deep-dive profile arrives confirmed. Check, reading the two frontmatters
and nothing else:

- `vault_profile` exists and has `status: confirmed`;
- its `id` equals `deep_dive_of`;
- both profiles have the same `paper_vault_path`.

If any check fails, stop and report it; never repair a profile yourself.

Resolve the plugin root (SKILL.md, "Before stage 3"), then snapshot the
vault, so later steps can tell the deep-dive's papers from the vault's:

```
python3 <plugin root>/scripts/stage_prep.py topic <pv> --topic <slug>:<aliases> \
  --profile <vault profile> --vault <vault> --snapshot <dd>
```

It writes `<pv>/.deep-dive/<dd>.json`, or keeps the one already there when a
run is resumed. Stop if its report has a `WARNING` line.

**One deep-dive per vault at a time.** The candidate lists, digests and linker
state under `<pv>` are shared.

## Stage 3

The three legs and the citation chaser run as written, with the **deep-dive
profile's** path; it is a topic profile, so they need nothing else. Its
`paper_vault_path` is the vault's, so new papers land in the vault's paper
vault and each leg skips what the vault already holds. The chaser's `--fresh`
discards the vault's earlier `core-*` lists, which is intended. Then the
merge, as written.

**Skip the code leg.** The deep-dive is about the literature on one topic. Say
so in one line at stage 4; the vault's repo notes are left as they are.

## Stage 4

Before the report, one Bash call:

```
python3 <plugin root>/scripts/stage_prep.py topic <pv> --topic <slug>:<aliases> \
  --profile <vault profile> --since <dd>
```

The checkpoint report is SKILL.md's, framed as a deep-dive:

- the topic: its slug, whether its note exists, and how many papers it had;
- the new records since the snapshot, full text versus abstract-only, and
  their extraction warnings, from this report (the merge report's figures
  cover the whole vault);
- per leg, with the core question's count separate; zero-hit and too-broad
  queries; merges;
- the needs-manual-download list, verbatim, as SKILL.md says;
- core coverage, as SKILL.md says;
- one line: the code leg was skipped.

Then stop and wait, as at every checkpoint.

## Stage 5

**Step 1, papers.** As written, with `problem profile: <vault profile>`. New
summaries must carry the vault's `related_problem` and tag the vault's own
review questions, or they would not count in its index. Without
`--regenerate`, `stage_prep.py summaries` plans only records that have no
summary: the new ones, and any older record without one, which the `--since`
report names. Say so if there are any.

**Step 2, topics: no index and no picker.** The researcher chose the topic
when they started. One Bash call writes its digest:

```
python3 <plugin root>/scripts/stage_prep.py digest <pv> --topic <slug>:<aliases> --since <dd>
```

Its report gives the digest's `lines`, and `found_untagged`: papers the search
saved that neither carry the slug or an alias nor name it. Then **one**
`topic-summarizer` dispatch, with SKILL.md's prompt and two more lines:

```
keyword: <slug>
aliases: <alias>, <alias>
digest: <pv>/.digests/<slug>.md
paper vault path: <pv>
problem profile: <vault profile>
format: <plugin root>/templates/topic-note-template.md
output: <pv>/topics/<slug>.md
output exists: <true | false>
existing note: <path>
deep-dive profile: <deep-dive profile path>
vault topics: <slug>, <slug>, ...
```

- `existing note`: the snapshot report said which case this is. For an
  existing note, pass the Obsidian copy `<vault>/topics/<slug>.md` when it
  exists, else the record, as SKILL.md says. For a note only in the Obsidian
  vault, pass that copy. For a new topic, leave the line out.
- `vault topics`: the stems of `<pv>/topics/*.md` other than `<slug>`, from
  one `ls`.

The rebuilt topic is `<slug>` alone. Then run the `--since` report once more:
its "Other topic notes the new summaries carry" line names the notes that
gained papers they do not list yet. A deep-dive does not rewrite them; the
final report names them for the researcher's next normal run.

**Steps 3, 3b, 4 and 5** run as written. `link_papers.py` covers the whole
vault, so the new papers get citation and content links to the old ones.
`build_vault.py` gets `--profile <vault profile> --vault <vault>
--rebuilt-topics <slug>`. It writes the note's `## Related topics` from shared
papers, and the same section on each topic it names, so the links run both
ways.

## Report back

In place of SKILL.md's topic lines:

- the note: created or deepened, and its paper count before and after (the
  `--since` report's "Note papers" line);
- each deep-dive question, answered, partly answered or not answered, from the
  summarizer's `questions:` line;
- papers found (the new records), summarized and vaulted, and the
  core-coverage line;
- links: the new papers' citation and content links from the linker report,
  and the note's related topics;
- the other topic notes that gained papers, as "pick them on your next normal
  run";
- whether the slug is in the vault profile's `keywords_of_interest`.

Both check results, the precision of the cross-links and the list of what is
not built follow as SKILL.md says; add that the code leg did not run.
