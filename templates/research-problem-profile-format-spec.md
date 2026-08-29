# Research problem profile — output format spec

What the intake Q&A (`research-problem-intake` skill) produces, for the two groups consuming it downstream. This is the contract between stages 1–2 and everything after — if the format needs to change, it should change here first, not silently in either consuming group's code.

## Where this sits

Q&A intake → **this file** → paper/code discovery (uses the frontmatter to search) → checkpoint → vault build (files get linked into Obsidian).

We hand off a single `.md` file per problem. We do not write into the vault, do not perform cross-linking, and do not run discovery ourselves — those are owned by the Obsidian group and the paper-search group respectively.

## File

One `.md` file per problem, YAML frontmatter + free-text body. Delivered as a plain file (via whatever handoff mechanism the pipeline settles on — filesystem, message attachment, etc.), not written directly into any vault.

**Naming — still an open decision.** Current placeholder: `<slug>-<yyyymmdd>.md`, e.g. `sarcopenia-ct-embedding-20260825.md`. Neither group should treat this as final; flag it back to intake if you need it changed.

## Frontmatter schema

| Field | Type | Required | Description | Primarily used by |
|---|---|---|---|---|
| `id` | string | yes | Unique identifier, matches filename slug. This is the key everything links against — papers reference it via `related_problem`, cross-project links reference it directly. | Obsidian group |
| `created` | date | yes | `yyyy-mm-dd` | Obsidian group |
| `status` | enum | yes | `draft` (mid-Q&A, not yet confirmed) or `confirmed` (researcher approved, ready for discovery). **Discovery should not run against a `draft` file.** | Paper-search group |
| `domain` | string | yes | Free-text field/domain, e.g. "sarcopenia CT segmentation" | Paper-search group |
| `data_modality` | string | yes | Modality + acquisition detail | Paper-search group |
| `study_design` | string | no | Prospective / retrospective | Paper-search group (context, not a query term) |
| `data_source` | string | no | Named public dataset, or private/multi-site description | Paper-search group |
| `cohort_description` | string | yes | Size, subgroups, skew | Both (context) |
| `inclusion_exclusion_criteria` | string | no | Notable exclusions affecting comparability | Paper-search group |
| `task` | string | yes | The actual task, e.g. "binary classification from CT slice" | Paper-search group |
| `reference_standard` | string | yes | What's used as ground truth, plus rationale/annotation notes | Both |
| `data_partitioning` | string | no | Split strategy, disjoint level | Both (also a failure-mode signal) |
| `sample_size` | string | no | Intended or actual N | Paper-search group |
| `current_approach` | string | yes | What's been tried | Both |
| `observed_failure_mode` | string | yes | What went wrong | Both |
| `close_field_terms` | list[string] | yes | Direct search terms for pass 1 of discovery | **Paper-search group — this is a primary input** |
| `generalized_methodology_terms` | list[string] | yes | Abstracted terms for pass 2 (cross-field transfer search) | **Paper-search group — this is a primary input** |
| `keywords_of_interest` | list[string] | yes | Subtopic taxonomy for this problem — the buckets papers get filed under. Lowercase kebab-case slugs. Not search input; see "Keyword vocabulary" below. | Obsidian group (topic notes) + `paper-summarizer` (preferred vocabulary) |
| `cross_project_linking` | bool | yes | Whether this note should link to other active projects | Obsidian group |
| `related_projects` | list[string] | no | IDs of other problem-profile notes to check against | Obsidian group |
| `paper_vault_path` | string | no | Local path for this problem's downloaded PDFs, e.g. `<project-root>/second-brain/paper_vault/<id>/`. Blank if the intake skill didn't have filesystem access when it ran. | **Paper-search group — where to save PDFs** |
| `code_vault_path` | string | no | Local path for this problem's cloned repos, e.g. `<project-root>/second-brain/code_vault/<id>/`. Blank if the intake skill didn't have filesystem access when it ran. | **Paper-search group — where to clone repos** |

## Keyword vocabulary

`keywords_of_interest` is the subtopic taxonomy for this problem — what the researcher wants papers organized by. It is a different axis from the two term lists above: those are **search queries** tuned for recall, and often carry several phrasings of one idea. Keywords are meant to be few and orthogonal, because each one is a bucket a paper gets filed under.

The contract between this file and the paper notes:

- **Lowercase kebab-case slugs**, e.g. `distribution-shift`, `contrastive-pretraining`. Matching is plain string equality, so form matters. Human-readable topic-note titles can be derived from these later.
- **This list is a preferred vocabulary, not a closed one.** Its job is to prevent synonym drift: when a paper covers a concept already named here, `paper-summarizer` must reuse this exact slug rather than coining `domain-shift` alongside our `distribution-shift`. That reuse rule is the entire matching mechanism.
- **Paper notes may carry keywords beyond this list, by design.** A paper's `keywords` describe the paper itself, not its relation to this problem, so a subtopic irrelevant to this review may match a future one and let that paper be picked up again. Do not treat an unlisted keyword on a paper as an error.
- **Absent on older profiles is not an error** — treat a missing `keywords_of_interest` as an empty preferred vocabulary and carry on.

## Body

Free-text paragraph(s) restating the problem in plain language, underneath the frontmatter. This is for human readability in Obsidian — the frontmatter is the machine-consumable part. Neither group should need to parse the body for structured data; if a field is missing from frontmatter, that's a gap to flag back to intake, not something to extract from prose.

## Local directory structure

Intake also ensures three shared local directories exist (Claude Code sessions only — skipped silently from Claude app), at a placeholder default root of `<project-root>/second-brain/` — a folder created at the root of the current project, not the user's home directory:

```
<root>/
├── obsidian_vault/   # Obsidian vault root — Obsidian group owns everything inside it
├── paper_vault/      # downloaded PDFs, one subfolder per problem id
└── code_vault/       # cloned repos, one subfolder per problem id
```

Intake only creates the folders — it never writes into `obsidian_vault/`, and it only creates the empty per-problem subfolders under `paper_vault/`/`code_vault/`, not their contents. If `paper_vault_path`/`code_vault_path` are blank in a given note, the paper-search group should create the folder itself before writing rather than assuming it exists.

The root path itself is not yet a settled team convention — treat `<project-root>/second-brain/` as a placeholder until agreed otherwise.

## Notes for the paper-search group

- `close_field_terms` and `generalized_methodology_terms` are the two inputs for the two discovery passes described in the pipeline spec — treat them as separate query sets, not one merged list. A hit that only matches `generalized_methodology_terms` is a genuine cross-field transfer candidate and probably worth surfacing even with a weaker literal match.
- Don't query against a note with `status: draft` — it means the researcher hasn't confirmed the profile yet.
- `keywords_of_interest` is **not** search input. It's the vault's subtopic taxonomy — discovery still queries the two term lists only.
- `domain`, `data_modality`, `task`, `reference_standard`, `data_partitioning` are free text, not enums — expect variation in phrasing across notes, no fixed vocabulary yet.

## Notes for the Obsidian group

- `id` is the stable key for cross-linking — use it, not the filename, if the naming convention changes later.
- `cross_project_linking: true` + a populated `related_projects` list means the researcher explicitly asked for this note to be checked against named other notes — that's distinct from any automatic "related" linking via embedding similarity, which is a separate, still-undecided mechanism (open question in the pipeline spec).
- `status` will need a value beyond `draft`/`confirmed` once this note starts accumulating linked papers (e.g. `active`) — not yet defined here, since that lifecycle is vault-side, not intake-side. Worth deciding together rather than either group assuming.

## Open items neither group should treat as settled

- File/ID naming convention
- Full `status` lifecycle beyond draft → confirmed
- Whether `related_projects` should be validated (i.e. checked to exist) at write time, and by whom
