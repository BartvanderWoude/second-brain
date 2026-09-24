#!/usr/bin/env python3
"""Check one problem's records, or its Obsidian vault, for the defects that
break links. Stdlib only; prints a JSON report on stdout.

  records <paper_vault_path> [--fix]
      Before vault-build. Every saved paper has its identity header and its
      header id is its filename stem; every summary's id is its paper's id;
      every wikilink in summaries/, topics/ and repos/ resolves inside the
      problem's vault layout (papers/<id>, topics/<slug>, repos/<id>,
      <problem-id>); every id in a topic's `papers`, a repo's `related_papers`
      or a summary's `related_notes` is a real paper; no file carries leaked
      tool-call markup; no stray side files. --fix strips markup trailing at the
      end of a file and deletes stray side files, and nothing else.

  vault <vault_path>
      After vault-build. Resolves every wikilink the way Obsidian does, from the
      vault root, and lists the dead ones.

Exit 0 when clean, 1 when errors (or dead links) remain, 2 on bad input.
"""
import argparse, json, re, sys
from pathlib import Path

from link_papers import FM_RE, block_list, s2_ident, scalar

LINK_RE = re.compile(r"\[\[([^\]\|#\^]*)(?:[#\^][^\]\|]*)?(?:\|[^\]]*)?\]\]")
# Obsidian renders no links inside code or display math; equations can hold `[[`.
SKIP_RE = re.compile(r"```.*?```|~~~.*?~~~|\$\$.*?\$\$|`[^`\n]*`", re.S)
MARKUP_RE = re.compile(r"^\s*</?(?:content|invoke|parameter|function_calls|antml:[\w-]+)\b[^>]*>\s*$")
SUMMARY_MARKERS = ("## Synthesis", "\nmatched_terms:", "**Why relevant**")
MIN_FULL_BYTES = 10_000


def links(text):
    return [m.group(1).strip() for m in LINK_RE.finditer(SKIP_RE.sub("", text))]


def split(text):
    """(frontmatter or None, body)"""
    m = FM_RE.match(text)
    return (m.group(1), text[m.end():]) if m else (None, text)


def trailing_markup(text):
    """(line numbers of markup lines, text with trailing markup removed or None
    when markup also occurs before the end and so is not safe to strip)"""
    lines = text.split("\n")
    hits = [i + 1 for i, ln in enumerate(lines) if MARKUP_RE.match(ln)]
    if not hits:
        return [], None
    end = len(lines)
    while end and (MARKUP_RE.match(lines[end - 1]) or not lines[end - 1].strip()):
        end -= 1
    if any(h <= end for h in hits):
        return hits, None
    return hits, "\n".join(lines[:end]) + "\n"


# ---------------------------------------------------------------- records

def check_records(root, fix):
    pid = root.name
    err = {k: [] for k in ("paper_no_header", "paper_id_mismatch", "summary_without_paper",
                           "summary_id_mismatch", "dead_links", "unknown_paper_ids",
                           "tool_markup", "stray_files")}
    warn = {k: [] for k in ("summary_missing_identifier", "full_text_suspect",
                            "extraction_warnings", "non_markdown_in_vault_root")}
    fixed = []
    counts = {"full": 0, "abstract-only": 0, "unset": 0}

    papers = {}
    for f in sorted(root.glob("*.md")):
        fm, body = split(f.read_text())
        papers[f.stem] = f
        if fm is None:
            err["paper_no_header"].append(f.name)
            counts["unset"] += 1
            continue
        if scalar(fm, "id") != f.stem:
            err["paper_id_mismatch"].append({"file": f.name, "id": scalar(fm, "id")})
        ft = scalar(fm, "full_text")
        counts[ft if ft in counts else "unset"] += 1
        if ft == "full":
            reasons = []
            if len(body.encode()) < MIN_FULL_BYTES:
                reasons.append(f"body {len(body.encode())} bytes")
            if any(mk in body for mk in SUMMARY_MARKERS):
                reasons.append("body is summary-shaped")
            if reasons:
                warn["full_text_suspect"].append({"file": f.name, "reasons": reasons})
        if scalar(fm, "extraction_warning"):
            warn["extraction_warnings"].append({"file": f.name, "warning": scalar(fm, "extraction_warning")})
    for f in sorted(root.iterdir()):
        if f.is_file() and f.suffix != ".md":
            warn["non_markdown_in_vault_root"].append(f.name)

    topics = {f.stem for f in (root / "topics").glob("*.md")}
    repos = {f.stem for f in (root / "repos").glob("*.md")}
    targets = {f"papers/{p}" for p in papers} | {f"topics/{t}" for t in topics} | \
              {f"repos/{r}" for r in repos} | {pid}

    for sub, idfields in (("summaries", ["related_notes"]), ("topics", ["papers"]),
                          ("repos", ["related_papers"])):
        d = root / sub
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            rel = f"{sub}/{f.name}"
            if f.is_dir():
                continue
            if f.suffix != ".md":
                if fix:
                    f.unlink()
                    fixed.append({"file": rel, "action": "deleted stray file"})
                else:
                    err["stray_files"].append(rel)
                continue
            text = f.read_text()
            hits, stripped = trailing_markup(text)
            if hits and fix and stripped is not None:
                f.write_text(stripped)
                text = stripped
                fixed.append({"file": rel, "action": f"stripped trailing markup (lines {hits})"})
            elif hits:
                err["tool_markup"].append({"file": rel, "lines": hits})
            fm, _ = split(text)

            if sub == "summaries":
                stem = f.stem[:-len("_summary")] if f.stem.endswith("_summary") else f.stem
                if stem not in papers:
                    err["summary_without_paper"].append(rel)
                if fm is not None and scalar(fm, "id") != stem:
                    err["summary_id_mismatch"].append({"file": rel, "id": scalar(fm, "id"), "expected": stem})
                if fm is not None and not s2_ident(fm):
                    warn["summary_missing_identifier"].append(rel)

            for field in idfields:
                for i in block_list(fm or "", field):
                    if i not in papers:
                        err["unknown_paper_ids"].append({"file": rel, "field": field, "id": i})
            for t in links(text):
                t = t[:-3] if t.endswith(".md") else t
                if t not in targets:
                    reason = "problem-id prefix" if t.startswith(pid + "/") else "no such note"
                    err["dead_links"].append({"file": rel, "link": t, "reason": reason})

    n = sum(len(v) for v in err.values())
    return {
        "mode": "records",
        "problem_id": pid,
        "papers": len(papers),
        "full_text": counts,
        "topics": len(topics),
        "repos": len(repos),
        "error_count": n,
        "errors": err,
        "warnings": warn,
        "fixed": fixed,
    }, n


# ---------------------------------------------------------------- vault

def resolve(t, src, notes, files):
    """Obsidian's rules: a path relative to the note (./, ../), else an exact
    path from the vault root, else any note whose path ends with the link."""
    if not t:
        return True  # [[#heading]] points into the note itself
    if t.startswith(("./", "../")):
        p = (src.parent / t)
        parts = []
        for seg in p.as_posix().split("/"):
            if seg == "..":
                if not parts:
                    return False
                parts.pop()
            elif seg not in ("", "."):
                parts.append(seg)
        t = "/".join(parts)
    key = t[:-3] if t.endswith(".md") else t
    if key in notes or t in files:
        return True
    return any(n == key or n.endswith("/" + key) for n in notes) or \
        any(f == t or f.endswith("/" + t) for f in files)


def check_vault(root):
    notes, files, dead, total = set(), set(), [], 0
    md = []
    for f in sorted(root.rglob("*")):
        rel = f.relative_to(root).as_posix()
        if not f.is_file() or rel.split("/")[0] in (".obsidian", ".trash"):
            continue
        files.add(rel)
        if f.suffix == ".md":
            notes.add(rel[:-3])
            md.append(f)
    for f in md:
        rel = Path(f.relative_to(root).as_posix())
        for t in links(f.read_text()):
            total += 1
            if not resolve(t, rel, notes, files):
                dead.append({"file": rel.as_posix(), "link": t})
    return {
        "mode": "vault",
        "notes": len(notes),
        "links": total,
        "dead_count": len(dead),
        "dead_links": dead,
    }, len(dead)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["records", "vault"])
    ap.add_argument("path", type=Path)
    ap.add_argument("--fix", action="store_true", help="records mode: strip trailing tool-call "
                    "markup and delete stray side files")
    a = ap.parse_args()
    root = a.path.resolve()
    if not root.is_dir():
        print(json.dumps({"error": f"not a directory: {a.path}"}))
        return 2
    report, n = check_records(root, a.fix) if a.mode == "records" else check_vault(root)
    print(json.dumps(report, indent=1))
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
