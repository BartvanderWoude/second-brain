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

## Existing building blocks worth evaluating before building from scratch

- Claude Code plugin **obsidian-vault-agent** (paper discovery + vault note writing)
- **ai-skill-arxiv** / **ai-skill-scholar** (lightweight arXiv/OpenAlex fetch skills)
- Obsidian MCP servers (vault read/write from Claude app)
- PubMed E-utilities integration likely needs custom work — existing tools skew CS/arXiv-heavy

## Open questions for the team to brainstorm

- Note schema: exact YAML frontmatter fields, naming convention for files/IDs
- Dedup/ranking logic: how to merge near-duplicate hits across arXiv/PubMed/Semantic Scholar, and how much to weight citation count vs. recency vs. embedding similarity
- How many candidate papers/repos per query is the right cap before it’s noise?
- Repo analysis depth: how far to go beyond “structure + key classes” — does it need to identify the actual trainable entry point?
- Embedding model choice for the “related” link generation
- Checkpoint UI: what does the researcher actually see/approve at the pause point?
- Cross-project linking toggle: automatic suggestion vs. fully manual
- Team ownership: how do the two vaults (yours + collaborator’s) relate, if at all?
