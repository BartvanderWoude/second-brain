---
name: second-brain-causal-graph
description: >
  Builds a causal graph (GraphCreator DAG) of what the literature says causes a
  prediction target: a short Q&A, discovery (arXiv, PubMed, cross-field,
  citation chasing), a checkpoint, then claim extraction with verbatim quotes,
  variable harmonization, a search for edges among the causes, and graph
  assembly. Use when a researcher wants the causes of an outcome they predict
  as a graph. Not for a literature review (second-brain-pipeline).
---

# Causal graph

Builds the most likely causal graph of a prediction target from what the
literature reports: the target, its direct causes, and the edges among those
causes. Every arrow traces back to a sentence quoted from a paper; the model's
own background knowledge never adds an edge. The output is two GraphCreator
DAGs (strict and full) and an evidence report. Comparing them with an
expert-built graph happens outside the plugin.

Act as the calling agent: this skill runs the Q&A, dispatches agents and runs
scripts in order, and holds the checkpoint. It does no searching, extraction
or harmonizing itself. There are no paper summaries, topic notes, Obsidian
vault or code leg; the records stay in a standard paper vault, so a normal
`second-brain-pipeline` run can still build a vault from them later.

**Keep this conversation lean.** Every turn here re-reads the whole
conversation, so read only the scripts' compact reports and the agents'
replies, never papers, claims files, `names.txt` or `variables.json`. Give
each agent only its step's prompt template, filled in. Dispatch every fan-out
in **waves**:

- all `Agent` calls of a wave in **one message**, each with
  `run_in_background: false`;
- at most the wave size (read under "Plugin root") per wave; a call past it is
  refused, not queued. Start the next wave once the previous one has returned.

Agents reply `OK …` or `FAIL <reason>` plus a few anomaly lines; carry every
`FAIL` and anomaly line to the report. When an agent's reply recommends a
human step (a restart, an install, a login), relay it and stop: never do an
agent's job yourself or route around it. The one exception is the cross-field
leg's skip for a missing `ASTA_API_KEY`: an optional leg skipped, not a
failed run.

## 1. Q&A: the causal profile

`<root>` is `<project-root>/second-brain/`, in the directory Claude Code was
started in, never the home directory.

If the researcher names an existing causal profile
(`<root>/causal_graphs/<id>/<id>.md`), read its frontmatter: a `draft` comes
back here to be finished, a `confirmed` one goes straight to "Plugin root".

**No patient data.** The profile stays at the level of population, setting
and outcome descriptions.

Ask one question at a time, skipping anything the researcher already said. If
an answer is thin ("not sure", one word), ask exactly one follow-up, then
record what you have and name the gap in the draft.

1. **Target, setting, field.** If the opening message did not give them, ask
   in one open question: "What outcome do you predict, in which population and
   setting, over what time horizon, and in which field?"
   - `causal_target`: the outcome as a short node name (`Surgical site
     infection`).
   - `causal_setting`: population, setting and time horizon in one line. A
     claim from another population counts one grade lower, so ask once if the
     population or the horizon is missing.
   - `domain`: the field. `task`: "predict `<target>` `<setting>`" in one
     line.
2. **What the graph must not see.** Always ask, even if it seems unlikely:
   "Is there a paper or a graph this result must not see — for instance the
   paper your expert graph comes from? Titles, DOIs, PMIDs or arXiv ids are
   all fine; 'none' is a real answer." Record each as `seed_papers` entries are
   written: `"<exact title> — <doi>"`, `"<exact title>"`, or a bare DOI, PMID,
   PMCID or arXiv id. None: `exclude_papers: []`.
3. **Propose the rest, then confirm.** Draft these yourself from the answers
   and show them in one message:
   - `review_questions`, fixed, with the target and setting filled in:
     1. What causes `<causal_target>` in `<causal_setting>`?
     2. How do those causes affect each other?
     3. How large are the effects, and how common are the causes in this
        setting?

     and `core_questions: [1]`, so the legs and the citation chaser cover
     question 1 exhaustively.
   - `review_scope`: IN, studies reporting causes, risk factors or predictors
     of the target in the setting or in adjacent settings, with an effect
     estimate or an explicit causal claim, and studies reporting effects among
     those factors; OUT, papers that report only a prediction model's
     performance, plus anything the researcher rules out.
   - `review_purpose`: building a literature-derived causal graph of the
     target in the setting, and what it is for if the researcher said.
   - `close_field_terms`, cause-oriented, each with the setting's words:
     "`<target>` risk factors", "predictors of `<target>`", "Mendelian
     randomization `<target>`", "`<target>` meta-analysis".
   - `generalized_methodology_terms`: the target in **adjacent settings or
     populations** (infection after colorectal surgery → "postoperative wound
     infection", "infection after any abdominal surgery"), so the cross-field
     leg finds causes established in neighbouring settings. Ask: "Which
     neighbouring settings would you trust as evidence too?"
   - `recall_probes`: 1–3 PubMed queries for question 1. Each has 2–3 concept
     blocks joined by AND, a block being an OR-group of synonyms in
     parentheses with every multi-word phrase quoted and terms tagged
     `[tiab]`: the target, the setting, and a cause block (`"risk factor*"`,
     `predictor*`, `"odds ratio"`, `"mendelian randomi*"`). Truncate word
     families with a stem of 4+ characters. Aim for tens of hits, not
     thousands. Ask: "Would the papers you'd expect to name the causes match
     these?"
   - The defaults, which the researcher may change: `pair_search_k` 15 (how
     many top causes get the search for edges among them),
     `pair_search_max_papers` 40 (papers that search may add in total),
     `date_window_years` 10 (the core question has no window anyway).

   `seed_papers` stays `[]` unless the researcher names papers they know
   report causes. `keywords_of_interest` is `[]` (no topic notes are written)
   and there is no `code_vault_path` (no code leg).
4. **Write the draft.** `<id>` is `<slug>-<yyyymmdd>`, the slug a short
   hyphenated tag from the target and setting (`ssi-colorectal-causes`), with
   `-2` if `<root>/causal_graphs/<id>/` already exists. Create, with
   `mkdir -p` semantics, `<root>/causal_graphs/<id>/.work/` and
   `<root>/paper_vault/<id>/`. Write the profile to
   `<root>/causal_graphs/<id>/<id>.md` with `status: draft`, in this format,
   writing every field (the causal fields with their defaults):

   ```yaml
   ---
   id: <slug>-<yyyymmdd>
   created: <yyyy-mm-dd>
   status: draft               # confirmed only on the researcher's yes
   profile_type: topic
   domain: <field>
   task: predict <target> <setting>
   causal_target: <outcome node name>
   causal_setting: <population, setting, time horizon>
   exclude_papers: []          # same string forms as seed_papers
   pair_search_k: 15
   pair_search_max_papers: 40
   review_scope: >-
     IN: <causes, risk factors or predictors of the target in this or adjacent
     settings, with an effect estimate or a causal claim; effects among those
     factors>. OUT: <performance-only prediction-model papers; more if named>.
   review_purpose: <build a literature-derived causal graph of the target>
   review_questions:
     - What causes <causal_target> in <causal_setting>?
     - How do those causes affect each other?
     - How large are the effects, and how common are the causes in this setting?
   core_questions: [1]
   seed_papers: []
   date_window_years: 10
   recall_probes: []           # 1–3 single-quoted PubMed boolean queries
   close_field_terms: []
   generalized_methodology_terms: []
   keywords_of_interest: []
   paper_vault_path: <root>/paper_vault/<id>/
   ---
   ```

   `paper_vault_path` is the absolute path created above. Below the
   frontmatter, a short paragraph restating the target, the setting and what
   the graph is for.
5. **Show it and confirm.** Show the frontmatter and ask the researcher to
   confirm or edit. Apply edits to the file; set `status: confirmed` only on
   their yes. Discovery never runs against a `draft`.

## Plugin root

The plugin's `templates/` and `scripts/` are needed from here on, by absolute
path. Resolve the root once, and read the wave size, with this Bash call as
written. It takes the first folder whose `.claude-plugin/plugin.json` names
this plugin, from: `$CLAUDE_PLUGIN_ROOT`; the working directory; the installed
copy; a marketplace clone.

```bash
python3 - <<'EOF'
import glob, json, os
def ours(d):
    try: return json.load(open(os.path.join(d, ".claude-plugin", "plugin.json")))["name"] == "second-brain-researcher"
    except Exception: return False
p = os.path.expanduser("~/.claude/plugins")
dirs = [os.environ.get("CLAUDE_PLUGIN_ROOT", ""), os.getcwd()]
try: dirs += [e["installPath"] for k, v in json.load(open(p + "/installed_plugins.json"))["plugins"].items()
              if k.startswith("second-brain-researcher@") for e in v]
except Exception: pass
dirs += sorted(glob.glob(p + "/marketplaces/*/"))
print("plugin root:", next((os.path.normpath(d) for d in dirs if d and ours(d)), "NOT FOUND"))
print("wave size:", os.environ.get("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", "20"))
EOF
```

On `NOT FOUND`, stop and tell the researcher the plugin's files could not be
found. If a resumed run reaches a later step without a plugin root in this
conversation, run this call first. If a template or script path below does not
exist, stop and report it; never guess a path.

Below, `<profile>` is the confirmed profile's absolute path,
`<paper_vault_path>` its `paper_vault_path`, and `<causal_graphs/<id>>` the
absolute folder `<root>/causal_graphs/<id>`.

## 2. Discovery

Dispatch the three discovery legs as **one wave**, each with this prompt and
nothing else (the `find_papers` line for the biomedical leg only):

```
profile: <profile>
identity spec: <plugin root>/templates/paper-identity-spec.md
fetcher: <plugin root>/scripts/fetch_fulltext.py
find_papers: <plugin root>/scripts/find_papers.py
```

- `second-brain-paper-downloader`: arXiv.
- `second-brain-biomed-downloader`: PubMed, PMC, Europe PMC.
- `second-brain-crossfield-searcher`: the target in adjacent settings, via
  Asta. Dispatch it **unconditionally**; it checks its own key.

The legs are independent: one failing never discards another's results. A leg
that reports a skip is one line in the checkpoint. Never re-run discovery to
fix a missing key.

Once the three legs have returned, dispatch `second-brain-citation-chaser`:

```
profile: <profile>
find_papers: <plugin root>/scripts/find_papers.py
```

It replies `OK` with the core question, seeds, probes (drafted ones marked),
candidates and additions per round, why it stopped, OpenAlex gaps, and a
**needs-manual-download** list; keep all of it for the checkpoint.

Then two Bash calls, in order:

```
python3 <plugin root>/scripts/stage_prep.py merge <paper_vault_path>
python3 <plugin root>/scripts/causal_graph.py exclude <paper_vault_path> --profile <profile>
```

`merge` keeps one file per paper and moves the other copies to `.merged/`;
keep each merge, its `possible_duplicates` and its coverage block for the
checkpoint. `exclude` moves every record matching an `exclude_papers` entry to
`.excluded/`; keep its `excluded` and `not_found`.

## 3. Checkpoint — stop and wait

Relay one combined summary to the researcher and **stop**:

- **Papers**: what each leg saved, with question 1's count separate; which
  legs ran and which were skipped; each leg's zero-hit and too-broad queries;
  what was merged; what was skipped, dropped, or left abstract-only. The total
  paper count up front: extraction is the costly step, so this is the cheap
  point to trim, and a very large count means narrowing `causal_setting` or
  the window, which is the researcher's call.
- **Full-text coverage as numbers**, from the merge report: `full_text` (full
  versus abstract-only), `by_source`, `extraction_warnings`, `no_header`, and
  `possible_duplicates`. An abstract-only paper is extracted from its abstract
  alone, so it yields fewer claims.
- **needs-manual-download**, from the biomedical leg and the chaser, verbatim
  as one list with title, DOI and PMID; mark the chaser's as core papers.
  Never fold it into the skipped tally, and never proceed past it without an
  explicit decision. To supply one, the researcher saves the PDF as
  `<paper_vault_path>/<id>.pdf`; when they say so, run for each:

  ```
  python3 <plugin root>/scripts/fetch_fulltext.py --source manual \
    --record <paper_vault_path>/<id>.md --from-pdf <paper_vault_path>/<id>.pdf
  ```

  Delete the PDF once the report says `full_text: full`. If it says the file is
  not a PDF (a browser often saves a publisher's HTML page as `.pdf`), tell the
  researcher and delete nothing.
- **Core coverage**: the core question, seeds, the probes (drafted ones
  marked, so the researcher can add them to `recall_probes`), candidates and
  additions per round, the total added by title, and why it stopped. Name
  OpenAlex's gaps. If the chaser hit its 40-paper guard or 4-round cap, say so
  prominently.
- **Exclusions**: each excluded record with the entry it matched, and every
  `not_found` entry (not in the vault, or written in a form that could not
  match).

Ask whether to proceed to extraction, add missing papers first, or change
something (remove a paper, add an `exclude_papers` entry and run `exclude`
again, re-run discovery with other terms). Do not continue in the same turn:
wait for an explicit go-ahead.

## 4. Extraction

Only after the researcher's go-ahead. Plan the fan-out (add `--redo` only if
the researcher asked to redo existing claims files):

```
python3 <plugin root>/scripts/causal_graph.py plan <paper_vault_path>
```

Dispatch `causal-claim-extractor` once per entry of its `dispatches`, in
waves:

```
papers:
- <paper_vault_path>/<id>.md (read_until: <N>)
- <paper_vault_path>/<id>.md
format: <plugin root>/templates/causal-claims-spec.md
profile: <profile>
```

`(read_until: <N>)` only on an entry whose dispatch has `read_until`. Then
check every claims file and its quotes:

```
python3 <plugin root>/scripts/causal_graph.py check <paper_vault_path>
```

Relay its counts (`papers`, `claims_kept`, `claims_rejected`), the `invalid`
files and the `missing` papers by name, and the `presents_dag` papers: a paper
that draws its own causal diagram of the target may be the expert graph's
source.

## 5. Harmonize, pass 1

```
python3 <plugin root>/scripts/causal_graph.py names <paper_vault_path> \
  --variables <causal_graphs/<id>>/.work/variables.json \
  --out <causal_graphs/<id>>/.work/names.txt
```

Then dispatch `causal-variable-harmonizer`:

```
names: <causal_graphs/<id>>/.work/names.txt
variables: <causal_graphs/<id>>/.work/variables.json
variables exists: false
profile: <profile>
format: <plugin root>/templates/causal-claims-spec.md
```

## 6. Pair round: edges among the causes

```
python3 <plugin root>/scripts/causal_graph.py pairs <paper_vault_path> \
  --variables <causal_graphs/<id>>/.work/variables.json --profile <profile> \
  --out <causal_graphs/<id>>/.work/pairs.json
```

If it reports no `pairs`, skip to step 7. Otherwise dispatch
`causal-pair-searcher`:

```
pairs: <causal_graphs/<id>>/.work/pairs.json
profile: <profile>
find_papers: <plugin root>/scripts/find_papers.py
```

It replies `OK` with hits, screened and added per pair, the too-broad pairs,
whether it hit the `max_papers` cap, and a **needs-manual-download** list.
Then, as after discovery:

```
python3 <plugin root>/scripts/stage_prep.py merge <paper_vault_path>
python3 <plugin root>/scripts/causal_graph.py exclude <paper_vault_path> --profile <profile>
```

**Stop once, and only** if the searcher reported needs-manual-download papers
or hit its cap. Relay the per-pair counts, the list verbatim (title, DOI,
PMID), and the cap, and offer: supply PDFs (the `fetch_fulltext.py --source
manual` route under "Checkpoint"), raise `pair_search_max_papers` in the
profile and re-run the round (`pairs`, the searcher, `merge`, `exclude`), or
continue as is. Wait for the answer. Otherwise, and after that answer,
continue without stopping again; a re-run round that hits the cap again is
reported, not a second stop.

Extract the new papers: `plan` (only the new records lack claims files), the
extractor in waves with the step 4 prompt, and `check`, relaying as in step 4.
Then the names the harmonizer has not mapped yet:

```
python3 <plugin root>/scripts/causal_graph.py names <paper_vault_path> \
  --variables <causal_graphs/<id>>/.work/variables.json --new-only \
  --out <causal_graphs/<id>>/.work/names.txt
```

If it reports `names` 0, skip pass 2. Otherwise dispatch
`causal-variable-harmonizer` with the step 5 prompt and
`variables exists: true`: it keeps every existing node and mapping and only
adds aliases or nodes for the new names.

## 7. Assemble

```
python3 <plugin root>/scripts/causal_graph.py assemble <paper_vault_path> \
  --variables <causal_graphs/<id>>/.work/variables.json --profile <profile> \
  --out <causal_graphs/<id>>
```

It writes `<id>.dag.yaml` (strict: edges graded probable or better),
`<id>.full.dag.yaml` (every supported edge) and `<id>.evidence.md` into
`<causal_graphs/<id>>`. On exit 2 with `{"error": …}`, fix the named input and
run it again; never write a graph or the report by hand.

## Report back

- **If `target_edges` is 0 in the full graph, say so first**: the files hold
  the target alone. Usually the harmonizer missed the target's synonyms; offer
  a harmonizer re-run (pass 2) and `assemble` again, which is cheap.
- The profile id; papers in the vault, excluded, and extracted; claims kept
  and rejected by the quote check, with the papers that lost the most.
- Both graphs: nodes, edges, and edges into the target, strict and full; the
  cycle drops; `warnings`.
- `top_unmapped`: the names too vague to be one variable that lost the most
  claims.
- `presents_dag` papers by name: if one is the expert graph's source, add it
  to `exclude_papers`, then run `exclude` and `assemble` again (scripts only,
  free).
- The pair round in one line: pairs searched, papers added, too-broad pairs,
  whether the cap was hit.
- Anything that failed at any step, plainly, with every agent's `FAIL` line.
- The three output paths. The researcher may edit
  `<causal_graphs/<id>>/.work/variables.json` (merge or split nodes, fix
  levels) and re-run `assemble`, which costs nothing.

Then say that every edge cites quoted evidence in `<id>.evidence.md`, and that
comparing the graphs with an expert-built graph happens outside the plugin.
