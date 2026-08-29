# Second-Brain for a Researcher

### Agentic research pipeline for literature + code discovery, built on Claude Code + Claude app + Obsidian

## Motivation

Methods relevant to a problem often already exist in an adjacent field, but finding them is manual and ad hoc — and whatever we do find rarely gets captured anywhere durable, so the next project starts from zero. Example: MedDINOv3 embeddings underperformed on sarcopenia CT without finetuning, for reasons (CLS-token pooling losing texture signal, domain gap from natural-image pretraining) that were already documented in the literature — we just weren’t systematically searching for it.

## Core pipeline (7 stages)

1. **Intake** — researcher provides domain, data description, reference standard, task, via Claude app or Claude Code. Metadata/description level only — no patient data ever enters the system.
2. **Problem profile** — interactive Q&A deepens the profile, written to a new Obsidian project note.
3. **Discovery (parallel)**
   - Papers: arXiv API, PubMed E-utilities, Semantic Scholar Graph API. Two passes — close-field terms, then generalized methodology terms (for cross-field transfer hits).
   - Code: GitHub, matched to discovered papers where possible.
4. **Checkpoint** — pipeline pauses here for researcher review/approval before anything is cloned or executed.
5. **Vault build**
   - Papers: structured fields (problem, data/modality, method, result, code link) + a short synthesis (why relevant, what would need to change to apply it, one skeptical note) extracted from ar5iv/PMC full text where available, PDF fallback otherwise.
   - Repos: cloned, structure/classes summarized into a note; optionally run/tested in a local Docker sandbox.
6. **Cross-linking** — paper and repo notes linked to each other and to the problem node (embedding similarity for “related” links), forming a browsable Obsidian graph.
7. **Experiment plan** — proposes baseline + ideas; can adapt code from the repo vault directly into the researcher’s *existing* project repo (not a new one).

## Architecture

- **Claude app** — intake, Q&A, review/approval at checkpoints.
- **Claude Code** — orchestrates search, cloning, analysis, sandboxed execution.
- **External sources** — arXiv, PubMed, Semantic Scholar, GitHub APIs.
- **Local Docker sandbox** — runs/tests cloned code, isolated from production data.
- **Obsidian vault** — personal, local, per researcher. Cross-project linking is an optional per-project toggle (e.g. a segmentation paper relevant to both EPAT and sarcopenia work).

## Constraints / decisions locked in

- No patient data ever referenced — profile stays at modality/cohort/task description level.
- Paywalled papers are flagged for manual download, not auto-fetched.
- Pipeline pauses after discovery, before any cloning or code execution.
- Experiment-plan code reuse targets the existing project repo, not a fresh one.
- Built and maintained by [you] + one collaborator.
- MVP = full pipeline in reduced form (fewer sources, simpler linking); no committed timeline yet, direction only.
- Every agent's `description:` must warn against being reimplemented from the description alone or routed around after a blocking completion report — it's the only content ambiently visible to an orchestrating session before dispatch (no plugin-level CLAUDE.md equivalent exists), and a past incident showed exactly that: a session treated a subagent's correct "needs a restart" report as license to fabricate the job itself.
- `arxiv-mcp-server` is declared as a real cross-marketplace dependency in `plugin.json`/`marketplace.json`. Verified by live testing (not assumed): the `dependencies` field auto-installs and auto-enables it — including a previously-`failed to load` install self-healing to enabled with no restart — but only once `arxiv-mcp-server`'s own marketplace is already registered; it does not auto-add an unregistered marketplace. README's install section adds both marketplaces up front for exactly this reason.
- **Agent vs. skill split.** A piece is a *skill* only if it needs the main conversation: `research-problem-intake` runs a live adaptive Q&A, and `second-brain-pipeline` has to hold the stage-4 checkpoint across a real turn (a dispatched agent runs to completion and returns once, so it structurally cannot pause for approval). Everything else is an *agent* — bounded, non-conversational work with a system-enforced `tools:` allowlist. `obsidian-vault` was originally a skill whose whole body was "dispatch a subagent," with that subagent existing only as prose; it is now `agents/obsidian-vault-writer.md`, so its tool scope is actually enforced rather than merely instructed. - **Workers never ask, never check the environment, never resolve their own inputs.** The orchestrator owns all three. An agent runs once and returns, so it structurally cannot pause for a human answer — any instruction telling one to "ask" is a bug (both `obsidian-vault-writer` and `paper-summarizer` had one). Every input an agent needs is passed explicitly by `second-brain-pipeline`, which is why template-path resolution lives in the pipeline and not in `paper-summarizer`. Agents report problems; the pipeline decides what to do about them and re-dispatches.
- **Vault-build does not depend on Obsidian being installed.** A vault is a folder of markdown files. `obsidian-vault-writer` originally returned `approval_required` and refused to write anything when the app was missing — backwards, since the notes could have been written regardless. The install check belonged only to *opening* the result, which is now an optional convenience step after stage 5 in `second-brain-pipeline`. Auto-install was dropped entirely (it was `winget`-only, so Windows-only, and wouldn't work under WSL anyway): the pipeline offers to launch Obsidian if present, and otherwise just reports the vault path. Installing software on the researcher's machine is out of scope.
- **One copy of each schema.** `templates/research-problem-profile-format-spec.md` and `templates/paper-page-template.md` are the only definitions of those two contracts. `skills/obsidian-vault/references/{problem-profile,paper-note}.md` used to restate both independently — deleted, because the vault stage's *input* is the summarizer stage's *output*, so any drift between the two copies would break the handoff silently. New consumers cite the `templates/` files; don't restate a schema locally.
- Also verified live (both the real install path and `claude --plugin-dir`): when `arxiv-mcp-server` is missing, Claude Code's plugin loader refuses to load `second-brain-researcher` at all — every agent and skill in it is completely unreachable, not just degraded. Because of this, `second-brain-paper-downloader` no longer contains its own `claude plugin list` dependency check (removed — it was a leftover from before the `dependencies` field existed, and could never actually run: the loader already blocks the whole plugin upstream in every supported invocation path). The general "don't improvise a substitute for a subagent that can't proceed" guardrail in the agent descriptions (see above) is unrelated to this and stays — it covers any reason an agent can't proceed, not specifically this dependency.

- Claude Code plugin **obsidian-vault-agent** (paper discovery + vault note writing)
- **ai-skill-arxiv** / **ai-skill-scholar** (lightweight arXiv/OpenAlex fetch skills)
- Obsidian MCP servers (vault read/write from Claude app)
- PubMed E-utilities integration likely needs custom work — existing tools skew CS/arXiv-heavy

## Open questions for the team to brainstorm

- ~~`obsidian-vault/SKILL.md`'s project-resolution heuristic still names `.agents` as a marker~~ — fixed: it now checks for a `.claude-plugin/plugin.json` naming `second-brain-researcher` instead, which actually exists post-restructure. (That file is now `agents/obsidian-vault-writer.md` — see the agent/skill split decision above.)
- ~~Template path resolution~~ — fixed in `second-brain-pipeline/SKILL.md`: the orchestrator now resolves `templates/paper-page-template.md` itself at Stage 5, via the explicit-runtime-lookup approach (checks `${CLAUDE_PLUGIN_ROOT}`, then a repo-relative path for local dev, then scans `~/.claude/plugins/marketplaces/*/` for a `.claude-plugin/plugin.json` naming this plugin), rather than each agent assuming a fixed path. **Not yet verified against a real marketplace install of this plugin** — the scan directory shape was inferred from how `arxiv-mcp-server` (a different, already-installed plugin) is laid out on disk, not confirmed for this one. Do a real `/plugin install` + invocation before treating this as fully closed.
- Note schema: exact YAML frontmatter fields, naming convention for files/IDs
- Dedup/ranking logic: how to merge near-duplicate hits across arXiv/PubMed/Semantic Scholar, and how much to weight citation count vs. recency vs. embedding similarity
- How many candidate papers/repos per query is the right cap before it’s noise?
- Repo analysis depth: how far to go beyond “structure + key classes” — does it need to identify the actual trainable entry point?
- Embedding model choice for the “related” link generation
- Checkpoint UI: what does the researcher actually see/approve at the pause point?
- Cross-project linking toggle: automatic suggestion vs. fully manual
- Team ownership: how do the two vaults (yours + collaborator’s) relate, if at all?
