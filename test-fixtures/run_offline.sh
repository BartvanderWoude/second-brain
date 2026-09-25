#!/usr/bin/env bash
# Runs the offline fixture suites: no model, no network, and the fixtures stay
# unchanged (everything that writes runs on a copy in a temp dir). A development
# tool; the pipeline never calls it. From the repo root:
#
#   bash test-fixtures/run_offline.sh              # every suite
#   bash test-fixtures/run_offline.sh linker fetch # just these
#
# Prints one line per suite, PASS or FAIL with the first lines of what failed,
# and exits 1 if any suite failed. Each suite runs the command block of its
# README (test-fixtures/<suite>/README.md) with every expectation there,
# including the ones given only as comments, turned into a check. Change a
# README's block and its suite here together.

set -u
cd "$(dirname "$0")/.." || exit 2

SUITES=(check-vault fetch find-papers linker stage-prep stage-prep-deep-dive vault-build)

# fail LABEL TEXT: record a failure for the suite that is running.
fail() { printf '%s: %s\n' "$1" "$2" >> "$LOG"; }
# same LABEL DIFF-ARGS...: fail with the diff when the two differ.
same() {
  local label=$1 out; shift
  out=$(diff "$@" 2>&1) || fail "$label" "$out"
}
# expect LABEL WANT GOT
expect() { [ "$2" = "$3" ] || fail "$1" "expected '$2', got '$3'"; }

suite_check_vault() {
  local B=test-fixtures/check-vault
  local C=$B/records/fixture-problem-20260924
  same records <(python3 scripts/check_vault.py records $C) $B/expected_records_report.json
  same vault <(python3 scripts/check_vault.py vault $B/vault/fixture-problem-20260924) \
    $B/expected_vault_report.json
  # --fix strips the leaked markup and the stray .tmp, and changes nothing else
  cp -r $C $T/fix
  python3 scripts/check_vault.py records $T/fix --fix > /dev/null
  expect fix-files 2 "$(diff -rq $C $T/fix | wc -l)"
  expect fix-tmp 1 "$(diff -rq $C $T/fix | grep -c 'Only in .*: good-topic.md.tmp$')"
  expect fix-markup $'26,27d25\n< </content>\n< </invoke>' \
    "$(diff $C/topics/good-topic.md $T/fix/topics/good-topic.md)"
}

suite_fetch() {
  local F=test-fixtures/fetch
  # 1. JATS XML -> Markdown
  cp $F/2020_antaki_kahwati.md $T/
  python3 scripts/fetch_fulltext.py --record $T/2020_antaki_kahwati.md \
    --from-xml $F/PMC7658348_trimmed.xml > /dev/null
  same xml $T/2020_antaki_kahwati.md $F/expected_2020_antaki_kahwati.md
  # 2. an HTML page saved as .pdf is refused, the record untouched
  cp $F/2020_antaki_kahwati.md $T/rec.md
  python3 scripts/fetch_fulltext.py --record $T/rec.md \
    --from-pdf $F/html-error-page.pdf --source scihub-pdf | grep -q '"html-not-pdf: ' \
    || fail html-pdf "not refused as html-not-pdf"
  cmp -s $T/rec.md $F/2020_antaki_kahwati.md || fail html-pdf "record was changed"
  # 3. several records in one call; one bad record does not stop the others
  printf 'no header\n' > $T/bad.md
  python3 scripts/fetch_fulltext.py --record $T/2020_antaki_kahwati.md $T/bad.md \
    | python3 -c 'import json,sys; r=json.load(sys.stdin); \
        assert [x["id"] for x in r["records"]] == ["2020_antaki_kahwati", "bad"]; \
        assert r["still_abstract_only"] == ["bad"] and "error" in r["records"][1]' \
    || fail batch "the batch report is wrong"
}

suite_find_papers() {
  local B=test-fixtures/find-papers
  local F="--cache $B/cache.json --offline"
  local P1='("proliferative vitreoretinopathy" OR redetachment) AND (nomogram OR "deep learning" OR "machine learning")'
  local P2='("retinal detachment" OR redetachment) AND (recurrence OR recurrent OR "proliferative vitreoretinopathy") AND (nomogram OR "deep learning")'
  local BROAD='"retinal detachment" AND ("machine learning" OR "deep learning")'
  # in this order: each command reads what the one before it wrote
  cp -r $B/records/fixture-recall-20260924 $T/a
  local V=$T/a
  same seeds <(python3 scripts/find_papers.py seeds $V --profile $B/fixture-recall-20260924.md $F) \
    $B/expected_seeds.txt
  same pubmed <(python3 scripts/find_papers.py pubmed $V --list core-probe --fresh --max 40 \
    --query "$P1" --query "$P2" --query "$BROAD" $F) $B/expected_pubmed.txt
  same pubmed-top <(python3 scripts/find_papers.py pubmed $V --list background --max 40 --top 5 \
    --query "$BROAD" $F) $B/expected_pubmed_top.txt
  same chase1 <(python3 scripts/find_papers.py chase $V --list core-1 --max-citing 6 \
    --seed 2024_catania_chapron --seed 2023_gao_wu --seed 2026_xing_shao \
    --seed 2021_nobody_known $F) $B/expected_chase1.txt
  same show <(python3 scripts/find_papers.py show $V --list core-1 19 60 $F) $B/expected_show.txt
  same add-chase <(python3 scripts/find_papers.py add $V --no-fetch --list core-1 19 60 $F) \
    $B/expected_add_chase.json
  same add-probe <(python3 scripts/find_papers.py add $V --no-fetch --list core-probe 7 $F) \
    $B/expected_add_probe.json
  same wrong-list <(python3 scripts/find_papers.py add $V --no-fetch --list core-probe 19 $F) \
    $B/expected_wrong_list.json
  same chase2 <(python3 scripts/find_papers.py chase $V --list core-2 \
    --seed 2013_salapuigdollers_fernandez $F) $B/expected_chase2.txt
  same rec-savastano $V/2024_savastano_crincoli.md $B/expected_2024_savastano_crincoli.md
  same rec-salapuigdollers $V/2013_salapuigdollers_fernandez.md \
    $B/expected_2013_salapuigdollers_fernandez.md
  same rec-zhou $V/2023_zhou_lu.md $B/expected_2023_zhou_lu.md
  # add by PMID, on a fresh copy
  cp -r $B/records/fixture-recall-20260924 $T/b
  V=$T/b
  same add-pmid <(python3 scripts/find_papers.py add $V --no-fetch \
    --pmid 37013114 --pmid 40235812 --pmid 38682863 $F) $B/expected_add.json
  same pmid-zhou $V/2023_zhou_lu.md $B/expected_2023_zhou_lu.md
  same pmid-gan $V/2025_gan_cao_2.md $B/expected_2025_gan_cao_2.md
  cmp -s $V/2025_gan_cao.md $B/records/fixture-recall-20260924/2025_gan_cao.md \
    || fail pmid-collision "2025_gan_cao.md was changed"
}

suite_linker() {
  same report <(python3 scripts/link_papers.py --summaries test-fixtures/linker/summaries \
    --state test-fixtures/linker/state --offline --dry-run) test-fixtures/linker/expected_report.json
}

suite_stage_prep() {
  local B=test-fixtures/stage-prep
  local R=$B/records/fixture-prep-20260924
  same merge-dry <(python3 scripts/stage_prep.py merge $R --dry-run) $B/expected_merge.json
  same summaries <(python3 scripts/stage_prep.py summaries $R --regenerate --solo-kb 1) \
    $B/expected_summaries.json
  same keywords <(python3 scripts/stage_prep.py keywords $R --profile $B/fixture-prep-20260924.md) \
    $B/expected_keywords.txt
  # merge for real, and digest (both write), on a copy
  cp -r $R $T/
  local W=$T/fixture-prep-20260924
  python3 scripts/stage_prep.py merge $W > /dev/null
  expect merged-files $'2021_smith_jones.md\n2024_lee_park.md' "$(ls $W/.merged)"
  expect merged-header $'source: arxiv, pubmed\ndoi: 10.1000/jrec.2024.1\npmid: "38000001"' \
    "$(grep -E '^(source|doi|pmid):' $W/2023_lee_park.md)"
  expect merge-again 0 "$(python3 scripts/stage_prep.py merge $W | grep -c '"kept"')"
  python3 scripts/stage_prep.py digest $W --topic survival-analysis:time-to-event-prediction > /dev/null
  same digest $W/.digests/survival-analysis.md $B/expected_digest_survival-analysis.md
}

suite_stage_prep_deep_dive() {
  local B=test-fixtures/stage-prep/deep-dive
  local P=$B/fixture-dd-20260925.md
  local V=$B/vault/fixture-dd-20260925
  local ID=survival-analysis-deep-dive-20260925
  cp -r $B/records/fixture-dd-20260925 $T/
  local R=$T/fixture-dd-20260925
  tp() { python3 scripts/stage_prep.py topic $R --profile $P "$@"; }

  same existing <(tp --topic survival-analysis --vault $V --snapshot $ID) $B/expected_topic_existing.txt
  case "$(tp --topic survival-analysis --snapshot $ID | tail -1)" in
    "Snapshot: kept the existing"*) ;;
    *) fail snapshot-kept "a second --snapshot did not keep the first" ;;
  esac
  same alias <(tp --topic time-to-event --vault $V) $B/expected_topic_alias.txt
  same new-one <(tp --topic competing-risks) $B/expected_topic_new_one.txt
  same new-none <(tp --topic ultra-widefield-imaging) $B/expected_topic_new_none.txt
  same obsidian-only <(tp --topic hand-topic --vault $V) $B/expected_topic_obsidian_only.txt

  # the deep-dive's search saves four records; three get summaries
  cp $B/new/*.md $R/
  cp $B/new/summaries/*.md $R/summaries/
  same since <(tp --topic survival-analysis --since $ID) $B/expected_topic_since.txt
  python3 scripts/stage_prep.py digest $R --topic survival-analysis:time-to-event --since $ID > /dev/null
  same digest-since $R/.digests/survival-analysis.md $B/expected_digest_since.md
  tp --topic survival-analysis --since nope > /dev/null
  expect since-unknown-exit 2 $?
  tp --topic survival-analysis --since $ID --snapshot $ID > /dev/null
  expect since-and-snapshot-exit 2 $?

  # keywords marks a note a deep-dive wrote
  sed -i 's/^related_problem: .*/&\ndeep_dive: '$ID'/' $R/topics/survival-analysis.md
  expect keywords-deep-dive 1 \
    "$(python3 scripts/stage_prep.py keywords $R --profile $P | grep -c 'deep-dive)')"

  # an old-id vault is refused
  cp -r $B/records/fixture-dd-20260925 $T/old
  sed -i 's/^id: 2021_smith_jones$/id: smith-cox-models-20260924/' \
    $T/old/summaries/2021_smith_jones_summary.md
  expect old-ids 1 "$(python3 scripts/stage_prep.py topic $T/old --profile $P \
    --topic survival-analysis | grep -c '^WARNING: old-style ids')"
}

suite_vault_build() {
  local B=test-fixtures/vault-build
  build() { python3 scripts/build_vault.py --profile $B/fixture-vault-20260924.md \
    --records $B/records/fixture-vault-20260924 --vault $1 --offline ${2:-}; }
  # first run into an empty vault
  build $T/first/fixture-vault-20260924 > /dev/null
  same first -r $T/first $B/expected-first
  # re-run over a vault the researcher has edited, with one rebuilt topic
  cp -r $B/expected-first $T/rerun
  patch -s -d $T/rerun -p1 < $B/researcher-edits.patch
  build $T/rerun/fixture-vault-20260924 "--rebuilt-topics survival-analysis" > /dev/null
  same rerun -r $T/rerun $B/expected-rerun
  expect dead-links 1 \
    "$(python3 scripts/check_vault.py vault $T/rerun/fixture-vault-20260924 | grep -c '"dead_count": 0,')"
  # idempotent: building either vault again merges nothing
  expect idempotent-first 1 \
    "$(build $T/first/fixture-vault-20260924 | grep -c '"merged": \[\],')"
  expect idempotent-rerun 1 \
    "$(build $T/rerun/fixture-vault-20260924 "--rebuilt-topics survival-analysis" | grep -c '"merged": \[\],')"
}

[ $# -gt 0 ] && SUITES=("$@")
status=0
for name in "${SUITES[@]}"; do
  fn="suite_${name//-/_}"
  if ! declare -F "$fn" > /dev/null; then
    echo "unknown suite: $name (suites: check-vault fetch find-papers linker stage-prep stage-prep-deep-dive vault-build)"
    status=1
    continue
  fi
  T=$(mktemp -d)
  LOG=$T.log
  : > "$LOG"
  ("$fn") 2> "$T.err"
  if [ -s "$LOG" ]; then
    echo "FAIL $name"
    head -n 12 "$LOG" | sed 's/^/  /'
    [ -s "$T.err" ] && tail -n 5 "$T.err" | sed 's/^/  stderr: /'
    status=1
  else
    echo "PASS $name"
  fi
  rm -rf "$T" "$LOG" "$T.err"
done
exit $status
