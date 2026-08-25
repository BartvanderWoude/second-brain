# Obsidian vault agent plan

## Goal

Provide a reusable workspace skill, `obsidian-vault`, that another skill or agent can invoke. The caller delegates vault work to a subagent. The subagent checks the Obsidian prerequisite and turns one problem profile plus a related paper collection into a local Obsidian graph.

## Version 1 contract

Input:

- One problem-profile Markdown file.
- One collection containing one or more paper records in the agreed paper-note format.
- Optional vault path; default is `obsidian-vault` in this workspace.

Output:

```text
obsidian-vault/
`-- <problem-id>/
    |-- <problem-id>.md
    `-- papers/
        `-- <paper-id>.md
```

`<problem-id>` must be a descriptive, filesystem-safe ID related to the supplied problem, for example `sarcopenia-ct-embedding-20260825`. It is also the folder name; generic names such as `problem` or `project` are not used.

The problem note links to every paper note. Every paper note links back to the problem. Obsidian therefore renders a star graph centered on the research problem.

## Execution

1. The calling agent invokes `obsidian-vault` and supplies the input artifacts.
2. The skill dispatches a subagent for the vault operation.
3. The subagent checks whether the exact winget package `Obsidian.Obsidian` is installed.
4. If missing, it reports the official install command and stops. The parent asks for approval, installs, and retries.
5. The subagent validates required structured fields without inventing missing research facts.
6. It creates or updates the problem folder, problem note, and one note per paper.
7. It creates only problem-to-paper wikilinks and reads the files back to verify them.
8. It returns prerequisite evidence and absolute paths for all created or updated files.

## Acceptance test

- Obsidian installation is confirmed independently after installation.
- A synthetic problem fixture is clearly marked as test data.
- At least one synthetic paper note is created from the agreed template.
- The problem and paper contain reciprocal wikilinks.
- All generated Markdown files can be read back.
- No paper-to-paper or cross-project edges are created.
