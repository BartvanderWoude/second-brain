# paper-summarizer

Summarizes a single research paper into a structured markdown summary page.
The output schema (frontmatter fields and section headings) is not
hardcoded — it's read fresh from a separate format/template file on every
invocation, so the same skill works with any format file.

## What it does

Given a paper and a format file, the skill:

1. Reads the format file's YAML frontmatter to determine which fields the
   output needs, and its body headings to determine which sections the
   output needs.
2. Fills in frontmatter fields it can determine from the paper's own
   content (title, authors, year, venue, url, etc.). If a field's
   information isn't stated in the paper, it's left blank rather than
   guessed or fabricated.
3. Writes each output section using the format file's guidance text as
   instructions (not literal content), grounded in what the paper actually
   says.
4. Sets `status: draft`, `created` to today's date, and derives an `id`
   slug when the format file's placeholder implies one.
5. Writes the result to a fixed path and reports what it did, including
   which fields were left blank for lack of upstream context (e.g. a
   linked "problem profile") and whether it overwrote an existing file.

It processes exactly one paper per invocation — it does not scan
directories or batch-process multiple papers.

## Inputs

Two explicit `.md` file paths, given in the invocation prompt:

- **paper** — the research paper to summarize (substantive prose: title,
  abstract/body, etc.)
- **format file** — the template whose frontmatter fields and section
  headings define the output schema (e.g. `paper-page-template.md`;
  placeholder-style frontmatter and instructional guidance text rather than
  real content)

Paths should ideally be labeled in the prompt (e.g. "paper:", "format:").
If unlabeled, the skill disambiguates them structurally; if it still can't
tell them apart, it stops and asks rather than guessing. If either path
doesn't exist or isn't markdown, it stops and reports the problem instead
of proceeding with a partial input.

## Output

A single markdown file at:

```
<paper's directory>/summaries/<paper basename>_summary.md
```

e.g. paper `/some/dir/foo.md` → `/some/dir/summaries/foo_summary.md`.

The filename is always derived from the paper's own basename, independent
of any `id` convention used inside the format file. If a file already
exists at that path, it is overwritten and this is called out explicitly
in the final report.
