# Full-text fetcher fixture

Offline tests for `scripts/fetch_fulltext.py`. The script rewrites the record it
is given, so each test runs on a scratch copy. From the repo root:

```
F=test-fixtures/fetch; T=$(mktemp -d)

# 1. JATS XML -> Markdown: headings, a pipe table, references, clean digits
cp $F/2020_antaki_kahwati.md $T/
python3 scripts/fetch_fulltext.py --record $T/2020_antaki_kahwati.md \
  --from-xml $F/PMC7658348_trimmed.xml > /dev/null
diff $T/2020_antaki_kahwati.md $F/expected_2020_antaki_kahwati.md

# 2. An HTML page saved as .pdf is refused, and the record is left untouched
cp $F/2020_antaki_kahwati.md $T/rec.md
python3 scripts/fetch_fulltext.py --record $T/rec.md \
  --from-pdf $F/html-error-page.pdf --source scihub-pdf | grep -q '"html-not-pdf: ' \
  && cmp $T/rec.md $F/2020_antaki_kahwati.md && echo "2 passes"
```

```
# 3. Several records in one call; one bad record does not stop the others.
#    Needs test 1's output in $T. Offline: that record is already full.
printf 'no header\n' > $T/bad.md
python3 scripts/fetch_fulltext.py --record $T/2020_antaki_kahwati.md $T/bad.md \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); \
      assert [x["id"] for x in r["records"]] == ["2020_antaki_kahwati", "bad"]; \
      assert r["still_abstract_only"] == ["bad"] and "error" in r["records"][1]; print("3 passes")'
```

Test 1 passes when `diff` prints nothing; tests 2 and 3 print `2 passes` and `3 passes`.

- `2020_antaki_kahwati.md` — an abstract-only record in the "Saved paper file"
  format of `templates/paper-identity-spec.md`.
- `PMC7658348_trimmed.xml` — Europe PMC's full-text XML for Antaki et al.,
  *Sci Rep* 2020 (CC BY 4.0), trimmed to the abstract, the introduction, one
  results subsection with Table 3, and three references. This is the paper whose
  Docling extraction rendered `0.90` as `Ͷ.ͿͶ` on a real run; the expected output
  has `0.90`.
- `expected_2020_antaki_kahwati.md` — the record after test 1: the body replaced,
  `full_text: full` and `full_text_source: europepmc-xml` in the header.
- `html-error-page.pdf` — an HTML 403 page under a `.pdf` name, which is what
  Europe PMC's PDF endpoint served to a download tool that reported success.

The network rungs are not covered here. Check them by hand on scratch copies of
real records: an open-access PMC paper should come back `europepmc-xml`, an NIH
author manuscript `pmc-bioc`, and an arXiv paper with no HTML version
`arxiv-pdf` (this last one needs Docling).
