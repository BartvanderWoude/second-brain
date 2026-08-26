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

## Structure

```
second-brain-researcher/
├── skills/
│   └── research-problem-intake.skill             # stage 1–2: Q&A that produces the problem-profile note
├── .agents/
│   ├── second-brain-paper-downloader.md           # stage 3 (arXiv only): finds + saves papers into paper_vault/<id>/
│   ├── paper-summarizer.md                        # stage 5 (papers): one paper -> one structured summary note
│   └── skills/
│       ├── second-brain-pipeline/SKILL.md          # orchestrator: runs stages 1–5 end to end, holds the stage-4 checkpoint
│       └── obsidian-vault/SKILL.md                 # stage 5 (vault): materializes profile + paper notes into the Obsidian vault
├── templates/
│   ├── paper-page-template.md                    # stage 5: structure for a discovered-paper note
│   └── research-problem-profile-format-spec.md   # shared contract: exact schema the intake skill outputs
└── README.md
```

**Note on placement:** `research-problem-profile-format-spec.md` is a format contract more than a fill-in-the-blanks template, but it lives in `templates/` for now since that's the only place for shared reference docs in the current structure. Worth revisiting once there's more than one non-skill, non-template doc to place (e.g. a `docs/` folder).

## What's built so far

- **`research-problem-intake` skill** — runs the adaptive Q&A, deepens the researcher's initial description (including fields drawn from the CLAIM checklist for AI-in-medical-imaging reporting), produces the two search-term lists discovery consumes, and writes a confirmed problem-profile `.md` file. Also sets up three local working directories (`paper_vault/`, `code_vault/`, `obsidian_vault/`) when run from Claude Code.
- **`second-brain-paper-downloader` agent** — stage 3, arXiv only. Reads a confirmed problem profile's `paper_vault_path`, searches arXiv in two passes (close-field, then generalized terms), and saves up to 20 matched papers there.
- **`paper-summarizer` agent** — stage 5 (papers). Turns one saved paper into a structured summary note conforming to `paper-page-template.md`. Optionally takes the confirmed problem profile as a third input, in which case `related_problem`, `matched_terms`, and the relevance synthesis are grounded in that specific problem rather than written as a generic assessment.
- **`obsidian-vault` skill** — stage 5 (vault). Materializes a confirmed problem profile and a collection of paper-summary notes into an Obsidian vault as a star graph (problem ↔ papers).
- **`second-brain-pipeline` skill** — the orchestrator. Runs the above four in sequence against one research problem, pausing at the stage-4 checkpoint for researcher review before vault-build.
- **`paper-page-template.md`** — the note format for a paper once discovery finds it, including how it links back to the problem that surfaced it.
- **`research-problem-profile-format-spec.md`** — the frontmatter schema for the problem-profile note, field by field, with notes for what the paper-search and Obsidian groups each need from it.
