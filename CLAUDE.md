# second-brain-researcher

A Claude Code plugin that turns a research problem or review topic into a
linked Obsidian vault, or a prediction target into a literature-derived causal
graph: `skills/` orchestrate, `agents/` do the judgment work,
`scripts/` (stdlib Python) do everything deterministic, `templates/` hold the
formats, `test-fixtures/` hold the offline tests.

## Three docs, three readers

- **`README.md`** is for colleagues who install and use the plugin: what it
  is, how to install and use it, where it searches, what the vault looks like.
  Plain language, short. No design reasoning and no internals; those go here.
- **`CLAUDE.md`** (this file) is how the project works and its rules, complete
  and current. Anything a session needs to work on this repo belongs here, even
  when `PROJECT_CONTEXT.md` also records it.
- **`PROJECT_CONTEXT.md`** is the history: the changes and design decisions of
  past sessions, the reasoning and the measurements behind them. Search it to
  learn what was decided before and why. It never replaces this file.

When a session decides something, the rule or fact that results goes here, the
story and evidence go in a new `PROJECT_CONTEXT.md` entry, and whatever a user
sees goes in `README.md`.

## PROJECT_CONTEXT.md: search it, never read it whole

At ~33 KB `PROJECT_CONTEXT.md` is meant to be searched, not read: reading it
whole adds ~8k tokens to the context, paid again on every later turn. Never
`Read` it without `offset`/`limit`, never `cat` it, and never `@`-import it
here.

- **Find:** `grep -n -i '<term>' PROJECT_CONTEXT.md | cut -c1-200`. Each
  paragraph is one line of up to ~1,500 characters, so trim the output.
  `grep -n '^## \|^- \*\*' PROJECT_CONTEXT.md | cut -c1-120` lists the
  sections and decision entries.
- **Read:** only the entry you need, by its line numbers:
  `sed -n '<from>,<to>p' PROJECT_CONTEXT.md`, or `Read` with `offset`/`limit`.
- **Write:** add a new decision as its own entry, in the section it belongs
  to, found and placed the same way; do not load the file to edit it. When a
  decision is reversed, rewrite or delete its entry rather than striking it
  through: git keeps the old one.

## How it works

The spec has 7 stages. 1–5 are built. Stage 6 (cross-linking) is built only
in reduced form: topic notes from shared keywords, `## Related topics`, and
`link_papers.py`'s paper-to-paper edges. Stage 7 (experiment plan) is not
built, and neither are repo cloning, running, or the Docker sandbox.

Beside the pipeline, the `second-brain-causal-graph` skill builds a causal DAG
of a prediction target from the literature, in the researcher's GraphCreator
format, to be compared with an expert-built graph outside the plugin. It
reuses discovery (the arXiv, biomedical and cross-field legs, the chaser, the
merge, the checkpoint), then runs claim extraction, variable harmonization, a
pair round (edges among the top causes) and an upstream round (causes of the
top causes, one hop up), and assembles the target's ancestors
deterministically into a strict DAG (edges graded probable or better), a full
DAG and an evidence report. Every arrow traces to a verbatim quote that
`causal_graph.py check` has found in its paper. No summaries, topic notes, vault or code leg; the
records stay in a standard paper vault. The design record, with every rule of
grading, sign, strength, shares and cycles and the decisions behind them, is
[CAUSAL_GRAPH_DESIGN.md](CAUSAL_GRAPH_DESIGN.md).

| Stage | Piece | Job |
|---|---|---|
| 1–2 | skill `research-problem-intake` (+ `deep-dive.md`) | adaptive Q&A for a problem or a topic review → profile note: CLAIM-checklist fields, the two term lists, recall probes, keyword taxonomy; sets up the working dirs |
| all | skill `second-brain-pipeline` (+ `deep-dive.md`) | orchestrator: runs 1–5, holds the stage-4 checkpoint, dispatches agents in waves, reads script reports only |
| — | skill `second-brain-topic-deep-dive` | resolves vault and note (`stage_prep.py topic`, which also warns about old-style ids), then intake's deep-dive branch and pipeline 3–5 on a `deep_dive_of` profile; new papers go into the vault's own paper vault, summarized against the vault's profile |
| 3 | `second-brain-paper-downloader` (sonnet) | arXiv leg: close-field then generalized terms; every core paper, the background capped at 20 |
| 3 | `second-brain-biomed-downloader` (sonnet) | PubMed/PMC/Europe PMC leg, via `paper-search-mcp` and `find_papers.py pubmed` (whole hit sets) |
| 3 | `second-brain-crossfield-searcher` (sonnet) | paper bodies via Asta, for methods from adjacent fields |
| 3 | `second-brain-citation-chaser` (sonnet) | after the legs: the core question exhaustively. Recall probes as whole PubMed hit sets, then OpenAlex one hop both ways from the core papers, round after round until one adds nothing. Screens titles first, abstracts only where a title leaves it unsure |
| 3 | `second-brain-code-finder` (sonnet) | after the paper legs and the merge (it needs the papers on disk): repos the papers name, plus `gh search repos`; GitHub API only. Notes record the license (`none` = no reuse rights) and whether it is the official implementation |
| 3 | `scripts/fetch_fulltext.py` | upgrades a saved record to full text in place |
| 3 | `scripts/find_papers.py` | the vault's records as chase seeds (`seeds`); numbered candidate lists (`pubmed`, `chase`, `show`); `add` saves chosen ones as records and fetches their full text. A query too large to fetch whole is flagged, never silently cut to its top hits |
| 3–5 | `scripts/stage_prep.py` | duplicate merge and coverage figures, summarizer fan-out plan, keyword index, topic digests, `topic` report, `digest --since` |
| 5 | `paper-summarizer` (sonnet) | one long paper, or up to 8 short ones → summaries per `paper-page-template.md`; long papers read up to the references. Given the profile, `related_problem`, `matched_terms` and the relevance synthesis are grounded in that problem |
| 5 | `topic-summarizer` (opus) | one keyword + its digest → topic note; checks the full text of ≤3 central papers (6 in a deep-dive) on a fixed budget |
| 5 | `scripts/link_papers.py` | citation links and SPECTER2 similarity from Semantic Scholar |
| 5 | `scripts/check_vault.py` | `records` before the vault, `vault` links after |
| 5 | `scripts/build_vault.py` | profile, papers, topics, repos → the Obsidian vault, with BibTeX from arXiv's own metadata |
| causal | skill `second-brain-causal-graph` | self-contained: its own Q&A (a causal profile: a topic profile plus the causal fields), its own copy of the plugin-root call, discovery without the code leg, the checkpoint, extraction, harmonization, the pair and upstream rounds (each stops once, only on manual downloads or a hit cap), assembly, report |
| causal | `causal-claim-extractor` (sonnet) | one long paper, or up to 8 short ones → `claims/<id>.json` per `causal-claims-spec.md`: every cause–effect pair the paper itself reports, each with a verbatim quote; prevalences; every variable's measurement; the paper's design and `setting_match` |
| causal | `causal-variable-harmonizer` (opus) | `names.txt` → `variables.json`: raw names merged into nodes, the target's synonyms mapped to the target, types and levels, and each node's `timing` against the profile's `prediction_time` (`baseline`, `later`, `target_measure`, `unknown`) and `exogenous`; a later pass keeps every existing node, mapping and tag |
| causal | `causal-pair-searcher` (sonnet) | PubMed via `find_papers.py`, two modes: `pairs:` (an effect between two top causes no paper links yet) and `upstream:` (what affects a top cause: reviews first, then the setting). In both modes the variables are in the title, and a still-too-broad query gives the top 50 by relevance, reported as such. A paper passes only on the nodes themselves, not a distinct condition sharing a word. At most 5 papers per item, a total cap per run |
| causal | `scripts/causal_graph.py` | `plan`, `check` (spec and quote check), `exclude`, `names`, `pairs`, `upstream`, `assemble` (target measures and edges into exogenous nodes dropped, later nodes flagged, grades, signs, strength, shares, cycle drops, ancestors only → both DAGs and `<id>.evidence.md`); `pairs` and `upstream` skip target measures, `upstream` also exogenous nodes |
| causal | `scripts/graphcreator.py` | validates a graph and writes `graphcreator/0.1` YAML; no reader |
| dev | `scripts/token_report.py` | a session's real token spend; never called by the pipeline |

Topics: the picker offers keywords on ≥2 papers, near-duplicate slugs merged;
a profile keyword with no papers still gets a note (a gap worth seeing). The
index and digests also count papers that name a topic without carrying its
slug, since tags drift between summarizer batches. Re-selecting a topic deepens
its note and keeps the researcher's edits; a `deep_dive` note is written deeper
and a later re-run cannot shrink it.

Templates: `paper-identity-spec.md` (when two hits are one paper, filename,
id, the identity header every saved record carries);
`research-problem-profile-format-spec.md` (the profile schema, a contract kept
in `templates/` because there is no `docs/`); `paper-page-template.md`,
`topic-note-template.md`, `repo-note-template.md` (note formats);
`graphcreator-dag-format.md` (the researcher's `graphcreator/0.1` DAG format,
kept verbatim; the causal graph's output); `causal-claims-spec.md` (claims
files, `names.txt`, `variables.json`, `pairs.json`, `upstream.json`, the
quote check, and the rules the extractor and harmonizer follow).

A run writes into the researcher's own project, never into this repo, under
`<project>/second-brain/`: `paper_vault/<id>/` (records, `summaries/`,
`topics/`, `repos/`; for a causal run `claims/` instead, and `.excluded/`
beside `.merged/`), `code_vault/<id>/` (stays empty), `obsidian_vault/<id>/`,
`deep_dives/<vault id>/` (deep-dive profiles) and `causal_graphs/<id>/` (the
causal profile `<id>.md`, the two DAGs `<id>.dag.yaml` and
`<id>.full.dag.yaml`, `<id>.evidence.md`, and `.work/` with `names.txt`,
`variables.json`, `pairs.json`, `upstream.json`). A causal profile lives
there, never in `<root>/*.md`, where the deep-dive would read it as a vault's
profile. The researcher may edit `variables.json` and re-run `assemble`, which
costs no tokens. Each problem is
its own vault, opened at `obsidian_vault/<id>/`. Every wikilink is written from
that folder (`[[papers/<id>|Title]]`, `[[topics/<slug>]]`,
`[[repos/<owner>-<name>]]`, `[[<id>]]`) and `check_vault.py vault` checks
them. On a re-run `build_vault.py` replaces only the `##` sections it owns
(listed in its docstring) and keeps everything else. A vault is a folder of
Markdown, so none of this needs Obsidian installed; the pipeline only offers to
open the vault at the end, and never installs Obsidian.

## Rules

- **No patient data.** A profile stays at the level of modality, cohort and
  task descriptions.
- **Nothing is cloned or executed before the stage-4 checkpoint.** The code leg
  runs before it, so it uses the GitHub API only: no clone, no install, and
  `code_vault/<id>/` stays empty.
- **Paywalled papers: open access first, then Sci-Hub.** The biomedical leg's
  last rung is `download_scihub`, and `fetch_fulltext.py` validates what it
  returns. Only what resolves nowhere is flagged for manual download, and the
  checkpoint stops on that list. Sci-Hub is legally contested and ships to
  everyone who installs the plugin. Using it is the operator's deliberate
  decision, and the README says so.
- **One copy of each schema.** The `templates/` files are the only
  definitions; consumers cite them, never restate them. A drifting copy breaks
  a handoff silently. The one exception is the YAML skeletons of the profile
  in intake and in the causal-graph skill (reading the whole spec in the main
  conversation costs more); the `schema-copies` suite fails when their fields
  drift from the spec's.
- **Every agent's `description:` warns against being reimplemented** from the
  description alone or routed around after a blocking report. It is the only
  text an orchestrating session sees before dispatch.
- **Skill, agent, or script.** A skill only when it needs the main conversation
  (live Q&A, holding the checkpoint, asking which vault is meant); otherwise an
  agent with an enforced `tools:` allowlist, or a script when no model is
  needed.
- **Model tiers are pinned per agent, never `inherit`.** `sonnet` for per-item
  and mechanical work, `opus` only for `topic-summarizer` and
  `causal-variable-harmonizer` (its merges decide the graph's node set), so
  synthesis quality does not depend on the main session's model.
- **Grounding: no edge without a quote.** Every arrow of a causal graph
  traces to a verbatim quote that `causal_graph.py check` finds in its paper;
  the model's own knowledge never adds an edge or fills a claim. The
  comparison with an expert graph stays outside the plugin, and
  `exclude_papers` keeps that graph's source out of the run.
- **The main conversation reads compact script reports**, never papers,
  summaries or notes: every turn there re-reads the whole conversation.
- **Prompts carry instructions, not history.** Agents, skills and templates
  are read by a model on every run: no past-run anecdotes, no measurements, no
  citations of `PROJECT_CONTEXT.md` (an installed plugin's agents cannot use
  it). A reason stays only where it decides an edge case. The story goes in
  `PROJECT_CONTEXT.md`.
- **Descriptions stay short**, about 80 words at most: what it does, when to
  use it, its inputs, and the reimplementation warning. Every skill's and
  agent's description is loaded into every session of everyone who installs
  the plugin.
- **Experiment-plan code reuse** (when built) targets the researcher's existing
  project repo, not a new one.

## Plugin mechanics

- **Install and the arXiv dependency.** The home repo is
  `github.com/BartvanderWoude/second-brain`, and it is its own marketplace
  (`.claude-plugin/marketplace.json`): users add it with
  `/plugin marketplace add BartvanderWoude/second-brain`. `plugin.json` declares `arxiv-mcp-server`
  (marketplace `arxiv-mcp`) as a dependency, which is auto-installed only once
  that marketplace is registered. Without it the install command still reports
  success, but Claude Code refuses to load this plugin at all, in a real install and under `--plugin-dir` alike. So no agent
  re-checks the dependency. Adding the marketplace later self-heals without a
  restart.
- **Use vs. dev.** Real runs, the author's included, use the marketplace
  install, from any project folder, with the keys in `~/.claude/settings.json`
  (below). It runs from a cached copy of what was pushed to `develop`, so
  edits reach it only after a push and `claude plugin update
  second-brain-researcher@second-brain-researcher` plus a restart. That
  update compares `version` in `plugin.json` only: without a bump it reports
  "already at the latest version" and keeps the old copy, though it pulls the
  marketplace clone to the new commit. So **bump `version` in every push that
  should reach installs** (skills, agents, scripts, templates, `.mcp.json`):
  the patch number by default (`0.1.0` → `0.1.1` → `0.1.2`), the minor one
  (`0.2.0`) only when the user decides a release warrants it.
  `claude --plugin-dir <repo>` is for testing: it loads
  the working tree live, with no reinstall after edits. Started outside the
  repo it also needs `CLAUDE_PLUGIN_ROOT=<repo>`, or the root lookup takes the
  installed copy, or reports `NOT FOUND` when there is none (checked with
  `claude -p`). The dependency must be installed either way.
- **The `[pdf]` extra.** The `arxiv-mcp-server` plugin launches plain
  `uvx arxiv-mcp-server`, which cannot extract arXiv papers that have no HTML
  version. The README has users add a second
  server named `arxiv` with the extra, at user scope (`-s user`; the default
  local scope exists only in the directory where it was added). Without the
  extra that failure is permanent: the arXiv leg does not retry, and hands the
  paper to `fetch_fulltext.py`'s arXiv-PDF route. So the second server is
  recommended, not required. Check it with `claude mcp get arxiv`: `Scope: User
  config`, the `[pdf]` args, `✔ Connected`. Open sessions keep the old server
  until restarted.
- **MCP tool names.** A server bundled by a plugin is
  `mcp__plugin_<plugin>_<server>__<tool>`, a user-level one
  `mcp__<server>__<tool>`. Every agent allowlists both forms
  (`mcp__arxiv__*` and `mcp__plugin_arxiv-mcp-server_arxiv__*`;
  `mcp__paper-search__*` and `mcp__plugin_second-brain-researcher_paper-search__*`)
  and names tools by their bare name in its body. A wrong prefix fails
  silently: the agent just has no tools.
- **`Grep` and `Glob` do not exist in every Claude Code build**; some search
  through Bash instead, and an allowlisted tool that does not exist is
  dropped without an error. So every agent that searches files has `Bash` in
  its allowlist, and one that names `Grep` says to fall back to `grep -n`
  through Bash, for searching only.
- **`.mcp.json`** bundles `paper-search-mcp` (run by `uvx`; it is not a
  marketplace plugin, so it cannot be a dependency) and Asta (remote HTTP,
  `x-api-key`). Without `uv` only the biomedical leg is unavailable, and the
  agent says so. `.mcp.json` passes `UNPAYWALL_EMAIL` through to
  `paper-search-mcp`; that server's own optional keys (CORE, DOAJ) go in
  `~/.config/paper-search-mcp/.env`. Every env var in `.mcp.json` needs a
  default (`${VAR:-}`): an unset one without it is substituted literally.
- **No `${CLAUDE_PLUGIN_ROOT}` in prose.** It works only in hook, monitor and MCP
  command fields, not in skill or agent Markdown and not in Bash. Never write
  repo-relative paths into skills or agents. The skills resolve the plugin root
  with one Bash call in the pipeline skill ("Before stage 3"): the first of
  the env var, the working directory (dev), the installed copy (`installPath`
  in `~/.claude/plugins/installed_plugins.json`) and a marketplace clone
  whose `.claude-plugin/plugin.json` names this plugin. A folder that merely
  has `templates/` and `scripts/` never counts. They stop when none resolves,
  and pass every template and script to an agent as an absolute path in a
  labelled prompt (`profile:`, `identity spec:`, `format:`, `fetcher:`,
  `find_papers:`). The causal-graph skill is self-contained and keeps a copy
  of the call under `## Plugin root`. The `plugin-root` suite runs that call
  on fake layouts and fails when the copy differs from it by a byte; on a
  real install, from a folder outside the repo with
  `CLAUDE_PLUGIN_ROOT` unset, it returns
  `~/.claude/plugins/cache/second-brain-researcher/second-brain-researcher/<version>`.
- **Keys come from the environment only**, never plugin config:
  `ASTA_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`, `UNPAYWALL_EMAIL`,
  `OPENALEX_API_KEY`, `NCBI_API_KEY`. The README puts them in the `env` block
  of `~/.claude/settings.json`, which every session reads, desktop app
  included; a shell profile reaches only sessions started from a terminal.
  `claude mcp get plugin:second-brain-researcher:asta` shows whether the Asta
  header is set (the value is redacted). For a dev session from a terminal,
  `.env` (gitignored; `.env.example` is the committed template) can be loaded
  with `set -a; source .env; set +a` before `claude`, because Claude Code does
  not read `.env` itself. The cross-field agent's skip message points
  installed users to the README's "API keys".
- **Waves.** Agents go out in waves no larger than
  `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` (20 by default): a call past it is
  refused, not queued. Raising it in `~/.claude/settings.json` saves wall-clock
  time, not tokens, and can hit the organization's rate limits.

## Sources and full text

- **Every leg saves a record first** (identity header plus abstract), then
  runs `fetch_fulltext.py`, which upgrades it in place from the first route
  that works: Europe PMC full-text XML (JATS straight to Markdown, so tables
  and numbers survive) → NCBI BioC (NIH author manuscripts, which Europe PMC's
  XML answers with a 500) → the arXiv PDF → Semantic Scholar's open-access PDF
  → Unpaywall (needs `UNPAYWALL_EMAIL`). It first fills any missing
  DOI/PMID/PMCID from Semantic Scholar. A download that does not start with
  `%PDF-` is refused.
- **Never `download_with_fallback`** from `paper-search-mcp` for open access:
  it lost most of one run's clinical full texts (PROJECT_CONTEXT.md, "Full
  text comes from `fetch_fulltext.py`").
- **Docling converts PDFs** and is optional: without it a PDF-only paper stays
  abstract-only, with the reason in the report. `--image-export-mode
  placeholder`, because base64 figures made one paper 545 KB instead of 56 KB;
  `--no-ocr`, 10 s instead of 49 s on born-digital PDFs. Output under 10 KB is
  retried with OCR. Digits extracted as substituted glyphs (`0.90` as `Ͷ.ͿͶ`)
  are retried with full-page OCR, else flagged `extraction_warning:
  garbled-digits`. The first run downloads a few hundred MB of models.
- **Asta's key is effectively required**, whatever its docs say: without it
  `snippet_search` and `search_papers_by_relevance` hang ~271 s, then fail with
  a misleading `ConnectionRefusedError`. Identifier lookups such as
  `search_paper_by_title` do work without it, which is what makes the docs'
  framing easy to believe. The cross-field agent checks the key first. The pipeline dispatches it unconditionally and reports a skip as an
  optional leg skipped, never a failed run.
- **Citation chasing uses OpenAlex, not Semantic Scholar.** S2 returns empty
  reference lists for many clinical publishers (0 where OpenAlex has 35 and 29
  for two core reRD papers). No key needed: ~1,000 filter requests a day, ~10
  per chase round; `OPENALEX_API_KEY` raises that tenfold.
- **`link_papers.py`** fetches references and SPECTER2 embeddings from Semantic
  Scholar in one batch. The embeddings cover title and abstract only, not full
  text. Without `SEMANTIC_SCHOLAR_API_KEY` the public quota often refuses; the
  linker retries for up to 10 minutes, then skips linking.
- **`NCBI_API_KEY`** is added to `find_papers.py`'s E-utilities requests. It
  gives the user their own rate limit instead of the network's shared one; the
  script keeps the same 0.4 s pace either way.

## Testing: small scale by default

A live pipeline run is expensive: the 42-paper run cost 20.8M weighted tokens,
and one topic deep-dive live test cost 9.8M in agents alone and hit the
session limit. Test every change at the lowest rung below that exercises it.

Testing belongs here only. Skills and agents never get a test mode, a test cap
or a mention of fixtures.

### Rules

- **Never run the full pipeline as a test**: not stages 1–5, not a whole
  deep-dive. That happens only when the user asks for a real run.
- **Never test against a real vault.** Copy what a test needs into the
  scratchpad and point the test there; never write into a `paper_vault/` or
  `obsidian_vault/` of the user's.
- **State the estimate before any step that uses a model, and the measured cost
  after it** (see "Measuring cost").
- **T0–T2 need no approval. T3 and up need the user's yes**, asked with the
  estimate.
- A failed live test is diagnosed from its output, not re-run to see if it
  happens again. Fix, cover the fix offline if a script can hold it, then
  re-run only the piece that failed.

### The ladder

**T0, static (free).** `python3 -m py_compile scripts/*.py`

**T1, offline fixtures (free).** No model, no network, the fixtures untouched:

```
bash test-fixtures/run_offline.sh              # every suite, ~2 s
bash test-fixtures/run_offline.sh stage-prep   # one suite
```

One line per suite, `PASS` or `FAIL` with the diff. Run the touched suite while
working and every suite before calling a change done.

| Script | Suite | README |
|---|---|---|
| `check_vault.py` | `check-vault` | `test-fixtures/check-vault/` |
| `fetch_fulltext.py` (offline rungs) | `fetch` | `test-fixtures/fetch/` |
| `find_papers.py`, including `.excluded/` counted as in the vault | `find-papers` | `test-fixtures/find-papers/` (§ Excluded records) |
| `link_papers.py` | `linker` | `test-fixtures/linker/` |
| the pipeline skill's plugin-root Bash call, and the causal-graph skill's copy of it | `plugin-root` | `test-fixtures/plugin-root/` |
| the profile skeletons of intake and the causal-graph skill vs the profile spec | `schema-copies` | `test-fixtures/schema-copies/` |
| `stage_prep.py` merge, summaries, keywords, digest | `stage-prep` | `test-fixtures/stage-prep/` |
| `stage_prep.py topic`, `digest --since` | `stage-prep-deep-dive` | `test-fixtures/stage-prep/` (§ Topic deep-dive) |
| `build_vault.py` | `vault-build` | `test-fixtures/vault-build/` |
| `graphcreator.py` | `graphcreator` | `test-fixtures/graphcreator/` |
| `causal_graph.py`, all seven commands | `causal-graph` | `test-fixtures/causal-graph/`, on a copy of the shared causal fixture `test-fixtures/causal/` |

New script behavior gets a new fixture case (a record that exercises it, the
expected output, one line in the README's "what each tests" list), not a live
run. When behavior changes on purpose, update the expected files. A README's
command block and its suite in `run_offline.sh` change together.

**T1b, scripts against the live APIs (no model tokens).** For network code the
fixtures cannot reach, on scratch copies:
`find_papers.py pubmed … --max 20 --top 5`, `fetch_fulltext.py --record` on one
record, `link_papers.py` on the linker fixture's summaries without `--offline`
(with `--dry-run`).

**T2, one agent on one tiny input.** A single dispatch, no approval, estimate
stated first. Fixture papers are synthetic: this tests format, paths and
handoffs, not the quality of what the agent writes. When quality is the point,
use a scratch copy of 3–5 records from a real vault instead.

| Agent | Input (copied to scratch) | Check |
|---|---|---|
| `paper-summarizer` | `test-fixtures/sample-paper.md` into `<scratch>/ssl-pretraining-ct-review-20260924/`; profile `test-fixtures/sample-topic-profile.md` | `summaries/sample-paper_summary.md` against `test-fixtures/summaries/sample-paper_summary.md` (fields, sections); `check_vault.py records <dir>` |
| `topic-summarizer` | `test-fixtures/stage-prep/deep-dive/records/fixture-dd-20260925/`, then `stage_prep.py digest <dir> --topic survival-analysis:time-to-event`; profile `…/deep-dive/fixture-dd-20260925.md`. Delete `topics/survival-analysis.md` first to test create mode instead of deepen mode | `check_vault.py records <dir>`; the note's frontmatter and section headings against `templates/topic-note-template.md` |
| `second-brain-paper-downloader` (arXiv) | a copy of `test-fixtures/sample-topic-profile.md` with `paper_vault_path:` pointing at a scratch dir | saved records have the identity header (`stage_prep.py merge <dir> --dry-run`: `no_header` empty) |
| `second-brain-biomed-downloader` | a copy of `test-fixtures/find-papers/fixture-recall-20260924.md` with a `paper_vault_path:` line added, pointing at a scratch dir | as above |
| `second-brain-citation-chaser` | that profile, pointing at a scratch copy of `test-fixtures/find-papers/records/fixture-recall-20260924/` | its reply's rounds and stop reason; `merge --dry-run` |
| `second-brain-crossfield-searcher` | as for the arXiv leg, with a methodology term added (the sample profile has none). Without `ASTA_API_KEY` in Claude Code's environment it stops at its key check, which tests only pre-flight | as above, or its skip reply |
| `second-brain-code-finder` | as for the arXiv leg, on a scratch copy of a vault with saved papers (the arXiv leg's T2 output will do) | `repos/*.md` fields and headings against `templates/repo-note-template.md`; `check_vault.py records`; `code_vault` empty |
| `causal-claim-extractor` | a scratch copy of `test-fixtures/causal/records/fixture-causal-20261119/` with its `claims/` deleted; a 3-paper `papers:` list; profile a copy of `test-fixtures/causal/fixture-causal-20261119.md` with `paper_vault_path:` pointing at the scratch copy | the three claims files load as JSON with every spec field; `causal_graph.py check <dir>`: nothing `invalid`, `claims_rejected` 0 (every quote verbatim) |
| `causal-variable-harmonizer` | a scratch copy of `test-fixtures/causal/names.txt`, `variables exists: false`, the profile copy above pointing at a scratch copy of the fixture records (claims included); then pass 2 with two extra names appended and `variables exists: true` | `variables.json` loads; the target node exists with `FO` and `postoperative fixture outcome` among its aliases; pass 2 kept every pass-1 node name |
| `causal-pair-searcher`, pairs mode | a scratch `pairs.json` with one real pair (e.g. diabetes / obesity) and a small `max_papers`; the profile copy pointing at a scratch paper vault | its reply's per-pair counts; `stage_prep.py merge <dir> --dry-run`: `no_header` empty |
| `causal-pair-searcher`, upstream mode | a scratch `upstream.json` with one real cause (`query` and `fallback` built as `causal_graph.py upstream` builds them) and `max_papers` 2; as above | its reply's per-entry counts, and `top 50 of N` when it ended too broad; as above |

Give the agent the pipeline's own prompt template for that step
(`skills/second-brain-pipeline/SKILL.md`; for the causal agents,
`skills/second-brain-causal-graph/SKILL.md`), filled in with the scratch paths.
Discovery agents get one extra line at the end of the prompt, and only there:
`TEST RUN: at most 2 queries and 3 saved papers in total; the chaser runs 1
round from at most 2 seeds and runs only the first recall probe.` The pair
searcher gets `TEST RUN: at most 1 pair and 2 saved papers` (upstream mode:
`at most 1 entry and 2 saved papers`).

**T3, a mini pipeline (ask first).** Run the skill, but start at the stage that
changed, never at stage 1, on a scratch vault seeded from fixture records:

- stage 5: seed from the deep-dive fixture's records, whose summaries already
  exist, so `stage_prep.py summaries` plans no summarizer dispatch. Select one
  topic, then linker, checks and vault build into a scratch `obsidian_vault/`.
  Cost: about one topic-summarizer plus the conversation.
- stages 3–4: a scratch profile with narrow terms, one leg with the `TEST RUN`
  line, merge, and stop at the checkpoint.
- a deep-dive: a scratch copy of the deep-dive fixture's records and vault, one
  leg capped, one topic note.
- a causal graph: in a fresh session with this repo as the working directory,
  the causal-graph skill on a scratch causal profile with a narrow target,
  its root a scratch folder (never a real `second-brain/`), agents dispatched
  as `general-purpose` per "Dispatching a plugin agent in this repo". One
  discovery leg with the `TEST RUN` line, at most 5 papers; extraction;
  harmonizer pass 1; a pair round capped at 1 pair and 2 papers and an
  upstream round capped at 1 cause and 2 papers (through the profile:
  `pair_search_k: 2`, `pair_search_max_papers: 2`, `upstream_search_k: 1`,
  `upstream_search_max_papers: 2`), each with its extraction and harmonizer
  pass; `assemble`. Check that both DAGs and the evidence report exist.

At most 5 papers, 1 topic, 1 discovery leg (for a causal graph, plus the two
capped rounds).

**T4, the full pipeline.** Only on the user's request for a real run.

### Which rung for which change

| Changed | Minimum |
|---|---|
| `scripts/*.py` | T1 (+ T1b for network code) |
| `templates/*` | T1, plus the T2 of each agent that reads the template |
| `agents/<name>.md` | T2 of that agent |
| `agents/causal-pair-searcher.md` | T2 of each mode the change touches |
| `scripts/causal_graph.py`, `scripts/graphcreator.py` | T1 (`causal-graph`, `graphcreator`); no network code |
| `templates/causal-claims-spec.md` | T1 (`causal-graph`), plus the T2 of the extractor and the harmonizer, and of the pair searcher when `pairs.json` or `upstream.json` changed |
| `templates/graphcreator-dag-format.md` | the researcher's format, changed only when theirs changes: T1 (`graphcreator`, `causal-graph`) |
| a skill's `SKILL.md` or `deep-dive.md` | T1 for the scripts it calls; T3 only if an agent handoff changed |
| `skills/second-brain-causal-graph/SKILL.md` | T1 (`plugin-root`, `schema-copies`, `causal-graph`); the causal T3 only if an agent handoff changed; Q&A changes inline on a test target |
| `research-problem-intake` | run its Q&A inline on a test problem; it dispatches no agents |

### Dispatching a plugin agent in this repo

The plugin's agents are not registered as agent types in a dev session. Dispatch
a `general-purpose` agent with `model` set to the one its definition names
(`sonnet`; `opus` for `topic-summarizer` and `causal-variable-harmonizer`)
and a prompt that starts
`Follow agents/<name>.md in this repo as your instructions, using only the tools
it lists.`, then the filled-in template. One dispatch at a time, in the
foreground. In the main conversation read only compact output: the agent's
`OK`/`FAIL` reply, script reports, `grep` of frontmatter, `head`. Never whole
papers, summaries or notes; the conversation is paid for again on every turn.

### Measuring cost

```
P=~/.claude/projects/-home-bartvdw-Documents-Fun-SecondBrain-second-brain
python3 scripts/token_report.py "$(ls -t $P/*.jsonl | head -1)"
```

It sums the whole session by agent type, so for one test run it before and
after and report the difference. It counts every turn; the harness's own
per-agent token figure is only the final context size, not what was billed.

Measured per agent on the deep-dive live test (session `7d220f0b…`,
2026-09-25, no caps), weighted tokens. That session also held development
work, so its main-conversation cost says nothing about orchestration and is
left out; measure that on a real full run.

| Dispatch | Cost |
|---|---|
| `paper-summarizer`, per dispatch (~1.7 papers) | ~120k (~70k per paper) |
| `topic-summarizer`, deepening a 62-paper note | ~1.6M |
| biomedical leg | ~1.0M |
| arXiv leg | ~430k |
| citation chaser, 4 rounds | ~1.4M |
| cross-field leg, stopped at its key check | ~45k |

Measured at T2 (2026-09-25, the cleanup session), weighted tokens:
`paper-summarizer` on the sample paper ~120k; `topic-summarizer` deepening the
2-paper fixture note ~120k; the arXiv, biomedical and code legs with the
`TEST RUN` cap ~250k each; the chaser capped ~120k (its paper cap was reached
in round 0, so no chase round ran); the cross-field leg stopped at its key
check ~50k.

Measured at T2 for the causal graph (2026-11-19, synthetic fixture papers and
live PubMed), weighted tokens: `causal-claim-extractor` on 3 short papers
~170k; `causal-variable-harmonizer` ~80k per pass; `causal-pair-searcher` on
one 25-hit pair ~90k, and in upstream mode ~110–130k per test (one or two
entries, up to 3 papers). A full causal run is estimated at 11–16M for ~80
papers (CAUSAL_GRAPH_DESIGN.md, "Cost"); measure it on the first real run.
