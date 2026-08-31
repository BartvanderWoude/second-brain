# second-brain-researcher

Agentic research pipeline for literature and code discovery, built on Claude Code + Claude app + Obsidian.

Methods relevant to a problem often already exist in an adjacent field, but finding them is manual and ad hoc — and whatever gets found rarely ends up captured anywhere durable, so the next project starts from zero. This pipeline turns a researcher's problem description into a structured search, and structures what it finds into a browsable, linked knowledge base.

## Pipeline overview

1. **Intake** — researcher describes the problem (domain, data, task, reference standard).
2. **Problem profile** — an adaptive Q&A deepens the description into a structured note, including the two term lists discovery searches against.
3. **Discovery** — parallel search across papers (arXiv, PubMed, Semantic Scholar) and code (GitHub).
4. **Checkpoint** — pause for researcher review before anything downstream consumes what was found.
5. **Vault build** — discovered papers and repos become structured notes, materialized into an Obsidian vault.
6. **Cross-linking** (partly implemented) — papers are linked to each other through per-subtopic topic notes built from their shared keywords. The spec's embedding-similarity linking is still not implemented.
7. **Experiment plan** (not implemented) — proposes a baseline + ideas from the vault, optionally adapted into the researcher's existing project repo.

**What's actually wired end to end right now:** stages 1–2 (`research-problem-intake`), stage 3 for **arXiv only** (`second-brain-paper-downloader`), stage 4 as a conversational pause, stage 5 for **papers only** (`paper-summarizer` → `topic-summarizer` → `obsidian-vault-writer`), and keyword-based cross-linking via topic notes. No code/repo discovery or vault-build yet. PubMed, Semantic Scholar, and GitHub discovery, repo cloning/summarization, embedding-similarity cross-linking, and the experiment plan are all still unimplemented. The `second-brain-pipeline` skill is the entry point that runs the wired stages in sequence; the five pieces it calls can also still be invoked individually.

## Install

This repo is a Claude Code **plugin** (and self-hosts its own marketplace) — you install it, you don't clone-and-work inside it. Once installed, the second-brain pipeline is available in every project you open Claude Code in, not just this one:

```
/plugin marketplace add ofulla/second-brain-researcher
/plugin marketplace add blazickjp/arxiv-mcp-server
/plugin install second-brain-researcher@second-brain-researcher
```

The second command adds the marketplace for `arxiv-mcp-server`, a separate plugin `second-brain-paper-downloader` depends on for its MCP tools. It's declared as a real dependency in `plugin.json`, so the third command auto-installs and auto-enables it too — but only once its marketplace is already registered, which is why that line has to come first. If you skip it: the install *command* reports success, but the plugin itself ends up `failed to load` and every one of its agents/skills is completely unreachable in any session — not degraded, just gone — until you add that marketplace, at which point it self-heals to enabled with no restart needed. All verified directly, not assumed. There's no reason to hit that broken intermediate state when running both commands up front avoids it entirely.

Because Claude Code's own plugin loader already refuses to load this plugin at all when `arxiv-mcp-server` is missing — confirmed in both the real install path and local dev below — none of this plugin's own agents/skills need to re-check that dependency themselves; there's no scenario where they'd run with it actually absent.

### The PubMed leg needs `uv` on your PATH

`second-brain-biomed-downloader` uses [`paper-search-mcp`](https://github.com/openags/paper-search-mcp) (MIT) for PubMed/PMC/Europe PMC. Unlike `arxiv-mcp-server` this is **not** a Claude Code plugin — it has no marketplace, so it cannot be a `dependencies` entry, which accepts marketplace plugins only. This plugin therefore bundles it as its own MCP server in `.mcp.json`:

```json
{ "mcpServers": { "paper-search": { "command": "uvx", "args": ["paper-search-mcp"] } } }
```

That means there is nothing extra to install *if you have [`uv`](https://docs.astral.sh/uv/) on your PATH* — `uvx` fetches and runs the server on demand. If `uv` is missing, the arXiv leg still works and only the biomedical leg goes unavailable; the agent reports that plainly rather than silently skipping PubMed.

Optional API keys (CORE, DOAJ, Unpaywall email) go in `~/.config/paper-search-mcp/.env`. None are required — without them those sources are rate-limited, not broken.

Note the tool-prefix consequence: a bundled server's tools are named `mcp__plugin_<plugin-name>_<server-name>__<tool>`, so these arrive as `mcp__plugin_second-brain-researcher_paper-search__*`. If you instead configure `paper-search-mcp` yourself as a user-level server named `paper-search`, they arrive as `mcp__paper-search__*`. The agent allowlists both, for the same reason the arXiv agents do — an allowlist naming a prefix that doesn't exist fails silently, leaving an agent with no tools rather than an error.

### Full text for non-arXiv papers needs Docling (optional)

The arXiv leg gets clean Markdown from `arxiv-mcp-server`'s own extraction. Nothing equivalent exists for PubMed/PMC, where `download_with_fallback` returns a **PDF**. `second-brain-biomed-downloader` converts it with [Docling](https://github.com/docling-project/docling) (MIT):

```bash
uv tool install docling
```

Optional. Without it the biomedical leg still saves every paper it found — just as abstract-only notes, flagged as such, rather than full text.

Two flags matter and the agent always passes them. `--image-export-mode placeholder` stops Docling embedding every figure as a base64 data URI: on a real Europe PMC paper that was **545 KB versus 56 KB**, including one 200,132-character line, with identical document structure either way. `--no-ocr` skips OCR on born-digital journal PDFs — 10s versus 49s on the same paper. If the converted Markdown comes back under 10 KB the PDF was probably scanned, and the agent retries that one paper with OCR enabled.

First run downloads layout models (a few hundred MB), so expect the first paper to be slow.

### Code discovery needs the GitHub CLI (optional)

`second-brain-code-finder` catalogues the repositories behind a problem: the ones the saved papers name, plus what `gh search repos` turns up for the profile's terms. It needs [`gh`](https://cli.github.com/) on your PATH and logged in:

```bash
gh auth login
```

Optional. Without it the paper legs run normally and the code leg reports that it was skipped.

**It never clones, downloads, or executes anything.** Every note is built from the GitHub API — README plus the file tree — so `code_vault/<id>/` stays empty and no third-party code reaches your machine. That is deliberate: the code leg runs *before* the stage-4 checkpoint, and `PROJECT_CONTEXT.md` locks in that nothing is cloned or executed until you have approved it. Cloning, running, and the Docker sandbox remain unbuilt.

Each repo note records what the repo is, how it is structured, its entry points, and what it would take to run — plus two things that are easy to miss and expensive to discover late: whether it has **any license at all** (unlicensed code grants no reuse rights), and whether it is the paper's **official implementation** or a third-party reimplementation.

### The cross-field pass needs an Asta API key (optional)

`second-brain-crossfield-searcher` uses [Ai2's Asta Scientific Corpus Tool](https://allenai.org/asta/resources/mcp) to search *paper bodies* rather than abstracts — the pass that finds methods from adjacent fields whose abstracts never mention your domain. It is bundled in `.mcp.json` as a remote HTTP server and reads `ASTA_API_KEY` from the environment.

```bash
cp .env.example .env          # then paste your key into .env
set -a; source .env; set +a   # Claude Code does NOT read .env by itself
claude
```

Request a free key at [share.hsforms.com/1L4hUh20oT3mu8iXJQMV77w3ioxm](https://share.hsforms.com/1L4hUh20oT3mu8iXJQMV77w3ioxm). Keys are personal — `.env` is gitignored, `.env.example` is the committed placeholder, so nobody has to share one.

**Without a key the pipeline still works.** The arXiv and PubMed legs are unaffected; the cross-field pass reports that it was skipped and the run continues. What you must *not* do is run that pass unauthenticated and hope: Ai2's docs describe the key as enabling "higher rate limits", but the search tools are gated outright — `snippet_search` and `search_papers_by_relevance` hang for ~271 seconds and then fail with a misleading `ConnectionRefusedError` rather than a clean 401. That is why the agent checks for the key before it searches instead of letting the call fail. (Identifier lookups like `search_paper_by_title` do work without a key, which is what makes the docs' framing so easy to believe.)

For local development, run Claude Code straight from a checkout of this repo with `claude --plugin-dir .` — it loads the plugin live from the working tree, no install step, no re-running anything after an edit. Verified directly: this enforces the same `arxiv-mcp-server` dependency as a real install — with it missing, none of this plugin's agents/skills appear at all; with it present, everything loads normally. So it still needs to be installed (via the marketplace commands above) for local testing to work, same as for a real user.

Once installed, running the pipeline against a real research problem happens in *your own* project — that's where `research-problem-intake` sets up `paper_vault/`, `code_vault/`, and `obsidian_vault/` as working directories, and where the resulting notes live.

## Structure

```
second-brain-researcher/
├── .claude-plugin/
│   ├── plugin.json                                # plugin manifest (name, version, description)
│   └── marketplace.json                            # self-hosted marketplace listing this one plugin
├── agents/
│   ├── second-brain-paper-downloader.md           # stage 3 (arXiv only): finds + saves papers into paper_vault/<id>/
│   ├── paper-summarizer.md                        # stage 5 (papers): one paper -> one structured summary note
│   ├── topic-summarizer.md                        # stage 5 (topics): one keyword -> one synthesized topic note
│   └── obsidian-vault-writer.md                   # stage 5 (vault): materializes profile + paper + topic notes into the Obsidian vault
├── skills/
│   ├── research-problem-intake/SKILL.md           # stage 1–2: Q&A that produces the problem-profile note
│   └── second-brain-pipeline/SKILL.md              # orchestrator: runs stages 1–5 end to end, holds the stage-4 checkpoint
├── templates/
│   ├── paper-page-template.md                    # stage 5: structure for a discovered-paper note
│   ├── topic-note-template.md                    # stage 5: structure for a per-subtopic topic note
│   └── research-problem-profile-format-spec.md   # shared contract: exact schema the intake skill outputs
├── test-fixtures/                                # sample paper + expected summary, for testing paper-summarizer
└── README.md
```

**Note on placement:** `research-problem-profile-format-spec.md` is a format contract more than a fill-in-the-blanks template, but it lives in `templates/` for now since that's the only place for shared reference docs in the current structure. Worth revisiting once there's more than one non-skill, non-template doc to place (e.g. a `docs/` folder).

**Fixed (needs real-install verification):** agent/skill content used to reference `templates/...` by a path relative to this repo's root (e.g. `templates/paper-page-template.md`), which doesn't resolve once installed and invoked from an unrelated project. `${CLAUDE_PLUGIN_ROOT}` looked like the fix Claude Code's plugin system provides for exactly this, but it's scoped to hook/monitor/MCP *command* config fields — not to skill/agent Markdown prose, and not exposed as a Bash-tool environment variable (verified directly: `echo $CLAUDE_PLUGIN_ROOT` under `--plugin-dir` returns empty). `second-brain-pipeline/SKILL.md` now resolves the template path itself at Stage 5 (checks `${CLAUDE_PLUGIN_ROOT}`, then a repo-relative path for local dev, then scans `~/.claude/plugins/marketplaces/*/` for this plugin's installed copy) instead of assuming a fixed path. The third case's directory shape is inferred from how the (already-installed) `arxiv-mcp-server` plugin is laid out, not yet verified against a real marketplace install of *this* plugin — do that before trusting it fully. See [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).

## What's built so far

- **`research-problem-intake` skill** — runs the adaptive Q&A, deepens the researcher's initial description (including fields drawn from the CLAIM checklist for AI-in-medical-imaging reporting), produces the two search-term lists discovery consumes, and writes a confirmed problem-profile `.md` file. Also sets up three local working directories (`paper_vault/`, `code_vault/`, `obsidian_vault/`) when run from Claude Code.
- **`second-brain-paper-downloader` agent** — stage 3, arXiv only. Reads a confirmed problem profile's `paper_vault_path`, searches arXiv in two passes (close-field, then generalized terms), and saves up to 20 matched papers there.
- **`paper-summarizer` agent** — stage 5 (papers). Turns one saved paper into a structured summary note conforming to `paper-page-template.md`. Optionally takes the confirmed problem profile as a third input, in which case `related_problem`, `matched_terms`, and the relevance synthesis are grounded in that specific problem rather than written as a generic assessment.
- **`topic-summarizer` agent** — stage 5 (topics). Takes one subtopic keyword plus the paper summaries carrying it, reads those papers' full text selectively (greps to the relevant passages rather than loading whole 20–140 KB extractions), and writes one short topic note synthesizing what the papers collectively establish, where they disagree, and what's missing. Dispatched once per subtopic, in parallel. A profile keyword that matched no papers still gets a note saying so — that's a gap worth seeing.
- **`obsidian-vault-writer` agent** — stage 5 (vault). Materializes a confirmed problem profile, the paper-summary notes, and the topic notes into an Obsidian vault (problem ↔ papers, problem ↔ topics, topics ↔ papers). Takes all four inputs explicitly from the caller. A vault is just a folder of markdown files, so this works whether or not the Obsidian application is installed — the pipeline offers to open the result afterwards, separately.
- **`second-brain-pipeline` skill** — the orchestrator. Runs the above four (one skill, three agents) in sequence against one research problem, pausing at the stage-4 checkpoint for researcher review before vault-build.
- **`paper-page-template.md`** — the note format for a paper once discovery finds it, including how it links back to the problem that surfaced it.
- **`research-problem-profile-format-spec.md`** — the frontmatter schema for the problem-profile note, field by field, with notes for what the paper-search and Obsidian groups each need from it.
