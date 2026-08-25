---
name: obsidian-vault
description: Build or update a local Obsidian research vault from a problem-profile Markdown file and a collection of structured paper records. Use when another skill or agent needs problem and paper notes materialized as an Obsidian graph; delegate the vault work to a subagent.
---

# Obsidian vault

Act as the calling agent. Dispatch one subagent with the input artifacts and the workspace vault path, then wait for its result. Give the subagent this file and only the relevant schema references. After a successful result, open the vault when the user already requested it; otherwise ask whether they want to see it in Obsidian.

## Inputs

- One problem-profile Markdown file following [the problem profile contract](references/problem-profile.md).
- One paper collection containing records following [the paper note contract](references/paper-note.md). The collection may contain one or more records; materialize one note per record.
- Vault path, defaulting to `<workspace>/obsidian-vault`.

## Subagent task

1. Check whether Obsidian is installed. On Windows, use the exact winget package ID `Obsidian.Obsidian` plus standard executable locations. Report the evidence.
2. If Obsidian is absent, stop and return `approval_required` with the proposed official command:
   `winget install --id Obsidian.Obsidian --exact --source winget --accept-package-agreements --accept-source-agreements`
   The calling agent obtains user approval and performs the installation, then dispatches the vault task again.
3. Validate the problem profile's required fields and each paper record's required structure. Require a descriptive, filesystem-safe problem `id` related to the supplied problem, such as `sarcopenia-ct-embedding-20260825`; report a missing or generic ID instead of inventing one.
4. Name the problem folder exactly `<problem-id>` and create it at `<vault>/<problem-id>/`. Use no generic folder names. Put the problem note at `<problem-id>.md` and paper notes under `papers/`.
5. Preserve the supplied content. Add a `## Papers` list to the problem note linking every paper as `[[papers/<paper-id>]]`.
6. In each paper note, preserve `related_problem: <problem-id>` and add a `## Links` entry linking `[[<problem-id>]]`.
7. Read the written files back. Return Obsidian evidence, absolute paths, the created or updated file list, and the verified vault path.
8. If the invocation explicitly requested opening the result, launch the installed Obsidian application with the verified vault path. Otherwise return `open_offer` so the calling agent asks the user whether to open it. Launch only after an explicit request or affirmative answer, and report any launch failure without changing the created files.

The graph for this version is a star: problem to papers only. Leave paper-to-paper similarity, cross-project edges, deduplication, lifecycle changes, and source discovery untouched.
