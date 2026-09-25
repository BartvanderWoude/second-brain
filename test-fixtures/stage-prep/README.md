# Stage-prep fixture

Offline test for `scripts/stage_prep.py`. From the repo root:

```
B=test-fixtures/stage-prep
R=$B/records/fixture-prep-20260924
diff <(python3 scripts/stage_prep.py merge $R --dry-run) $B/expected_merge.json
diff <(python3 scripts/stage_prep.py summaries $R --regenerate --solo-kb 1) \
     $B/expected_summaries.json
diff <(python3 scripts/stage_prep.py keywords $R --profile $B/fixture-prep-20260924.md) \
     $B/expected_keywords.txt

# merge for real, and digest (both write), on a copy
T=$(mktemp -d); cp -r $R $T/
python3 scripts/stage_prep.py merge $T/fixture-prep-20260924 > /dev/null
ls $T/fixture-prep-20260924/.merged     # 2021_smith_jones.md  2024_lee_park.md
python3 scripts/stage_prep.py merge $T/fixture-prep-20260924 | grep -c '"kept"'   # 0: nothing left to merge
python3 scripts/stage_prep.py digest $T/fixture-prep-20260924 \
  --topic survival-analysis:time-to-event-prediction > /dev/null
diff $T/fixture-prep-20260924/.digests/survival-analysis.md $B/expected_digest_survival-analysis.md
```

No `diff` output means everything passes. After the real merge,
`2023_lee_park.md` must read `source: arxiv, pubmed`, `doi: 10.1000/jrec.2024.1`
and `pmid: "38000001"`, and `2024_lee_park.md` and `2021_smith_jones.md` must
have moved to `.merged/`. The parent folder is `records/` rather than `paper_vault/` because
`.gitignore` excludes that name everywhere.

What each record tests:

- `2023_lee_park` (arXiv preprint, full text, arXiv DOI) and `2024_lee_park`
  (PubMed, abstract-only, journal DOI) have titles that differ only in case and
  punctuation. They are a preprint/published pair. The full-text copy is kept,
  and it takes the journal DOI, the PMID and the second source.
- `2021_smith_jones` and `2021_smith_jones_2` have the same DOI, written with
  and without `https://doi.org/` and in different case. The `_2` copy has full
  text, so it is kept under its own name.
- `2020_hand_a` and `2020_hand_b` share a title, but have different DOIs and
  neither is a preprint. They are reported under `possible_duplicates`
  ("same title, different doi") and not merged.
- `2019_legacy` has no header. It is listed under `no_header`, and its title is
  its first line.
- `2021_smith_jones_2` carries `extraction_warning: garbled-digits`.
- `summaries`: with `--solo-kb 1`, `2023_lee_park` (just over 1 KB) stands in
  for a long full text and gets its own dispatch. `read_until: 31` stops one
  line before `## References`, so the reference list and the appendix after it
  are not read. Everything else goes in one batch.
  Without `--regenerate`, the two papers that have summaries are skipped.
- `keywords`: `survival-analysis` has a note that lists only `2019_legacy`, so
  it shows `+1 new`. `2020_hand_a`'s summary is tagged `model-updating` but
  says "Survival Analysis" in its Method section, so the line also shows
  `+1 mention it untagged`. The profile keyword `external-validation` is on no
  paper. `time-to-event-prediction` appears only among the single-paper slugs
  that are available for merging. Q2 is not cited by any summary.
- `digest`: collects every summary that carries the slug or one of its
  aliases, each paper once. `## Code notes` and most of the frontmatter are
  dropped. `2020_hand_a` is listed under `## Mentioned but not tagged` with
  the sentence from its Method section; the mention in its `## Code notes`
  does not count, because code notes are dropped everywhere else too.

## Topic deep-dive

`deep-dive/` tests `stage_prep.py topic` and `digest --since`. From the repo
root:

```
B=test-fixtures/stage-prep/deep-dive
P=$B/fixture-dd-20260925.md
V=$B/vault/fixture-dd-20260925
ID=survival-analysis-deep-dive-20260925
T=$(mktemp -d); cp -r $B/records/fixture-dd-20260925 $T/; R=$T/fixture-dd-20260925
tp() { python3 scripts/stage_prep.py topic $R --profile $P "$@"; }

diff <(tp --topic survival-analysis --vault $V --snapshot $ID) $B/expected_topic_existing.txt
tp --topic survival-analysis --snapshot $ID | tail -1   # Snapshot: kept the existing …
diff <(tp --topic time-to-event --vault $V) $B/expected_topic_alias.txt
diff <(tp --topic competing-risks) $B/expected_topic_new_one.txt
diff <(tp --topic ultra-widefield-imaging) $B/expected_topic_new_none.txt
diff <(tp --topic hand-topic --vault $V) $B/expected_topic_obsidian_only.txt

# the deep-dive's search saves four records; three get summaries
cp $B/new/*.md $R/; cp $B/new/summaries/*.md $R/summaries/
diff <(tp --topic survival-analysis --since $ID) $B/expected_topic_since.txt
python3 scripts/stage_prep.py digest $R --topic survival-analysis:time-to-event --since $ID > /dev/null
diff $R/.digests/survival-analysis.md $B/expected_digest_since.md
tp --topic survival-analysis --since nope; echo $?        # 2
tp --topic survival-analysis --since $ID --snapshot $ID; echo $?   # 2

# keywords marks a note a deep-dive wrote
sed -i 's/^related_problem: .*/&\ndeep_dive: '$ID'/' $R/topics/survival-analysis.md
python3 scripts/stage_prep.py keywords $R --profile $P | grep -c 'deep-dive)'   # 1

# an old-id vault is refused
O=$(mktemp -d); cp -r $B/records/fixture-dd-20260925 $O/; O=$O/fixture-dd-20260925
sed -i 's/^id: 2021_smith_jones$/id: smith-cox-models-20260924/' $O/summaries/2021_smith_jones_summary.md
python3 scripts/stage_prep.py topic $O --profile $P --topic survival-analysis | grep -c '^WARNING: old-style ids'   # 1
```

No `diff` output, and the counts and exit codes in the comments, mean it
passes.

What the fixture tests:

- `survival-analysis` has a note with the alias `time-to-event` and two
  papers. `2022_wu_chen` carries only the alias, and its title holds `"`, so
  its seed line escapes it. It has no DOI, so the seed is the title alone:
  `find_papers.py` reads a DOI anywhere in a seed, but a vault id or anything
  else beside a title would be taken as part of the title.
- `2023_lee_park` names "survival analysis" in its Method section without
  carrying the slug, so it is listed as an untagged mention; the same words in
  its `## Code notes` do not count.
- Nearby slugs come in three kinds. `competing-risk`, on `2021_smith_jones`,
  is the same name as `competing-risks` spelled differently, so it is an alias
  for certain. `survival-models` shares the word "survival" with
  `survival-analysis`; "analysis" alone would not count, being on the
  stoplist. `calibration` is on both of the note's papers: related, but not
  an alias. A slug has to share at least 2 papers to count as the third kind:
  on a one-paper topic, every keyword of that paper would otherwise crowd out
  the name matches, as happened on a live run.
- The Obsidian copy in `vault/` has its `## Summary` edited, which a rebuild
  replaces, and a `## My notes` section, which a rebuild keeps. The report
  says both.
- `time-to-event` resolves to the note it is an alias of.
- `competing-risks` is a new topic on one paper, `ultra-widefield-imaging` a
  new topic on none. `hand-topic` exists only in the Obsidian vault.
- `--snapshot` writes `.deep-dive/<ID>.json` once and keeps it on a second
  run, so a resumed pipeline does not move the baseline.
- `new/` holds what the search saves: `2025_kim_cho` carries the slug and
  `calibration`, so `calibration` is named as another note to refresh;
  `2025_diaz_ruiz` names the alias untagged and has `garbled-digits`;
  `2025_ng_ong` does neither, so the digest lists it under "Found by this
  deep-dive, not tagged" with its task and method; `2025_orphan` has no
  summary yet.
