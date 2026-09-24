# Linker fixture

Offline test for `scripts/link_papers.py`. From the repo root:

```
diff <(python3 scripts/link_papers.py --summaries test-fixtures/linker/summaries \
        --state test-fixtures/linker/state --offline --dry-run) \
     test-fixtures/linker/expected_report.json
```

No output means it passes. `--dry-run` writes nothing, so the fixture stays
unchanged.

`state/s2_cache.json` holds real Semantic Scholar batch records for four arXiv
papers, with embeddings rounded to 5 decimals. Two entries are made up to cover
the failure cases:

- `DOI:10.0000/fixture-no-embedding` is arXiv 2312.11976's real record with its
  embedding removed. It must get citation links only, and be listed under
  `no_content_links_possible`.
- `DOI:10.0000/fixture-not-in-s2` is `null`, meaning Semantic Scholar doesn't
  know the paper. It must get no links and be listed under `not_in_s2`.

CALM and CANDI have no citation relation to each other. They must be linked
by `similar-content` (0.961).

Two more made-up entries cover identifier resolution:

- `2024_s2_only` has no DOI, only a Semantic Scholar paper URL, and an empty
  `id`. It must resolve by the URL's 40-hex paper id (cache key
  `0123456789abcdef…`), take its id from the filename stem, and get a
  `direct-citation` link to CALM.
- `2022_header_fallback` is a summary with no identifier at all. The linker
  must take the DOI from its paper file's header, `../2022_header_fallback.md`,
  and link it to CANDI by `direct-citation`.

Neither may appear under `no_identifier`.
