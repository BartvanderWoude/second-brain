# Research problem profile — output format spec

What the intake Q&A (`research-problem-intake` skill) produces, for the two groups consuming it downstream. This is the contract between stages 1–2 and everything after — if the format needs to change, it should change here first, not silently in either consuming group's code.

## Where this sits

Q&A intake → **this file** → paper/code discovery (uses the frontmatter to search) → checkpoint → vault build (files get linked into Obsidian).

We hand off a single `.md` file per problem. We do not write into the vault, do not perform cross-linking, and do not run discovery ourselves — those are owned by the Obsidian group and the paper-search group respectively.

## File

One `.md` file per problem, YAML frontmatter + free-text body. Delivered as a plain file (via whatever handoff mechanism the pipeline settles on — filesystem, message attachment, etc.), not written directly into any vault.

**Naming — still an open decision.** Current placeholder: `<slug>-<yyyymmdd>.md`, e.g. `sarcopenia-ct-embedding-20260825.md`. Neither group should treat this as final; flag it back to intake if you need it changed.

## Profile types

A profile is one of two types, set by `profile_type`:

- **`problem`** — a concrete research problem with data behind it: a task, a reference standard, something tried, something that failed. Relevance downstream is anchored on `observed_failure_mode` and `current_approach`.
- **`topic`** — a literature review of a topic, with no specific problem or dataset. Relevance downstream is anchored on `review_questions` and `review_purpose`.

**A missing `profile_type` means `problem`.** Every profile written before this field existed is a problem profile, and must keep working unchanged.

Both types share the id, status, term lists, keywords, linking and vault-path fields, and produce the same vault layout. Only the context fields in between differ — the "Required" column below says which apply to which type.

## Frontmatter schema

Required: **all** = both types; **problem** / **topic** = required for that type and absent (or ignored) for the other; **no** = optional.

| Field | Type | Required | Description | Primarily used by |
|---|---|---|---|---|
| `id` | string | all | Unique identifier, matches filename slug. This is the key everything links against — papers reference it via `related_problem`, cross-project links reference it directly. | Obsidian group |
| `created` | date | all | `yyyy-mm-dd` | Obsidian group |
| `status` | enum | all | `draft` (mid-Q&A, not yet confirmed) or `confirmed` (researcher approved, ready for discovery). **Discovery should not run against a `draft` file.** | Paper-search group |
| `profile_type` | enum | no | `problem` or `topic`. Missing means `problem`. | Everyone — decides which fields below apply |
| `domain` | string | problem | Free-text field/domain, e.g. "sarcopenia CT segmentation". Optional for topic profiles, but useful for arXiv category choice when given. | Paper-search group |
| `data_modality` | string | problem | Modality + acquisition detail | Paper-search group |
| `study_design` | string | no | Prospective / retrospective. Problem profiles only. | Paper-search group (context, not a query term) |
| `data_source` | string | no | Named public dataset, or private/multi-site description. Problem profiles only. | Paper-search group |
| `cohort_description` | string | problem | Size, subgroups, skew | Both (context) |
| `inclusion_exclusion_criteria` | string | no | Notable exclusions affecting comparability. Problem profiles only. | Paper-search group |
| `task` | string | problem | The actual task, e.g. "binary classification from CT slice". Optional for topic profiles. | Paper-search group |
| `reference_standard` | string | problem | What's used as ground truth, plus rationale/annotation notes | Both |
| `data_partitioning` | string | no | Split strategy, disjoint level. Problem profiles only. | Both (also a failure-mode signal) |
| `sample_size` | string | no | Intended or actual N. Problem profiles only. | Paper-search group |
| `current_approach` | string | problem | What's been tried | Both |
| `observed_failure_mode` | string | problem | What went wrong | Both |
| `review_scope` | string | topic | What the review covers and what it explicitly rules out | Both — discovery screens against it |
| `review_purpose` | string | topic | Why the review is being done — entering a field, grant background, judging whether a method is mature, etc. | Summarizers (steers relevance) |
| `review_questions` | list[string] | topic | 1–5 guiding questions the review should answer. The topic-profile counterpart of `observed_failure_mode`: the anchor every relevance section ties back to. | Summarizers + pipeline report |
| `seed_papers` | list[string] | no | Known key papers (title, DOI or arXiv id) or authors. Extra query anchors for discovery, not an allowlist. Topic profiles mostly, but valid on either type. | Paper-search group |
| `date_window_years` | integer | no | How many years back the main discovery sweep reaches. Missing means `3`; `0` means no lower bound. Either type. | Paper-search group |
| `recall_probes` | list[string] | no | 1–3 boolean queries in PubMed syntax describing the **direct-comparator** category — papers doing this profile's own task on its own condition. Not discovery input: the stage-4 recall check runs them and reports hits the vault lacks. Missing means the pipeline drafts its own at stage 4. Either type. See "Recall probes" below. | Pipeline (stage-4 recall check) |
| `close_field_terms` | list[string] | all | Direct search terms for pass 1 of discovery | **Paper-search group — this is a primary input** |
| `generalized_methodology_terms` | list[string] | all | Abstracted terms for pass 2 (cross-field transfer search). **May be empty on a topic profile** — the researcher declined the cross-field pass — in which case that pass is skipped, not failed. | **Paper-search group — this is a primary input** |
| `keywords_of_interest` | list[string] | all | Subtopic taxonomy for this problem — the buckets papers get filed under. Lowercase kebab-case slugs. Not search input; see "Keyword vocabulary" below. | Obsidian group (topic notes) + `paper-summarizer` (preferred vocabulary) |
| `cross_project_linking` | bool | all | Whether this note should link to other active projects | Obsidian group |
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

## Recall probes

`recall_probes` is the check on discovery, not an input to it. The discovery legs build their own queries from the two term lists, and nothing downstream sees what those queries missed: a reRD review once lacked two of the four papers that were its closest comparators, and no stage noticed. A probe is a small, precise query for the one category whose gaps matter most — the papers the researcher's own work would be compared against. At the stage-4 checkpoint, `scripts/recall_check.py` runs each probe on PubMed and arXiv and lists every top hit that is not already in the paper vault.

- **Syntax: concept blocks.** Each probe has 2–3 blocks joined by AND; a block is an OR-group of synonyms in parentheses, with every multi-word phrase in quotes — `("retinal detachment" OR redetachment) AND (recurrence OR "anatomical success") AND (nomogram OR "machine learning" OR "prediction model")`. PubMed syntax; the script translates it for arXiv, dropping any `[tiab]`-style field tag there. Tagging a block's terms `[tiab]` keeps PubMed from widening them through MeSH mapping, which trims off-target hits.
- **Precise, not exhaustive.** A probe should return tens of hits, mostly on target. The check flags a probe that returns more than 60 as `too_broad` — the top of a flood is not a recall test.
- **Write each as a single-quoted YAML string** (`- '(...) AND (...)'`), since probes carry double quotes; a literal single quote is doubled.
- **Discovery legs do not read this field.** Letting them query with it would make the check test itself.
- **Absent is not an error.** Older profiles have none; the pipeline drafts 1–3 at stage 4 from `task`, `domain` and `close_field_terms`, and labels them as drafted in its report.

## Body

Free-text paragraph(s) restating the problem in plain language, underneath the frontmatter. This is for human readability in Obsidian — the frontmatter is the machine-consumable part. Neither group should need to parse the body for structured data; if a field is missing from frontmatter, that's a gap to flag back to intake, not something to extract from prose.

## Local directory structure

Intake also ensures three shared local directories exist (Claude Code sessions only — skipped silently from Claude app), at a placeholder default root of `<project-root>/second-brain/` — a folder created at the root of the current project, not the user's home directory:

```
<root>/
├── obsidian_vault/   # one Obsidian vault per problem id (obsidian_vault/<id>/ is the vault you open) — Obsidian group owns everything inside it
├── paper_vault/      # downloaded PDFs, one subfolder per problem id
└── code_vault/       # cloned repos, one subfolder per problem id
```

Intake only creates the folders — it never writes into `obsidian_vault/`, and it only creates the empty per-problem subfolders under `paper_vault/`/`code_vault/`, not their contents. If `paper_vault_path`/`code_vault_path` are blank in a given note, the paper-search group should create the folder itself before writing rather than assuming it exists.

The root path itself is not yet a settled team convention — treat `<project-root>/second-brain/` as a placeholder until agreed otherwise.

## Notes for the paper-search group

- `close_field_terms` and `generalized_methodology_terms` are the two inputs for the two discovery passes described in the pipeline spec — treat them as separate query sets, not one merged list. A hit that only matches `generalized_methodology_terms` is a genuine cross-field transfer candidate and probably worth surfacing even with a weaker literal match.
- Don't query against a note with `status: draft` — it means the researcher hasn't confirmed the profile yet.
- `keywords_of_interest` is **not** search input. It's the vault's subtopic taxonomy — discovery still queries the two term lists only.
- `recall_probes` is not search input either. It is the stage-4 check on what discovery found; a leg that queried with it would be grading its own work.
- `domain`, `data_modality`, `task`, `reference_standard`, `data_partitioning` are free text, not enums — expect variation in phrasing across notes, no fixed vocabulary yet.
- On a `topic` profile, most of those fields are absent. Screen relevance against `review_scope` instead, and treat `seed_papers` as extra query anchors — search for them and their neighbourhood, but don't save a seed paper that falls outside `review_scope` just because it was named.
- Read `date_window_years` for the main sweep's lower bound: missing → 3 years, `0` → none. Never hardcode the window.

## Notes for the Obsidian group

- `id` is the stable key for cross-linking — use it, not the filename, if the naming convention changes later.
- `cross_project_linking: true` + a populated `related_projects` list means the researcher explicitly asked for this note to be checked against named other notes — that's distinct from any automatic "related" linking via embedding similarity, which is a separate, still-undecided mechanism (open question in the pipeline spec).
- `status` will need a value beyond `draft`/`confirmed` once this note starts accumulating linked papers (e.g. `active`) — not yet defined here, since that lifecycle is vault-side, not intake-side. Worth deciding together rather than either group assuming.

## Open items neither group should treat as settled

- File/ID naming convention
- Full `status` lifecycle beyond draft → confirmed
- Whether `related_projects` should be validated (i.e. checked to exist) at write time, and by whom
