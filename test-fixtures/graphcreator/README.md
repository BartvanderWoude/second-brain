# GraphCreator writer

Offline test for `scripts/graphcreator.py`, which validates a causal graph and
writes it in the format of `templates/graphcreator-dag-format.md`. Each
`<case>.json` is a graph as the plain dict the writer takes. From the repo
root, `$T` a temp dir:

```
B=test-fixtures/graphcreator
G=scripts/graphcreator.py
awk '/^## Example/{s=1} s && /^```yaml/{p=1; next} p && /^```/{exit} p' \
  templates/graphcreator-dag-format.md > $T/example.dag.yaml
grep -v -e '^    pos: ' -e '^    form: ' $T/example.dag.yaml > $T/example-bare.dag.yaml
diff <(python3 $G < $B/example.json) $T/example.dag.yaml
diff <(python3 $G < $B/example-bare.json) $T/example-bare.dag.yaml
for c in quoting signs empties numbers empty-graph; do
  diff <(python3 $G < $B/$c.json) $B/expected_$c.dag.yaml
done
for c in warnings invalid-cycle invalid-duplicate-name invalid-dangling invalid-unknown-key \
    invalid-shares-count invalid-unit-categorical invalid-other; do
  diff <(python3 $G --validate < $B/$c.json) $B/expected_$c.json
done
python3 $G < $B/warnings.json > $T/warnings.dag.yaml 2> /dev/null; echo $?   # 0
python3 $G < $B/invalid-cycle.json > $T/out.yaml 2> $T/err.txt; echo $?     # 2
wc -c < $T/out.yaml                                                          # 0
head -1 $T/err.txt                                                           # invalid graph:
python3 $B/roundtrip.py $B/example.json $T/example.dag.yaml \
  $B/example-bare.json $T/example-bare.dag.yaml \
  $B/quoting.json $B/expected_quoting.dag.yaml $B/signs.json $B/expected_signs.dag.yaml \
  $B/empties.json $B/expected_empties.dag.yaml $B/numbers.json $B/expected_numbers.dag.yaml \
  $B/empty-graph.json $B/expected_empty-graph.dag.yaml $B/warnings.json $T/warnings.dag.yaml
```

`bash test-fixtures/run_offline.sh graphcreator` runs the commands above and
checks every expectation below; change the README and the runner together.

Every `diff` and the round trip print nothing when they pass; the four
commented lines must print what their comments say. Nothing writes into the
fixture.

What each tests:

- `example.json` is the format's own example: the writer's output must equal
  the YAML block under "## Example" in the format, byte for byte.
  `example-bare.json` is the same graph without `pos` and `form`, and must
  equal that block with those lines removed.
- `quoting.json` covers the format's "Text and YAML 1.1" list: YAML 1.1
  booleans and null in all three casings (`no`, `Yes`, `NULL`, `~`, `n`, `y`,
  `Off`, `TRUE`), YAML 1.1 and 1.2 numbers (`1_000`, `0x1F`, `0o17`, `1:30`,
  `.inf`, `.nan`, `1e3`, `3.5`), dates (`2024-01-31`, `2024-01-31 10:00:00`),
  `<<` and `=`; and text YAML 1.2 requires quoted: `a: b`, a trailing `:`,
  ` #`, a leading or trailing space, a leading indicator (`#`, `-`, `"`, `` ` ``,
  `@`, `%`), a line break and a tab (escaped), a backslash, and in flow
  collections `,`, `[`, `]` and `:`. Text that needs no quotes stays plain:
  `BMI (kg/m²)`, `kg/m²`, `a:b` and `1:30 pm` inside a description,
  `say "hi" here`. Node names are compared and written stripped: the node
  `" Age "` is written `Age`, and the edges naming `Age`, `"a: b "` and
  `" no"` resolve. Evidence is always quoted. The sign map's keys
  (`Yes`, `NULL`, `~`) are quoted and in level order.
- `signs.json` covers every sign shape of the format's sign table: maps over a
  nominal cause's levels (`Smoking`, `Wound class`) and a binary cause's
  (`Sex`, `Diabetes` with quoted `"no"`, `"yes"`), each given out of order and
  written in level order; a map over a nominal effect's levels
  (`Age → Wound class`); one word on a binary cause, an ordinal cause and a
  continuous one; and no sign between two nominal nodes. No warnings.
- `empties.json`: a blank graph name, `locked: false`, `role: other`, null
  values, empty `levels` on a continuous node, empty and blank description,
  unit and note, an empty sign map and empty evidence are all left out.
- `numbers.json`: `locked: true` is written; shares are rounded to 3 decimals,
  a whole share written without a decimal point (`[1, 0]`, from `[1.0, 0.0]`,
  `[0.9996, 0.0004]` and `[0, 1]`); `pos` is rounded to whole numbers.
- `empty-graph.json`: `nodes: []` and `edges: []` are written when empty.
- `warnings.json` holds every warning the format lists and no error, so it is
  still written (exit 0): an untyped node, one level, a level twice, shares
  adding up to 0.9 (`Close sum`, 1.001, is within 0.001 and gives none), a
  form on a node without causes (`Lonely`; `Measure` has causes and gives
  none), one word on a three-level cause, one word towards a nominal effect,
  a sign between two nominal nodes, a map on an untyped cause, and maps
  naming levels the node does not have. One word on a two-level or ordinal
  cause fits and gives none.
- `invalid-*.json` hold what GraphCreator refuses, each as `--validate`'s
  JSON: a directed cycle; a duplicate name after stripping (`age` is a
  different node); edges to and from missing nodes; unknown keys at the top
  level, in a node and in an edge; three shares for two levels; a unit on a
  categorical node. `invalid-other.json` holds the rest: a missing schema,
  empty and blank names, levels on a continuous and on an untyped node, a unit
  on an untyped node, shares without levels, a negative share, words outside
  the format's lists (role, var_type, form, sign, strength), a `pos` that is
  not two numbers, text that is not a string, a self edge, a duplicate edge,
  a missing `from`. The writer refuses such a graph: exit 2, nothing on
  stdout, `invalid graph:` and the errors on stderr.
- `roundtrip.py` reads each written file back with PyYAML's `safe_load`, a
  YAML 1.1 reader, and checks it equals the input graph less the omissions
  above, so every quoted text reads back as text. Without PyYAML it prints
  `roundtrip skipped: PyYAML is not installed` on stderr and passes.
