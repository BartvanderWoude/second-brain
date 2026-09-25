# second-brain-researcher

A Claude Code plugin that turns a research problem or review topic into a
linked Obsidian vault: `skills/` orchestrate, `agents/` do the judgment work,
`scripts/` (stdlib Python) do everything deterministic, `templates/` hold the
formats, `test-fixtures/` hold the offline tests.

## PROJECT_CONTEXT.md: search it, never read it whole

`PROJECT_CONTEXT.md` is the design log: every decision and why, with the
measured costs of past runs. At 64 KB it is meant to be searched, not read:
reading it whole adds ~16k tokens to the context, paid again on every later
turn. Never `Read` it without `offset`/`limit`, never `cat` it, and never
`@`-import it here.

- **Find:** `grep -n -i '<term>' PROJECT_CONTEXT.md | cut -c1-200`. Each
  paragraph is one line of up to ~1,500 characters, so trim the output.
  `grep -n '^## \|^- \*\*' PROJECT_CONTEXT.md | cut -c1-120` lists the
  sections and decision entries.
- **Read:** only the entry you need, by its line numbers:
  `sed -n '<from>,<to>p' PROJECT_CONTEXT.md`, or `Read` with `offset`/`limit`.
- **Write:** add a new decision as its own entry, found and placed the same
  way; do not load the file to edit it.

A large file here is fine. Shrinking it is not the fix; reading it only in
pieces is.

## Testing: small scale by default

A live pipeline run is expensive: the 42-paper run cost 20.8M weighted tokens,
and one topic deep-dive live test cost 9.8M in agents alone and hit the
session limit. Test every change at the lowest rung below that exercises it.

Testing belongs here only. Skills and agents never get a test mode, a test cap
or a mention of fixtures.

### Rules

- **Never run the full pipeline as a test**: not stages 1–5, not a whole
  deep-dive. That happens only when the user asks for a real run.
- **Never test against a real vault.** Copy what a test needs into the
  scratchpad and point the test there; never write into a `paper_vault/` or
  `obsidian_vault/` of the user's.
- **State the estimate before any step that uses a model, and the measured cost
  after it** (see "Measuring cost").
- **T0–T2 need no approval. T3 and up need the user's yes**, asked with the
  estimate.
- A failed live test is diagnosed from its output, not re-run to see if it
  happens again. Fix, cover the fix offline if a script can hold it, then
  re-run only the piece that failed.

### The ladder

**T0, static (free).** `python3 -m py_compile scripts/*.py`

**T1, offline fixtures (free).** No model, no network, the fixtures untouched:

```
bash test-fixtures/run_offline.sh              # every suite, ~2 s
bash test-fixtures/run_offline.sh stage-prep   # one suite
```

One line per suite, `PASS` or `FAIL` with the diff. Run the touched suite while
working and every suite before calling a change done.

| Script | Suite | README |
|---|---|---|
| `check_vault.py` | `check-vault` | `test-fixtures/check-vault/` |
| `fetch_fulltext.py` (offline rungs) | `fetch` | `test-fixtures/fetch/` |
| `find_papers.py` | `find-papers` | `test-fixtures/find-papers/` |
| `link_papers.py` | `linker` | `test-fixtures/linker/` |
| `stage_prep.py` merge, summaries, keywords, digest | `stage-prep` | `test-fixtures/stage-prep/` |
| `stage_prep.py topic`, `digest --since` | `stage-prep-deep-dive` | `test-fixtures/stage-prep/` (§ Topic deep-dive) |
| `build_vault.py` | `vault-build` | `test-fixtures/vault-build/` |

New script behavior gets a new fixture case (a record that exercises it, the
expected output, one line in the README's "what each tests" list), not a live
run. When behavior changes on purpose, update the expected files. A README's
command block and its suite in `run_offline.sh` change together.

**T1b, scripts against the live APIs (no model tokens).** For network code the
fixtures cannot reach, on scratch copies:
`find_papers.py pubmed … --max 20 --top 5`, `fetch_fulltext.py --record` on one
record, `link_papers.py` on the linker fixture's summaries without `--offline`
(with `--dry-run`).

**T2, one agent on one tiny input.** A single dispatch, no approval, estimate
stated first. Fixture papers are synthetic: this tests format, paths and
handoffs, not the quality of what the agent writes. When quality is the point,
use a scratch copy of 3–5 records from a real vault instead.

| Agent | Input (copied to scratch) | Check |
|---|---|---|
| `paper-summarizer` | `test-fixtures/sample-paper.md` into `<scratch>/ssl-pretraining-ct-review-20260924/`; profile `test-fixtures/sample-topic-profile.md` | `summaries/sample-paper_summary.md` against `test-fixtures/summaries/sample-paper_summary.md` (fields, sections); `check_vault.py records <dir>` |
| `topic-summarizer` | `test-fixtures/stage-prep/deep-dive/records/fixture-dd-20260925/`, then `stage_prep.py digest <dir> --topic survival-analysis:time-to-event`; profile `…/deep-dive/fixture-dd-20260925.md`. Delete `topics/survival-analysis.md` first to test create mode instead of deepen mode | `check_vault.py records <dir>`; the note's frontmatter and section headings against `templates/topic-note-template.md` |
| `second-brain-paper-downloader` (arXiv) | a copy of `test-fixtures/sample-topic-profile.md` with `paper_vault_path:` pointing at a scratch dir | saved records have the identity header (`stage_prep.py merge <dir> --dry-run`: `no_header` empty) |
| `second-brain-biomed-downloader` | a copy of `test-fixtures/find-papers/fixture-recall-20260924.md` with a `paper_vault_path:` line added, pointing at a scratch dir | as above |
| `second-brain-citation-chaser` | that profile, pointing at a scratch copy of `test-fixtures/find-papers/records/fixture-recall-20260924/` | its reply's rounds and stop reason; `merge --dry-run` |
| `second-brain-crossfield-searcher`, `second-brain-code-finder` | as for the arXiv leg | as above; code-finder: `repos/*.md` |

Give the agent the pipeline's own prompt template for that step
(`skills/second-brain-pipeline/SKILL.md`), filled in with the scratch paths.
Discovery agents get one extra line at the end of the prompt, and only there:
`TEST RUN: at most 2 queries and 3 saved papers in total; the chaser runs 1
round from at most 2 seeds and runs only the first recall probe.`

**T3, a mini pipeline (ask first).** Run the skill, but start at the stage that
changed, never at stage 1, on a scratch vault seeded from fixture records:

- stage 5: seed from the deep-dive fixture's records, whose summaries already
  exist, so `stage_prep.py summaries` plans no summarizer dispatch. Select one
  topic, then linker, checks and vault build into a scratch `obsidian_vault/`.
  Cost: about one topic-summarizer plus the conversation.
- stages 3–4: a scratch profile with narrow terms, one leg with the `TEST RUN`
  line, merge, and stop at the checkpoint.
- a deep-dive: a scratch copy of the deep-dive fixture's records and vault, one
  leg capped, one topic note.

At most 5 papers, 1 topic, 1 discovery leg.

**T4, the full pipeline.** Only on the user's request for a real run.

### Which rung for which change

| Changed | Minimum |
|---|---|
| `scripts/*.py` | T1 (+ T1b for network code) |
| `templates/*` | T1, plus the T2 of each agent that reads the template |
| `agents/<name>.md` | T2 of that agent |
| a skill's `SKILL.md` or `deep-dive.md` | T1 for the scripts it calls; T3 only if an agent handoff changed |
| `research-problem-intake` | run its Q&A inline on a test problem; it dispatches no agents |

### Dispatching a plugin agent in this repo

The plugin's agents are not registered as agent types in a dev session. Dispatch
a `general-purpose` agent with `model` set to the one its definition names
(`sonnet`; `opus` for `topic-summarizer`) and a prompt that starts
`Follow agents/<name>.md in this repo as your instructions, using only the tools
it lists.`, then the filled-in template. One dispatch at a time, in the
foreground. In the main conversation read only compact output: the agent's
`OK`/`FAIL` reply, script reports, `grep` of frontmatter, `head`. Never whole
papers, summaries or notes; the conversation is paid for again on every turn.

### Measuring cost

```
P=~/.claude/projects/-home-bartvdw-Documents-Fun-SecondBrain-second-brain
python3 scripts/token_report.py "$(ls -t $P/*.jsonl | head -1)"
```

It sums the whole session by agent type, so for one test run it before and
after and report the difference.

Measured per agent on the deep-dive live test (session `7d220f0b…`,
2026-09-25, no caps), weighted tokens. That session also held development
work, so its main-conversation cost says nothing about orchestration and is
left out; measure that on a real full run.

| Dispatch | Cost |
|---|---|
| `paper-summarizer`, per dispatch (~1.7 papers) | ~120k (~70k per paper) |
| `topic-summarizer`, deepening a 62-paper note | ~1.6M |
| biomedical leg | ~1.0M |
| arXiv leg | ~430k |
| citation chaser, 4 rounds | ~1.4M |
| cross-field leg, stopped at its key check | ~45k |

Estimates for T2, until measured: `paper-summarizer` on the sample paper
50–100k; `topic-summarizer` on a 4-paper digest 200–500k; a capped leg or a
1-round chaser 150–600k. Replace an estimate with the measured figure after the
first such run.
