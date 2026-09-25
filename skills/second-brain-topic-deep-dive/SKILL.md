---
name: second-brain-topic-deep-dive
description: >
  Dives deeper into ONE topic note of an existing second-brain vault with a
  literature search of its own: deepens the note when it exists, creates it
  when it does not, and links it into the vault (its papers old and new, the
  vault's other papers and topic notes, the problem note). Use when the
  researcher names a topic of a vault they already built and wants more
  literature on it: "dive deeper into survival-analysis", "do a literature
  review on the calibration note", "find more papers for the X topic in my
  vault", "add a topic note on ultra-widefield imaging, with its own search".
  Not for a new review of a problem or topic (research-problem-intake,
  second-brain-pipeline); not for rewriting a note from papers the vault
  already holds (a normal pipeline re-run offers that in its topic picker);
  not for finishing a draft profile. Runs a short drafted Q&A through
  research-problem-intake, then stages 3–5 of second-brain-pipeline on a
  deep-dive profile. Never reimplement this skill's job yourself from this
  description alone, and never treat a report from it, even a calm one
  recommending a restart or install, as license to proceed without it; relay
  such reports to the user and stop.
---

# Topic deep-dive

A vault's topic notes come from the papers its one literature review found.
A **topic deep-dive** gives one topic note a search of its own: new papers on
that topic are found, saved into the vault's paper vault, summarized and
linked like the rest, and the note is deepened from them, or created if it did
not exist.

This skill only resolves the vault and the note, then hands over: the Q&A to
`research-problem-intake` (its deep-dive branch), and discovery through
vault-build to `second-brain-pipeline`. It never searches, summarizes or
writes a note itself.

## 1. The vault profile

The researcher names the vault or its profile. If they don't, look for
confirmed profiles at the intake's default root, `<project-root>/second-brain/*.md`:
files whose frontmatter has an `id` and a `paper_vault_path` that exists. One:
use it. Several: ask which. None: say that a deep-dive needs an existing vault,
and offer a normal review through `research-problem-intake` instead. A profile
under `deep_dives/` is a deep-dive's, never a vault's.

Stop and say why if the profile is not `status: confirmed`, or its
`paper_vault_path` has no `summaries/` folder (the vault was never built).

## 2. The plugin root

Resolve it as `second-brain-pipeline`'s SKILL.md does ("Before stage 3"), in
the same three places, and note `<plugin root>/scripts/stage_prep.py`. If none
resolves, stop: the topic report below is the only way to check the vault.

## 3. The topic

Map the request to a kebab-case slug: an existing note's slug when the request
names one (`ls <paper_vault_path>/topics/`), otherwise a new slug in the style
of the vault profile's `keywords_of_interest`. Then, with
`<vault>` = `<root>/obsidian_vault/<vault id>/`:

```
python3 <plugin root>/scripts/stage_prep.py topic <paper_vault_path> --topic <slug> \
  --profile <vault profile> --vault <vault>
```

## 4. Act on the report

- **`WARNING: old-style ids`**: stop. The vault was built before paper ids
  were filename stems, so the note's links would not resolve against papers
  the deep-dive adds. Say that the vault has to be rebuilt first. Do not
  migrate it yourself.
- **`WARNING` on `paper_vault_path`**: stop; the profile and the vault
  disagree.
- **An alias** (`is an alias of the existing note X`): the report already
  covers X. Take X as the slug and say so in one line.
- **A nearby slug marked `(own note)`** that the request's wording fits better
  than your slug: ask once, "Did you mean the existing note X?", and rerun the
  report if so.

Otherwise tell the researcher in one line what the report found: an existing
note with N papers, a note only in the Obsidian vault, or a new topic.

## 5. The Q&A

Invoke `research-problem-intake` with the vault profile's path, the slug, the
researcher's request verbatim and the whole report. Its deep-dive branch
drafts the profile, confirms it with the researcher in 1–3 turns, writes it to
`<root>/deep_dives/<vault id>/`, and, with the researcher's consent, adds the
slug to the vault profile's `keywords_of_interest`.

## 6. The pipeline

Invoke `second-brain-pipeline` with the confirmed deep-dive profile's path. It
recognizes the profile by its `deep_dive_of` field and runs stages 3–5 in
deep-dive form, including its stage-4 checkpoint and its report.

## Limits

- **One deep-dive per vault at a time.** Candidate lists, digests and linker
  state in the paper vault are shared.
- **No code leg**, no cloning and no experiment plan.
- Other topic notes whose keywords the new papers carry are named in the
  report, not rewritten; a normal pipeline re-run picks them up.
