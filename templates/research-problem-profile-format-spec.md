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

Required: **all** = both types; **problem** / **topic** = required for that type and absent (or ignored) for the other; **deep-dive** = required on a topic deep-dive profile and absent everywhere else (see "Deep-dive profiles" below); **no** = optional.

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
| `core_questions` | list[int] | topic | The 1-based numbers of the `review_questions` whose papers must be covered **completely**, usually one: the question the researcher's own work is compared against. The discovery legs do not cap its papers, and the citation chaser covers it exhaustively. `[]` means none (a broad survey): nothing is uncapped and citation chasing is skipped. Missing on a topic profile means the pipeline asks for it before discovery. A problem profile has no field: its core is always the direct comparators, papers doing its `task` on its `domain`. See "Core question" below. | Discovery legs + citation chaser |
| `seed_papers` | list[string] | no | Known key papers (title, DOI or arXiv id) or authors. Extra query anchors for discovery, not an allowlist. Topic profiles mostly, but valid on either type. Write each as `"<exact title> — <doi>"`, or `"<exact title>"` without a DOI, or a bare DOI, PMID, PMCID or arXiv id. `find_papers.py` takes a DOI from anywhere in the string, but otherwise reads the whole string as one id or one exact title, so a vault id or a trailing `# comment` makes a seed unfindable. | Paper-search group |
| `date_window_years` | integer | no | How many years back the main discovery sweep reaches. Missing means `3`; `0` means no lower bound. Either type. | Paper-search group |
| `recall_probes` | list[string] | no | 1–3 boolean queries in PubMed syntax for the **core** category — on a problem profile, papers doing its own task on its own condition. Not discovery-leg input: the citation chaser runs them, whole and without a date window, as its first round. Missing means the chaser drafts its own and reports them. Either type. See "Recall probes" below. | Citation chaser |
| `close_field_terms` | list[string] | all | Direct search terms for pass 1 of discovery | **Paper-search group — this is a primary input** |
| `generalized_methodology_terms` | list[string] | all | Abstracted terms for pass 2 (cross-field transfer search). **May be empty on a topic profile** — the researcher declined the cross-field pass — in which case that pass is skipped, not failed. | **Paper-search group — this is a primary input** |
| `keywords_of_interest` | list[string] | all | Subtopic taxonomy for this problem — the buckets papers get filed under. Lowercase kebab-case slugs. Not search input; see "Keyword vocabulary" below. | Obsidian group (topic notes) + `paper-summarizer` (preferred vocabulary) |
| `cross_project_linking` | bool | all | Whether this note should link to other active projects | Obsidian group |
| `related_projects` | list[string] | no | IDs of other problem-profile notes to check against | Obsidian group |
| `paper_vault_path` | string | no | Local path for this problem's downloaded PDFs, e.g. `<project-root>/second-brain/paper_vault/<id>/`. Blank if the intake skill didn't have filesystem access when it ran. | **Paper-search group — where to save PDFs** |
| `code_vault_path` | string | no | Local path for this problem's cloned repos, e.g. `<project-root>/second-brain/code_vault/<id>/`. Blank if the intake skill didn't have filesystem access when it ran. | **Paper-search group — where to clone repos** |
| `deep_dive_of` | string | deep-dive | The `id` of the vault this deep-dive deepens. Its presence is what makes a profile a deep-dive. | Pipeline |
| `vault_profile` | string | deep-dive | Absolute path to that vault's own profile. Every stage that writes vault content (summaries, links, vault-build) uses that profile, not this one. | Pipeline |
| `topic_note` | string | deep-dive | The kebab-case slug of the topic note being deepened or created. | Pipeline + `topic-summarizer` |
| `topic_aliases` | list[string] | deep-dive | Other slugs the note covers. `[]` when none. | Pipeline (digest) |

## Keyword vocabulary

`keywords_of_interest` is the subtopic taxonomy for this problem — what the researcher wants papers organized by. It is a different axis from the two term lists above: those are **search queries** tuned for recall, and often carry several phrasings of one idea. Keywords are meant to be few and orthogonal, because each one is a bucket a paper gets filed under.

The contract between this file and the paper notes:

- **Lowercase kebab-case slugs**, e.g. `distribution-shift`, `contrastive-pretraining`. Matching is plain string equality, so form matters. Human-readable topic-note titles can be derived from these later.
- **This list is a preferred vocabulary, not a closed one.** Its job is to prevent synonym drift: when a paper covers a concept already named here, `paper-summarizer` must reuse this exact slug rather than coining `domain-shift` alongside our `distribution-shift`. That reuse rule is the entire matching mechanism.
- **Paper notes may carry keywords beyond this list, by design.** A paper's `keywords` describe the paper itself, not its relation to this problem, so a subtopic irrelevant to this review may match a future one and let that paper be picked up again. Do not treat an unlisted keyword on a paper as an error.
- **Absent on older profiles is not an error** — treat a missing `keywords_of_interest` as an empty preferred vocabulary and carry on.

## Core question

Most of a review's questions are background: a fair sample of their literature is enough. One usually is not: the question the researcher's own work answers, whose papers are the direct comparators. A reRD review once found 5 of the 19 papers on that question, because every discovery stage treated it like the others. It rested on a few queries, their results were cut to the top 30, and its papers competed with epidemiology and cost papers for 20 slots.

`core_questions` names that question, so that:

- the discovery legs save **every** paper that passes screening for it, and cap only the background questions;
- the **citation chaser** runs after the legs and covers it exhaustively, independently of how the legs worded their queries. It runs the recall probes as whole hit sets, then chases citations one hop both ways from the vault's core papers through OpenAlex, round after round until a round adds nothing. No date window applies.

A problem profile needs no field: its core is always the direct comparators, papers doing its `task` on its `domain`.

## Recall probes

`recall_probes` are the core category's own queries, written at intake with the researcher, who knows the comparators best. The citation chaser runs them first, on PubMed, fetching every hit and never just the top ones, and screens them with its first round of citation candidates. On the reRD run, citation chasing recovered 10 of the 14 core papers discovery had missed, and a probe-style concept-block query recovered the other 4.

- **Syntax: concept blocks.** Each probe has 2–3 blocks joined by AND; a block is an OR-group of synonyms in parentheses, with every multi-word phrase in quotes — `("retinal detachment" OR redetachment) AND (recurren* OR "anatomical success") AND (nomogram* OR "risk score*" OR "logistic regression" OR "prediction model*" OR "machine learning" OR "deep learning")`.
- **Both method families.** A prediction-type probe names classical models (nomogram, risk score, logistic regression, prediction model) and machine learning together. The reRD run's only core query named machine learning alone and missed the four classical PVR models the field is built on.
- **Truncation for word families** (`predict*`, `recurren*`), with a stem of at least 4 characters. A truncated word escapes PubMed's automatic MeSH mapping, so keep the plain form beside it when it has a MeSH heading.
- **Tens of hits, not thousands.** A probe matching more than 300 papers is reported too broad and not fetched; the chaser splits it. Tagging a block's terms `[tiab]` keeps PubMed from widening them through MeSH mapping, which trims off-target hits.
- **Write each as a single-quoted YAML string** (`- '(...) AND (...)'`), since probes carry double quotes; a literal single quote is doubled.
- **Discovery legs do not read this field.** The chaser runs after them, and whatever the probes find that the legs missed is what it adds.
- **Absent is not an error.** Older profiles have none; the chaser drafts 1–3 from the core question, `task` and `domain`, and labels them as drafted in its report so the researcher can add them here.

## Deep-dive profiles

A **topic deep-dive** runs a literature search for one topic note of an existing vault: it deepens the note when it exists and creates it when it does not. The `second-brain-topic-deep-dive` skill drafts its profile through `research-problem-intake` and hands it to `second-brain-pipeline`.

- **It is a topic profile** (`profile_type: topic`), valid on its own, so every discovery leg and the citation chaser run on it unchanged. Its `review_scope`, `review_purpose`, 1–4 `review_questions` and `core_questions` are about the topic alone; its `keywords_of_interest` is `[<topic_note>]`; its body describes only the deep-dive.
- **Inherited from the vault profile:** `paper_vault_path` (new papers land in the vault's own paper vault and are deduplicated against it), `code_vault_path`, `date_window_years`, `cross_project_linking` and `related_projects`, and `domain` and `task` when the topic is anchored in the vault's domain. The vault profile's OUT exclusions carry over into `review_scope`.
- **Id:** `<topic_note>-deep-dive-<yyyymmdd>`, with `-2` on a same-day collision.
- **Where it lives:** `<root>/deep_dives/<vault-id>/<id>.md`. Never in the paper vault: every script reads each `.md` file at its top level as a paper record.
- **Who reads it.** The discovery legs and the citation chaser read it as their profile. `paper-summarizer` and `build_vault.py` never do: they get the vault profile, so new summaries tag the vault's review questions and carry its `related_problem`. `topic-summarizer` reads both, the vault profile for relevance and this one for scope, questions and depth.
- **The vault profile changes by one line:** the topic's slug is appended to its `keywords_of_interest`, with the researcher's consent, so `paper-summarizer` files new papers under it. Only the slug, never its aliases: an alias listed there would get a topic note of its own on the next normal run.
- **Seeds** are papers already in the note, at most 8, in the format the `seed_papers` row gives.

## Body

Free-text paragraph(s) restating the problem in plain language, underneath the frontmatter. This is for human readability in Obsidian — the frontmatter is the machine-consumable part. Neither group should need to parse the body for structured data; if a field is missing from frontmatter, that's a gap to flag back to intake, not something to extract from prose.

## Local directory structure

Intake also ensures three shared local directories exist (Claude Code sessions only — skipped silently from Claude app), at a placeholder default root of `<project-root>/second-brain/` — a folder created at the root of the current project, not the user's home directory:

```
<root>/
├── obsidian_vault/   # one Obsidian vault per problem id (obsidian_vault/<id>/ is the vault you open) — Obsidian group owns everything inside it
├── paper_vault/      # downloaded PDFs, one subfolder per problem id
├── code_vault/       # cloned repos, one subfolder per problem id
└── deep_dives/       # topic deep-dive profiles, one subfolder per vault id
```

Intake only creates the folders — it never writes into `obsidian_vault/`, and it only creates the empty per-problem subfolders under `paper_vault/`/`code_vault/`, not their contents. If `paper_vault_path`/`code_vault_path` are blank in a given note, the paper-search group should create the folder itself before writing rather than assuming it exists.

The root path itself is not yet a settled team convention — treat `<project-root>/second-brain/` as a placeholder until agreed otherwise.

## Notes for the paper-search group

- `close_field_terms` and `generalized_methodology_terms` are the two inputs for the two discovery passes described in the pipeline spec — treat them as separate query sets, not one merged list. A hit that only matches `generalized_methodology_terms` is a genuine cross-field transfer candidate and probably worth surfacing even with a weaker literal match.
- Don't query against a note with `status: draft` — it means the researcher hasn't confirmed the profile yet.
- `keywords_of_interest` is **not** search input. It's the vault's subtopic taxonomy — discovery still queries the two term lists only.
- `recall_probes` is not search input either. It is the citation chaser's first round, run after the legs.
- `core_questions` (or, on a problem profile, the direct comparators) marks the question whose papers are **not capped**: save every one that passes screening, and spread the usual 20 slots across the other questions only.
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
