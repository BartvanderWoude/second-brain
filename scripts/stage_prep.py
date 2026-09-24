#!/usr/bin/env python3
"""Deterministic prep work for the pipeline's stages 3-5, so the main
conversation reads a compact report instead of paper headers and grep dumps.
Stdlib only.

  merge <paper_vault_path> [--dry-run]
      Stage 3. Finds papers saved twice by the parallel legs, using the key
      ladder in templates/paper-identity-spec.md (DOI, then source ids, then
      normalized title; a title match with different DOIs is a
      preprint/published pair when one side is a preprint). Keeps one file
      per paper: the one that already has a summary, else the one with full
      text, else the published version. Never renames it; adds the other
      copies' sources and missing ids to its header and moves them into
      <paper_vault_path>/.merged/, which nothing downstream reads. Then
      reports stage-4 coverage: full vs abstract-only by source, extraction
      warnings, files with no header. JSON.

  summaries <paper_vault_path> [--regenerate]
      Stage 5 step 1. Plans the paper-summarizer fan-out. A paper file over
      --solo-kb (a full text, header or not) gets its own dispatch, with
      `read_until` set to the line before its references or acknowledgements
      heading; the rest go in batches of up to --batch. Papers that already
      have a summary are skipped unless --regenerate. JSON.

  keywords <paper_vault_path> --profile P
      Stage 5 step 2a. The keyword index as one line per slug: paper count,
      two titles, whether a topic note exists and how many papers it lacks.
      Profile keywords first, then candidates on >= --min papers. Also which
      review questions (Q1, Q2, ...) no summary cites. Text.

  digest <paper_vault_path> --topic slug[:alias,alias] ...
      Stage 5 step 2d. Writes <paper_vault_path>/.digests/<slug>.md per topic:
      each matched summary's identity line, one-liners and body sections
      (everything but ## Code notes), without the rest of the frontmatter.
      One file for topic-summarizer to read instead of one Read per summary.
      JSON.
"""
import argparse, json, re, sys
from pathlib import Path

from check_vault import split
from link_papers import FM_RE, block_list, norm_doi, scalar

# The end of the main text. An appendix before it is kept; one after it goes
# with the references, and the summarizer may still read on when the main text
# defers a formulation to it.
TAIL_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:[\dIVX]+[.)]?\s+)?\**(references|bibliography|literature cited|works cited|"
    r"acknowledge?ments?)\**\s*:?\s*$", re.I)
PREPRINT_DOI = ("10.48550/", "10.1101/", "10.21203/", "10.2139/ssrn")
MERGED = ".merged"


def norm_title(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())


def unq(v):
    return v.replace('\\"', '"')


def papers(root):
    """Saved paper files -> header fields. A headerless file falls back to its
    first line as the title, per the identity spec."""
    out = {}
    for f in sorted(root.glob("*.md")):
        text = f.read_text()
        fm, body = split(text)
        g = lambda k: scalar(fm, k) if fm else ""
        title = unq(g("title")) or next((ln.strip("# ").strip() for ln in body.splitlines() if ln.strip()), "")
        out[f.stem] = {
            "file": f, "text": text, "fm": fm, "title": title, "bytes": len(text.encode()),
            "doi": norm_doi(g("doi")), "arxiv_id": re.sub(r"v\d+$", "", g("arxiv_id")),
            "pmid": g("pmid").strip("\"'"), "pmcid": g("pmcid").strip("\"'").upper(),
            "source": g("source"), "full_text": g("full_text"), "venue": g("venue"),
            "extraction_warning": g("extraction_warning"),
            "summary": (root / "summaries" / f"{f.stem}_summary.md").exists(),
        }
    return out


def preprint(p):
    return p["source"].split(",")[0].strip() == "arxiv" or p["doi"].startswith(PREPRINT_DOI) or \
        (not p["doi"] and bool(p["arxiv_id"]))


def same(a, b):
    """(matched, key) per the ladder: the first key both have decides, and
    on a mismatch names the key that kept the two apart."""
    for k in ("arxiv_id", "pmid", "pmcid"):
        if a[k] and a[k] == b[k]:
            return True, k
    if a["doi"] and b["doi"]:
        if a["doi"] == b["doi"]:
            return True, "doi"
        t = norm_title(a["title"])
        if t and t == norm_title(b["title"]) and (preprint(a) != preprint(b)):
            return True, "title (preprint/published)"
        return False, "doi"
    for k in ("arxiv_id", "pmid", "pmcid"):
        if a[k] and b[k]:
            return False, k
    t = norm_title(a["title"])
    return (bool(t) and t == norm_title(b["title"])), "title"


def set_field(fm, key, value):
    line = f"{key}: {value}\n"
    if re.search(rf"^{key}:.*$", fm, re.M):
        return re.sub(rf"^{key}:.*\n", lambda _: line, fm, count=1, flags=re.M)
    return fm + line


# ---------------------------------------------------------------- merge

def cmd_merge(a):
    root = a.path
    ps = papers(root)
    ids = sorted(ps)
    parent = {i: i for i in ids}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    keys, near = {}, []
    for n, x in enumerate(ids):
        for y in ids[n + 1:]:
            m, k = same(ps[x], ps[y])
            if m:
                parent[find(y)] = find(x)
                keys[(x, y)] = k
            elif norm_title(ps[x]["title"]) and norm_title(ps[x]["title"]) == norm_title(ps[y]["title"]):
                near.append({"files": [x, y], "reason": f"same title, different {k}"})
    groups = {}
    for i in ids:
        groups.setdefault(find(i), []).append(i)

    merged = []
    for g in (g for g in groups.values() if len(g) > 1):
        rank = lambda i: (not ps[i]["summary"], ps[i]["full_text"] != "full", preprint(ps[i]), i)
        keep, drop = sorted(g, key=rank)[0], sorted(g, key=rank)[1:]
        k = ps[keep]
        fm = k["fm"]
        added = {}
        if fm is not None:
            srcs = [s.strip() for s in k["source"].split(",") if s.strip()]
            for d in drop:
                for s in ps[d]["source"].split(","):
                    if s.strip() and s.strip() not in srcs:
                        srcs.append(s.strip())
                for f in ("doi", "arxiv_id", "pmid", "pmcid"):
                    if not k[f] and ps[d][f] and f not in added:
                        added[f] = ps[d][f]
                # an arXiv DOI is derivable from arxiv_id; the journal DOI is not
                if k["doi"].startswith("10.48550/") and ps[d]["doi"] and not ps[d]["doi"].startswith(PREPRINT_DOI):
                    added["doi"] = ps[d]["doi"]
            if srcs and ", ".join(srcs) != k["source"]:
                fm = set_field(fm, "source", ", ".join(srcs))
                added = {"source": ", ".join(srcs), **added}
            for f, v in added.items():
                if f != "source":
                    fm = set_field(fm, f, f'"{v}"' if f == "pmid" else v)
        rec = {"kept": keep, "removed": drop,
               "key": sorted({keys.get(tuple(sorted((keep, d))), "linked via another copy") for d in drop}),
               **({"added_to_header": added} if added else {})}
        orphans = [d for d in drop if ps[d]["summary"]]
        if orphans:
            rec["removed_with_summary"] = orphans
        merged.append(rec)
        if not a.dry_run:
            if fm is not None and fm != k["fm"]:
                m = FM_RE.match(k["text"])
                k["file"].write_text("---\n" + fm + "---\n" + k["text"][m.end():])
            (root / MERGED).mkdir(exist_ok=True)
            for d in drop:
                ps[d]["file"].rename(root / MERGED / ps[d]["file"].name)
        for d in drop:
            ps.pop(d)

    by_source, counts = {}, {"full": 0, "abstract-only": 0, "unset": 0}
    for p in ps.values():
        ft = p["full_text"] if p["full_text"] in counts else "unset"
        counts[ft] += 1
        src = p["source"].split(",")[0].strip() or "unknown"
        by_source.setdefault(src, {"full": 0, "abstract-only": 0, "unset": 0})[ft] += 1
    print(json.dumps({
        "papers": len(ps),
        "dry_run": a.dry_run,
        "merged": merged,
        **({"moved_to": f"{MERGED}/"} if merged and not a.dry_run else {}),
        "possible_duplicates": near,
        "full_text": counts,
        "by_source": by_source,
        "abstract_only": sorted(i for i, p in ps.items() if p["full_text"] == "abstract-only"),
        "extraction_warnings": [{"id": i, "warning": p["extraction_warning"]}
                                for i, p in sorted(ps.items()) if p["extraction_warning"]],
        "no_header": sorted(i for i, p in ps.items() if p["fm"] is None),
    }, indent=1))
    return 0


# ---------------------------------------------------------------- summaries

def read_until(text):
    """Number of lines to read: those before the first references or
    acknowledgements heading past 40% of the file, or None to read it all."""
    lines = text.splitlines(keepends=True)
    total, pos = len(text), 0
    for n, ln in enumerate(lines):
        if pos >= 0.4 * total and TAIL_RE.match(ln):
            return n
        pos += len(ln)
    return None


def cmd_summaries(a):
    ps = papers(a.path)
    todo = [i for i in sorted(ps) if a.regenerate or not ps[i]["summary"]]
    solo, small = [], []
    for i in todo:
        p = ps[i]
        if p["bytes"] > a.solo_kb * 1024:
            ru = read_until(p["text"])
            solo.append({"papers": [i], "kb": round(p["bytes"] / 1024),
                         **({"read_until": ru} if ru else {})})
        else:
            small.append(i)
    batches = [{"papers": small[n:n + a.batch]} for n in range(0, len(small), a.batch)]
    print(json.dumps({
        "to_summarize": len(todo),
        "skipped_existing": len(ps) - len(todo),
        "dispatch_count": len(solo) + len(batches),
        "dispatches": solo + batches,
    }, indent=1))
    return 0


# ---------------------------------------------------------------- keywords

def summaries(root):
    out = {}
    for f in sorted((root / "summaries").glob("*_summary.md")):
        text = f.read_text()
        fm, body = split(text)
        if fm is None:
            continue
        out[f.stem[:-len("_summary")]] = {"fm": fm, "body": body, "title": unq(scalar(fm, "title")),
                                          "keywords": block_list(fm, "keywords")}
    return out


def cmd_keywords(a):
    root = a.path
    ss = summaries(root)
    pfm, _ = split(a.profile.read_text())
    wanted = block_list(pfm or "", "keywords_of_interest")
    index = {}
    for i, s in ss.items():
        for k in s["keywords"]:
            index.setdefault(k, []).append(i)
    notes, alias_of = {}, {}
    for f in sorted((root / "topics").glob("*.md")):
        fm, _ = split(f.read_text())
        if fm is None:
            continue
        slug = scalar(fm, "keyword") or f.stem
        al = block_list(fm, "aliases") or [x.strip() for x in scalar(fm, "aliases").strip("[]").split(",") if x.strip()]
        notes[slug] = (set(block_list(fm, "papers")), al)
        for x in al:
            alias_of[x] = slug

    def line(k):
        ids = index.get(k, [])
        s = f"  {k}  {len(ids)} paper{'s' if len(ids) != 1 else ''}"
        topic = k if k in notes else alias_of.get(k)
        if topic:
            covered, al = notes[topic]
            members = set(ids)
            for x in ([topic] + al) if topic == k else []:
                members |= set(index.get(x, []))
            new = len(members - covered)
            s += f"  (note exists, +{new} new)" if topic == k else f"  (alias of existing note {topic})"
        titles = [ss[i]["title"] for i in ids[:2]]
        if titles:
            s += "  e.g. " + "; ".join(f'"{t[:70]}{"…" if len(t) > 70 else ""}"' for t in titles)
        return s

    out = [f"{len(ss)} summaries, {len(index)} distinct keywords", "",
           "Profile keywords_of_interest:"]
    out += [line(k) for k in wanted] or ["  (none)"]
    cands = sorted((k for k in index if k not in wanted and len(index[k]) >= a.min),
                   key=lambda k: (-len(index[k]), k))
    out += ["", f"Other keywords on >= {a.min} papers ({len(cands)}):"] + ([line(k) for k in cands] or ["  (none)"])
    single = sorted(k for k in index if k not in wanted and len(index[k]) < a.min)
    out += ["", f"Keywords below {a.min} papers ({len(single)}; not offered alone, but can merge into a "
                f"topic above as an alias): " + ", ".join(single)]
    zero = [k for k in wanted if not index.get(k)]
    if zero:
        out += [f"Profile keywords on 0 papers: {', '.join(zero)}"]
    rq = block_list(pfm or "", "review_questions")
    if rq:
        cited = {n: 0 for n in range(1, len(rq) + 1)}
        for s in ss.values():
            for n in {int(m) for m in re.findall(r"\bQ(\d+)\b", s["body"])}:
                if n in cited:
                    cited[n] += 1
        out += ["", "Review questions cited by summaries: " +
                ", ".join(f"Q{n} {c}" for n, c in cited.items())]
        unc = [f"Q{n}" for n, c in cited.items() if not c]
        out += [f"Uncited review questions: {', '.join(unc) if unc else 'none'}"]
    print("\n".join(out))
    return 0


# ---------------------------------------------------------------- digest

def cmd_digest(a):
    root = a.path
    ss = summaries(root)
    ps = papers(root)
    ddir = root / ".digests"
    report = []
    for spec in a.topic:
        slug, _, al = spec.partition(":")
        slugs = [slug] + [x for x in al.split(",") if x]
        ids = [i for i, s in ss.items() if any(k in s["keywords"] for k in slugs)]
        parts = [f"# Digest: {slug}" + (f" (aliases: {', '.join(slugs[1:])})" if slugs[1:] else ""),
                 "", f"{len(ids)} papers. Full text of each: <paper vault path>/<id>.md. "
                 "Full summary: <paper vault path>/summaries/<id>_summary.md.", ""]
        for i in ids:
            s, p = ss[i], ps.get(i, {})
            fm = s["fm"]
            aid = (p.get("arxiv_id") or "") or (re.search(r"arxiv\.org/abs/([^\s/]+?)(?:v\d+)?$", scalar(fm, "url")) or [None, ""])[1]
            vals = {"year": scalar(fm, "year"), "source": scalar(fm, "source") or p.get("source"),
                    "full_text": p.get("full_text") or scalar(fm, "full_text"), "arxiv_id": aid,
                    "extraction_warning": p.get("extraction_warning")}
            parts += [f"## {i} — {s['title']}", "", " | ".join(f"{k}: {v}" for k, v in vals.items() if v)]
            for k in ("data_modality", "task", "method", "result"):
                if scalar(fm, k):
                    parts.append(f"{k}: {unq(scalar(fm, k))}")
            body = s["body"]
            body = re.sub(r"^## Code notes\n.*?(?=^## |\Z)", "", body, flags=re.S | re.M)
            body = re.sub(r"^## ", "### ", body, flags=re.M).strip()
            parts += ["", body, ""]
        text = "\n".join(parts).rstrip() + "\n"
        out = ddir / f"{slug}.md"
        ddir.mkdir(exist_ok=True)
        out.write_text(text)
        report.append({"topic": slug, "papers": len(ids), "digest": f".digests/{slug}.md",
                       "kb": round(len(text.encode()) / 1024, 1)})
    print(json.dumps({"digests": report}, indent=1))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("merge")
    m.add_argument("path", type=Path)
    m.add_argument("--dry-run", action="store_true")
    s = sub.add_parser("summaries")
    s.add_argument("path", type=Path)
    s.add_argument("--regenerate", action="store_true")
    s.add_argument("--batch", type=int, default=8)
    s.add_argument("--solo-kb", type=int, default=12)
    k = sub.add_parser("keywords")
    k.add_argument("path", type=Path)
    k.add_argument("--profile", type=Path, required=True)
    k.add_argument("--min", type=int, default=2)
    d = sub.add_parser("digest")
    d.add_argument("path", type=Path)
    d.add_argument("--topic", action="append", required=True, help="slug, or slug:alias,alias")
    a = ap.parse_args()
    if not a.path.is_dir():
        print(json.dumps({"error": f"not a directory: {a.path}"}))
        return 2
    a.path = a.path.resolve()
    return {"merge": cmd_merge, "summaries": cmd_summaries, "keywords": cmd_keywords, "digest": cmd_digest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
