# Causal graph design

**Status:** design agreed 2026-11-19, extended the same day (causes of causes; after the T3 run, timing and the T3 fixes); implemented, all 5 waves done (phases 1–15). This document is the
brief for the implementation sessions. It extends the plugin described in
[CLAUDE.md](CLAUDE.md); the output format is
[templates/graphcreator-dag-format.md](templates/graphcreator-dag-format.md).

## Purpose

A causal graph (DAG) for a prediction task normally comes from domain experts:
clinicians draw which variables cause the outcome and how those causes relate.
The researcher wants to test whether a **thorough literature review can stand
in for that expertise**: given a prediction target, its setting and field,
build the most likely causal graph from what the literature reports, then
compare it with an expert-built ground-truth graph they already have.

So the one hard requirement is **grounding**: every arrow must trace back to
a quoted sentence in a paper. The model's own background knowledge must not
add edges, or the experiment measures the model instead of the literature.

The skill is `second-brain-causal-graph`. It reuses the plugin's discovery
(arXiv, PubMed/Europe PMC, Asta cross-field, the citation chaser, the merge,
the checkpoint) and adds claim extraction, variable harmonization, a search
for edges among the causes, and a deterministic graph assembly that writes the
researcher's GraphCreator format. Comparing with the expert graph is **not**
part of the plugin.

## Overview

```
Q&A ─► causal profile (a topic profile + causal fields)
discovery: arXiv + biomedical + cross-field legs (one wave) ─► citation chaser
  ─► stage_prep.py merge ─► causal_graph.py exclude
checkpoint (stop, wait for go-ahead)
causal_graph.py plan ─► causal-claim-extractor (waves) ─► causal_graph.py check
causal_graph.py names ─► causal-variable-harmonizer (pass 1)
causal_graph.py pairs ─► causal-pair-searcher ─► merge ─► exclude
  (stop once only if manual downloads or the cap was hit)
plan ─► extractor (new papers) ─► check ─► names --new-only ─► harmonizer (pass 2)
causal_graph.py upstream ─► causal-pair-searcher (upstream mode) ─► merge ─► exclude
  (stop once only if manual downloads or the cap was hit)
plan ─► extractor (new papers) ─► check ─► names --new-only ─► harmonizer (pass 3)
causal_graph.py assemble ─► <id>.dag.yaml, <id>.full.dag.yaml, <id>.evidence.md
```

- **Graph scope:** the target's **ancestors**: its direct causes, the edges
  among them (confounders and mediators), and the causes of those causes. A
  variable that only receives an edge from a cause and leads nowhere near the
  target is dropped. Causes of causes come from what the papers report and
  from a deliberate **upstream round** for the top causes (one hop up).
- **Nodes** come from the literature; there is no researcher variable list.
- **No vault:** no paper summaries, topic notes or Obsidian build, and no code
  leg. The records stay in a standard paper vault, so a normal
  `second-brain-pipeline` run can still build a vault from them later.
- The main conversation reads only script reports and agent replies, never
  papers or claim files (the plugin's standing rule).

New pieces:

| Piece | Kind | Model | Job |
|---|---|---|---|
| `skills/second-brain-causal-graph/SKILL.md` | skill | session | Q&A, orchestration, checkpoint, report. Self-contained |
| `agents/causal-claim-extractor.md` | agent | sonnet | one long paper or up to 8 short ones → one claims file each |
| `agents/causal-variable-harmonizer.md` | agent | opus | raw variable names → canonical nodes (`variables.json`) |
| `agents/causal-pair-searcher.md` | agent | sonnet | PubMed searches for pairs of causes with no claim yet |
| `scripts/causal_graph.py` | script | — | `plan`, `check`, `exclude`, `names`, `pairs`, `assemble` |
| `scripts/graphcreator.py` | module | — | validate and write `graphcreator/0.1` YAML, stdlib only |
| `templates/causal-claims-spec.md` | schema | — | claims files, `variables.json`, `pairs.json` |
| `templates/graphcreator-dag-format.md` | schema | — | the output format (the researcher's, saved verbatim) |

## Formats and interfaces

### Files and folders

`<root>` is `<project-root>/second-brain/`, as for every profile.

```
<root>/
├── causal_graphs/<id>/
│   ├── <id>.md               # the causal profile
│   ├── <id>.dag.yaml         # strict DAG: edges graded probable or better
│   ├── <id>.full.dag.yaml    # full DAG: every supported edge
│   ├── <id>.evidence.md      # the human-readable evidence report
│   └── .work/                # variables.json, names.txt, pairs.json, plan.json
└── paper_vault/<id>/
    ├── <paper id>.md         # records, as for any run
    ├── claims/<paper id>.json
    ├── .merged/  .excluded/  .candidates/
```

The profile lives in `causal_graphs/<id>/`, not in `<root>/*.md`, because the
topic deep-dive skill lists `<root>/*.md` profiles as vaults and would stop on
one with no `summaries/`.

### The causal profile

A causal profile is a **topic profile** (`profile_type: topic`) plus causal
fields, valid on its own, so every discovery leg and the citation chaser run on
it unchanged (as they do on a deep-dive profile). `causal_target` is what marks
it as causal. Example:

```yaml
---
id: ssi-colorectal-causes-20261119
created: 2026-11-19
status: confirmed
profile_type: topic
domain: colorectal surgery
task: predict surgical site infection within 30 days of elective colorectal surgery
causal_target: Surgical site infection
causal_setting: adults undergoing elective colorectal resection; infection within 30 days
exclude_papers:
  - "10.1000/the-paper-our-expert-dag-came-from"
pair_search_k: 15
pair_search_max_papers: 40
review_scope: >-
  IN: studies reporting causes, risk factors or predictors of surgical site
  infection after colorectal surgery or in adjacent surgical settings, with an
  effect estimate or an explicit causal claim; studies reporting effects among
  those factors. OUT: prediction-model papers that report only performance;
  treatment of an established infection.
review_purpose: Build a literature-derived causal graph of surgical site infection after colorectal surgery, to compare with an expert-built graph.
review_questions:
  - What causes surgical site infection in adults undergoing elective colorectal resection?
  - How do those causes affect each other?
  - How large are the effects, and how common are the causes in this setting?
core_questions: [1]
seed_papers: []
date_window_years: 10
recall_probes:
  - '("surgical site infection*"[tiab] OR "wound infection*"[tiab]) AND (colorectal[tiab] OR colectom*[tiab]) AND ("risk factor*"[tiab] OR predictor*[tiab] OR "odds ratio"[tiab])'
close_field_terms:
  - surgical site infection colorectal surgery risk factors
  - predictors of surgical site infection after colectomy
  - Mendelian randomization surgical site infection
  - surgical site infection meta-analysis risk factors
generalized_methodology_terms:
  - postoperative wound infection risk factors abdominal surgery
  - infection after gastrointestinal surgery predictors
keywords_of_interest: []
paper_vault_path: <root>/paper_vault/ssi-colorectal-causes-20261119/
---
```

New fields, added to `templates/research-problem-profile-format-spec.md` with
a new **causal** value in its "Required" column (required on a causal profile,
absent elsewhere) and a "Causal profiles" section. The skill always writes all
five, the defaults included (`exclude_papers: []` when none); a reader still
treats a missing `pair_search_k` or `pair_search_max_papers` as its default:

| Field | Type | Required | Meaning | Used by |
|---|---|---|---|---|
| `causal_target` | string | causal | The prediction target as the outcome node's name, e.g. `Surgical site infection`. Its presence makes a profile causal. | harmonizer, `assemble` |
| `causal_setting` | string | causal | Population, setting and time horizon. A claim from another population counts one grade lower. | extractor (`setting_match`), `assemble` |
| `exclude_papers` | list[string] | causal | Papers the graph must not see, typically the source of the expert graph. Same string forms as `seed_papers`. | `exclude` |
| `pair_search_k` | integer | causal | How many top causes get the pair search. Missing means 15. | `pairs` |
| `pair_search_max_papers` | integer | causal | Papers the pair search may add in one run. Missing means 40. | `causal-pair-searcher` |
| `upstream_search_k` | integer | causal | How many top causes of the target get an upstream search for their own causes. Missing means 5. | `upstream` |
| `upstream_search_max_papers` | integer | causal | Papers the upstream round may add in one run. Missing means 15. | `causal-pair-searcher` |
| `setting_terms` | list[string] | causal | 2–5 PubMed terms for the setting's population (e.g. `surgery`, `surgical`, `postoperative`), OR-ed into the upstream round's setting-restricted query. | `upstream` |
| `prediction_time` | string | causal | When the prediction is made, in words (e.g. `at hospital admission, before surgery`); proposed from the task and confirmed at intake. The harmonizer judges each variable's timing against it. | harmonizer |

How the Q&A fills the shared fields on a causal profile:

- `review_questions` are the three fixed questions above, with the target and
  setting filled in; `core_questions: [1]`. Q1 is therefore covered
  exhaustively by the legs and the chaser.
- `close_field_terms` are cause-oriented: "`<target>` risk factors",
  "predictors of `<target>`", "Mendelian randomization `<target>`",
  "`<target>` meta-analysis", with the setting's words.
- `generalized_methodology_terms` are **the target in adjacent settings or
  populations** (SSI after colorectal surgery → "postoperative wound
  infection", "infection after any abdominal surgery"), so the cross-field leg
  finds causes established in neighbouring settings.
- `recall_probes`: 1–3, per the spec's syntax rules, for Q1.
- `date_window_years`: proposed as 10 (risk-factor literature is older than
  method literature); the core question has no window anyway.
- `keywords_of_interest: []` (no topic notes are written).
- `code_vault_path` is omitted (no code leg).

### Claims file: `<paper_vault>/claims/<paper id>.json`

Written by `causal-claim-extractor`, one per paper, defined in
`templates/causal-claims-spec.md`. Example:

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

| Field | Values | Meaning |
|---|---|---|
| `design` | `rct`, `mendelian-randomization`, `meta-analysis`, `cohort`, `case-control`, `cross-sectional`, `mechanistic`, `animal`, `review`, `other` | The paper's own study design. A narrative review or a background statement is `review`. |
| `meta_analysis_of` | list of designs | For `meta-analysis`: the designs it pooled. `[]` otherwise. |
| `population` | text | Who was studied, in one line. |
| `setting_match` | bool | Whether `population` matches the profile's `causal_setting`. |
| `presents_dag` | bool | The paper itself draws a causal diagram for the target. |
| `claims[].cause`, `.effect` | text | Variable names as the paper words them. Any pair of variables, not only those into the target. |
| `claims[].cause_level`, `.cause_reference` | text or null | For a categorical cause: the level compared and its reference. |
| `claims[].effect_level` | text or null | For a categorical effect: the level whose chance changes. |
| `claims[].direction` | `increases`, `decreases`, `none`, `unclear` | `none`: the paper reports no effect. `unclear`: an effect without a direction (e.g. "a significant predictor"). |
| `claims[].language` | `causal`, `association` | How the paper words it. Reported, not graded. |
| `claims[].adjusted` | bool | Whether the estimate is adjusted for other variables. |
| `claims[].measure` | `OR`, `RR`, `HR`, `beta_std`, `d`, `other`, null | The effect measure. |
| `claims[].scale` | `category`, `per_sd`, `per_unit`, null | What the estimate compares: a level with its reference, one SD, or one unit. |
| `claims[].value`, `.ci` | number, [lo, hi] or null | The estimate and its 95% CI, as reported. |
| `claims[].quote` | text | **Verbatim** from the paper, at most 400 characters; `...` may join two fragments of one passage. |
| `claims[].section` | text | The section the quote is from. |
| `prevalences[]` | variable, level, proportion (0–1), quote, section | How common a level is in the paper's population. |
| `measurements[]` | variable, var_type, levels, unit | How the paper measured a variable (`var_type` as in the GraphCreator format). |
| `rejected` | list | Written by `check`, never by the extractor: the claims and prevalences whose quote was not found, each with `reason`. |

### `variables.json`: `causal_graphs/<id>/.work/variables.json`

Written by `causal-variable-harmonizer`, defined in the same spec:

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
      "measurement_note": "Two papers used HbA1c >= 6.5% instead of a diagnosis."
    }
  ],
  "unmapped": ["comorbidities", "other factors"]
}
```

- `target` equals the profile's `causal_target`; that node exists in `nodes`
  and every synonym of the target is among its aliases.
- A raw name maps to a node when, after Unicode NFKC, case folding and
  whitespace collapsing, it equals the node's `name` or one of its `aliases`.
  `level_map` maps raw level names the same way.
- `unmapped`: names the harmonizer judged too vague to be one variable.
- Each node also has `timing` and `exogenous`, set by the harmonizer (wave 5):
  - `timing`: `baseline` (known by the profile's `prediction_time`),
    `later` (measured after it, before or around the outcome),
    `target_measure` (a measure or early form of the target itself, e.g. a
    delirium assessment score before surgery), or `unknown`; missing means
    `unknown`;
  - `exogenous`: `true` for a variable nothing in the graph can cause (age,
    sex, genotype, calendar time); missing means `false`.
- The researcher may edit this file and re-run `assemble` (script only, free).

### `pairs.json`: `causal_graphs/<id>/.work/pairs.json`

Written by `causal_graph.py pairs`, read by `causal-pair-searcher`:

```json
{
  "k": 15,
  "max_papers": 40,
  "pairs": [
    {"n": 1, "a": "Diabetes", "b": "Obesity", "support": 31,
     "query": "(\"diabetes mellitus\"[tiab] OR diabetes[tiab]) AND (obesity[tiab] OR \"body mass index\"[tiab])",
     "narrow": "(...) AND (...) AND (cohort[tiab] OR \"risk factor*\"[tiab] OR \"odds ratio\"[tiab] OR \"mendelian randomi*\"[tiab] OR meta-analysis[tiab])"}
  ]
}
```

### `upstream.json`: `causal_graphs/<id>/.work/upstream.json`

Written by `causal_graph.py upstream`, read by `causal-pair-searcher` in
upstream mode:

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

`a` is a cause of the target (a node with a kept claim into it that shows an
effect), ranked by support as in `pairs`; `query` looks for reviews and
meta-analyses of its risk factors, with the cause and the risk words in the
title (`[ti]`), so papers on the cause as a risk factor for something else
mostly fall out; `fallback` for primary studies in the setting, from
`setting_terms` (an entry without `setting_terms` has `fallback: null`). When
an entry still ends too broad, the searcher takes the top 50 by PubMed
relevance and reports it as `top 50 of N`. Defined, like the
other files, in `templates/causal-claims-spec.md`.

### `scripts/causal_graph.py`

Stdlib only, like every script. Imports `papers`, `read_until`, `BATCH`,
`norm_title`, `same` from `stage_prep.py` and `seed_ident`, `EXCLUDED` from
`find_papers.py`. Exit 0 on a result, 2 on bad input with `{"error": …}` on
stdout. Every report is compact JSON (the main conversation reads it).

| Command | Does | Report |
|---|---|---|
| `plan <paper_vault> [--redo] [--solo-kb 60]` | Plans extractor dispatches for records without a claims file, exactly as `stage_prep.py summaries` plans summarizer dispatches (one long paper with `read_until`, or up to `BATCH` short ones). | `{"to_extract", "skipped_existing", "dispatch_count", "dispatches": [{"papers": [id], "read_until"?: N}]}` |
| `check <paper_vault>` | Validates every claims file against the spec and checks each quote against the paper's text (below). Moves failing claims and prevalences to `rejected`, rewriting the file. Idempotent. | `{"papers", "claims_kept", "claims_rejected", "by_paper": {id: rejected}, "invalid": [file: reason], "missing": [ids with no claims file], "presents_dag": [ids]}` |
| `exclude <paper_vault> --profile P` | Moves every record matching an `exclude_papers` entry (DOI, PMID, PMCID, arXiv id, or exact title via `seed_ident` and `same`) to `.excluded/`, with its claims file. | `{"excluded": [{"id", "matched"}], "not_found": [entries]}` |
| `names <paper_vault> --variables V [--new-only] --out F` | Writes every raw variable name in the kept claims, prevalences and measurements, one line each in the `names.txt` format of `templates/causal-claims-spec.md` (paper count, as cause / as effect, the raw level names, one quote cut to 160 characters), sorted by paper count, then name. `--new-only`: only names `V` does not map yet. `V` may not exist on pass 1. | `{"names", "written": F}` |
| `pairs <paper_vault> --variables V --profile P --out F` | Ranks the non-target nodes by the number of papers with a kept claim touching them; takes the top `pair_search_k`; writes every pair with no claim in either direction to `F`, ordered by combined support; within a pair `a` is the better-supported node, ties by name.  Wave 5: leaves out `target_measure` nodes and pairs of two exogenous nodes; `query` puts both nodes' terms in the title (`[ti]`) AND the design block, `narrow` both title blocks AND the review block. | `{"k", "pairs", "already_linked", "written": F}` |
| `upstream <paper_vault> --variables V --profile P --out F` | Ranks the causes of the target (nodes with a kept claim into it) by support, takes the top `upstream_search_k`, and writes one entry each to `F` with its two queries (see "`upstream.json`"). Query terms as in `pairs`. Wave 5: skips `exogenous` and `target_measure` nodes and takes the next cause. | `{"k", "entries", "written": F}` |
| `assemble <paper_vault> --variables V --profile P --out D` | Builds both graphs and the evidence report (see "Graph assembly") and writes `<id>.dag.yaml`, `<id>.full.dag.yaml`, `<id>.evidence.md` into `D`. | `{"nodes": [strict, full], "edges": [strict, full], "target_edges": [strict, full], "cycle_drops", "unmapped_claims", "top_unmapped": [[name, n]], "presents_dag": [ids], "excluded": n, "warnings": [...]}` |

### `scripts/graphcreator.py`

```python
SCHEMA = "graphcreator/0.1"

def validate(graph: dict) -> tuple[list[str], list[str]]:
    """(errors, warnings) per the format's "What a valid file guarantees":
    errors are what GraphCreator refuses (unknown keys, duplicate or empty
    names, dangling or self or duplicate edges, cycles, levels/unit/shares
    on the wrong type); warnings are what it only warns about."""

def dump(graph: dict) -> str:
    """The graph as graphcreator/0.1 YAML text. Raises ValueError listing the
    errors when validate() finds any. Keys in the format's order; empty text,
    `role: other`, empty evidence and empty sign maps left out; `levels` and
    `shares` and sign maps in flow style, sign-map keys in level order;
    evidence always double-quoted; any text a YAML 1.1 reader would read as
    something else (the format's list: booleans, null, YAML 1.1 numbers,
    dates) or that YAML 1.2 requires quoted, double-quoted; shares rounded to
    3 decimals, a share of 1 written `1`."""

def needs_quotes(text: str) -> bool: ...
```

`graph` is a plain dict shaped like the YAML (`schema`, `name`, `nodes`,
`edges`). No reader is built: nothing in the plugin reads `.dag.yaml` back.

### Agents

Every description is under ~80 words and carries the reimplementation warning
(CLAUDE.md, "Rules"). Replies are `OK …` or `FAIL <reason>` plus a few
anomaly lines, as for the existing agents.

**`causal-claim-extractor`** (sonnet; tools `Read, Write, Bash`). Prompt:

```
papers:
- <paper_vault_path>/<id>.md (read_until: <N>)
- <paper_vault_path>/<id>.md
format: <plugin root>/templates/causal-claims-spec.md
profile: <causal profile path>
```

Reads each paper up to `read_until` (the whole file without it) and writes
`<paper_vault_path>/claims/<id>.json` per the spec. Rules it carries: quote
verbatim, never paraphrase, never fill a claim from background knowledge; one
claim per (cause, effect, level comparison) per paper, taking the paper's main
adjusted estimate; every variable pair the paper reports, not only those into
the target; a meta-analysis's pooled estimates are its claims, its included
studies are not re-listed; `setting_match` judged against `causal_setting`;
`presents_dag` true only for a drawn causal diagram of the target. Reply:
`OK <n> files, <m> claims` plus `presents_dag: <id>` lines and any paper it
could not read.

**`causal-variable-harmonizer`** (opus; tools `Read, Write, Bash`). Prompt:

```
names: <causal_graphs/<id>>/.work/names.txt
variables: <causal_graphs/<id>>/.work/variables.json
variables exists: <true | false>
profile: <causal profile path>
format: <plugin root>/templates/causal-claims-spec.md
```

Groups raw names into nodes. Rules: merge true synonyms and operationalizations
of one construct (obesity and BMI → one node; its type is the majority
operationalization from `measurements`, the others in `measurement_note`);
keep distinct constructs apart even when correlated; map every synonym of the
target to the `causal_target` node; names too vague to be one variable go to
`unmapped`; node names short and human (`Diabetes`, `BMI`), unique. With
`variables exists: true` (pass 2) it keeps every existing node name and
mapping, and only adds aliases or nodes for the new names. Reply:
`OK <nodes> nodes, <mapped> names mapped, <unmapped> unmapped`.

**`causal-pair-searcher`** (sonnet; tools `Read, Bash, Glob`). Wave 5: in pairs mode too, a `narrow` that is still too broad is rerun with `--top 50` and reported as `top 50 of N`. It has two
modes, chosen by the prompt's first label: `pairs:` (below) or `upstream:`.
In upstream mode it reads `upstream.json`; per entry, list `up-<n>`: run
`query` (reviews and meta-analyses); when it is too broad or no candidate
passes, run `fallback` (skipped when null); when the entry still ends too
broad, rerun the review `query` (or, if only `fallback` was too broad, the
`fallback`) with `--top 50` and report `top 50 of N`.
A paper passes if it reports an effect of some variable on the entry's cause,
in humans; prefer reviews and meta-analyses, then setting-matched papers; at
most 5 per entry and `max_papers` in total. The reply has the same shape, per
entry. Pairs-mode prompt:

```
pairs: <causal_graphs/<id>>/.work/pairs.json
profile: <causal profile path>
find_papers: <plugin root>/scripts/find_papers.py
```

For each pair in order: `find_papers.py pubmed <vault> --list pair-<n>
--query <query>` (no window); on `too_broad`, the same with `narrow`; still
too broad: skip and report. Screens titles, then abstracts where a title
leaves it unsure: a paper passes if it reports an effect of one of the two
variables on the other, in humans. Keeps at most 5 per pair, preferring
setting-matched papers and stronger designs, and saves them with
`find_papers.py add <vault> --list pair-<n> <N…>`. Stops at `max_papers`
added. Reply: `OK` with per pair hits / screened / added, the too-broad pairs,
whether the cap was hit, and a **needs-manual-download** list (added papers
still `full_text: abstract-only`: title, DOI, PMID).

### The skill: `second-brain-causal-graph`

Self-contained (the researcher's choice): it holds its own Q&A, its own copy of
the pipeline's plugin-root Bash call (under a heading `## Plugin root`), the
discovery prompt templates and the checkpoint, rather than handing over to
`research-problem-intake` and `second-brain-pipeline`. Two suites guard the
copies (see "Tests"). Its description: builds a causal graph (GraphCreator
DAG) of what the literature says causes a prediction target; use when a
researcher wants the causes of an outcome they predict as a graph; not for a
literature review (`second-brain-pipeline`).

## Behaviour and algorithms

### The run, step by step

1. **Q&A.** Ask for the target, the setting (population, time horizon), the
   field; propose the causal fields and the shared fields as described under
   "The causal profile"; ask explicitly whether there is a paper or graph the
   result must not see (`exclude_papers`). Show the defaults (`pair_search_k`
   15, `pair_search_max_papers` 40, window 10). Write the profile as `draft`,
   show it, and set `status: confirmed` only on the researcher's yes. Create
   `causal_graphs/<id>/.work/` and `paper_vault/<id>/`. No patient data, as for
   every profile.
2. **Plugin root** with the copied Bash call; stop on `NOT FOUND`. Read the
   wave size.
3. **Discovery.** One wave of `second-brain-paper-downloader`,
   `second-brain-biomed-downloader`, `second-brain-crossfield-searcher`, with
   the pipeline's prompt (`profile`, `identity spec`, `fetcher`,
   `find_papers`). Then `second-brain-citation-chaser`. Then
   `stage_prep.py merge`, then `causal_graph.py exclude`.
4. **Checkpoint.** The pipeline's stage-4 report without the repositories
   section, plus the exclusion report. Stop; wait for an explicit go-ahead.
   This is the cheap point to trim: extraction is the costly step.
5. **Extraction.** `plan`, then `causal-claim-extractor` in waves, then
   `check`. Relay `check`'s counts and `presents_dag`.
6. **Harmonize, pass 1.** `names --out .work/names.txt`, then
   `causal-variable-harmonizer` with `variables exists: false`.
7. **Pair round.** `pairs`, then `causal-pair-searcher`, then `merge`,
   `exclude`. **Stop once** only if the searcher reports needs-manual-download
   papers or hit its cap: the researcher can supply PDFs (the pipeline's
   `fetch_fulltext.py --source manual` route) or raise
   `pair_search_max_papers` and re-run the round. Otherwise continue. Then
   `plan` (only the new records lack claims), extractor, `check`,
   `names --new-only`, harmonizer with `variables exists: true`.
8. **Upstream round.** `upstream`, then `causal-pair-searcher` with
   `upstream:` instead of `pairs:`, then `merge`, `exclude`; the same single
   stop rule as the pair round (its own cap, `upstream_search_max_papers`);
   then `plan`, extractor, `check`, `names --new-only`, harmonizer pass 3
   (`variables exists: true`). Skipped when `upstream` writes no entries.
9. **Assemble** and report: node and edge counts for both graphs, edges into
   the target, cycle drops, the unmapped names that lost the most claims,
   `presents_dag` papers (suggest adding them to `exclude_papers` and
   re-assembling if they are the expert graph's source), quote-check
   rejections, the output paths. Say that the comparison with an expert graph
   happens outside the plugin.

### Quote check (`check`)

The paper text is the record's body after the identity header. Both sides are
normalized: Unicode NFKC, soft hyphens removed, a hyphen at a line end joined
to the next word, every dash (–, —, −) to `-`, whitespace collapsed, case
folded. A quote passes when every fragment (split on `...` or `…`) occurs in
the normalized text, in order. An empty quote, or one over 400 characters,
fails. Failing claims and prevalences move to `rejected` with
`reason: quote not found | quote empty | quote too long`.

### Grades

Each kept claim gets a grade from its paper's design:

| Grade | Value | Designs |
|---|---|---|
| established | 3 | `rct`, `mendelian-randomization`; a `meta-analysis` whose `meta_analysis_of` holds only `rct`, `mendelian-randomization`, `cohort` |
| probable | 2 | `cohort` with `adjusted: true` |
| suggested | 1 | `case-control`, `cross-sectional`, `cohort` with `adjusted: false` |
| speculative | 0 | `mechanistic`, `animal`, `review`, `other` |

- Any other meta-analysis takes the grade of its weakest pooled design.
- A claim from a paper with `setting_match: false` counts one grade lower,
  floor 0.
- **An edge exists** when at least one claim on that (cause node, effect node)
  has direction `increases`, `decreases` or `unclear`. `none` claims never
  create an edge.
- **Edge grade** = the highest grade among its existence claims, one lower
  (floor 0) when the edge **conflicts**: some claim whose direction is the
  opposite of the edge's sign, or `none`, has a grade at least the edge's
  highest grade. Weaker contrary evidence does not downgrade stronger
  evidence. The number of papers never raises a grade (a meta-analysis and its
  own studies would double-count).
- The strict DAG keeps edges graded 2 or 3; the full DAG keeps all.

### Sign

Decided from the edge's highest-grade claims with direction `increases` or
`decreases`; a tie leaves no sign. The shape follows the format's sign table:

- **Cause without levels for signs** (continuous, discrete, ordinal, untyped,
  or categorical with fewer than two levels), effect not nominal: one word.
  `increases` → `positive`. A claim about the effect's lower level of a
  two-level effect (`effect_level` = the first level) is flipped. An ordinal
  claim of a lower versus a higher level is flipped.
- **Binary categorical cause**, effect not nominal: one word, signing the
  second level. A claim comparing the first level with the second is flipped.
- **Nominal cause** (categorical, three or more levels), effect not nominal: a
  map over the cause's levels. Take the reference level most claims use; give
  it 0 and each level compared with it `ln(value)` (the median per level), or
  ±1 when only a direction is known; centre on the mean over the levels that
  have a value; each level's sign is that of its centred value; levels without
  a value, or centred to 0, are left out.
- **Nominal effect**: a map over the effect's levels, `effect_level` with
  `increases` → `positive`. Nominal to nominal: no sign.
- Raw levels map to canonical levels through the node's `level_map`; a claim
  whose levels do not map gives no sign (it still counts for existence and
  grade).

### Strength

From the edge's highest-grade claims that have a `value`:

- `OR`, `RR`, `HR` with `scale: category` or `per_sd`: `d = |ln(value)|·√3/π`
  (RR and HR treated as OR, and the note says so).
- `beta_std` and `d`: `|value|`.
- `scale: per_unit` gives no strength: a per-unit estimate depends on the
  unit.
- The edge's d is the median; bands on d, each including its lower
  bound: below 0.1 no strength, 0.1 to below 0.3 `small`, 0.3 to below 0.6
  `medium`, 0.6 and above `large`. So OR 1.4 → small, OR 2 →
  medium (d 0.38), OR 3.5 → large (d 0.69).

### Shares

Only from prevalences in papers with `setting_match: true` whose level maps to
a canonical level: the median proportion per level. A two-level variable with
one level known gets the complement. With three or more levels, shares are
written only when every level has a value. Otherwise no shares. The target's
shares come the same way (its incidence in the setting).

### Node fields

`name` from `variables.json`; `role: outcome` on the target, nothing on the
others; `var_type`, `levels`, `unit`, `description` from `variables.json`.
`form` and `pos` are never written (GraphCreator lays the graph out). A node
enters a graph only through an edge in that graph; the target is always
written.

**Timing (wave 5).** Before cycles are broken: a `target_measure` node and
its edges leave both graphs (listed as `target_measures` in the report); an
edge into an `exogenous` node leaves both graphs (listed as
`into_exogenous`). A `later` node stays in both graphs: its `description`
ends with "Measured after the prediction time.", it is listed as `later`,
and the evidence report shows every node's timing.

**Ancestors only.** After cycles are broken, each graph keeps an edge only
when its effect is the target or has a path into the target in that graph.
So causes, their causes, and edges among them stay; an edge into a variable
that leads nowhere near the target goes, and is reported as `off_path` (in
`assemble`'s report, per graph) and in the evidence report.

### Edge fields

`evidence`: one entry per supporting paper (a paper with an existence
claim on the edge whose direction agrees with the sign, or `unclear`; a paper
whose claims only contradict the edge is named in the evidence report, not
here), `PMID:<pmid>`, else
`doi:<doi>`, else `arXiv:<id>`, else `vault:<paper id>`, ordered by grade then
year. `note`: one line, e.g. `probable; 2 cohort, 1 case-control; 3 papers; no
conflict; strength from 2 ORs (median d 0.41)`.

### Cycles

In each graph separately: while a directed cycle exists (`graphlib`), drop the
cycle's worst-supported edge (lowest grade, then fewest supporting papers, then
the later `(from, to)` in name order). Every drop is reported in the evidence
report and in `cycle_drops`. A two-way pair (A→B and B→A) is a cycle like any
other.

### The evidence report: `<id>.evidence.md`

Generated by `assemble`, for people:

1. Header: profile id, target, setting, date, paper count, the two graph
   files.
2. **Nodes:** per node, its name, aliases, type, levels, unit, shares and
   their source, and `measurement_note`.
3. **Edges:** per edge in the full graph, `from → to`, strict or full only,
   grade, sign and strength with how they were derived, conflicts, and every
   claim: paper id, PMID/DOI, design, setting match, the effect with its CI,
   and the quote.
4. **Dropped:** edges below the strict threshold (listed in the strict
   section's terms), cycle drops with the reason, and edges leading nowhere
   near the target.
5. **Not used:** unmapped names with their claim counts; quote-check
   rejections per paper; excluded papers; papers with `presents_dag: true`.

### Edge cases

- **No claims at all, or no claim into the target:** `assemble` still writes
  the files (the target alone) and the report says so in its first line;
  the skill reports it as the main finding. Usually the harmonizer missed the
  target's synonyms; a re-run of pass 2 is cheap.
- **Abstract-only papers** are extracted from the abstract; their quotes must
  be in it.
- **A cause with no type** gets one-word signs (the format treats it as
  neither nominal nor leveled).
- **A huge core question** (a common target in a broad setting): the
  checkpoint shows the paper count before anything costly; narrowing
  `causal_setting` or the window is the researcher's call.
- **An excluded paper found again** by the pair round: `find_papers.py`
  treats `.excluded/` as already in the vault, so it is never re-added; a leg
  that saves it anyway is caught by the next `exclude`.

## Changes to existing modules

### `templates/research-problem-profile-format-spec.md`

The five causal fields in the schema table with Required `causal`; the
legend gains "**causal** = required on a causal profile, absent elsewhere"; a
"Causal profiles" section (what marks one, the fixed questions, how the shared
fields are filled, where it lives); "Directories" gains `causal_graphs/`.

### `scripts/find_papers.py`

`EXCLUDED = ".excluded"`; `known()` adds the records in `.excluded/` as it
does `.merged/`'s, so `add` never re-saves an excluded paper and `pubmed`
never lists one. One new `find-papers` fixture case.

### `test-fixtures/run_offline.sh` and suite READMEs

- New suites `graphcreator` and `causal-graph`.
- `plugin-root`: also checks that the Bash block under `## Plugin root` in
  `skills/second-brain-causal-graph/SKILL.md` is identical to the pipeline's.
- `schema-copies`: `fields_intake` also reads the causal skill's YAML
  skeleton. (Until that skeleton exists, `fields_spec` leaves out rows whose
  Required column is `causal`; phase 1 adds that filter, phase 8 removes it.)

### `CLAUDE.md`

Stage table rows for the skill, the three agents and two scripts; the
templates paragraph names the two new specs; the model-tier rule becomes
"`opus` only for `topic-summarizer` and `causal-variable-harmonizer`"; "A
run writes into…" gains `causal_graphs/<id>/` and `claims/`; the test tables
gain the two suites, the three agents' T2 rows and a causal T3 rung; the
"designed, not built" pointer to this doc is removed.

### `README.md`

A "Causal graph" section: what it makes, how to start it, the three output
files, that every arrow has a quoted source, `exclude_papers`, and the rough
cost.

### `.claude-plugin/plugin.json`

A version bump when the feature lands; patch or minor is the researcher's
call.

### Unchanged

The discovery agents, the citation chaser, `stage_prep.py`,
`fetch_fulltext.py`, `link_papers.py`, `check_vault.py`, `build_vault.py`,
`second-brain-pipeline`, `research-problem-intake`,
`second-brain-topic-deep-dive`, `paper-summarizer`, `topic-summarizer`.

## Decisions and alternatives considered

| Topic | Chosen | Alternatives considered | Why |
|---|---|---|---|
| Entry point | Own flow reusing the discovery stages | Layer on an existing review vault; both | A review's searches are not aimed at causes |
| Wiring | One self-contained skill (user's choice) | Thin skill handing over to intake and pipeline branches, like the deep-dive | One file to read; copies guarded by two suites |
| Graph scope | The target's ancestors: direct causes, edges among them, causes of causes (user's choice, after wave 2; first agreed as "target, direct causes, edges among causes") | Direct causes only; keep every variable with any edge | The researcher wants how causes affect each other and what affects the causes |
| Causes of causes | A deliberate upstream round (user's choice) | Only what the papers report incidentally | Variables that affect the causes are part of the question |
| Upstream narrowing | Reviews and meta-analyses of each cause's risk factors first, then primary studies in the setting | Reviews only; setting-restricted only | Best evidence per paper; a fallback when no review exists |
| Upstream queries (after the wave-3 T2) | Cause and risk words in the title; the top 50 by relevance, reported as such, when still too broad (user's choice) | Title words only, too-broad causes skipped; MeSH `/etiology` subheadings | With `[tiab]` the review query for preoperative anemia found only reviews of anemia as a cause of outcomes, and every common cause (frailty, diabetes) was too broad; in the title, frailty gave 126 on-topic hits, and diabetes' top 50 held an exposure-wide umbrella review of its risk factors |
| Causes for the upstream round | Only nodes whose claims into the target show an effect | Any claim into the target | A node with only `none` claims is not a cause |
| T3 evaluation (2026-11-19) | Fix: exogenous nodes, title-restricted pair queries, skill wording; add timing | Fix only the T3 issues; also record model selection (stepwise vs pre-specified) | The T3 graph held a target proxy (preoperative CAM-CR) and postoperative variables with no notion of prediction time; model selection was left for later |
| Prediction time | A `prediction_time` profile field asked at intake (user's choice) | Inferred from the task | A vague task would give inconsistent timing tags |
| Later variables | Kept in both graphs, flagged in the description and the report (user's choice) | Full graph only; dropped from both | They can be real mediators an expert DAG includes; filtering for prediction is the researcher's step |
| Target measures | Dropped from both graphs, listed | Kept and flagged | A measure of the target is not a cause of it |
| Exogenous variables | Tagged by the harmonizer; skipped by upstream; an edge into one is dropped; a pair of two is not searched | No tag | Nothing causes age or sex; the T3 upstream round was spent on Age |
| Pair queries | Both nodes in the title AND the design block; narrow to reviews; top 50 when still too broad | `[tiab]` with a design block | Probe 2026-11-19: `[tiab]` + design was too broad for every pair tried (frailty × sarcopenia 1,411); in the title: 258, CHD × AF 20, dementia × stroke 41 as reviews, diabetes × obesity 423 reviews |
| Skill wording | "Dispatch the wave's calls in one message and wait for them all to return" | Naming `run_in_background: false` | Not every Agent tool has that parameter |
| Upstream size | Top 5 causes, at most 15 papers per run (user's choice) | Top 10 and 30; every cause and 60 | Cost (~+1M weighted) |
| Upstream agent | The pair searcher with an upstream mode | A new agent | Same tools and screening; one agent to maintain |
| Upstream stop | As the pair round: once, only on cap or manual downloads | Always stop before it | Consistent with the pair round |
| Setting terms | New `setting_terms` profile field, written at intake | Derive from `causal_setting` | A script cannot build a PubMed block from free text |
| Node set | Discovered from the literature | Researcher's variable list; either | A given list would hand over part of the answer |
| Evaluation | Outside the plugin (user's choice) | A dev script in `scripts/`; a final step of the skill | Keeps the plugin general and the ground truth away from generation |
| Vault | None, graph only | Light vault of variable notes; full vault | Cost; records stay reusable by a normal run |
| Extraction | New extractor, one read per paper | Summarizer writing claims in the same pass; claims from summaries | Without summaries there is no second read to save; summaries lose effects |
| Grounding | Verbatim quote, checked by script | Quote unchecked; model knowledge allowed | The experiment is literature versus expert, not model versus expert |
| Evidence admitted | All designs, graded | Causal designs only; ungraded | Risk-factor literature is mostly observational |
| Grade rule | Best design, one lower on conflict | Weighted paper count; agent judgement per edge | Reproducible; no double-counting of reviews and their studies |
| Adjacent settings | One grade lower | Full DAG only; no difference | Usable, but needs same-setting support for the strict DAG |
| Harmonization | Automatic, opus agent, editable JSON | Researcher checkpoint; script only | Hands-off for the experiment, still correctable |
| Aliases | Shown in the evidence report; mapping in internal `variables.json` (user's choice) | GraphCreator nodes-only file with aliases in descriptions; extra `aliases` key | Simplest for the researcher: one graph format, aliases readable |
| Fields filled | sign, strength, var_type/levels/unit, shares (user added shares) | form | Papers rarely support a functional form |
| Evidence output | Markdown report (user's choice) | YAML sidecar; notes only | For reading; the scripts keep JSON intermediates |
| Edge inclusion | Two DAGs, strict (probable+) and full | Threshold at intake; one DAG with every edge | Two thresholds to score without re-running |
| Legs | arXiv, biomedical, cross-field, chaser; no code (user's choice) | Biomedical and chaser only; a new Asta causal-sentence leg | Recall; existing agents unchanged |
| Cross-field terms | The target in adjacent settings | Causal-method terms; both | Finds causes from neighbouring settings |
| Inner edges | From all papers, then a capped pair search | Papers only; uncapped pair search | Inner edges are sparse otherwise; the cap bounds cost |
| Pair search agent | New sonnet agent | The chaser with pair probes | The chaser would also chase citations, past the cap |
| Pair round stop | Only on manual downloads or cap | Always; never | One turn of the researcher's only when it matters |
| Profile type | Topic profile plus causal fields | New `profile_type: causal` | Legs and chaser run unchanged |
| Leakage | `exclude_papers` plus `presents_dag` flag | Exclusion only; no guard | The expert graph's source must not hand back the answer |
| Strength | OR → d = ln(OR)·√3/π, bands on d | Via r; fixed OR cut-offs | Standard conversion; usable bands |
| Model tiers | Extractor and pair searcher sonnet, harmonizer opus | All sonnet; extraction on opus | Merging decides the node set; one small opus call per pass |
| Output folder | `second-brain/causal_graphs/<id>/` | Inside the paper vault | Matches `obsidian_vault/`, `deep_dives/` |
| Profile location | `causal_graphs/<id>/<id>.md` | `<root>/<id>.md` | The deep-dive would mistake it for a vault |
| Doc location | `CAUSAL_GRAPH_DESIGN.md` at the root | In the skill folder; `docs/` | No running model reads it as instructions |
| Optional causal fields | Required `causal`, always written with defaults | Required `no` | Found in wave 1: the doc said both; `no` would break the schema-copies check |
| Gaps settled in wave 1 | `names.txt` line format in the claims spec, with raw levels; strength bands include their lower bound; `evidence` lists supporting papers only; pair `a` is the better-supported node | — | Raised by the phase 1 agent; the doc left them open |
| Settled in wave 2 | A tie among the top-grade signed claims is a conflict (otherwise a contrary claim could never reach the edge's grade); only a paper's own findings are claims, not the work it cites; every variable in a claim gets a `measurements` entry, yes/no variables as `categorical ["no", "yes"]`; the harmonizer types a node from its raw levels when no measurement covers it; a pair or upstream cap counts papers added in that run (`find_papers.py` never lists a saved paper again); a null result passes the pair searcher's screening; the T2 tests of phases 3–5 ran from the orchestrating session after landing, one at a time | — | Raised by the wave-2 agents and the T2 tests |
| Defaults set in the design, not discussed | A `none` claim can be a conflict; per-unit estimates give no strength; window 10; 5 papers per pair; cycle tie-break by grade, papers, name; strength below d 0.1 omitted | — | Change in this doc if they prove wrong |

## Implementation phases

Phases form a dependency graph and are grouped into waves. Every phase in a
wave depends only on phases in earlier waves and owns a disjoint set of files,
so a wave can run in parallel (one sub agent per phase, "run wave N") or phase
by phase. Each phase is one commit and leaves the full test suite
(`bash test-fixtures/run_offline.sh`) passing. Status: `[ ]` to do, `[x]` done
(with the commit hash). Agent tests follow CLAUDE.md's ladder: state the
estimate first, T2 needs no approval, T3 needs the researcher's yes.

### Task graph

| Phase | Title | Depends on | Wave | Owns files |
|---|---|---|---|---|
| 1 | Contracts | none | 1 | `templates/causal-claims-spec.md`, `templates/research-problem-profile-format-spec.md`, `test-fixtures/causal/`, `test-fixtures/run_offline.sh`, `test-fixtures/schema-copies/README.md` |
| 2 | GraphCreator writer | none | 1 | `scripts/graphcreator.py`, `test-fixtures/graphcreator/` |
| 3 | Claim extractor | 1 | 2 | `agents/causal-claim-extractor.md` |
| 4 | Variable harmonizer | 1 | 2 | `agents/causal-variable-harmonizer.md` |
| 5 | Pair searcher | 1 | 2 | `agents/causal-pair-searcher.md` |
| 6 | Graph script | 1, 2 | 2 | `scripts/causal_graph.py`, `test-fixtures/causal-graph/`, `scripts/find_papers.py`, `test-fixtures/find-papers/` |
| 7 | The skill | 1 | 2 | `skills/second-brain-causal-graph/SKILL.md` |
| 9 | Upstream script and contracts | 6 | 3 | `scripts/causal_graph.py`, `test-fixtures/causal-graph/`, `templates/causal-claims-spec.md`, `templates/research-problem-profile-format-spec.md`, `test-fixtures/causal/fixture-causal-20261119.md` |
| 10 | Pair searcher upstream mode | 5 | 3 | `agents/causal-pair-searcher.md` |
| 11 | Skill upstream round | 7 | 3 | `skills/second-brain-causal-graph/SKILL.md` |
| 8 | Integration | 2–7, 9–11 | 4 | `test-fixtures/run_offline.sh`, `test-fixtures/plugin-root/README.md`, `test-fixtures/schema-copies/README.md`, `CLAUDE.md`, `README.md`, `PROJECT_CONTEXT.md`, `.claude-plugin/plugin.json`, `CAUSAL_GRAPH_DESIGN.md` |
| 12 | Timing contracts and script | 9 | 5 | `templates/causal-claims-spec.md`, `templates/research-problem-profile-format-spec.md`, `scripts/causal_graph.py`, `test-fixtures/causal-graph/`, `test-fixtures/causal/` |
| 13 | Harmonizer tags | 4 | 5 | `agents/causal-variable-harmonizer.md` |
| 14 | Pair searcher top 50 in pairs mode | 10 | 5 | `agents/causal-pair-searcher.md` |
| 15 | Skill: prediction time and wording | 11 | 5 | `skills/second-brain-causal-graph/SKILL.md` |

### Wave 1: contracts and the writer [x]

Phases: 1, 2. Parallel: yes. Integration check after the wave:
`bash test-fixtures/run_offline.sh`.

#### Phase 1: Contracts [x] (1f21eeb)

- **Goal:** the schemas every later phase codes against exist, with shared
  fixtures.
- **Depends on:** none.
- **Owns files:** `templates/causal-claims-spec.md`,
  `templates/research-problem-profile-format-spec.md`,
  `test-fixtures/causal/`, `test-fixtures/run_offline.sh`,
  `test-fixtures/schema-copies/README.md`.
- **Contracts used:** this doc's "Formats and interfaces".
- **Work:**
  - `templates/causal-claims-spec.md`: the claims file (example and field
    table from "Claims file"), `variables.json`, `pairs.json`, and the rules
    the extractor and harmonizer must follow that a reader of the files
    relies on (verbatim quotes, `...` joins, one claim per comparison, name
    matching). Instructions only, no history (CLAUDE.md rule).
  - Profile spec changes per "Changes to existing modules".
  - `test-fixtures/causal/`: a `README.md`; a causal profile
    `fixture-causal-20261119.md` (synthetic target "Fixture outcome", with an
    `exclude_papers` entry); `records/fixture-causal-20261119/` with 4–5 short
    synthetic records (identity headers per `paper-identity-spec.md`) whose
    bodies contain quotable effect sentences, including: a cohort with an
    adjusted OR, a case-control with the opposite direction, an RCT, a
    three-level categorical cause, a per-unit estimate, a prevalence, a paper
    to be excluded, and one with a drawn DAG; `claims/` files for them
    written by hand per the spec (one with a quote not in its paper); a
    `variables.json`; a `names.txt`.
  - `schema-copies`: `fields_spec` leaves out rows whose Required column is
    `causal`, in the README block and in `run_offline.sh` together.
- **Tests:** `schema-copies` still passes; every fixture claims file loads
  with `python3 -m json.tool`.
- **Done when:** `bash test-fixtures/run_offline.sh` passes; the spec's field
  table matches this doc's.
- **Out of scope:** any script or agent.

#### Phase 2: GraphCreator writer [x] (16d9123)

- **Goal:** `scripts/graphcreator.py` validates and writes `graphcreator/0.1`
  files exactly as `templates/graphcreator-dag-format.md` specifies.
- **Depends on:** none (the format is in the repo).
- **Owns files:** `scripts/graphcreator.py`, `test-fixtures/graphcreator/`.
- **Contracts used:** "`scripts/graphcreator.py`"; the format template.
- **Work:** `SCHEMA`, `validate`, `dump`, `needs_quotes` as specified; a
  `__main__` that reads a graph as JSON on stdin and prints the YAML (for the
  fixture suite). Stdlib only.
- **Tests:** `test-fixtures/graphcreator/` with a `README.md` holding the
  suite's command block: the format's own example as a JSON dict → expected
  YAML identical to the example minus `pos` and `form` lines that the dict
  leaves out (and one case keeping them); quoting cases (`no`, `Yes`, `1_000`,
  `2024-01-31`, `~`, a name with `:`); a per-level sign map in level order;
  empty fields left out; and invalid graphs (cycle, duplicate name, dangling
  edge, unknown key, shares count mismatch, unit on categorical) → expected
  error lists. If PyYAML happens to be importable, the README's block also
  round-trips each expected file; otherwise that line is skipped.
- **Done when:** the README's command block passes from the repo root;
  `python3 -m py_compile scripts/graphcreator.py`.
- **Out of scope:** reading YAML; `run_offline.sh` (phase 8).

### Wave 2: agents, the graph script and the skill [x]

Phases: 3, 4, 5, 6, 7. Parallel: yes. Integration check after the wave:
`bash test-fixtures/run_offline.sh`, plus the README block of
`test-fixtures/causal-graph/`.

#### Phase 3: Claim extractor [x] (75933c8)

- **Goal:** `agents/causal-claim-extractor.md` writes valid claims files.
- **Depends on:** 1.
- **Owns files:** `agents/causal-claim-extractor.md`.
- **Contracts used:** `templates/causal-claims-spec.md`; "Agents" above.
- **Work:** frontmatter (`name`, `description` ≤ ~80 words with the
  reimplementation warning, `tools: Read, Write, Bash`, `model: sonnet`); body
  per "Agents": inputs, reading with `read_until`, the extraction rules, the
  reply. Searching falls back to `grep -n` through Bash. No history, no test
  mode.
- **Tests:** T2 (~150k weighted tokens, stated first): copy
  `test-fixtures/causal/records/fixture-causal-20261119/` to the scratchpad,
  delete its `claims/`, dispatch per CLAUDE.md "Dispatching a plugin agent in
  this repo" with a 3-paper `papers:` list.
- **Done when:** the three claims files load as JSON, carry every spec field,
  and each quote is found by `grep -F` in its paper.
- **Out of scope:** the quote check script; harmonization.

#### Phase 4: Variable harmonizer [x] (9d3ea42)

- **Goal:** `agents/causal-variable-harmonizer.md` writes a valid
  `variables.json` from `names.txt`.
- **Depends on:** 1.
- **Owns files:** `agents/causal-variable-harmonizer.md`.
- **Contracts used:** the spec's `variables.json`; "Agents".
- **Work:** frontmatter (`tools: Read, Write, Bash`, `model: opus`); body:
  inputs, merge rules, pass-2 stability, target mapping, reply.
- **Tests:** T2 (~100k, stated first) on a scratch copy of
  `test-fixtures/causal/names.txt` with `variables exists: false`, then a
  pass 2 with two extra names appended.
- **Done when:** `variables.json` loads; the target node exists with the
  fixture's target synonyms as aliases; pass 2 kept every pass-1 node name.
- **Out of scope:** writing `names.txt` (phase 6).

#### Phase 5: Pair searcher [x] (cecd80a)

- **Goal:** `agents/causal-pair-searcher.md` searches pairs and saves papers
  through `find_papers.py`.
- **Depends on:** 1.
- **Owns files:** `agents/causal-pair-searcher.md`.
- **Contracts used:** the spec's `pairs.json`; `find_papers.py`'s `pubmed`,
  `show`, `add`; "Agents".
- **Work:** frontmatter (`tools: Read, Bash, Glob`, `model: sonnet`); body:
  per-pair loop, narrowing, screening, the 5-per-pair and total caps, the
  reply with needs-manual-download.
- **Tests:** T2 (~150k, stated first): a scratch `pairs.json` with one real
  pair (e.g. diabetes / obesity) and a scratch paper vault; prompt ends with
  the CLAUDE.md `TEST RUN` line adapted: "at most 1 pair and 2 saved papers".
- **Done when:** the saved records pass `stage_prep.py merge <dir> --dry-run`
  with `no_header` empty; the reply has the per-pair counts.
- **Out of scope:** writing `pairs.json`.

#### Phase 6: Graph script [x] (a973543)

- **Goal:** `scripts/causal_graph.py` with all six commands, and
  `find_papers.py` treating `.excluded/` as known.
- **Depends on:** 1, 2.
- **Owns files:** `scripts/causal_graph.py`, `test-fixtures/causal-graph/`,
  `scripts/find_papers.py`, `test-fixtures/find-papers/`.
- **Contracts used:** "`scripts/causal_graph.py`", "Behaviour and
  algorithms", `graphcreator.dump`, the claims spec.
- **Work:** the commands and reports as specified; quote normalization;
  grades, conflicts, sign, strength, shares, cycles, evidence report; `pairs`
  query building (each group: node name plus aliases, most-used first, at
  most 8 terms, multi-word terms quoted, each `[tiab]`; `narrow` adds the
  design block shown under "`pairs.json`"). In `find_papers.py`, `EXCLUDED`
  and `known()` as under "Changes to existing modules".
- **Tests:** `test-fixtures/causal-graph/README.md` with the command block,
  run on a temp copy of `test-fixtures/causal/`: `exclude` moves the excluded
  record and its claims; `check` rejects the planted bad quote; `plan` plans
  the records without claims; `names` and `pairs` match expected files;
  `assemble` matches expected `.dag.yaml` (strict and full) and
  `.evidence.md`, covering the conflict downgrade, the adjacent-setting
  downgrade, the per-level sign map, the per-unit estimate without strength,
  shares, a cycle drop and the `presents_dag` flag. One new `find-papers`
  case: a candidate whose record sits in `.excluded/` is not listed.
- **Done when:** the README block passes; `run_offline.sh find-papers`
  passes; `py_compile`.
- **Out of scope:** `run_offline.sh` entries (phase 8).

#### Phase 7: The skill [x] (595f0d1)

- **Goal:** `skills/second-brain-causal-graph/SKILL.md` runs the whole flow.
- **Depends on:** 1 (it codes against this doc's commands and agent prompts).
- **Owns files:** `skills/second-brain-causal-graph/SKILL.md`.
- **Contracts used:** "The run, step by step"; the agents' prompts; the
  scripts' commands and reports; the profile skeleton from "The causal
  profile".
- **Work:** frontmatter (`name`, `description` ≤ ~80 words); the Q&A with
  one YAML profile skeleton holding every causal and shared field it writes;
  `## Plugin root` with the pipeline's Bash block copied byte for byte; the
  discovery, checkpoint, extraction, harmonization, pair round, assembly and
  report steps; the lean-conversation and wave rules restated briefly.
- **Tests:** T1 is the skeleton and Bash-block checks, wired in phase 8;
  a T3 run is phase 8's.
- **Done when:** every command and agent name in the skill matches this doc
  (`grep`); the Bash block is identical to the pipeline's (`diff` of the two
  extracted blocks).
- **Out of scope:** CLAUDE.md, README.

After landing, two fixes went in as their own commits: `117fcf5` (ancestors
only, see "Node fields") and `24830df` (measurements for every variable;
types from raw levels), both found in review and the T2 tests.

### Wave 3: causes of causes [x]

Phases: 9, 10, 11. Parallel: yes. Integration check after the wave:
`bash test-fixtures/run_offline.sh`, the `causal-graph` README block, and the
T2 test of phase 10 (run from the orchestrating session after landing).

#### Phase 9: Upstream script and contracts [x] (e619200)

- **Goal:** `causal_graph.py upstream` writes `upstream.json`, and the
  contracts define it and the three new profile fields.
- **Depends on:** 6.
- **Owns files:** `scripts/causal_graph.py`, `test-fixtures/causal-graph/`,
  `templates/causal-claims-spec.md`,
  `templates/research-problem-profile-format-spec.md`,
  `test-fixtures/causal/fixture-causal-20261119.md`.
- **Contracts used:** "`upstream.json`", the `upstream` row of the commands
  table, the three new profile rows.
- **Work:** the `upstream` subcommand (ranking as `pairs` does, over causes
  of the target only; query terms built by the same helper; the review block
  and risk-factor block shown under "`upstream.json`"; the setting block
  from `setting_terms`, `fallback: null` without them; `--out` and the
  report); `upstream.json` in the claims spec (example, field table, that a
  cap counts papers added in one run); the three rows (Required `causal`) and
  the upstream round in the profile spec's "Causal profiles"; the three
  fields in the fixture profile.
- **Tests:** in the `causal-graph` README block: `upstream` on the fixture
  matches an expected `upstream.json` and report; a profile copy without
  `setting_terms` gives `fallback: null`.
- **Done when:** the README block passes; `run_offline.sh` passes.
- **Out of scope:** the agent and the skill.

#### Phase 10: Pair searcher upstream mode [x] (2f639fd)

- **Goal:** `causal-pair-searcher` runs `upstream.json` entries as described
  under "Agents".
- **Depends on:** 5 (and codes against phase 9's `upstream.json` as this doc
  defines it).
- **Owns files:** `agents/causal-pair-searcher.md`.
- **Work:** the `upstream:` input, the per-entry loop with `query` then
  `fallback`, the screening rule and preferences, list names `up-<n>`, the
  caps, the reply; the description mentions both modes and stays under ~80
  words.
- **Tests:** T2 from the orchestrating session after landing (~100k, stated
  first): one real cause, `max_papers` 2, the `TEST RUN` line.
- **Done when:** offline checks as in phase 5; then the T2 test's saved
  records pass `stage_prep.py merge --dry-run` with `no_header` empty.
- **Out of scope:** pairs mode, unchanged.

#### Phase 11: Skill upstream round [x] (6cc6d92)

- **Goal:** the skill runs step 8 of "The run, step by step" and asks for the
  new fields.
- **Depends on:** 7.
- **Owns files:** `skills/second-brain-causal-graph/SKILL.md`.
- **Work:** the Q&A writes `upstream_search_k` (5), `upstream_search_max_papers`
  (15) and `setting_terms` (drafted from the setting, confirmed with the
  researcher) into the skeleton; the upstream round after harmonizer pass 2,
  with its stop rule and pass 3; the report names the upstream round's
  additions.
- **Tests:** offline: names match this doc; the skeleton's fields are in the
  spec.
- **Done when:** grep checks pass; `run_offline.sh` passes.
- **Out of scope:** CLAUDE.md, README (phase 8).

After landing: `e09199c` (a cause needs a claim into the target that shows
an effect) and `6f20cfa` (upstream queries in the title; top 50 when still
too broad), the second after the T2 test of phase 10.

### Wave 4: integration [x]

Phases: 8. Parallel: single phase. Integration check after the wave:
`bash test-fixtures/run_offline.sh`, and the T3 run.

#### Phase 8: Integration [x] (8c30f5d)

- **Goal:** the feature is wired into the suites and documented, and has run
  once end to end at small scale.
- **Depends on:** 2–7, 9–11.
- **Owns files:** `test-fixtures/run_offline.sh`,
  `test-fixtures/plugin-root/README.md`,
  `test-fixtures/schema-copies/README.md`, `CLAUDE.md`, `README.md`,
  `PROJECT_CONTEXT.md`, `.claude-plugin/plugin.json`,
  `CAUSAL_GRAPH_DESIGN.md`.
- **Contracts used:** everything above.
- **Work:** add the `graphcreator` and `causal-graph` suites to `ALL` and as
  functions running their README blocks; extend `plugin-root` and
  `schema-copies` as under "Changes to existing modules" (removing phase 1's
  filter); update CLAUDE.md, README and a PROJECT_CONTEXT.md entry (placed by
  grep); ask the researcher patch or minor and bump `plugin.json`; mark this
  doc's status.
- **Tests:** every suite; then T3, with the researcher's yes and an estimate
  first: a scratch causal profile with a narrow target, one discovery leg with
  the `TEST RUN` line, at most 5 papers, through extraction, one harmonizer
  pass, a pair round capped at 1 pair and 2 papers, an upstream round capped
  at 1 cause and 2 papers, and `assemble`.
- **Done when:** `run_offline.sh` passes; the T3 run produces both DAGs and
  the report; its measured cost is recorded in PROJECT_CONTEXT.md.
- **Out of scope:** a full-scale run (only on the researcher's request).

### Wave 5: T3 fixes and timing [x]

Phases: 12, 13, 14, 15. Parallel: yes. After the wave the orchestrator lands
them, runs every suite, runs the T2 tests (the harmonizer's tags on the T3
run's real names and claims, then `assemble` on that copy; the pair
searcher's `top 50` in pairs mode), updates CLAUDE.md, README and
PROJECT_CONTEXT.md, and bumps the version to 0.1.3.

After landing: `a2d10ea` (the timing cases in the `causal-graph` suite) and
`22fc864` (the pair searcher screens the nodes themselves, not a distinct
condition sharing a word, and reads a listing in full when its output is cut
from view), the second after the pairs-mode T2 test.

#### Phase 12: Timing contracts and script [x] (b77ca93)

- **Goal:** the specs and `causal_graph.py` implement "Timing (wave 5)",
  the wave-5 `pairs` and `upstream` rules and the new profile field.
- **Depends on:** 9.
- **Owns files:** `templates/causal-claims-spec.md`,
  `templates/research-problem-profile-format-spec.md`,
  `scripts/causal_graph.py`, `test-fixtures/causal-graph/`,
  `test-fixtures/causal/`.
- **Work:** `variables.json`'s `timing` and `exogenous` (spec, defaults when
  missing, validation of `timing`'s values); `prediction_time` (profile spec
  row, Required `causal`, "Causal profiles"); in `assemble`, the timing
  rules and the three report keys, and the evidence report's timing line per
  node and its lists; in `pairs`, the exclusions and the new `query` and
  `narrow` (the same term helper with `[ti]`, `DESIGN` and review blocks);
  in `upstream`, the skip. Fixture: `prediction_time` in the profile; tags
  in `variables.json` that change no existing expected output unless the
  change is the point; side cases for a target-measure node dropped, a
  later node flagged, an edge into an exogenous node dropped, upstream
  skipping an exogenous top cause, and the new pair queries.
- **Done when:** the `causal-graph` README block and `run_offline.sh` pass;
  `py_compile`.
- **Out of scope:** the agents and the skill.

#### Phase 13: Harmonizer tags [x] (6b209fc)

- **Goal:** `causal-variable-harmonizer` sets `timing` and `exogenous` on
  every node.
- **Depends on:** 4.
- **Owns files:** `agents/causal-variable-harmonizer.md`.
- **Work:** read `prediction_time` and `causal_target` from the profile;
  the four timings and how to judge them (a variable the papers measure at
  or before the prediction time is `baseline`; one that can only exist
  after it, such as a postoperative event, is `later`; one that measures the
  target or its early form is `target_measure`; otherwise `unknown`);
  `exogenous` for variables nothing can cause; passes 2 and 3 keep existing
  tags and tag new nodes; the reply adds the counts per timing and the
  exogenous names.
- **Done when:** offline checks as in phase 4; the T2 test runs after
  landing.
- **Out of scope:** the script.

#### Phase 14: Pair searcher top 50 in pairs mode [x] (68a2add)

- **Goal:** pairs mode reruns a still-too-broad `narrow` with `--top 50`.
- **Depends on:** 10.
- **Owns files:** `agents/causal-pair-searcher.md`.
- **Work:** the pairs-mode loop and reply as in upstream mode's step 4
  (`top 50 of N`, never "searched whole"); pairs mode's screening and caps
  unchanged; the description stays under ~90 words.
- **Done when:** offline checks as in phase 10; the T2 test runs after
  landing.
- **Out of scope:** upstream mode.

#### Phase 15: Skill: prediction time and wording [x] (fae55fe)

- **Goal:** the skill asks for `prediction_time` and no longer names
  `run_in_background`.
- **Depends on:** 11.
- **Owns files:** `skills/second-brain-causal-graph/SKILL.md`.
- **Work:** `prediction_time` in the Q&A (proposed from the task, confirmed)
  and the skeleton; the wave rule reworded ("dispatch the wave's calls in
  one message and wait for them all to return before the next"); the report
  relays `target_measures`, `later` and `into_exogenous` and the
  harmonizer's timing counts.
- **Done when:** the Bash block still matches the pipeline's; the skeleton's
  fields are in the spec (after phase 12 lands); names match this doc.
- **Out of scope:** the agents.

## Tests

- **`graphcreator`** (phase 2): format example round trip, YAML 1.1 quoting,
  sign maps, omitted empties, and the refused-file errors.
- **`causal-graph`** (phase 6): the six commands on the shared fixture,
  covering every rule under "Behaviour and algorithms" that the fixture can
  hold.
- **`find-papers`** (phase 6): one case, `.excluded/` counts as known.
- **`plugin-root`**, **`schema-copies`** (phase 8): the skill's copies match.
- **`causal-graph`** (phase 9): `upstream` and its `fallback: null` case.
- **T2** per agent (phases 3–5, 10), on fixtures or a single live pair or
  cause: they test format, paths and handoffs, not extraction quality.
- **T3** (phase 8): the mini run above.

## Cost

A rough estimate for an 80-paper run, from the plugin's measurements
(CLAUDE.md, "Measuring cost"), weighted tokens: discovery ~3–3.5M (arXiv
~0.4M, biomedical ~1.0M, chaser ~1.4M, cross-field more than its 45k skip);
extraction ~70k per long paper, less for batched short ones, ~4–6M; the pair
round ~1M plus up to 40 papers' extraction (~2–3M); two harmonizer calls on a
names list, small; the upstream round ~0.3M plus up to 15 papers'
extraction (~1M); the orchestrating conversation on top. Roughly 11–16M in
all, against ~21M for the 42-paper review with summaries and topic notes.
Measure it on the first real run. Measured at T2 (2026-11-19, synthetic
fixture papers and one live pair): extractor on 3 short papers ~0.17M,
harmonizer ~0.08M per pass, pair searcher on one 25-hit pair ~0.09M, upstream
mode ~0.11–0.13M per test (one or two entries, up to 3 papers).

## Open issues

- **Model selection** is not recorded: most clinical risk-factor papers pick
  their adjustment set by univariate screening and stepwise regression, so
  their "adjusted" estimates are predictive, not causal, and still grade
  `probable`. Recording it (and possibly grading it lower) was left for later
  after the T3 evaluation.

- **Transitive edges** are kept as reported: if A→M→Y and A→Y are all
  claimed, all three stay. Pruning by mediation needs claims about adjusted
  mediators, which the extractor does not record.
- **Causes of causes** go one hop up, for the top causes only; deeper is out of scope.
- **`form`**, **`latent`** and the other roles are never written.
- **A vault for causal runs** (variable notes, a diagram) was declined for
  now; the records allow a normal pipeline run later.
- **Extraction quality** is untested by the fixtures (synthetic papers); the
  first real run should be checked by hand on a sample of edges.
- **Evaluation** against the expert graph lives in the researcher's own
  project: node alignment, SHD, edge precision and recall.
