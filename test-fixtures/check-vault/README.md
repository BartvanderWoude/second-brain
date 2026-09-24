# Vault-check fixture

Offline test for `scripts/check_vault.py`. From the repo root:

```
B=test-fixtures/check-vault
diff <(python3 scripts/check_vault.py records $B/records/fixture-problem-20260924) \
     $B/expected_records_report.json
diff <(python3 scripts/check_vault.py vault $B/vault/fixture-problem-20260924) \
     $B/expected_vault_report.json
```

No output means both pass. Neither command is run with `--fix`, so the fixture
stays unchanged. To test `--fix`, copy `records/fixture-problem-20260924` to a
scratch directory and run it there: it must strip the two markup lines at the
end of `topics/good-topic.md`, delete `topics/good-topic.md.tmp`, and change
nothing else.

The parent folders are `records/` and `vault/` rather than `paper_vault/` and
`obsidian_vault/`, because `.gitignore` excludes those names everywhere. The
script takes the problem id from the path's last segment, so the parent's name
does not matter.

`records/` holds one of each defect. Each file says in its own text which
finding it must produce:

- `2020_abstract_only` (paper and summary) is clean and must produce none.
- `2022_no_header.md` has no header. `2023_bad_id.md` has a header id that is
  not its filename stem.
- `summaries/2021_full_paper_summary.md` has a title-slug id, no identifier,
  and a slug in `related_notes`. `summaries/2019_orphan_summary.md` has no
  paper file.
- `topics/good-topic.md` has one link in the old `<problem-id>/papers/…` form,
  one link to a paper that does not exist, a `ghost_paper` id in `papers`, and
  leaked `</content></invoke>` at the end. Its `[[…]]` inside `$$…$$` and
  inline code must **not** be read as links.
- `topics/good-topic.md.tmp` is a stray side file. `repos/foo-bar.md` has a
  slug in `related_papers`.
- The warnings: `2021_full_paper.md` has `extraction_warning: garbled-digits`,
  `2024_fake_full.md` claims `full_text: full` with a short, summary-shaped
  body, and `2024_fake_full.pdf` sits in the vault root.

`vault/` resolves links the way Obsidian does, with the problem folder as the
vault root. Relative (`../topics/…`), bare-name and heading links must resolve.
The `<problem-id>/papers/…` link and the missing paper must be the only two
dead links.
