# causal_graph fixture

Offline test for `scripts/causal_graph.py`, on a copy of the shared causal
fixture `test-fixtures/causal/` (its README says what each record holds). From
the repo root, `$T` a temp dir:

```
B=test-fixtures/causal-graph
C=test-fixtures/causal
P=$C/fixture-causal-20261119.md
VJ=$C/variables.json
G="python3 scripts/causal_graph.py"
export SOURCE_DATE_EPOCH=1795046400    # the evidence report's date: 2026-11-19

# the commands move and rewrite files, so run them on a copy, in this order
cp -r $C/records/fixture-causal-20261119 $T/; V=$T/fixture-causal-20261119
diff <($G exclude $V --profile $P) $B/expected_exclude.json
(cd $V && find . -name '2018_keane_lowe*' | sort | paste -sd' ')   # ./.excluded/2018_keane_lowe.md ./.excluded/claims/2018_keane_lowe.json
diff <($G exclude $V --profile $P) $B/expected_exclude_again.json
diff <($G check $V) $B/expected_check.json
diff <($G check $V) $B/expected_check.json
diff $V/claims/2019_carver_dunn.json $B/expected_2019_carver_dunn.json
diff <($G names $V --variables $T/variables.json --out $T/names.txt | sed "s|$T/|\$T/|") \
     $B/expected_names.json
diff $T/names.txt $C/names.txt
sed 's/"diabetes mellitus", "DM"/"diabetes mellitus"/' $VJ > $T/variables-no-dm.json
diff <($G names $V --variables $T/variables-no-dm.json --new-only --out $T/names-new.txt \
        | sed "s|$T/|\$T/|") $B/expected_names_new.json
diff $T/names-new.txt $B/expected_names_new.txt
diff <($G pairs $V --variables $VJ --profile $P --out $T/pairs.json | sed "s|$T/|\$T/|") \
     $B/expected_pairs_report.json
diff $T/pairs.json $B/expected_pairs.json
diff <($G upstream $V --variables $VJ --profile $P --out $T/upstream.json | sed "s|$T/|\$T/|") \
     $B/expected_upstream_report.json
diff $T/upstream.json $B/expected_upstream.json
awk '/^setting_terms:/ {skip = 1; next} skip && /^  - / {next} {skip = 0; print}' $P > $T/no-setting.md
$G upstream $V --variables $VJ --profile $T/no-setting.md --out $T/up-no-setting.json > /dev/null
python3 -c "import json,sys; print({e['fallback'] for e in json.load(open(sys.argv[1]))['entries']})" \
  $T/up-no-setting.json                                                                            # {None}
grep -v '^upstream_search_' $P > $T/up-defaults.md
$G upstream $V --variables $VJ --profile $T/up-defaults.md --out $T/up-defaults.json \
  | python3 -c "import json,sys; r=json.load(sys.stdin); m=json.load(open('$T/up-defaults.json'))['max_papers']; print(r['k'], m, r['entries'])"   # 5 15 5
sed 's/^setting_terms:$/setting_terms: surgery/' $P > $T/up-bad.md
$G upstream $V --variables $VJ --profile $T/up-bad.md --out $T/up-bad.json > $T/up-bad.out; echo $? $(cat $T/up-bad.out)   # 2 {"error": "setting_terms is not a list: surgery"}
cp -r $V $T/up-none; python3 -c "
import json, sys; f = sys.argv[1]; d = json.load(open(f))
d['claims'] = [c for c in d['claims'] if c['cause'] != 'leisure-time physical activity']; json.dump(d, open(f, 'w'))" \
  $T/up-none/claims/2019_carver_dunn.json
$G upstream $T/up-none --variables $VJ --profile $P --out $T/up-none.json > /dev/null
python3 -c "import json; print(sum(e['a'] == 'Physical activity' for e in json.load(open('$T/up-none.json'))['entries']))"   # 0
diff <($G assemble $V --variables $VJ --profile $P --out $T/out) $B/expected_assemble.json
diff -r $T/out $B/expected
python3 $B/validate_dags.py $V $VJ $P $T/out

# an edge out of a cause into a variable with no path into the target is in neither graph
cp -r $V $T/side; python3 -c "
import json, sys
f, vj, out = sys.argv[1:]
d = json.load(open(f)); c = dict(d['claims'][0])
c.update(cause='diabetes', effect='retinopathy', cause_level=None, cause_reference=None, effect_level=None)
d['claims'].append(c); json.dump(d, open(f, 'w'))
v = json.load(open(vj)); v['nodes'].append({'name': 'Retinopathy', 'aliases': ['retinopathy']})
json.dump(v, open(out, 'w'))" $T/side/claims/2020_ashford_bell.json $VJ $T/variables-side.json
$G assemble $T/side --variables $T/variables-side.json --profile $P --out $T/side-out \
  | python3 -c "import json,sys; print(' '.join(d['graph']+':'+d['to'] for d in json.load(sys.stdin)['off_path']))"   # strict:Retinopathy full:Retinopathy
cat $T/side-out/*.dag.yaml | grep -c 'Retinopathy'                                                 # 0

# refused: a profile whose causal_target is not variables.json's target
sed 's/^causal_target: .*/causal_target: Other outcome/' $P > $T/other-target.md
diff <($G assemble $V --variables $VJ --profile $T/other-target.md --out $T/bad) $B/expected_bad_target.json
$G assemble $V --variables $VJ --profile $T/other-target.md --out $T/bad > /dev/null; echo $?   # 2
ls $T/bad 2> /dev/null | wc -l                                                                     # 0

# no claims at all: the target alone, said in the report's first line
mkdir $T/empty
diff <($G assemble $T/empty --variables $VJ --profile $P --out $T/empty-out) $B/expected_empty.json
head -1 $T/empty-out/fixture-causal-20261119.evidence.md | grep -c '^\*\*No claim into the target'   # 1

# plan, last: it needs a record without claims
diff <($G plan $V) $B/expected_plan_none.json
rm $V/claims/2022_ellery_finch.json
diff <($G plan $V) $B/expected_plan.json
diff <($G plan $V --redo --solo-kb 1) $B/expected_plan_solo.json
```

`bash test-fixtures/run_offline.sh causal-graph` runs the commands above and
checks every expectation below; change the README and the runner together.

Every `diff` and `validate_dags.py` print nothing when they pass; the lines
with a trailing comment (other than the `export`) must print what their
comments say. Nothing writes into the
fixture. `SOURCE_DATE_EPOCH` fixes the date the evidence report prints, so it
can be diffed. `validate_dags.py` rebuilds both graphs, checks them with
`graphcreator.validate` (no errors) and checks each written `.dag.yaml` is
exactly `graphcreator.dump` of its graph; nothing reads YAML back.

What the outputs must show:

- `exclude`: the profile's one `exclude_papers` entry, a title with an
  upper-case DOI, matches `2018_keane_lowe` by DOI; the record and its claims
  file move to `.excluded/` and `.excluded/claims/`. Run again, the entry
  matches the record already aside, reported as `.excluded/2018_keane_lowe`,
  and nothing is `not_found`.
- `check`: 4 papers, 13 claims kept, 1 rejected: the planted claim of
  `2019_carver_dunn` (diabetes mellitus → leisure-time physical activity),
  `quote not found`, and nothing else. The quotes that pass include ones that
  span line breaks, carry `–`, `−` and `²`, and join two fragments with
  `...`. `presents_dag` names `2023_garner_hale`. Run again, the report is the
  same and the rewritten file unchanged: the rejected claim sits in
  `rejected` with `kind` and `reason`, the other three claims are kept.
- `names`, pass 1 (`variables.json` does not exist yet): exactly the shared
  fixture's `names.txt`: 14 names, the excluded paper's and the rejected
  claim's uses not counted. `--new-only` against a `variables.json` without
  the alias `DM`: only `dm` (`comorbidities` is in `unmapped`, so it is not
  new).
- `pairs`: k 3 from the profile; support Diabetes 3, Physical activity 3,
  BMI 2; Physical activity–BMI already linked; two pairs, Diabetes–Physical
  activity (6) then Diabetes–BMI (5), `a` the better-supported node and
  Diabetes first on the tie by name; each query block the node's name and
  aliases, normalized, multi-word terms quoted; `narrow` adds the design
  block; `max_papers` 10 from the profile.
- `upstream`: k 4 and `max_papers` 6 from the profile. The causes of the
  target are six nodes; ranked by the same support as `pairs` (Diabetes 3,
  Physical activity 3, BMI 2, then Fixture prophylaxis, Operative duration
  and Smoking at 1), the top four are kept, Fixture prophylaxis taking the
  last place on the tie by name. Each `query` is the node's `pairs` block AND
  the risk-factor block AND the review block; each `fallback` the node block
  AND the risk-factor block AND the setting block from the profile's
  `setting_terms` (`"fixture surgery"` quoted, `surgical`, `postoperative`).
  A copy without carver_dunn's physical-activity claim leaves Physical
  activity with only a `none` claim into the target: it is no cause, so it
  gets no entry.
  A profile copy without `setting_terms` gives `fallback: null` on every
  entry; one without `upstream_search_k` and `upstream_search_max_papers`
  takes their defaults, 5 and 15 (five of the six causes). A scalar
  `setting_terms` exits 2 with an `error`.
- `assemble` (report, the two DAGs, the evidence report under `expected/`):
  - strict 6 nodes, 5 edges, 4 into the target; full 7 nodes, 7 edges, 6 into
    the target; one cycle drop.
  - Diabetes → Fixture outcome: the adjusted cohort (probable) against a
    case-control in the opposite direction (`diabetic` / `non-diabetic` and
    `FO` mapped): the weaker contrary claim does not downgrade it; `positive`,
    `medium` (OR 2.1, d 0.41). Its evidence lists the cohort and the
    other-setting cohort, which agrees; the case-control is named in the
    report as contrary, not in `evidence`.
  - Smoking → Fixture outcome: the per-level sign map against the reference
    `never`, centred: `{never: negative, former: negative, current: positive}`,
    `medium` (median d 0.33 of two ORs).
  - BMI → Fixture outcome: per-unit OR, `positive`, no strength.
  - Fixture prophylaxis → Fixture outcome: the trial, established, `negative`,
    `small` (RR read as an OR, d 0.25).
  - Physical activity → BMI: standardized beta −0.34, `negative`, `medium`.
  - Physical activity → Fixture outcome: the case-control's claim (suggested)
    meets a `none` claim of equal grade from the other-setting cohort: a
    conflict, so speculative, full graph only.
  - Operative duration → Fixture outcome: `unclear`, from the other-setting
    cohort (one grade lower, suggested): no sign, no strength, full only.
  - BMI → Physical activity: the other-setting cohort (suggested), the reverse
    of Physical activity → BMI: the cycle in the full graph drops it as the
    lowest grade; it is not in the strict graph at all.
  - shares: Fixture outcome `[0.915, 0.085]` (median of 9% and 8%), Diabetes
    `[0.82, 0.18]` (the other setting's 25% not used, the excluded 40% gone),
    Smoking `[0.48, 0.3, 0.22]` (`never smoked` through `level_map`).
  - `comorbidities`: one unmapped claim; `presents_dag`: `2023_garner_hale`;
    one excluded paper; no warnings; `off_path` empty (every node leads
    into the target).
- ancestors only: a copy with one extra adjusted-cohort claim, Diabetes →
  Retinopathy, and a Retinopathy node with no path into the target. The edge
  is probable, yet it is in neither graph: `off_path` lists it for both, and
  neither DAG names Retinopathy.
- refused: a profile whose `causal_target` differs from `variables.json`'s
  target exits 2 with an `error` and writes nothing.
- an empty vault: both graphs hold the target alone, the report warns, and the
  evidence report's first line says there is no claim into the target.
- `plan`: with every record's claims file present, nothing to extract; with
  one claims file deleted, that record alone; `--redo --solo-kb 1` plans each
  record alone, `2020_ashford_bell` with `read_until` before its
  `## References`.
