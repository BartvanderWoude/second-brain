# second-brain-researcher

Agentic research pipeline for literature and code discovery, built on Claude Code + Claude app + Obsidian.

Methods relevant to a problem often already exist in an adjacent field, but finding them is manual and ad hoc — and whatever gets found rarely ends up captured anywhere durable, so the next project starts from zero. This pipeline turns a researcher's problem description into a structured search, and structures what it finds into a browsable, linked knowledge base.

## Pipeline overview

1. **Intake** — researcher describes the problem (domain, data, task, reference standard).
2. **Problem profile** — an adaptive Q&A deepens the description into a structured note, including the two term lists discovery searches against.
3. **Discovery** — parallel search across papers (arXiv, PubMed, Semantic Scholar) and code (GitHub).
4. **Vault build** — discovered papers and repos become structured notes.
5. **Cross-linking** (not implemented) — notes get linked to each other and to the problem, forming an Obsidian graph.


This repo currently covers stages 1–2 (`research-problem-intake`) and defines the handoff format the later stages build against. 

## Structure

```
second-brain-researcher/
├── skills/
│   └── research-problem-intake.skill     # stage 1–2: Q&A that produces the problem-profile note
│    
├── templates/
│   ├── paper-page-template.md                    # stage 5: structure for a discovered-paper note
│   └── research-problem-profile-format-spec.md   # shared contract: exact schema the intake skill outputs
└── README.md
```

**Note on placement:** `research-problem-profile-format-spec.md` is a format contract more than a fill-in-the-blanks template, but it lives in `templates/` for now since that's the only place for shared reference docs in the current structure. Worth revisiting once there's more than one non-skill, non-template doc to place (e.g. a `docs/` folder).

## What's built so far

- **`research-problem-intake` skill** — runs the adaptive Q&A, deepens the researcher's initial description (including fields drawn from the CLAIM checklist for AI-in-medical-imaging reporting), produces the two search-term lists discovery consumes, and writes a confirmed problem-profile `.md` file. Also sets up three local working directories (`paper_vault/`, `code_vault/`, `obsidian_vault/`) when run from Claude Code.
- **`paper-page-template.md`** — the note format for a paper once discovery finds it, including how it links back to the problem that surfaced it.
- **`research-problem-profile-format-spec.md`** — the frontmatter schema for the problem-profile note, field by field, with notes for what the paper-search and Obsidian groups each need from it.
