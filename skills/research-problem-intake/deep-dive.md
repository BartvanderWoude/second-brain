# Topic deep-dive intake

The third kind of intake. `second-brain-topic-deep-dive` invokes it with four
things: the vault profile's path, the topic slug, the researcher's request in
their own words, and the report of `stage_prep.py topic` (the note, its papers
with a seed line each, what the vault has on the topic outside the note, nearby
slugs, the note's text). It writes a **deep-dive profile**, per "Deep-dive
profiles" in `templates/research-problem-profile-format-spec.md`: a topic
profile scoped to that one topic, plus four fields that tie it to the vault.

The researcher already built the vault, so most of what a normal intake asks is
known. Draft everything and ask nothing cold. The goal is one combined draft,
confirmed in 1–3 turns.

## Tier 0 — given

- **The vault profile**: its `domain` and `task`, or its `review_scope`,
  `review_purpose` and `review_questions`; its term lists; its exclusions
  (`review_scope`'s OUT part, `inclusion_exclusion_criteria`);
  `date_window_years`; the linking fields; `paper_vault_path` and
  `code_vault_path`.
- **The topic report**: what the note says now, the papers it rests on, what
  the vault has on the topic outside the note, and the nearby slugs.
- **The request**: why the researcher wants to go deeper. If it gives no reason
  ("dive deeper into X"), propose one from the note's gaps, its "Across the
  papers" section and the open ends of its relevance section.

If the report has a `WARNING` line, or the vault profile is not `confirmed`,
stop and hand back to the deep-dive skill.

## The draft

Present one draft with every item below, in this order, and ask the researcher
to confirm or edit. Take corrections as they come and re-present only what
changed.

1. **Scope** (`review_scope`, IN and OUT). Say which anchor it takes:
   - **the topic within the vault's domain** (survival analysis *for
     re-detachment outcomes*): inherit `domain` and `task`;
   - **the method across fields** (survival-analysis methods in any clinical
     field): inherit neither;
   - **both**, as separate questions: inherit `domain` and `task` for the
     in-domain question, and let the method questions reach past them.

   Default to the vault's domain, since the note serves the vault. The OUT part
   carries over the vault's exclusions.
2. **Purpose** (`review_purpose`): one line, from the request.
3. **Questions** (`review_questions`, 1–4) and the **core** (`core_questions`),
   drafted from the request and the note's gaps. The core is the question the
   note must cover completely, usually the first; offer `[]` only for a broad
   survey of a method family.
4. **Seeds** (`seed_papers`): the report's `seed:` lines for the note's
   central papers, at most 8, copied verbatim. Never a vault id and never a
   `# comment`: `find_papers.py` would read either as part of a title.
5. **Search terms**: `close_field_terms` and `recall_probes` for the core
   question, by Tier 2's rules in SKILL.md (concept blocks, both method
   families for a prediction core, truncation, single-quoted YAML). Take from
   the vault's own term lists what fits the topic.
6. **Cross-field pass**: offer `generalized_methodology_terms` as Tier 2's
   topic-profile offer does, drafted, or `[]` if declined. Lead with it when
   the anchor is the method across fields.
7. **Aliases** (`topic_aliases`): every slug the report lists as "Same name,
   spelled differently", and those under "Names sharing a word" that name the
   same topic rather than a narrower or neighbouring one. Slugs "On at least
   half of the topic's papers" are related topics, not aliases. Never a slug
   with its own note (`(own note)`): two notes would claim the same papers.
8. **Date window**: the vault's `date_window_years`. Change it only if the
   request implies it ("only recent work", "the classical models too").
9. **Expected volume**: a full targeted search usually saves 40–80 new papers
   into the vault's paper vault, each summarized and linked, before the one
   note is written. Say so, since it sets the time and cost.
10. **The keyword**: if the report says the slug is not in the vault profile's
    `keywords_of_interest`, ask to add it, so that new papers get filed under
    this topic. It is the only change to the vault profile. If declined, say
    that the summarizer will then tag new papers by its own judgement, and the
    note may collect fewer of them.

Tier 1 is not asked: the draft covers it. Tier 3 is inherited from the vault
profile.

## Write

After the researcher confirms:

1. `mkdir -p <root>/deep_dives/<vault-id>/`, where `<root>` is the directory
   holding the vault profile. This replaces steps 0 and 7 of SKILL.md: the
   vault's directories exist already, and a deep-dive creates no others.
2. Write the profile to
   `<root>/deep_dives/<vault-id>/<slug>-deep-dive-<yyyymmdd>.md`, with `-2`,
   `-3` on a same-day collision, and the same suffix on its `id`:

   ```yaml
   ---
   id: <slug>-deep-dive-<yyyymmdd>
   created: <yyyy-mm-dd>
   status: confirmed
   profile_type: topic
   deep_dive_of: <vault id>
   vault_profile: <absolute path of the vault profile>
   topic_note: <slug>
   topic_aliases: []
   domain:                     # only when anchored in the vault's domain
   task:                       # likewise
   review_purpose:
   review_scope:
   review_questions: []
   core_questions: []
   seed_papers: []
   date_window_years:          # the vault's; omit if it has none
   close_field_terms: []
   recall_probes: []
   generalized_methodology_terms: []
   keywords_of_interest:
     - <slug>
   cross_project_linking:      # the vault's
   related_projects: []        # the vault's
   paper_vault_path:           # the vault's, verbatim
   code_vault_path:            # the vault's, verbatim
   ---
   ```

   Drop the comments and any field left empty that SKILL.md's topic format
   omits. The body is one paragraph on this deep-dive alone: the topic, why the
   researcher wants depth on it, and where it sits in the vault. Do not restate
   the vault's problem.
3. If the researcher agreed to it, add the slug to the vault profile's
   `keywords_of_interest`, as one more item in the style the list already
   uses. Change nothing else in that file. Never add an alias there: an alias
   in that list would get a note of its own on the next normal run.
4. Hand the profile's path back to the deep-dive skill. Do not start
   discovery yourself.
