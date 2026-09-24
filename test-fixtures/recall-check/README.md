# Recall-check fixture

Offline test for `scripts/recall_check.py`. From the repo root:

```
B=test-fixtures/recall-check
R=$B/records/fixture-recall-20260924
diff <(python3 scripts/recall_check.py probe $R --profile $B/fixture-recall-20260924.md \
        --max 8 --cache $B/cache.json --offline) $B/expected_probe.json

# add writes, so run it on a copy; --no-fetch keeps the full-text fetcher off the network
T=$(mktemp -d); cp -r $R $T/
diff <(python3 scripts/recall_check.py add $T/fixture-recall-20260924 --no-fetch \
        --pmid 37013114 --pmid 40235812 --pmid 38682863 \
        --cache $B/cache.json --offline) $B/expected_add.json
diff $T/fixture-recall-20260924/2023_zhou_lu.md $B/expected_2023_zhou_lu.md
diff $T/fixture-recall-20260924/2025_gan_cao_2.md $B/expected_2025_gan_cao_2.md
cmp $T/fixture-recall-20260924/2025_gan_cao.md $R/2025_gan_cao.md
```

No output means everything passes. `--offline` answers every request from
`cache.json`, which holds the real PubMed E-utilities responses for the two
probes and the `add` lookup, recorded on 2026-09-24 with `--cache` and no
`--offline`. To keep the file small, the elements the script never reads were
cut from the PubMed XML: reference lists, affiliations, MeSH headings,
chemicals, keywords, grants and history dates.

**There are no arXiv responses in it.** arXiv's query API answered HTTP 406 to
every uncached request for over an hour that day. Offline, both arXiv lookups
therefore report `"error": "not in the cache (--offline)"`, which is the path
by which a failed source is reported as not checked instead of as 0 missing.
`expected_probe.json` still pins the translated arXiv query of each probe. To
add arXiv responses, rerun the probe with `--cache $B/cache.json` and without
`--offline` on a day arXiv answers, then regenerate `expected_probe.json`.

The parent folder is `records/` rather than `paper_vault/` because
`.gitignore` excludes that name everywhere.

The profile's two `recall_probes` are single-quoted YAML strings carrying
double-quoted phrases, which is how the format spec says to write them.
`date_window_years: 0` keeps the queries, and so the cache keys, free of
today's date.

What each record tests, all against real hits:

- `2026_xing_shao.md` has no header, and its first line is the paper's title in
  upper case with a trailing period. It is matched by normalized title.
- `2023_gao_wu.md` has a PMID, no DOI and a title that matches nothing. It is
  matched by PMID.
- `2024_catania_chapron.md` writes its DOI with a `doi.org` prefix in upper
  case. It is matched by DOI.
- `.merged/2026_ju_qin.md` is a copy the merge step moved aside. It still counts
  as in the vault, reported as `.merged/2026_ju_qin`.
- `2025_gan_cao.md` is a different paper by the same two authors in the same
  year. The AI-PVR paper (PMID 40235812) is therefore missing, and `add` saves
  it as `2025_gan_cao_2.md`, leaving this file untouched.

What the probe report must show:

- Probe 1 has 9 PubMed hits against `--max 8`: `too_broad`, 8 checked.
- PMIDs 40235812 and 41924382 are found by both probes and keep one number
  each in the top-level `missing` list, with both probes under `found_by`.
- Seeds: the DOI seed and the PMID seed are found; the title seed (Zhou's
  nomogram paper, which is missing) is not.
- arXiv: an `error` per probe, never a count, as explained above.

What `add` must show: Zhou (37013114) saved as `2023_zhou_lu.md` with the
identity header from PubMed's metadata and its abstract as the body; Gan saved
under the collision suffix; Catania (38682863) skipped as already in the vault
by DOI.
