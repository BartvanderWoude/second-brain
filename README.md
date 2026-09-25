# second-brain-researcher

A Claude Code plugin for literature reviews. You describe a research problem, or
a topic you want reviewed. It searches for papers and code, summarizes every
paper, and builds a linked [Obsidian](https://obsidian.md) vault you can browse.

It is built to find methods from neighbouring fields that a normal search would
miss, and to keep what it finds in one place for the next project.

## What it does

1. **Questions.** Claude asks about your problem or topic and writes a short
   profile of it, including the search terms. You check and confirm it.
2. **Search.** Several searches run at the same time (see
   [Where it searches](#where-it-searches)). Then it follows the citations of
   the most central papers until no new ones turn up.
3. **Checkpoint.** It stops and shows you what it found: how many papers per
   source, which have full text and which only an abstract, and which you need
   to download yourself. Nothing happens until you say go.
4. **Summaries and topics.** Every paper gets a structured summary. You pick
   which themes get a topic note: what those papers show together, where they
   disagree, and what is missing.
5. **Vault.** Everything is written into an Obsidian vault as linked notes.

Later, a **topic deep-dive** gives one topic note of an existing vault its own
literature search and deepens the note with what it finds.

Not built yet: running the code it finds, and proposing an experiment plan.

A full run uses a lot of your Claude usage: a 42-paper review used about 21
million tokens.

## Where it searches

| Source | What for |
|---|---|
| arXiv | preprints, mostly machine learning and computer science |
| PubMed, PMC, Europe PMC | biomedical and clinical papers |
| Semantic Scholar, through [Ai2 Asta](https://allenai.org/asta/resources/mcp) | the full text of papers, to find methods from other fields whose abstracts never mention yours |
| OpenAlex | the citations of the most central papers, in both directions |
| GitHub | code for the papers and the topic. It only reads the repository pages: nothing is downloaded or run. |

Full text comes from free sources first (Europe PMC, NCBI, arXiv, Semantic
Scholar, Unpaywall). For a paywalled paper it tries Sci-Hub as a last resort.
Papers it still cannot get are listed at the checkpoint.

## Install

You need [Claude Code](https://docs.claude.com/en/docs/claude-code/overview),
[uv](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.

1. In Claude Code, add the two marketplaces and install the plugin. Add both
   marketplaces before installing, or the plugin will not load.
   ```
   /plugin marketplace add blazickjp/arxiv-mcp-server
   /plugin marketplace add ofulla/second-brain-researcher
   /plugin install second-brain-researcher@second-brain-researcher
   ```
2. In a terminal, add the arXiv server with PDF support, so it can also read
   arXiv papers that have no HTML version. If it says `arxiv` already exists,
   run `claude mcp remove arxiv -s user` first.
   ```bash
   claude mcp add -s user arxiv -- uvx --from "arxiv-mcp-server[pdf]" arxiv-mcp-server
   ```
3. *Optional:* install Docling, to read papers that are only available as a
   PDF. Without it, those papers keep only their abstract. The first PDF is
   slow, because Docling downloads its models then.
   ```bash
   uv tool install docling
   ```
4. *Optional:* log in to the [GitHub CLI](https://cli.github.com/), to search
   for code. Without it, the code search is skipped.
   ```bash
   gh auth login
   ```
5. *Optional:* add API keys (below).
6. Restart Claude Code.

### API keys (all optional)

The plugin works without any of them: a source without its key is skipped or
slower. To add one, put `export NAME=value` in your `~/.bashrc` (or
`~/.zshrc`) and open a new terminal. All of them are free.

| Key | What it adds | Get it |
|---|---|---|
| `ASTA_API_KEY` | the full-text search for methods from other fields | [request form](https://share.hsforms.com/1L4hUh20oT3mu8iXJQMV77w3ioxm) |
| `SEMANTIC_SCHOLAR_API_KEY` | reliable links between papers, and more full text (the shared public quota is often full) | [request form](https://www.semanticscholar.org/product/api#api-key-form) |
| `UNPAYWALL_EMAIL` | one more source of free full text | no sign-up: just your email address |
| `OPENALEX_API_KEY` | ten times more citation searches a day; only needed for large or frequent runs | [API settings](https://openalex.org/settings/api), after making an account |
| `NCBI_API_KEY` | your own PubMed rate limit instead of the one shared by your network | [NCBI account settings](https://www.ncbi.nlm.nih.gov/account/settings/), under "API Key Management" |

## Use

Open Claude Code in the folder of your project and say what you want, for
example *"I want a literature review on self-supervised pretraining for CT"* or
*"I have a research problem: …"*. You can also start it by name:
`/second-brain-researcher:second-brain-pipeline`.

Claude then walks you through it:

1. Answer its questions and confirm the profile it writes.
2. Wait for the search, read the checkpoint summary, and say whether to go on.
3. Pick which topics get a topic note.
4. Open the vault in Obsidian. It offers to do this for you.

To dig deeper into one topic of a vault you already have, say *"dive deeper
into the survival-analysis note"*, or use
`/second-brain-researcher:second-brain-topic-deep-dive`.

It creates three folders in your project: `paper_vault/` (the papers it
found), `code_vault/` (empty for now) and `obsidian_vault/` (the vaults).

## The vault

Each problem or review gets its own vault. In Obsidian, open the folder
`obsidian_vault/<id>/` of that one problem, not `obsidian_vault/` itself.

```
obsidian_vault/<id>/
├── <id>.md     the problem or review question
├── papers/     one summary per paper
├── topics/     one note per topic: what its papers show together
└── repos/      one note per code repository
```

The notes link to each other:

- The **problem note** links to every paper, topic and repository.
- A **topic note** links to its papers, and to the other topics that share at
  least two papers with it.
- A **paper note** links to its topics, its repositories, and related papers:
  papers it cites or that cite it, and papers with a similar abstract.

You can edit any note. When the pipeline runs again, it updates only its own
sections and keeps your changes.

## Working on the plugin

Run `claude --plugin-dir .` in a clone of this repository to load the plugin
from your working copy. Install steps 1 and 2 are still needed: the plugin does
not load without the arXiv server. How it is built, its rules and how to test
it are in [CLAUDE.md](CLAUDE.md).
