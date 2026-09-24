# Vault-build fixture

Offline test for `scripts/build_vault.py`. From the repo root:

```
B=test-fixtures/vault-build
T=$(mktemp -d)
build() { python3 scripts/build_vault.py --profile $B/fixture-vault-20260924.md \
  --records $B/records/fixture-vault-20260924 --vault $1 --offline $2 > /dev/null; }

# first run into an empty vault
build $T/first/fixture-vault-20260924
diff -r $T/first $B/expected-first

# re-run over a vault the researcher has edited, with one rebuilt topic
cp -r $B/expected-first $T/rerun
patch -s -d $T/rerun -p1 < $B/researcher-edits.patch
build $T/rerun/fixture-vault-20260924 "--rebuilt-topics survival-analysis"
diff -r $T/rerun $B/expected-rerun

python3 scripts/check_vault.py vault $T/rerun/fixture-vault-20260924
```

No `diff` output means both pass, and the vault check must report
`"dead_count": 0`. Running either build a second time must report
`"merged": []`: the script is idempotent. `--offline` keeps it off the network
and leaves the fixture unchanged. The parent folder is `records/` rather than
`paper_vault/` because `.gitignore` excludes that name everywhere.

`records/fixture-vault-20260924/` covers each case once:

- Three summaries, holding only the fields the builder reads plus the ones the
  edits below touch. `2023_lee_park` is on arXiv, and its BibTeX comes from the
  cached metadata in `.vault/arxiv_meta.json`. The title escapes `%`, `&` and
  `_`. `2022_wu_chen` is on arXiv but not in the cache, so it gets no
  `## Citation` and is named under `citations.missing`. `2021_smith_jones` is
  a PubMed paper with no arXiv id, so it gets no citation and is not reported.
- `2022_wu_chen`'s title contains `|` and `[…]`, which would break a
  wikilink alias. The alias uses `/` and `(…)` instead.
- `related_basis` produces each `## Related` group. `2021_smith_jones_typo`
  in `2023_lee_park`'s `related_notes` and `ghost_paper` in the `calibration`
  topic are not papers. They are dropped and reported, never matched by title.
- `survival-analysis` has the alias `time-to-event`. `2022_wu_chen` carries
  only the alias and still links to the topic. `2023_lee_park` carries both
  and links to it once.
- `calibration`'s `papers` lists `2022_wu_chen`, whose summary does not carry
  the slug: a candidate topic-summarizer took from its digest's "Mentioned but
  not tagged" list. The paper's note still gets `[[topics/calibration]]` in
  `## Links`, so the topic's link to it has a way back.
- The repo `acme-survkit` names two papers. Each paper gets the repo link in
  its `## Code notes`, below the summarizer's prose.
- `2024_orphan.md` is a saved paper with no summary. It gets no note and is
  named under `papers_without_summary`.

`researcher-edits.patch` applies these researcher edits to `expected-first/`.
The re-run must keep or undo each one as described, which
`diff -r <patched copy> expected-rerun/` shows at a glance:

| Edit | Re-run |
|---|---|
| Problem note: `## My notes` added | kept, in place |
| Problem note: `## Topics` deleted | re-added between `## Papers` and `## Repos` |
| `2023_lee_park`: `status: reviewed`, `year: 2022`, a new `my_rating` key | kept |
| `2023_lee_park`: `## My notes` before `## Synthesis` | kept, in place |
| `2023_lee_park`: prose after the repo link in `## Code notes` | kept; the link stays where it was |
| `2023_lee_park`: a hand-added line inside `## Links` | replaced (an owned section) |
| `2021_smith_jones`: `## Related` deleted | re-added |
| `calibration` (not rebuilt): `## Summary` edited | kept |
| `survival-analysis` (rebuilt): `## Summary` edited, `paper_count: 99` | replaced from the record |
| `topics/my-own-topic.md`, a note with no record | untouched |
