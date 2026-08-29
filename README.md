# second-brain-researcher

Agentic research pipeline for literature and code discovery, built on Claude Code + Claude app + Obsidian.

Methods relevant to a problem often already exist in an adjacent field, but finding them is manual and ad hoc — and whatever gets found rarely ends up captured anywhere durable, so the next project starts from zero. This pipeline turns a researcher's problem description into a structured search, and structures what it finds into a browsable, linked knowledge base.

## Pipeline overview

1. **Intake** — researcher describes the problem (domain, data, task, reference standard).
2. **Problem profile** — an adaptive Q&A deepens the description into a structured note, including the two term lists discovery searches against.
3. **Discovery** — parallel search across papers (arXiv, PubMed, Semantic Scholar) and code (GitHub).
4. **Checkpoint** — pause for researcher review before anything downstream consumes what was found.
5. **Vault build** — discovered papers and repos become structured notes, materialized into an Obsidian vault.
6. **Cross-linking** (not implemented) — notes get linked to each other via embedding similarity, forming a fuller Obsidian graph.
7. **Experiment plan** (not implemented) — proposes a baseline + ideas from the vault, optionally adapted into the researcher's existing project repo.

**What's actually wired end to end right now:** stages 1–2 (`research-problem-intake`), stage 3 for **arXiv only** (`second-brain-paper-downloader`), stage 4 as a conversational pause, and stage 5 for **papers only** — no code/repo discovery or vault-build yet. PubMed, Semantic Scholar, and GitHub discovery, repo cloning/summarization, cross-linking, and the experiment plan are all still unimplemented. The `second-brain-pipeline` skill is the entry point that runs the wired stages in sequence; the four pieces it calls can also still be invoked individually.

## Install

This repo is a Claude Code **plugin** (and self-hosts its own marketplace) — you install it, you don't clone-and-work inside it. Once installed, the second-brain pipeline is available in every project you open Claude Code in, not just this one:

```
/plugin marketplace add ofulla/second-brain-researcher
/plugin marketplace add blazickjp/arxiv-mcp-server
/plugin install second-brain-researcher@second-brain-researcher
```

The second command adds the marketplace for `arxiv-mcp-server`, a separate plugin `second-brain-paper-downloader` depends on for its MCP tools. It's declared as a real dependency in `plugin.json`, so the third command auto-installs and auto-enables it too — but only once its marketplace is already registered, which is why that line has to come first. If you skip it: the install *command* reports success, but the plugin itself ends up `failed to load` and every one of its agents/skills is completely unreachable in any session — not degraded, just gone — until you add that marketplace, at which point it self-heals to enabled with no restart needed. All verified directly, not assumed. There's no reason to hit that broken intermediate state when running both commands up front avoids it entirely.

Because Claude Code's own plugin loader already refuses to load this plugin at all when `arxiv-mcp-server` is missing — confirmed in both the real install path and local dev below — none of this plugin's own agents/skills need to re-check that dependency themselves; there's no scenario where they'd run with it actually absent.

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
│   └── obsidian-vault-writer.md                   # stage 5 (vault): materializes profile + paper notes into the Obsidian vault
├── skills/
│   ├── research-problem-intake/SKILL.md           # stage 1–2: Q&A that produces the problem-profile note
│   └── second-brain-pipeline/SKILL.md              # orchestrator: runs stages 1–5 end to end, holds the stage-4 checkpoint
├── templates/
│   ├── paper-page-template.md                    # stage 5: structure for a discovered-paper note
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
- **`obsidian-vault-writer` agent** — stage 5 (vault). Materializes a confirmed problem profile and a collection of paper-summary notes into an Obsidian vault as a star graph (problem ↔ papers). Takes all three inputs (profile, papers, vault path) explicitly from the caller. A vault is just a folder of markdown files, so this works whether or not the Obsidian application is installed — the pipeline offers to open the result afterwards, separately.
- **`second-brain-pipeline` skill** — the orchestrator. Runs the above four (one skill, three agents) in sequence against one research problem, pausing at the stage-4 checkpoint for researcher review before vault-build.
- **`paper-page-template.md`** — the note format for a paper once discovery finds it, including how it links back to the problem that surfaced it.
- **`research-problem-profile-format-spec.md`** — the frontmatter schema for the problem-profile note, field by field, with notes for what the paper-search and Obsidian groups each need from it.
