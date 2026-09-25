# find_papers fixture

Offline test for `scripts/find_papers.py`. From the repo root:

```
B=test-fixtures/find-papers
F="--cache $B/cache.json --offline"
P1='("proliferative vitreoretinopathy" OR redetachment) AND (nomogram OR "deep learning" OR "machine learning")'
P2='("retinal detachment" OR redetachment) AND (recurrence OR recurrent OR "proliferative vitreoretinopathy") AND (nomogram OR "deep learning")'
BROAD='"retinal detachment" AND ("machine learning" OR "deep learning")'

# the commands write lists and records, so run them on a copy, in this order
T=$(mktemp -d); cp -r $B/records/fixture-recall-20260924 $T/; V=$T/fixture-recall-20260924
diff <(python3 scripts/find_papers.py seeds $V --profile $B/fixture-recall-20260924.md $F) $B/expected_seeds.txt
diff <(python3 scripts/find_papers.py pubmed $V --list core-probe --fresh --max 40 \
        --query "$P1" --query "$P2" --query "$BROAD" $F) $B/expected_pubmed.txt
diff <(python3 scripts/find_papers.py pubmed $V --list background --max 40 --top 5 --query "$BROAD" $F) \
     $B/expected_pubmed_top.txt
diff <(python3 scripts/find_papers.py chase $V --list core-1 --max-citing 6 --seed 2024_catania_chapron \
        --seed 2023_gao_wu --seed 2026_xing_shao --seed 2021_nobody_known $F) $B/expected_chase1.txt
diff <(python3 scripts/find_papers.py show $V --list core-1 19 60 $F) $B/expected_show.txt
diff <(python3 scripts/find_papers.py add $V --no-fetch --list core-1 19 60 $F) $B/expected_add_chase.json
diff <(python3 scripts/find_papers.py add $V --no-fetch --list core-probe 7 $F) $B/expected_add_probe.json
diff <(python3 scripts/find_papers.py add $V --no-fetch --list core-probe 19 $F) $B/expected_wrong_list.json
diff <(python3 scripts/find_papers.py chase $V --list core-2 --seed 2013_salapuigdollers_fernandez $F) \
     $B/expected_chase2.txt
diff $V/2024_savastano_crincoli.md $B/expected_2024_savastano_crincoli.md
diff $V/2013_salapuigdollers_fernandez.md $B/expected_2013_salapuigdollers_fernandez.md
diff $V/2023_zhou_lu.md $B/expected_2023_zhou_lu.md

# add by PMID, on a fresh copy; --no-fetch keeps the full-text fetcher off the network
T=$(mktemp -d); cp -r $B/records/fixture-recall-20260924 $T/; V=$T/fixture-recall-20260924
diff <(python3 scripts/find_papers.py add $V --no-fetch \
        --pmid 37013114 --pmid 40235812 --pmid 38682863 $F) $B/expected_add.json
diff $V/2023_zhou_lu.md $B/expected_2023_zhou_lu.md
diff $V/2025_gan_cao_2.md $B/expected_2025_gan_cao_2.md
cmp $V/2025_gan_cao.md $B/records/fixture-recall-20260924/2025_gan_cao.md
```

No output means everything passes. `--offline` answers every request from
`cache.json`, which holds the real PubMed E-utilities and OpenAlex responses
for these commands, recorded on 2026-09-25 by running them with
`--cache` and without `--offline`. To keep the file small, what the script
never reads was cut:

- from the PubMed XML: reference lists, affiliations, MeSH headings,
  chemicals, keywords, grants, dates other than the publication date, and the
  abstract of every paper that is neither saved nor shown;
- from the OpenAlex JSON: every field outside the `select`, author and venue
  detail beyond the display names, and the abstract of every work that is
  neither saved nor shown.

The parent folder is `records/` rather than `paper_vault/` because
`.gitignore` excludes that name everywhere. The profile has no date window,
and `pubmed` gets no `--window`, so no query carries today's date.

What each record tests:

- `2026_xing_shao.md` has no header, and its first line is the paper's title in
  upper case with a trailing period. `pubmed` matches it by normalized title;
  as a chase seed it resolves by exact title, and OpenAlex holds no reference
  list for it.
- `2023_gao_wu.md` has a PMID, no DOI and a title that matches nothing. It is
  matched by PMID, and as a seed it resolves by PMID.
- `2024_catania_chapron.md` writes its DOI with a `doi.org` prefix in upper
  case. It is matched by DOI and resolves by DOI.
- `2021_nobody_known.md` is made up. As a seed it resolves nowhere and is
  reported as not found.
- `.merged/2026_ju_qin.md` is a copy the merge step moved aside. It still
  counts as in the vault.
- `2025_gan_cao.md` is a different paper by the same two authors in the same
  year. The AI-PVR paper (PMID 40235812) is therefore not in the vault, and
  `add` saves it as `2025_gan_cao_2.md`, leaving this file untouched.

What the outputs must show:

- `seeds`: the five records, with first authors taken from the filenames, and
  the title seed (Zhou's nomogram paper) as the one `seed_papers` entry not in
  the vault.
- `pubmed`: q1 and q2 fetched whole, with their vault hits counted and not
  listed. Gan's AI-PVR paper, found by both, is listed once with both queries
  under `found_by`. q3 has 121 hits against `--max 40`: it is reported too
  broad and nothing of it is fetched.
- `pubmed --top 5`: the same query, now fetched as the top 5 of 121, and said
  so. Its numbers start at 9, after `core-probe`'s 1–8: numbering carries on
  across a vault's lists.
- `chase` round 1: three seeds found (by DOI, PMID and title), one not found.
  Catania has 7 citations against `--max-citing 6`, so its forward hop is
  skipped and reported, while Gao's citing works are chased. Candidates are
  ranked by how many seeds they link to, and numbered from 14.
- `show`: the abstracts of candidates 19 and 60.
- `add --list`: candidate 19 has no PMID or arXiv id and is saved from
  OpenAlex's metadata (`source: openalex`). Candidate 60 has a PMID and is
  saved from PubMed's. Zhou (probe candidate 7) came from PubMed already and is
  saved without another lookup, identical to the record `add --pmid` writes.
- `add --list core-probe 19`: refused, naming `core-1` as the list that holds
  19, and nothing is saved. That is the mistake a screening agent makes when
  it passes one list's number with another list's name.
- `chase` round 2, from the external-validation paper just added: 6 of its
  links were listed in `core-1` or `core-probe` already, and 1 is in the vault.
  None of them is listed again.
- `add --pmid`: Zhou saved as `2023_zhou_lu.md`, Gan under the collision
  suffix, Catania (38682863) skipped as already in the vault by DOI.
