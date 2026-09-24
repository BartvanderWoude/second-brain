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
