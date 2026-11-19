# Causal claims — format spec

The single definition of the files a causal-graph run passes between its
agents and `scripts/causal_graph.py`:

| File | Written by | Read by |
|---|---|---|
| `<paper_vault>/claims/<paper id>.json` | `causal-claim-extractor` (`rejected`: `causal_graph.py check`) | `causal_graph.py` |
| `causal_graphs/<id>/.work/names.txt` | `causal_graph.py names` | `causal-variable-harmonizer` |
| `causal_graphs/<id>/.work/variables.json` | `causal-variable-harmonizer`; the researcher may edit it | `causal_graph.py` |
| `causal_graphs/<id>/.work/pairs.json` | `causal_graph.py pairs` | `causal-pair-searcher` |
| `causal_graphs/<id>/.work/upstream.json` | `causal_graph.py upstream` | `causal-pair-searcher` (upstream mode) |

`<paper_vault>` is the causal profile's `paper_vault_path`; `<id>` is the
profile's `id`. The profile itself is defined in
`research-problem-profile-format-spec.md` ("Causal profiles"). Every file is
UTF-8. Every JSON file holds exactly the keys listed here.

## Name matching

Wherever a name or a level is compared with another, both are **normalized**
first: Unicode NFKC, then case folding, then every run of whitespace collapsed
to one space and the ends stripped. `Diabetes  Mellitus` and `diabetes
mellitus` are one name; `DM` and `diabetes mellitus` are not, until
`variables.json` makes one an alias of the other's node.

## Claims file: `<paper_vault>/claims/<paper id>.json`

One file per paper record, named by the paper's id (its filename stem, per
`paper-identity-spec.md`). It records what the paper itself reports about
causes and effects, each claim with a quote that proves it.

```json
{
  "paper_id": "2019_smith_jones",
  "profile_id": "ssi-colorectal-causes-20261119",
  "design": "cohort",
  "design_detail": "prospective multicentre cohort, multivariable logistic regression",
  "meta_analysis_of": [],
  "population": "1,245 adults after elective colorectal resection in 3 hospitals",
  "setting_match": true,
  "presents_dag": false,
  "claims": [
    {
      "cause": "diabetes mellitus",
      "effect": "surgical site infection",
      "cause_level": "yes",
      "cause_reference": "no",
      "effect_level": "yes",
      "direction": "increases",
      "language": "association",
      "adjusted": true,
      "measure": "OR",
      "scale": "category",
      "value": 1.9,
      "ci": [1.3, 2.8],
      "quote": "diabetes was independently associated with SSI (adjusted OR 1.9, 95% CI 1.3-2.8)",
      "section": "Results"
    }
  ],
  "prevalences": [
    {"variable": "diabetes mellitus", "level": "yes", "proportion": 0.14,
     "quote": "Of the 1,245 patients, 174 (14%) had diabetes", "section": "Results"}
  ],
  "measurements": [
    {"variable": "body mass index", "var_type": "continuous", "levels": [], "unit": "kg/m²"}
  ],
  "rejected": []
}
```

### Paper fields

| Field | Values | Meaning |
|---|---|---|
| `paper_id` | text | The paper's id, equal to the file's stem. |
| `profile_id` | text | The causal profile's `id`. |
| `design` | `rct`, `mendelian-randomization`, `meta-analysis`, `cohort`, `case-control`, `cross-sectional`, `mechanistic`, `animal`, `review`, `other` | The paper's own study design. A narrative review or a background statement is `review`. |
| `design_detail` | text | The design in a few words, as the paper describes it (prospective or retrospective, the model fitted). |
| `meta_analysis_of` | list of designs | For `meta-analysis`: the designs it pooled, from the `design` values. `[]` otherwise. |
| `population` | text | Who was studied, in one line. |
| `setting_match` | bool | Whether `population` matches the profile's `causal_setting`. |
| `presents_dag` | bool | The paper itself draws a causal diagram for the target. |
| `claims` | list | The paper's claims, below. `[]` when it reports none. |
| `prevalences` | list | How common a variable's levels are in the paper's population, below. `[]` when none. |
| `measurements` | list | How the paper measured its variables, below: one entry for every variable in a claim or prevalence, the target included. `[]` when there are none. |
| `rejected` | list | Written by `check`, never by the extractor: the claims and prevalences whose quote was not found, each with `reason`. The extractor writes `[]`. |

### Claim fields: `claims[]`

| Field | Values | Meaning |
|---|---|---|
| `cause`, `effect` | text | Variable names as the paper words them. Any pair of variables, not only those into the target. |
| `cause_level`, `cause_reference` | text or null | For a categorical cause: the level compared and its reference. |
| `effect_level` | text or null | For a categorical effect: the level whose chance changes. |
| `direction` | `increases`, `decreases`, `none`, `unclear` | `none`: the paper reports no effect. `unclear`: an effect without a direction (e.g. "a significant predictor"). |
| `language` | `causal`, `association` | How the paper words it. Reported, not graded. |
| `adjusted` | bool | Whether the estimate is adjusted for other variables. |
| `measure` | `OR`, `RR`, `HR`, `beta_std`, `d`, `other`, null | The effect measure. |
| `scale` | `category`, `per_sd`, `per_unit`, null | What the estimate compares: a level with its reference, one SD, or one unit. |
| `value`, `ci` | number, [lo, hi] or null | The estimate and its 95% CI, as reported. |
| `quote` | text | **Verbatim** from the paper, at most 400 characters; `...` may join two fragments of one passage. |
| `section` | text | The section the quote is from. |

### Prevalence fields: `prevalences[]`

| Field | Values | Meaning |
|---|---|---|
| `variable` | text | The variable's name as the paper words it. |
| `level` | text | The level whose share is given, as the paper words it. |
| `proportion` | number, 0–1 | Its share of the paper's population (14% is `0.14`). |
| `quote` | text | Verbatim, as for a claim. |
| `section` | text | The section the quote is from. |

### Measurement fields: `measurements[]`

| Field | Values | Meaning |
|---|---|---|
| `variable` | text | The variable's name as the paper words it. |
| `var_type` | `categorical`, `ordinal`, `continuous`, `discrete`, null | As in `graphcreator-dag-format.md`; null when the paper does not say. |
| `levels` | list of text | A categorical or ordinal variable's levels as the paper words them, an ordinal one's in order. `[]` otherwise. |
| `unit` | text or null | A continuous or discrete variable's unit. |

### Rejected entries: `rejected[]`

Each entry is the rejected claim or prevalence, unchanged, plus two keys:
`kind` (`claim` or `prevalence`) and `reason` (`quote not found`,
`quote empty` or `quote too long`).

### Rules for the extractor

Readers rely on every one of these.

- **Only what the paper says.** Every claim, prevalence and measurement comes
  from the paper's own text. Never fill one in from background knowledge,
  never add a claim the paper does not make, never complete a missing
  estimate. A paper whose record is abstract-only is extracted from its
  abstract, and its quotes come from the abstract.
- **Quotes are verbatim.** Copy the paper's characters exactly, dashes,
  symbols and case included; never paraphrase, correct or abridge inside a
  fragment. A quote may join two fragments of one passage with `...`; each
  fragment is verbatim, and they appear in the paper in that order. At most
  400 characters. The quote must show the claim: its variables, its direction
  and, when given, its estimate.
- **One claim per (cause, effect, level comparison) per paper.** When the
  paper reports several estimates for one comparison, take its main adjusted
  one. A three-level cause compared with one reference gives two claims, one
  per compared level.
- **Every pair the paper reports**, not only the ones into the target: an
  effect of one cause on another is a claim like any other.
- **A meta-analysis's pooled estimates are its claims.** Its included studies
  are not re-listed as claims of their own.
- **`direction` is read with the levels.** It says what happens to
  `effect_level` (or to the effect's value) when the cause moves from
  `cause_reference` to `cause_level` (or up by one SD or unit). A ratio below
  1 for that comparison is `decreases`. A ratio measure's `value` and `ci` are
  the ratio as reported, never its logarithm.
- **`setting_match`** is judged against the profile's `causal_setting`:
  population, setting and time horizon.
- **`presents_dag`** is true only when the paper draws a causal diagram of the
  target. A paper that only discusses causal pathways is false.
- **`rejected`** is always written as `[]`.

## The quote check

`causal_graph.py check` keeps a claim or prevalence only when its quote is
found in its paper; the others move to `rejected`. The paper text is the
record's body after its identity header. Both the text and the quote are
normalized: Unicode NFKC, soft hyphens removed, a hyphen at a line end joined
to the next word, every dash (`–`, `—`, `−`) made `-`, whitespace collapsed,
case folded. A quote passes when every fragment (split on `...` or `…`)
occurs in the normalized text, in order. An empty quote, or one over 400
characters, fails.

## `names.txt`: `causal_graphs/<id>/.work/names.txt`

Every raw variable name in the kept claims (as cause or effect), prevalences
and measurements of the vault's papers, one line per normalized name (see
"Name matching"). With `--new-only`, only the names `variables.json` does not
map yet. The first line is a header beginning `#`; then one line per name:

```
<papers> | <name> | cause <c>, effect <e> | levels: <levels> | <quote>
```

- `<papers>`: how many papers use the name anywhere.
- `<name>`: the normalized name.
- `<c>`, `<e>`: how many kept claims have it as cause and as effect.
- `<levels>`: every raw level used with it (`cause_level` and
  `cause_reference` where it is the cause, `effect_level` where it is the
  effect, prevalence levels, measurement levels), normalized, deduplicated,
  sorted, joined with `; `. `-` when none.
- `<quote>`: the quote of its first kept claim in paper-id order, else of its
  first prevalence, cut to its first 160 characters; `-` when it has neither.

Lines are sorted by `<papers>`, most first, then by name.

## `variables.json`: `causal_graphs/<id>/.work/variables.json`

The canonical nodes and which raw names map to them.

```json
{
  "target": "Surgical site infection",
  "nodes": [
    {
      "name": "Diabetes",
      "aliases": ["diabetes mellitus", "DM", "type 2 diabetes", "diabetic status"],
      "var_type": "categorical",
      "levels": ["no", "yes"],
      "level_map": {"yes": ["diabetic", "DM"], "no": ["non-diabetic", "no diabetes"]},
      "unit": null,
      "description": "A diagnosis of diabetes mellitus before surgery.",
      "measurement_note": "Two papers used HbA1c >= 6.5% instead of a diagnosis.",
      "timing": "baseline",
      "exogenous": false
    }
  ],
  "unmapped": ["comorbidities", "other factors"]
}
```

| Field | Values | Meaning |
|---|---|---|
| `target` | text | Equal to the profile's `causal_target`. |
| `nodes[].name` | text | The node's name in the graph: short and human (`Diabetes`, `BMI`), unique. |
| `nodes[].aliases` | list of text | The raw names that mean this node, other than its name. |
| `nodes[].var_type` | `categorical`, `ordinal`, `continuous`, `discrete`, null | The type of the majority operationalization in the papers' `measurements`; without measurements, the type the names' raw levels show (present/absent levels → categorical `["no", "yes"]`); null when neither says. |
| `nodes[].levels` | list of text | A categorical or ordinal node's canonical levels, an ordinal one's in order; a two-level node's first level is the absence or lower one (`["no", "yes"]`). `[]` otherwise. |
| `nodes[].level_map` | map: level → list of text | For each canonical level, the raw level names that mean it, other than the level itself. `{}` when none. |
| `nodes[].unit` | text or null | A continuous or discrete node's unit. |
| `nodes[].description` | text | What the variable is, in one sentence. |
| `nodes[].measurement_note` | text or null | How the papers' operationalizations differ, when they do. |
| `nodes[].timing` | `baseline`, `later`, `target_measure`, `unknown` | When the variable is known, judged against the profile's `prediction_time`: `baseline`, known by the prediction time; `later`, measured after it, before or around the outcome; `target_measure`, a measure or early form of the target itself (a preoperative delirium score for postoperative delirium); `unknown` when the papers do not say. Missing or null means `unknown`. |
| `nodes[].exogenous` | `true`, `false` | `true` for a variable nothing in the graph can cause (age, sex, genotype, calendar time). Missing or null means `false`. |
| `unmapped` | list of text | Raw names too vague to be one variable. |

- **Mapping.** A raw name maps to a node when, normalized, it equals the
  node's `name` or one of its `aliases`. A raw level maps to a canonical level
  when, normalized, it equals the level or one of its `level_map` entries. A
  normalized name belongs to at most one node, or to `unmapped`; a raw level
  to at most one level of its node.
- **The target.** A node named exactly `target` exists, and every synonym of
  the target in the papers is among its aliases.
- **Merging.** True synonyms and operationalizations of one construct are one
  node (obesity and body mass index are one node, typed as the majority
  operationalization, the others described in `measurement_note`). Distinct
  constructs stay apart even when they are correlated.
- **Timing.** `assemble` drops a `target_measure` node and all its edges
  from both graphs, and every edge into an `exogenous` node, before cycles
  are broken. A `later` node stays in both graphs; its description there ends
  with "Measured after the prediction time." `pairs` leaves out
  `target_measure` nodes and pairs of two `exogenous` nodes; `upstream` skips
  `exogenous` and `target_measure` causes. The target's own `timing` and
  `exogenous` are not used.
- **Later passes.** A harmonizer that finds `variables.json` already written
  keeps every node's name and every existing mapping, and only adds aliases,
  level-map entries and nodes for the new names.
- **Edits.** The researcher may edit the file; `causal_graph.py assemble` is
  re-run on it as it stands.

## `pairs.json`: `causal_graphs/<id>/.work/pairs.json`

The pairs of top causes with no claim between them yet, for the pair search.

```json
{
  "k": 15,
  "max_papers": 40,
  "pairs": [
    {"n": 1, "a": "Diabetes", "b": "Obesity", "support": 31,
     "query": "(\"diabetes mellitus\"[ti] OR diabetes[ti]) AND (obesity[ti] OR \"body mass index\"[ti]) AND (cohort[tiab] OR \"risk factor*\"[tiab] OR \"odds ratio\"[tiab] OR \"mendelian randomi*\"[tiab] OR meta-analysis[tiab])",
     "narrow": "(\"diabetes mellitus\"[ti] OR diabetes[ti]) AND (obesity[ti] OR \"body mass index\"[ti]) AND (\"systematic review\"[tiab] OR meta-analys*[tiab] OR \"umbrella review\"[tiab])"}
  ]
}
```

| Field | Values | Meaning |
|---|---|---|
| `k` | integer | How many top causes were paired: the profile's `pair_search_k`, 15 when missing. `target_measure` nodes are left out before the top `k` are taken. |
| `max_papers` | integer | Papers the pair search may add in one run: the profile's `pair_search_max_papers`, 40 when missing. A paper already in the vault is never listed again, so the cap counts only papers that run adds. |
| `pairs[].n` | integer | The pair's number, from 1, in search order. |
| `pairs[].a`, `.b` | text | The two nodes' names: `a` the one with more support, ties by name. The order says nothing about direction; both are searched. |
| `pairs[].support` | integer | Their combined support: papers with a kept claim touching `a`, plus those touching `b`. |
| `pairs[].query` | text | A PubMed query: one block per node, its name and aliases OR-ed, each in the title (`[ti]`), the two blocks AND-ed, AND a block of study-design terms (`cohort`, `risk factor*`, `odds ratio`, `mendelian randomi*`, `meta-analysis`, each `[tiab]`). |
| `pairs[].narrow` | text | The same two title blocks AND a review block (`systematic review`, `meta-analys*`, `umbrella review`, each `[tiab]`), for when `query` is too broad. |

Pairs are ordered by `support`, most first. No pair has a kept claim between
its nodes in either direction, a `target_measure` node, or two `exogenous`
nodes. `query` is run first, `narrow` when `query` is too broad; when
`narrow` is too broad as well, the searcher reruns it with `--top 50`, as for
`upstream.json` below.

## `upstream.json`: `causal_graphs/<id>/.work/upstream.json`

The top causes of the target, for the upstream round: a search for each
one's own causes.

```json
{
  "k": 5,
  "max_papers": 15,
  "entries": [
    {"n": 1, "a": "Diabetes", "support": 12,
     "query": "(\"diabetes mellitus\"[ti] OR diabetes[ti]) AND (\"risk factor*\"[ti] OR determinant*[ti] OR etiolog*[ti] OR aetiolog*[ti] OR predictor*[ti] OR \"factors associated with\"[ti]) AND (\"systematic review\"[tiab] OR meta-analys*[tiab] OR \"umbrella review\"[tiab])",
     "fallback": "(\"diabetes mellitus\"[ti] OR diabetes[ti]) AND (\"risk factor*\"[ti] OR determinant*[ti] OR etiolog*[ti] OR aetiolog*[ti] OR predictor*[ti] OR \"factors associated with\"[ti]) AND (surgery[tiab] OR surgical[tiab] OR postoperative[tiab])"}
  ]
}
```

| Field | Values | Meaning |
|---|---|---|
| `k` | integer | How many top causes of the target were taken: the profile's `upstream_search_k`, 5 when missing. |
| `max_papers` | integer | Papers the upstream round may add in one run: the profile's `upstream_search_max_papers`, 15 when missing. A paper already in the vault is never listed again, so the cap counts only papers that run adds. |
| `entries[].n` | integer | The entry's number, from 1, in search order. |
| `entries[].a` | text | A cause of the target: a node, other than the target, with a kept claim into the target that shows an effect (direction `increases`, `decreases` or `unclear`), and neither `exogenous` nor a `target_measure`: those are skipped and the next cause by support takes their place. |
| `entries[].support` | integer | Papers with a kept claim touching `a`, as in `pairs.json`. |
| `entries[].query` | text | A PubMed query for reviews and meta-analyses of `a`'s risk factors: `a`'s block (its name and aliases OR-ed, as in `pairs.json` but each `[ti]`) AND a risk-factor block in the title (`risk factor*`, `determinant*`, `etiolog*`, `aetiolog*`, `predictor*`, `factors associated with`, each `[ti]`) AND a review block (`[tiab]`). Both in the title, so a paper on `a` as a risk factor for something else mostly falls out. |
| `entries[].fallback` | text or null | A PubMed query for primary studies in the setting: `a`'s block AND the risk-factor block, both as in `query`, AND a block of the profile's `setting_terms` OR-ed, each `[tiab]`. `null` when the profile has no `setting_terms`. |

Entries are ordered by `support`, most first, ties by name. Per entry,
`query` is run first; `fallback` is run when `query` is too broad or no
candidate it finds passes screening, and is skipped when it is `null`. When
the entry ends with a too-broad query and nothing saved, the searcher reruns
it with `--top 50` (the review `query` if it was too broad, else
`fallback`): the 50 most relevant hits by PubMed's order, reported as
`top 50 of N`, never as the whole set.
