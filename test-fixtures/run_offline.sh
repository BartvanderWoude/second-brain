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

ALL=(check-vault fetch find-papers linker plugin-root schema-copies stage-prep stage-prep-deep-dive vault-build
     graphcreator causal-graph)
SUITES=("${ALL[@]}")

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
  # a record in .excluded/ counts as in the vault, on a third copy
  cp -r $B/records/fixture-recall-20260924 $T/c
  V=$T/c
  expect excluded-listed 1 "$(python3 scripts/find_papers.py pubmed $V --list pair-1 --max 40 \
    --query "$P2" $F | grep -c '^1\. 2023 Zhou')"
  mkdir $V/.excluded; cp $B/expected_2023_zhou_lu.md $V/.excluded/2023_zhou_lu.md
  same add-excluded <(python3 scripts/find_papers.py add $V --no-fetch --list pair-1 1 $F) \
    $B/expected_add_excluded.json
  expect excluded-not-saved 0 "$(ls $V/2023_zhou_lu.md 2> /dev/null | wc -l)"
  same pubmed-excluded <(python3 scripts/find_papers.py pubmed $V --list pair-1 --max 40 \
    --query "$P2" $F) $B/expected_pubmed_excluded.txt
}

suite_linker() {
  same report <(python3 scripts/link_papers.py --summaries test-fixtures/linker/summaries \
    --state test-fixtures/linker/state --offline --dry-run) test-fixtures/linker/expected_report.json
}

suite_plugin_root() {
  awk '/^## Before stage 3/{s=1} s && /^```bash/{p=1; next} p && /^```/{exit} p' \
    skills/second-brain-pipeline/SKILL.md > "$T/resolve.sh"
  mk() { mkdir -p "$1/.claude-plugin" "$1/templates" "$1/scripts"; echo "{\"name\": \"$2\"}" > "$1/.claude-plugin/plugin.json"; }
  root() { (cd "$1" && env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS HOME="$2" "${@:3}" bash "$T/resolve.sh"); }
  local P=.claude/plugins
  mkdir -p "$T/proj/scripts" "$T/proj/templates"; mk "$T/home1/$P/marketplaces/arxiv-mcp" arxiv-mcp-server
  expect dev "plugin root: $(pwd -P)|wave size: 20" "$(root "$PWD" "$T/home1" | paste -sd'|')"
  expect look-alike "plugin root: NOT FOUND" "$(root "$T/proj" "$T/home1" | head -1)"
  expect env-var "plugin root: $PWD" "$(root "$T/proj" "$T/home1" CLAUDE_PLUGIN_ROOT="$PWD" | head -1)"
  mk "$T/home2/$P/cache/sbr/second-brain-researcher/0.1.0" second-brain-researcher
  mk "$T/home2/$P/marketplaces/second-brain-researcher" second-brain-researcher
  expect marketplace "plugin root: $T/home2/$P/marketplaces/second-brain-researcher" \
    "$(root "$T/proj" "$T/home2" | head -1)"
  echo "{\"plugins\": {\"second-brain-researcher@sbr\": [{\"installPath\": \"$T/home2/$P/cache/sbr/second-brain-researcher/0.1.0\"}]}}" \
    > "$T/home2/$P/installed_plugins.json"
  expect installed "plugin root: $T/home2/$P/cache/sbr/second-brain-researcher/0.1.0" \
    "$(root "$T/proj" "$T/home2" | head -1)"
  # the causal-graph skill's copy of the call is the pipeline's, byte for byte
  awk '/^## Plugin root/{s=1} s && /^```bash/{p=1; next} p && /^```/{exit} p' \
    skills/second-brain-causal-graph/SKILL.md > "$T/resolve-causal.sh"
  same causal-copy "$T/resolve.sh" "$T/resolve-causal.sh"
}

suite_schema_copies() {
  fields_spec() { awk -F' *[|] *' '/^[|] `[a-z_]+`/ {print $2}' \
      templates/research-problem-profile-format-spec.md | tr -d '`' | sort -u; }
  fields_intake() { awk '/^ *```yaml/{p=1;next} /^ *```/{p=0} p' skills/research-problem-intake/SKILL.md \
      skills/research-problem-intake/deep-dive.md skills/second-brain-causal-graph/SKILL.md \
      | grep -oE '^ *[a-z_]+:' | tr -d ' :' | sort -u; }
  same fields <(fields_intake) <(fields_spec)
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

suite_graphcreator() {
  local B=test-fixtures/graphcreator
  local G=scripts/graphcreator.py c out
  awk '/^## Example/{s=1} s && /^```yaml/{p=1; next} p && /^```/{exit} p' \
    templates/graphcreator-dag-format.md > $T/example.dag.yaml
  grep -v -e '^    pos: ' -e '^    form: ' $T/example.dag.yaml > $T/example-bare.dag.yaml
  same example <(python3 $G < $B/example.json) $T/example.dag.yaml
  same example-bare <(python3 $G < $B/example-bare.json) $T/example-bare.dag.yaml
  for c in quoting signs empties numbers empty-graph; do
    same $c <(python3 $G < $B/$c.json) $B/expected_$c.dag.yaml
  done
  for c in warnings invalid-cycle invalid-duplicate-name invalid-dangling invalid-unknown-key \
      invalid-shares-count invalid-unit-categorical invalid-other; do
    same $c <(python3 $G --validate < $B/$c.json) $B/expected_$c.json
  done
  python3 $G < $B/warnings.json > $T/warnings.dag.yaml 2> /dev/null
  expect warnings-exit 0 $?
  python3 $G < $B/invalid-cycle.json > $T/out.yaml 2> $T/err.txt
  expect refused-exit 2 $?
  expect refused-stdout 0 "$(wc -c < $T/out.yaml | tr -d ' ')"
  expect refused-stderr "invalid graph:" "$(head -1 $T/err.txt)"
  out=$(python3 $B/roundtrip.py $B/example.json $T/example.dag.yaml \
    $B/example-bare.json $T/example-bare.dag.yaml \
    $B/quoting.json $B/expected_quoting.dag.yaml $B/signs.json $B/expected_signs.dag.yaml \
    $B/empties.json $B/expected_empties.dag.yaml $B/numbers.json $B/expected_numbers.dag.yaml \
    $B/empty-graph.json $B/expected_empty-graph.dag.yaml $B/warnings.json $T/warnings.dag.yaml \
    2> /dev/null) && [ -z "$out" ] || fail roundtrip "${out:-roundtrip.py failed}"
}

suite_causal_graph() {
  local B=test-fixtures/causal-graph
  local C=test-fixtures/causal
  local P=$C/fixture-causal-20261119.md
  local VJ=$C/variables.json
  local G="python3 scripts/causal_graph.py"
  local out
  export SOURCE_DATE_EPOCH=1795046400    # the evidence report's date: 2026-11-19

  # the commands move and rewrite files, so run them on a copy, in this order
  cp -r $C/records/fixture-causal-20261119 $T/
  local V=$T/fixture-causal-20261119
  same exclude <($G exclude $V --profile $P) $B/expected_exclude.json
  expect excluded-files "./.excluded/2018_keane_lowe.md ./.excluded/claims/2018_keane_lowe.json" \
    "$(cd $V && find . -name '2018_keane_lowe*' | sort | paste -sd' ')"
  same exclude-again <($G exclude $V --profile $P) $B/expected_exclude_again.json
  same check <($G check $V) $B/expected_check.json
  same check-again <($G check $V) $B/expected_check.json
  same check-file $V/claims/2019_carver_dunn.json $B/expected_2019_carver_dunn.json
  same names <($G names $V --variables $T/variables.json --out $T/names.txt | sed "s|$T/|\$T/|") \
    $B/expected_names.json
  same names-txt $T/names.txt $C/names.txt
  sed 's/"diabetes mellitus", "DM"/"diabetes mellitus"/' $VJ > $T/variables-no-dm.json
  same names-new <($G names $V --variables $T/variables-no-dm.json --new-only --out $T/names-new.txt \
    | sed "s|$T/|\$T/|") $B/expected_names_new.json
  same names-new-txt $T/names-new.txt $B/expected_names_new.txt
  same pairs <($G pairs $V --variables $VJ --profile $P --out $T/pairs.json | sed "s|$T/|\$T/|") \
    $B/expected_pairs_report.json
  same pairs-json $T/pairs.json $B/expected_pairs.json
  same upstream <($G upstream $V --variables $VJ --profile $P --out $T/upstream.json \
    | sed "s|$T/|\$T/|") $B/expected_upstream_report.json
  same upstream-json $T/upstream.json $B/expected_upstream.json
  awk '/^setting_terms:/ {skip = 1; next} skip && /^  - / {next} {skip = 0; print}' $P > $T/no-setting.md
  $G upstream $V --variables $VJ --profile $T/no-setting.md --out $T/up-no-setting.json > /dev/null
  expect up-no-setting "{None}" "$(python3 -c "import json,sys; \
    print({e['fallback'] for e in json.load(open(sys.argv[1]))['entries']})" $T/up-no-setting.json)"
  grep -v '^upstream_search_' $P > $T/up-defaults.md
  expect up-defaults "5 15 5" "$($G upstream $V --variables $VJ --profile $T/up-defaults.md \
    --out $T/up-defaults.json | python3 -c "import json,sys; r=json.load(sys.stdin); \
    m=json.load(open('$T/up-defaults.json'))['max_papers']; print(r['k'], m, r['entries'])")"
  sed 's/^setting_terms:$/setting_terms: surgery/' $P > $T/up-bad.md
  $G upstream $V --variables $VJ --profile $T/up-bad.md --out $T/up-bad.json > $T/up-bad.out
  expect up-bad '2 {"error": "setting_terms is not a list: surgery"}' "$? $(cat $T/up-bad.out)"
  cp -r $V $T/up-none; python3 -c "
import json, sys; f = sys.argv[1]; d = json.load(open(f))
d['claims'] = [c for c in d['claims'] if c['cause'] != 'leisure-time physical activity']; json.dump(d, open(f, 'w'))" \
    $T/up-none/claims/2019_carver_dunn.json
  $G upstream $T/up-none --variables $VJ --profile $P --out $T/up-none.json > /dev/null
  expect up-none 0 "$(python3 -c "import json; \
    print(sum(e['a'] == 'Physical activity' for e in json.load(open('$T/up-none.json'))['entries']))")"
  same assemble <($G assemble $V --variables $VJ --profile $P --out $T/out) $B/expected_assemble.json
  same assemble-files -r $T/out $B/expected
  out=$(python3 $B/validate_dags.py $V $VJ $P $T/out 2>&1) && [ -z "$out" ] \
    || fail validate-dags "${out:-validate_dags.py failed}"

  # an edge out of a cause into a variable with no path into the target is in neither graph
  cp -r $V $T/side; python3 -c "
import json, sys
f, vj, out = sys.argv[1:]
d = json.load(open(f)); c = dict(d['claims'][0])
c.update(cause='diabetes', effect='retinopathy', cause_level=None, cause_reference=None, effect_level=None)
d['claims'].append(c); json.dump(d, open(f, 'w'))
v = json.load(open(vj)); v['nodes'].append({'name': 'Retinopathy', 'aliases': ['retinopathy']})
json.dump(v, open(out, 'w'))" $T/side/claims/2020_ashford_bell.json $VJ $T/variables-side.json
  expect off-path "strict:Retinopathy full:Retinopathy" \
    "$($G assemble $T/side --variables $T/variables-side.json --profile $P --out $T/side-out \
      | python3 -c "import json,sys; \
        print(' '.join(d['graph']+':'+d['to'] for d in json.load(sys.stdin)['off_path']))")"
  expect off-path-dags 0 "$(cat $T/side-out/*.dag.yaml | grep -c 'Retinopathy')"

  # timing: a copy of variables.json with tags changed, "node:key:json value" each
  tag() { python3 -c "
import json, sys
v = json.load(open(sys.argv[1]))
for arg in sys.argv[3:]:
    name, key, val = arg.split(':', 2)
    [n for n in v['nodes'] if n['name'] == name][0][key] = json.loads(val)
json.dump(v, open(sys.argv[2], 'w'))" "$@"; }
  tag $VJ $T/variables-timing.json 'Operative duration:timing:"target_measure"' 'BMI:timing:"later"' \
    'Physical activity:exogenous:true'
  expect timing "['Operative duration'] ['BMI'] ['BMI>Physical activity'] 0 [5, 6]" \
    "$($G assemble $V --variables $T/variables-timing.json --profile $P --out $T/timing-out | python3 -c "
import json,sys; r=json.load(sys.stdin)
print(r['target_measures'], r['later'], [d['from']+'>'+d['to'] for d in r['into_exogenous']], len(r['cycle_drops']), r['edges'])")"
  expect timing-measure-dags 0 "$(cat $T/timing-out/*.dag.yaml | grep -c 'Operative duration')"
  expect timing-later-dags 2 "$(cat $T/timing-out/*.dag.yaml \
    | grep -cF 'Body mass index before surgery. Measured after the prediction time.')"
  expect timing-evidence 4 "$(grep -cE '^- (Timing: later, measured after the prediction time|Timing: baseline; exogenous|Operative duration: a measure of the target, not a cause; its edges left out of both graphs: Operative duration → Fixture outcome|BMI → Physical activity: suggested \(1\); nothing in the graph causes Physical activity)' \
    $T/timing-out/fixture-causal-20261119.evidence.md)"
  tag $VJ $T/variables-tags.json 'Diabetes:exogenous:true' 'Physical activity:exogenous:true' \
    'BMI:timing:"target_measure"'
  $G pairs $V --variables $T/variables-tags.json --profile $P --out $T/pairs-tags.json > /dev/null
  expect pairs-tags "Diabetes-Fixture prophylaxis, Physical activity-Fixture prophylaxis" \
    "$(python3 -c "import json; \
    print(', '.join(p['a']+'-'+p['b'] for p in json.load(open('$T/pairs-tags.json'))['pairs']))")"
  $G upstream $V --variables $T/variables-tags.json --profile $P --out $T/up-tags.json > /dev/null
  expect up-tags "1 Fixture prophylaxis, 2 Operative duration, 3 Smoking" \
    "$(python3 -c "import json; \
    print(', '.join(str(e['n'])+' '+e['a'] for e in json.load(open('$T/up-tags.json'))['entries']))")"
  tag $VJ $T/variables-bad-timing.json 'BMI:timing:"preoperative"'
  $G assemble $V --variables $T/variables-bad-timing.json --profile $P --out $T/bad-timing > $T/bad-timing.out
  expect bad-timing "2 {\"error\": \"variables file variables-bad-timing.json: node 'BMI': timing 'preoperative' is not one of baseline, later, target_measure, unknown\"}" \
    "$? $(cat $T/bad-timing.out)"

  # refused: a profile whose causal_target is not variables.json's target
  sed 's/^causal_target: .*/causal_target: Other outcome/' $P > $T/other-target.md
  same bad-target <($G assemble $V --variables $VJ --profile $T/other-target.md --out $T/bad) \
    $B/expected_bad_target.json
  $G assemble $V --variables $VJ --profile $T/other-target.md --out $T/bad > /dev/null
  expect bad-target-exit 2 $?
  expect bad-target-files 0 "$(ls $T/bad 2> /dev/null | wc -l)"

  # no claims at all: the target alone, said in the report's first line
  mkdir $T/empty
  same empty <($G assemble $T/empty --variables $VJ --profile $P --out $T/empty-out) \
    $B/expected_empty.json
  expect empty-first-line 1 "$(head -1 $T/empty-out/fixture-causal-20261119.evidence.md \
    | grep -c '^\*\*No claim into the target')"

  # plan, last: it needs a record without claims
  same plan-none <($G plan $V) $B/expected_plan_none.json
  rm $V/claims/2022_ellery_finch.json
  same plan <($G plan $V) $B/expected_plan.json
  same plan-solo <($G plan $V --redo --solo-kb 1) $B/expected_plan_solo.json
}

[ $# -gt 0 ] && SUITES=("$@")
status=0
for name in "${SUITES[@]}"; do
  fn="suite_${name//-/_}"
  if ! declare -F "$fn" > /dev/null; then
    echo "unknown suite: $name (suites: ${ALL[*]})"
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
