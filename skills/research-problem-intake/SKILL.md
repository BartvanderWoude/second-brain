---
name: research-problem-intake
description: "Runs the interactive Q&A that turns a researcher's initial description — either a concrete research problem or a topic they want reviewed — into a structured research-problem-profile markdown file, ready to hand off to literature/code discovery. Use this whenever a researcher describes a new research problem, method failure, or open question they want to investigate, or wants a literature review of a topic with no specific problem or dataset behind it — including phrases like 'help me define this problem', 'I want to search for related work on X', 'do a literature review on X', 'what's known about X', 'start a new research problem', or 'set up intake for this project'. Also use when the researcher pastes a rough problem description, a failed-experiment writeup, or asks to deepen/finish a partially-filled profile. Do not use for general literature search questions that already have a fully specified query — this skill is specifically for turning a vague or partial description into the structured profile that discovery consumes."
---

# Research problem intake

Turns a researcher's initial description into a structured markdown profile note through an adaptive Q&A, then writes that note as a `.md` file. The description is one of two kinds, and the Q&A branches on which:

- **Problem** — a concrete research problem with data behind it (domain, data, task, what failed). Written as `profile_type: problem`.
- **Topic** — a literature review of a topic, with no specific problem or dataset (e.g. "what's known about self-supervised pretraining for CT"). Written as `profile_type: topic`.

Only Tier 0 and Tier 1 differ between the two; Tier 2 and Tier 3 are shared.

This is stage 1–2 of the second-brain research pipeline — the output is what stage 3 (paper/code discovery) searches against, so the two term lists it produces (close-field and generalized-methodology) matter more than any other field.

Works identically whether invoked from Claude app or Claude Code — same questions, same schema, same output file. This skill only produces the `.md` file. Writing it into the Obsidian vault, cross-linking, or any vault-side handling is out of scope — a separate part of the system owns that.

## Process

0. **Ensure the shared local vault directories exist.** Only when this skill has filesystem access (Claude Code) — skip silently in Claude app. Before anything else in a session, idempotently create the top-level directory structure the rest of the pipeline reads from, if it doesn't already exist:

   ```
   <root>/
   ├── obsidian_vault/   # Obsidian vault root — owned by the Obsidian group after creation; this skill only ensures the folder exists, never writes into it
   ├── paper_vault/      # downloaded paper PDFs, one subfolder per problem
   └── code_vault/       # cloned repos, one subfolder per problem
   ```

   Default root: `<project-root>/second-brain/` — a `second-brain/` folder created at the root of the current project (the directory Claude Code was invoked in), not the user's home directory. This is a placeholder, not a settled team convention — if the team has already agreed on a root location, use that instead. Use `mkdir -p` semantics: create only what's missing, never touch or delete existing content in any of the three directories. If directory creation fails (e.g. no filesystem access, permission error), don't block the Q&A on it — note the failure plainly at the end and continue.

1. **Decide the profile type.** Infer it from the opening message: data, a task, a baseline or a failure means **problem**; "literature review", "what's known about", "overview of", "get into the field of" with no data behind it means **topic**. Only if it is genuinely unclear, ask once: "Is there a specific problem you're trying to solve with your own data, or do you want a review of a topic?" Never walk a topic researcher through the problem questions — cohort, reference standard and failure mode have no honest answer there, and forcing one pollutes every relevance section downstream.
2. **Take Tier 0 as given.** Problem type: if the researcher already stated domain, data modality, task, and reference standard (e.g. in their opening message), do not re-ask for these — treat them as the seed and move straight to deepening them in Tier 1. If none of this was given yet, ask for it first in one open question: "What's the problem — domain, data you're working with, the task, and what you're using as ground truth?" Topic type: the seed is the topic itself plus whatever framing came with it; if it was a bare phrase, ask one open question: "What's the topic, and what do you want out of the review?"
3. **Work through Tier 1** for the chosen type (below), one question at a time, adapting to what's already been said. Skip any question already answered by something the researcher volunteered earlier in the conversation.
4. **Run the Tier 2 abstraction step.** This is the highest-value part of the whole skill — see the dedicated section below. Do not skip or shortcut it even if the researcher seems ready to move on.
5. **Ask Tier 3 bookkeeping** questions.
6. **Present the full draft** (every field below, plus both term lists) as a single summary and ask the researcher to confirm or edit. Do not write the file until they confirm.
7. **Create this profile's subfolders**, if filesystem access is available: `paper_vault/<id>/` and `code_vault/<id>/`, using the `id` about to go into the frontmatter. Skip silently in Claude app, same as step 0.
8. **Write the `.md` file** using the output format below, setting `status: confirmed` — the researcher approved the draft in step 6, and every downstream stage refuses to run against a `draft` profile. Save it and hand it back to the researcher (e.g. via `present_files` if available). Tell them plainly this is ready for hand-off to discovery/vault-writing — don't perform those steps yourself.

   If the researcher stops partway and asks you to save an unfinished profile, write it with `status: draft` and tell them plainly that discovery won't run against it until it's confirmed.

### Handling thin answers

If an answer is a single word, "not sure," or otherwise clearly underdeveloped, ask exactly **one** follow-up (each field below has a suggested one). If the second answer is still thin, record what you have and move on — don't loop trying to extract depth that isn't there. Note the gap plainly in the confirmation summary rather than silently padding the field.

## Tier 1 (problem) — required fields

For each field: primary question, then a one-shot follow-up to use only if the first answer is thin.

**`study_design`**
- "Is the underlying data prospective or retrospective?"

**`data_source`**
- "Is this a named public dataset, a private single-site cohort, or multi-site? If public, which one?"

**`data_modality`** (deepens whatever was given in Tier 0)
- "What's the resolution/format/acquisition detail that actually matters for method choice — slice thickness, sequence length, sampling rate, whatever's relevant to this modality?"
- Follow-up: "Anything unusual about how this data was collected that a standard pipeline might not expect?"

**`cohort_description`**
- "Who or what is in the dataset — size, key subgroups, anything skewed or unusual about the population/sample?"
- Follow-up: "Any known confound or imbalance you're already worried about?"

**`inclusion_exclusion_criteria`**
- "Any notable inclusion/exclusion criteria — age range, disease stage, scanner type, anything excluded that a naive comparison might not account for?"

**`reference_standard`** (deepen, don't just carry through from Tier 0)
- "Why was this reference standard chosen over alternatives?"
- "Who produced the annotations, and is there any known inter-rater or intra-rater variability?"

**`data_partitioning`**
- "How is the data split into train/test, if at all yet? Is that split guaranteed disjoint at the patient level, not just image/scan level?"
- If the answer suggests non-patient-level splitting or leakage risk, flag it explicitly as a candidate for `observed_failure_mode` below rather than silently noting it only here.

**`sample_size`**
- "What's the intended or actual sample size?"

**`current_approach`**
- "What have you already tried, even informally? Include the baseline if there is one."
- If nothing tried yet: "What's the first method you'd reach for by default, and why?"

**`observed_failure_mode`**
- "What specifically went wrong — underperformance, a specific error pattern, instability, something that looked fine but didn't hold up?"
- Follow-up: "If you had to guess the mechanism behind that failure, what's your hunch, even unconfirmed?"

The failure-mode question is deliberately asked last in Tier 1, right before the abstraction step — the researcher's own hunch becomes raw material for it instead of the agent generalizing cold.

**`date_window_years`** — only ask if something the researcher said suggests the default is wrong (they mention a classic method, an old benchmark, or "only the last year"). Otherwise record nothing and let discovery use its 3-year default.

## Tier 1 (topic) — required fields

Same one-question-at-a-time rhythm and thin-answer rule as the problem branch. None of the problem fields are asked here — no cohort, reference standard, partitioning, or failure mode.

**`review_purpose`**
- "What's the review for — getting into a field, background for a grant or paper, deciding whether a method is mature enough to adopt, something else?"
- Follow-up: "What would you do differently depending on what the review finds?"

**`review_scope`**
- "Where are the edges of the topic — what's clearly in, and what's adjacent but out?"
- Follow-up: "Is there a nearby topic that people often lump in with this one that you want kept out?"

**`seed_papers`**
- "Are there papers or authors you already know are central? Titles, DOIs or names are all fine — it's fine if the answer is none."
- No follow-up. An empty list is a real answer for someone new to a field.

**`date_window_years`**
- "How far back should the search reach? The default is the last 3 years; say 'no limit' if foundational older work matters." Record `0` for no limit, and leave the field out if they accept the default.

**`review_questions`**
- "What 1–5 questions should the review answer by the end? For example: which methods exist, how they compare, what's still unsolved."
- Follow-up, if the answer is one vague question: "Here's how I'd split that into sharper questions: [draft]. Does that match what you want to know?"

`review_questions` is deliberately asked last, right before the abstraction step, for the same reason the failure mode is in the problem branch: it is the raw material the term lists and keywords are drafted from, and it is what every relevance section downstream ties back to. Where the researcher's topic implies a `domain` or `task`, record it — it helps discovery choose arXiv categories — but don't ask for either as a separate question.

## Tier 2 — abstraction step (produces the two term lists and the keyword taxonomy)

This is the skill's actual value-add and the part most likely to be shallow if rushed. Three sequential steps:

**Close-field terms** — usually mostly extractable from Tier 1 answers. Draft it yourself and confirm rather than asking cold:
- "Here's a draft of close-field search terms based on what you've described: [draft list]. Anything to add or cut?"

**Generalized methodology terms** — ask explicitly, never infer silently:
- "Strip away the domain framing for a second. What's the underlying computational or statistical problem — a distribution-shift problem, a small-sample problem, a representation/pooling problem, a label-noise problem, something else?"
- If the answer comes back in domain language again, reframe once: "Put it in terms that'd make sense to someone in a completely different field working on [your best candidate abstraction] — does that fit, or is it something else?"
- Close with: "Here's a draft of generalized terms: [draft list]. Does this feel like it'd actually surface the right adjacent-field work?"

Cap the reframe at one nudge. If the researcher's second answer is still domain-flavored, use their best attempt rather than pushing further — record it as-is and let the confirmation step catch it if it's not good enough.

**Topic profiles: offer the cross-field pass, don't impose it.** A topic review may or may not want work from other fields — a review of "sarcopenia biomarkers" usually doesn't, while a review of "self-supervised pretraining" often wants the same method as used in other literatures. So draft the generalized terms from `review_questions` and `review_scope` and put it as a choice: "Want a cross-field pass too — papers from other fields using the same ideas? Here's a draft of terms for it: [draft list]. Or we can skip it." If they skip it, record `generalized_methodology_terms: []`. That is valid on a topic profile, and the cross-field leg reports it as skipped, not failed. On a problem profile the list is never empty; run the steps above as written.

**Keywords of interest** — the subtopic taxonomy. Do this last, so it can draw on all of Tier 1 plus both term lists. **Always draft and confirm, never ask cold**: the whole premise is that a researcher knows their topic but not yet their subtopics, so asking "what subtopics interest you?" puts the work back on the person least able to do it. Infer them from everything said so far:

- "Based on everything you've described, here are the subtopics I'd track as keywords: [draft list]. These become the topic buckets papers get filed under — anything missing, too broad, or not actually of interest?"

Drafting guidance:

- Aim for roughly 5–15. A taxonomy too large to hold in your head is no longer a taxonomy.
- Each one should be a subtopic somebody could write a note about — not a search phrase.
- Keep them **orthogonal**. Near-synonyms are what the two term lists are for; here they'd just fragment the same papers across duplicate buckets.
- Cover both domain subtopics (`sarcopenia`, `abdominal-ct`) and method/technique subtopics (`contrastive-pretraining`, `distribution-shift`).
- Lowercase kebab-case slugs, always — paper notes match these by exact string.

Same thin-answer rule as everywhere else: one follow-up if the response is a shrug, then record the draft as-is and move on.

## Tier 3 — bookkeeping

**`cross_project_linking`**
- "Should this link to your other active projects if something turns out relevant, or stay standalone for now?"

**`related_projects`** — only ask if the above is yes:
- "Which existing project(s) should it check against?"

## Output format

Write a single markdown file with YAML frontmatter. **Problem profile:**

```yaml
---
id: <slug>-<yyyymmdd>
created: <yyyy-mm-dd>
status: confirmed
profile_type: problem
domain:
data_modality:
study_design:
data_source:
cohort_description:
inclusion_exclusion_criteria:
task:
reference_standard:
data_partitioning:
sample_size:
current_approach:
observed_failure_mode:
date_window_years:          # omit unless the researcher changed the 3-year default
close_field_terms: []
generalized_methodology_terms: []
keywords_of_interest: []
cross_project_linking: true/false
related_projects: []
paper_vault_path: <root>/paper_vault/<id>/
code_vault_path: <root>/code_vault/<id>/
---
```

**Topic profile:**

```yaml
---
id: <slug>-<yyyymmdd>
created: <yyyy-mm-dd>
status: confirmed
profile_type: topic
domain:                     # optional — only if the topic implies one
task:                       # optional — only if the topic implies one
review_purpose:
review_scope:
review_questions: []
seed_papers: []
date_window_years:          # omit for the 3-year default; 0 = no limit
close_field_terms: []
generalized_methodology_terms: []   # may be empty — cross-field pass declined
keywords_of_interest: []
cross_project_linking: true/false
related_projects: []
paper_vault_path: <root>/paper_vault/<id>/
code_vault_path: <root>/code_vault/<id>/
---
```

Never write problem-only fields (`cohort_description`, `reference_standard`, `observed_failure_mode`, etc.) into a topic profile, not even as blanks. A blank field there reads downstream as "unknown" rather than "doesn't apply".

`status:` is `confirmed` for a normal completed run (the researcher signed off in step 6 before anything was written). Only write `status: draft` for the partial-save case in step 8 — `draft` means "the Q&A didn't finish," and it blocks every downstream stage.

`keywords_of_interest` is the subtopic taxonomy, always lowercase kebab-case. It is a **preferred vocabulary, not a closed one** — paper notes reuse these slugs verbatim when they cover a concept named here (that exact-string reuse is what links a paper to a topic), but they may also carry keywords beyond this list, which is by design rather than an error. It is not search input; discovery queries the two term lists only.

`paper_vault_path` and `code_vault_path` are only populated when directory creation actually succeeded (step 0/7). Leave them blank rather than guessing a path if filesystem access wasn't available — a blank field is a clear signal to the paper-search group that they need to create the folder themselves before writing into it.

Followed by a short free-text section underneath restating the problem (or, for a topic profile, the topic and why it is being reviewed) in a paragraph or two — this is for human readability in Obsidian; the frontmatter is what discovery and cross-linking consume.

`<slug>` is a short hyphenated tag from the domain/task, or from the topic for a topic profile (e.g. `sarcopenia-ct-embedding`, `ssl-pretraining-ct-review`). File naming and ID conventions beyond this are still an open decision for the team — flag this to the researcher if it comes up rather than inventing a permanent convention unilaterally.

Save the file to the outputs location available in the current environment and hand it back to the researcher. Do not attempt to write into an Obsidian vault, perform cross-linking, or hand off to discovery yourself — those are owned by other parts of the system.
