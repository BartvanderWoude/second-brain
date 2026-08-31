# Paper identity, deduplication, and filenames

The single definition of **when two search hits are the same paper** and **what
the saved file is called**. Every discovery agent cites this file rather than
restating it — per the "one copy of each schema" rule in `PROJECT_CONTEXT.md`,
a second copy that drifts breaks dedup silently.

This began as arXiv-only rules inside `second-brain-paper-downloader.md`. It is
now shared, because once several sources run in parallel the same paper
routinely arrives twice — a preprint on arXiv and the published version on
PubMed are one paper, and saving both wastes a vault slot and double-counts the
subtopic in every topic note downstream.

## Identity: the key ladder

Compare candidates on the **first key both papers have**, in this order. A
match at any rung means the same paper; do not fall through to a weaker rung to
look for disagreement.

1. **DOI** — normalize by lowercasing and stripping any `https://doi.org/` or
   `doi:` prefix. Authoritative when present, which is most non-arXiv hits.
2. **Source-native id**, only when comparing two hits from the same source —
   arXiv id (strip the version suffix, so `2501.12345v2` and `2501.12345` are
   one paper), PMID, PMCID.
3. **Normalized title** — lowercase, then delete every character that is not
   `a–z` or `0–9`. This drops spaces, hyphens, colons, and case, so
   `Test-time Adaptation` and `Test-Time Adaptation` compare equal. Exact string
   comparison is not good enough: sources routinely disagree on the casing and
   punctuation of a title.

A normalized-title match with **different DOIs** is still the same paper when
one hit is a preprint and the other is the published version — that is the
common arXiv/PubMed case, not a collision. Prefer the version with a DOI and a
real venue, and record the other's id in the note rather than saving twice.

## Repository identity

Repos use the same idea with a simpler key: **`owner/name`, lowercased**, is the
identity. A fork and its upstream are different repos with different keys — but
they are usually *not* both worth a note, so resolve a fork to its canonical
upstream and keep one, exactly as a preprint and its published version collapse
to one paper above. The note filename is that key with the slash replaced by a
hyphen: `<owner>-<name>.md`.

Normalize a URL found in prose before keying on it: strip trailing sentence
punctuation, a `.git` suffix, and any `/tree/<branch>` or `/blob/<path>` tail.
`https://github.com/Foo/Bar.git`, `https://github.com/foo/bar`, and
`https://github.com/foo/bar/tree/main` are one repo.

## Which copy to keep

When one paper is reachable from several sources, keep **one** file:

1. Prefer whichever source yields **usable full text** — that is the whole point
   of saving it. An arXiv extraction beats a PubMed abstract-only record.
2. Otherwise prefer the **published version** over the preprint, for the DOI and
   venue.

Record the sources that were merged in the note's `source` field so the merge is
visible rather than silent.

## Filenames

`YEAR_firstauthor_secondauthor.md`, identical across every source, so the same
paper cannot land twice under two names.

- `YEAR` — the publication year of the version being saved. For arXiv use the
  `published` (v1) date, never an update/revision date, so the same paper yields
  the same `YEAR` on every run.
- `firstauthor` / `secondauthor` — surname slugs for the first two listed
  authors. One author means `YEAR_firstauthor.md`.

**Surname slug rule** — deterministic above all else, because the filename is
half the idempotency check. Take the author string as the source returns it
(`"First M. Last"`). The surname is the substring after the **final space**.
Lowercase it, fold accented Latin characters to ASCII (`é`→`e`, `ø`→`o`), then
delete every character that is not `a–z`. So `Jan-Christoph Goos` → `goos`,
`Geoffrey I. Webb` → `webb`, `Zahra Zamanzadeh Darban` → `darban`. This drops
surname particles (`van der`, `de`) — accept that. A slug that is reproducible
matters more than one that is linguistically correct.

Some sources return authors surname-first (`"Last, First M."`). Detect the comma
and take the part **before** it instead; applying the final-space rule to
`"Goos, Jan-Christoph"` would slug the given name.

**Collision suffix** — in this order:

1. The first paper saved under a base name is `YEAR_first_second.md`, with **no**
   suffix. Never write `_1`.
2. Only if that filename exists **and its normalized title differs** from the
   candidate's is it a real collision — then `YEAR_first_second_2.md`, then `_3`.
   A prolific group can put the same two authors on several papers in one year;
   that is what this suffix is for.
3. A file whose normalized title *matches* is the same paper. That is a skip,
   never a collision.

## Idempotency on re-runs

Build the index of what is already saved **once per run**, before fetching
anything: glob `<paper_vault_path>/*.md`, read each file's first line (the saved
extraction begins with the title), and normalize it. Do not glob per candidate,
and do not narrow the glob to a candidate's expected filename — the same paper
can be sitting under a different year (v1 vs. v2 dates) or a differently-slugged
second author.

When several fetchers run in parallel they cannot see each other's writes, so
each one dedups against what was on disk when it started. Cross-fetcher
duplicates are resolved by the pipeline's merge step before the stage-4
checkpoint, not by the fetchers.
