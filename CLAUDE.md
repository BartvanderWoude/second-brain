# second-brain-researcher

A Claude Code plugin that turns a research problem or review topic into a
linked Obsidian vault: `skills/` orchestrate, `agents/` do the judgment work,
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

At 64 KB `PROJECT_CONTEXT.md` is meant to be searched, not read: reading it
whole adds ~16k tokens to the context, paid again on every later turn. Never
`Read` it without `offset`/`limit`, never `cat` it, and never `@`-import it
here.

- **Find:** `grep -n -i '<term>' PROJECT_CONTEXT.md | cut -c1-200`. Each
  paragraph is one line of up to ~1,500 characters, so trim the output.
  `grep -n '^## \|^- \*\*' PROJECT_CONTEXT.md | cut -c1-120` lists the
  sections and decision entries.
- **Read:** only the entry you need, by its line numbers:
  `sed -n '<from>,<to>p' PROJECT_CONTEXT.md`, or `Read` with `offset`/`limit`.
- **Write:** add a new decision as its own entry, found and placed the same
  way; do not load the file to edit it.

A large file here is fine. Shrinking it is not the fix; reading it only in
pieces is.

## How it works

The spec has 7 stages. 1–5 are built. Stage 6 (cross-linking) is built only
in reduced form: topic notes from shared keywords, `## Related topics`, and
`link_papers.py`'s paper-to-paper edges. Stage 7 (experiment plan) is not
built, and neither are repo cloning, running, or the Docker sandbox.

| Stage | Piece | Job |
|---|---|---|
| 1–2 | skill `research-problem-intake` (+ `deep-dive.md`) | adaptive Q&A for a problem or a topic review → profile note: CLAIM-checklist fields, the two term lists, recall probes, keyword taxonomy; sets up the working dirs |
| all | skill `second-brain-pipeline` (+ `deep-dive.md`) | orchestrator: runs 1–5, holds the stage-4 checkpoint, dispatches agents in waves, reads script reports only |
| — | skill `second-brain-topic-deep-dive` | resolves vault and note (`stage_prep.py topic`, which also warns about old-style ids), then intake's deep-dive branch and pipeline 3–5 on a `deep_dive_of` profile; new papers go into the vault's own paper vault, summarized against the vault's profile |
| 3 | `second-brain-paper-downloader` (sonnet) | arXiv leg: close-field then generalized terms, ≤20 papers |
| 3 | `second-brain-biomed-downloader` (sonnet) | PubMed/PMC/Europe PMC leg, via `paper-search-mcp` and `find_papers.py pubmed` (whole hit sets) |
| 3 | `second-brain-crossfield-searcher` (sonnet) | paper bodies via Asta, for methods from adjacent fields |
| 3 | `second-brain-citation-chaser` (sonnet) | after the legs: the core question exhaustively. Recall probes as whole PubMed hit sets, then OpenAlex one hop both ways from the core papers, round after round until one adds nothing. Screens titles first, abstracts only where a title leaves it unsure |
| 3 | `second-brain-code-finder` (sonnet) | after the paper legs and the merge (it needs the papers on disk): repos the papers name, plus `gh search repos`; GitHub API only. Notes record the license (`none` = no reuse rights) and whether it is the official implementation |
| 3 | `scripts/fetch_fulltext.py` | upgrades a saved record to full text in place |
| 3 | `scripts/find_papers.py` | numbered candidate lists (`pubmed`, `chase`, `show`); `add` saves chosen ones as records and fetches their full text. A query too large to fetch whole is flagged, never silently cut to its top hits |
| 3–5 | `scripts/stage_prep.py` | duplicate merge and coverage figures, summarizer fan-out plan, keyword index, topic digests, `topic` report, `digest --since` |
| 5 | `paper-summarizer` (sonnet) | one long paper, or up to 8 short ones → summaries per `paper-page-template.md`; long papers read up to the references. Given the profile, `related_problem`, `matched_terms` and the relevance synthesis are grounded in that problem |
| 5 | `topic-summarizer` (opus) | one keyword + its digest → topic note; checks the full text of ≤3 central papers on a fixed budget |
| 5 | `scripts/link_papers.py` | citation links and SPECTER2 similarity from Semantic Scholar |
| 5 | `scripts/check_vault.py` | `records` before the vault, `vault` links after |
| 5 | `scripts/build_vault.py` | profile, papers, topics, repos → the Obsidian vault, with BibTeX from arXiv's own metadata |
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
`topic-note-template.md`, `repo-note-template.md` (note formats).

A run writes into the researcher's own project, never into this repo:
`paper_vault/<id>/` (records, `summaries/`, `topics/`, `repos/`),
`code_vault/<id>/` (stays empty) and `obsidian_vault/<id>/`. Each problem is
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
  a handoff silently.
- **Every agent's `description:` warns against being reimplemented** from the
  description alone or routed around after a blocking report. It is the only
  text an orchestrating session sees before dispatch.
- **Skill, agent, or script.** A skill only when it needs the main conversation
  (live Q&A, holding the checkpoint, asking which vault is meant); otherwise an
  agent with an enforced `tools:` allowlist, or a script when no model is
  needed.
- **Model tiers are pinned per agent, never `inherit`.** `sonnet` for per-item
  and mechanical work, `opus` only for `topic-summarizer`, so synthesis quality
  does not depend on the main session's model.
- **The main conversation reads compact script reports**, never papers,
  summaries or notes: every turn there re-reads the whole conversation.
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
- **Local dev:** `claude --plugin-dir .` loads the working tree live, with no
  reinstall after edits. The dependency must still be installed.
- **The `[pdf]` extra.** The `arxiv-mcp-server` plugin launches plain
  `uvx arxiv-mcp-server`, which cannot extract arXiv papers that have no HTML
  version (one run lost 17 that way). The README has users add a second
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
  themselves (the env var, then repo-relative for dev, then a scan of
  `~/.claude/plugins/marketplaces/*/`) and pass absolute paths on. That third
  case is not yet verified against a real marketplace install of this plugin.
- **Keys come from the environment only**, never plugin config:
  `ASTA_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`, `UNPAYWALL_EMAIL`,
  `OPENALEX_API_KEY`, `NCBI_API_KEY`. The README tells users to export them in
  their shell profile. For dev, `.env` (gitignored; `.env.example` is the
  committed template) is loaded with `set -a; source .env; set +a` before
  `claude`, because Claude Code does not read `.env` itself. The cross-field
  agent's skip message names the `.env` route.
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
- **It replaced `paper-search-mcp`'s `download_with_fallback`** for open access.
  On the 42-paper run 16 of 20 clinical papers ended up abstract-only through
  it: PMC called open-access papers closed, Europe PMC's PDFs returned 403,
  HTML error pages were saved as `.pdf` and reported as success, CORE failed on
  every DOI, and the Sci-Hub mirror did not resolve.
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
| `find_papers.py` | `find-papers` | `test-fixtures/find-papers/` |
| `link_papers.py` | `linker` | `test-fixtures/linker/` |
| `stage_prep.py` merge, summaries, keywords, digest | `stage-prep` | `test-fixtures/stage-prep/` |
| `stage_prep.py topic`, `digest --since` | `stage-prep-deep-dive` | `test-fixtures/stage-prep/` (§ Topic deep-dive) |
| `build_vault.py` | `vault-build` | `test-fixtures/vault-build/` |

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
| `second-brain-crossfield-searcher`, `second-brain-code-finder` | as for the arXiv leg | as above; code-finder: `repos/*.md` |

Give the agent the pipeline's own prompt template for that step
(`skills/second-brain-pipeline/SKILL.md`), filled in with the scratch paths.
Discovery agents get one extra line at the end of the prompt, and only there:
`TEST RUN: at most 2 queries and 3 saved papers in total; the chaser runs 1
round from at most 2 seeds and runs only the first recall probe.`

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

At most 5 papers, 1 topic, 1 discovery leg.

**T4, the full pipeline.** Only on the user's request for a real run.

### Which rung for which change

| Changed | Minimum |
|---|---|
| `scripts/*.py` | T1 (+ T1b for network code) |
| `templates/*` | T1, plus the T2 of each agent that reads the template |
| `agents/<name>.md` | T2 of that agent |
| a skill's `SKILL.md` or `deep-dive.md` | T1 for the scripts it calls; T3 only if an agent handoff changed |
| `research-problem-intake` | run its Q&A inline on a test problem; it dispatches no agents |

### Dispatching a plugin agent in this repo

The plugin's agents are not registered as agent types in a dev session. Dispatch
a `general-purpose` agent with `model` set to the one its definition names
(`sonnet`; `opus` for `topic-summarizer`) and a prompt that starts
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

Estimates for T2, until measured: `paper-summarizer` on the sample paper
50–100k; `topic-summarizer` on a 4-paper digest 200–500k; a capped leg or a
1-round chaser 150–600k. Replace an estimate with the measured figure after the
first such run.
