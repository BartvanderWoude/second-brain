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
      how many untagged summaries name the slug in their text, two titles,
      whether a topic note exists and how many papers it lacks. Profile
      keywords first, then candidates on >= --min papers. Also which review
      questions (Q1, Q2, ...) no summary cites. Text.

  digest <paper_vault_path> --topic slug[:alias,alias] ...
      Stage 5 step 2d. Writes <paper_vault_path>/.digests/<slug>.md per topic:
      each matched summary's identity line, one-liners and body sections
      (everything but ## Code notes), without the rest of the frontmatter.
      Then the summaries that name the slug or an alias without carrying it,
      one sentence each, for topic-summarizer to take or leave. One file to
      read instead of one Read per summary. With --since ID, also the papers
      that topic deep-dive ID saved which carry neither the slug nor an alias
      and do not name it, one line each. JSON.

  topic <paper_vault_path> --topic slug[:alias,...] --profile P [--vault V]
        [--snapshot ID | --since ID]
      A topic deep-dive. Resolves the slug against the vault's topic notes (an
      existing note, an alias of one, a note only in the Obsidian vault V, or a
      new topic) and reports what the draft needs: the note's papers with a
      ready seed line each, papers carrying the slug outside the note, untagged
      mentions, nearby slugs, the review questions its summaries cite, and the
      note's text. Warns when the vault uses old-style ids. --snapshot writes
      <paper_vault_path>/.deep-dive/<ID>.json (the records and summaries
      there now), keeping an existing one; --since reports against it: new
      records, which are summarized, which carry or name the slug, which other
      topic notes they carry. No dates in the output. Text; exit 2 on a bad
      path, an unknown snapshot, or both flags.
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


def phrase_re(slugs):
    """A slug as prose: its words in order, hyphen or space between, a plural
    s allowed, case ignored."""
    alts = [r"[-\s]+".join(map(re.escape, x.split("-"))) + "(?:e?s)?" for x in slugs]
    return re.compile(r"\b(?:" + "|".join(alts) + r")\b", re.I)


def prose(s):
    fm = s["fm"]
    lines = [s["title"]] + [unq(scalar(fm, k)) for k in ("task", "method", "result") if scalar(fm, k)]
    body = re.sub(r"^## Code notes\n.*?(?=^## |\Z)", "", s["body"], flags=re.S | re.M)
    return "\n".join(lines) + "\n" + body


def sentence(text, m, width=240):
    """The sentence around match m, cut to about width characters on word
    boundaries, keeping the match in view."""
    dot = text.rfind(". ", 0, m.start())
    a = max(dot + 2 if dot >= 0 else 0, text.rfind("\n", 0, m.start()) + 1)
    ends = [x for x in (text.find(". ", m.end()), text.find("\n", m.end())) if x >= 0]
    out = " ".join(text[a:(min(ends) + 1 if ends else len(text))].split())
    if len(out) <= width:
        return out
    at = out.lower().find(" ".join(m.group(0).split()).lower())
    lo = max(0, min(at - width // 3, len(out) - width))
    words = out[lo:lo + width].split(" ")
    return ("… " if lo else "") + " ".join(words[1 if lo else 0:-1]) + " …"


def mentions(ss, slugs):
    """id -> the first sentence naming the slug or an alias, for each summary
    that carries none of them. Tags drift across summarizer batches: a paper
    that says "events per variable" throughout can be filed under another
    slug, and a keyword index built from tags alone never sees it."""
    rx, out = phrase_re(slugs), {}
    for i, s in ss.items():
        if any(k in s["keywords"] for k in slugs):
            continue
        text = prose(s)
        m = rx.search(text)
        if m:
            out[i] = sentence(text, m)
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
        notes[slug] = (set(block_list(fm, "papers")), al, bool(scalar(fm, "deep_dive")))
        for x in al:
            alias_of[x] = slug

    def line(k):
        ids = index.get(k, [])
        s = f"  {k}  {len(ids)} paper{'s' if len(ids) != 1 else ''}"
        topic = k if k in notes else alias_of.get(k)
        untagged = len(mentions(ss, [k] + (notes[k][1] if k in notes else [])))
        if untagged:
            s += f", +{untagged} mention it untagged"
        if topic:
            covered, al, dd = notes[topic]
            members = set(ids)
            for x in ([topic] + al) if topic == k else []:
                members |= set(index.get(x, []))
            new = len(members - covered)
            s += (f"  (note exists, +{new} new{', deep-dive' if dd else ''})" if topic == k
                  else f"  (alias of existing note {topic})")
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
    before = None
    if a.since:
        snap = load_snapshot(root, a.since)
        if snap is None:
            print(json.dumps({"error": f"no snapshot {a.since!r} in {DEEP_DIVE}/"}))
            return 2
        before = set(snap["records"])
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
        cands = mentions(ss, slugs)
        if cands:
            parts += ["## Mentioned but not tagged", "",
                      f"{len(cands)} more summar{'ies name' if len(cands) != 1 else 'y names'} this topic without "
                      "carrying the slug. Add one to the note's `papers` only if it covers the topic, not if it "
                      "mentions it in passing.", ""]
            parts += [f"- {i} — {ss[i]['title']}: \"{snip}\"" for i, snip in cands.items()] + [""]
        found = [i for i in ss if before is not None and i not in before and i not in ids and i not in cands]
        if found:
            parts += ["## Found by this deep-dive, not tagged", "",
                      f"Papers this deep-dive's search saved that carry neither the slug nor an alias and do "
                      f"not name it: {len(found)}. The search found them for this topic, so judge each against "
                      "the note's scope: add one to `papers` only if it covers the topic.", ""]
            for i in found:
                fm = ss[i]["fm"]
                bits = [f"{k}: {unq(scalar(fm, k))}" for k in ("task", "method") if scalar(fm, k)]
                parts.append(f"- {i} — {ss[i]['title']}" + (f": {'; '.join(bits)}" if bits else ""))
            parts.append("")
        text = "\n".join(parts).rstrip() + "\n"
        out = ddir / f"{slug}.md"
        ddir.mkdir(exist_ok=True)
        out.write_text(text)
        report.append({"topic": slug, "papers": len(ids), "mentioned_untagged": len(cands),
                       **({"found_untagged": len(found)} if before is not None else {}),
                       "digest": f".digests/{slug}.md", "kb": round(len(text.encode()) / 1024, 1),
                       "lines": text.count("\n")})
    print(json.dumps({"digests": report}, indent=1))
    return 0


# ---------------------------------------------------------------- topic

DEEP_DIVE = ".deep-dive"
CONTENT = ["Summary", "Across the papers", "Core technical details", "Relevance to the problem"]
OWNED = {"Papers", "Related topics"}
# words too generic to make two slugs neighbours on their own
STOP = {"model", "models", "modeling", "modelling", "learning", "analysis", "prediction", "predictive",
        "based", "data", "method", "methods", "deep", "clinical", "approach", "study", "studies",
        "network", "networks", "machine", "risk", "using", "imaging", "image", "images", "outcome",
        "outcomes", "factor", "factors", "assessment", "evaluation", "review"}


def name_words(slug):
    """A slug's words of 4+ letters off the stoplist, plus each pair of
    neighbours joined, so `wide-field` meets `widefield`."""
    ws = slug.split("-")
    return {w for w in ws + [a + b for a, b in zip(ws, ws[1:])] if len(w) >= 4 and w not in STOP}


def body_sections(body):
    """{name: text} of a note's `##` sections, text without its heading."""
    out, name = {}, None
    for ln in body.splitlines(keepends=True):
        if ln.startswith("## "):
            name = ln[3:].strip()
            out[name] = ""
        elif name is not None:
            out[name] += ln
    return {k: v.strip() for k, v in out.items()}


def topic_notes(root):
    """slug -> note record, from <paper_vault_path>/topics/."""
    notes = {}
    for f in sorted((root / "topics").glob("*.md")):
        fm, body = split(f.read_text())
        if fm is None:
            continue
        slug = scalar(fm, "keyword") or f.stem
        al = block_list(fm, "aliases") or [x.strip().strip("\"'") for x in scalar(fm, "aliases").strip("[]").split(",")
                                           if x.strip()]
        notes[slug] = {"file": f, "papers": block_list(fm, "papers"), "aliases": al,
                       "deep_dive": scalar(fm, "deep_dive"), "sections": body_sections(body)}
    return notes


def snapshot_path(root, sid):
    if not re.fullmatch(r"[a-z0-9][\w.-]*", sid):
        raise ValueError(f"bad deep-dive id: {sid}")
    return root / DEEP_DIVE / f"{sid}.json"


def load_snapshot(root, sid):
    f = snapshot_path(root, sid)
    return json.loads(f.read_text()) if f.is_file() else None


def seed_line(title, doi):
    t = title.replace('"', '\\"')
    return f'"{t} — {doi}"' if doi else f'"{t}"'


def qcites(ss, ids, n):
    cited = {q: 0 for q in range(1, n + 1)}
    for i in ids:
        for q in {int(m) for m in re.findall(r"\bQ(\d+)\b", ss[i]["body"])}:
            if q in cited:
                cited[q] += 1
    return ", ".join(f"Q{q} {c}" for q, c in cited.items())


def cmd_topic(a):
    root = a.path
    if a.snapshot and a.since:
        print("error: pass --snapshot or --since, not both")
        return 2
    if not a.profile.is_file():
        print(f"error: profile not found: {a.profile}")
        return 2
    if a.vault and not a.vault.is_dir():
        print(f"error: Obsidian vault not a directory: {a.vault}")
        return 2
    pfm, _ = split(a.profile.read_text())
    pfm = pfm or ""
    ps, ss, notes = papers(root), summaries(root), topic_notes(root)
    slug, _, al = a.topic.partition(":")
    given = [x for x in al.split(",") if x]
    out = []

    # resolution
    alias_of = {x: t for t, n in notes.items() for x in n["aliases"]}
    if slug not in notes and slug in alias_of:
        out.append(f"Resolution: `{slug}` is an alias of the existing note `{alias_of[slug]}`; "
                   f"reported for `{alias_of[slug]}`.")
        given = [x for x in [slug] + given if x != alias_of[slug]]
        slug = alias_of[slug]
    note = notes.get(slug)
    aliases = list(dict.fromkeys((note["aliases"] if note else []) + given))
    slugs = [slug] + aliases
    tagged = [i for i, s in ss.items() if any(k in s["keywords"] for k in slugs)]
    obs = a.vault / "topics" / f"{slug}.md" if a.vault else None
    if note:
        kind = "existing note"
        out.append(f"Resolution: existing note topics/{slug}.md, {len(note['papers'])} "
                   f"paper{'s' if len(note['papers']) != 1 else ''}.")
    elif obs and obs.is_file():
        kind = "obsidian-only"
        out.append(f"Resolution: note only in the Obsidian vault: topics/{slug}.md has no record in the paper "
                   f"vault (written by hand). The deep-dive creates the record from it; pass the Obsidian copy "
                   f"as the existing note. {len(tagged) or 'No'} paper{'s' if len(tagged) != 1 else ''} "
                   f"carr{'ies' if len(tagged) == 1 else 'y'} the slug.")
    else:
        kind = "new"
        n = len(tagged)
        out.append(f"Resolution: new topic; {n or 'no'} paper{'s' if n != 1 else ''} carr{'ies' if n == 1 else 'y'} "
                   f"the slug{' or an alias' if aliases else ''}{'' if n else ' yet'}.")

    # old-style ids: a deep-dive links by id, so it cannot run on them
    bad_sum = [i for i, s in ss.items() if scalar(s["fm"], "id") != i]
    bad_note = [x for x in (note["papers"] if note else []) if x not in ps]
    if bad_sum or bad_note:
        bits = []
        if bad_sum:
            bits.append(f"{len(bad_sum)} of {len(ss)} summaries have an id that is not their file's name")
        if bad_note:
            bits.append(f"the note lists {len(bad_note)} id{'s' if len(bad_note) != 1 else ''} that "
                        f"{'are' if len(bad_note) != 1 else 'is'} not a saved paper ({', '.join(bad_note[:3])}"
                        f"{', …' if len(bad_note) > 3 else ''})")
        out.append("WARNING: old-style ids: " + "; ".join(bits) + ". A deep-dive needs a vault whose paper ids "
                   "are filename stems (templates/paper-identity-spec.md). Stop.")
    pv = scalar(pfm, "paper_vault_path")
    if pv and Path(pv).expanduser().resolve() != root:
        out.append(f"WARNING: the profile's paper_vault_path is {pv}, not this directory. Stop.")

    if a.since:
        snap = load_snapshot(root, a.since)
        if snap is None:
            print(f"error: no snapshot {a.since!r} in {root / DEEP_DIVE}/")
            return 2
        return since(a, root, ps, ss, notes, slug, slugs, snap, out, pfm)

    wanted = block_list(pfm, "keywords_of_interest")
    ft = [p["full_text"] for p in ps.values()]
    out += ["", f"Vault: {len(ps)} papers ({ft.count('full')} full text, {ft.count('abstract-only')} abstract-only), "
                f"{len(ss)} summaries, {len(notes)} topic notes.",
            f"Vault profile: {scalar(pfm, 'id')}, status {scalar(pfm, 'status') or 'unset'}, "
            f"{len(block_list(pfm, 'review_questions'))} review questions.",
            f"In the vault profile's keywords_of_interest: {'yes' if slug in wanted else 'no'}."]
    if note:
        out.append(f"Note aliases: {', '.join(note['aliases']) or 'none'}. deep_dive: {note['deep_dive'] or 'none'}.")
        more = [x for x in given if x not in note["aliases"]]
        if more:
            out.append(f"Aliases given here, not on the note: {', '.join(more)}.")

    def pline(i):
        p, s = ps.get(i, {}), ss.get(i)
        title = (s["title"] if s else "") or p.get("title", "")
        year = (scalar(s["fm"], "year") if s else "") or (i[:4] if i[:4].isdigit() else "----")
        return [f"  {i} {year} {title}", f"    seed: {seed_line(title, p.get('doi', ''))}"]

    members = list(note["papers"]) if note else []
    extra = [i for i in tagged if i not in members]
    if note:
        out += ["", f"Note papers ({len(members)}):"] + [x for i in members if i in ps for x in pline(i)]
        out += ["", f"Carry the slug{' or an alias' if aliases else ''}, not in the note ({len(extra)}):"]
        out += [x for i in extra for x in pline(i)] or ["  none"]
    else:
        out += ["", f"Carry the slug{' or an alias' if aliases else ''} ({len(extra)}):"]
        out += [x for i in extra for x in pline(i)] or ["  none"]
    cands = mentions(ss, slugs)
    cands = {i: t for i, t in cands.items() if i not in members}
    out += ["", f"Name it without carrying it ({len(cands)}):"]
    out += [f"  - {i} — {ss[i]['title']}: \"{t}\"" for i, t in cands.items()] or ["  none"]

    # nearby slugs, in three kinds: the same name spelled differently (an
    # alias for certain), a name sharing a real word (maybe an alias), and a
    # slug on the same papers (context, not an alias)
    topic_ids = set(members) | set(extra)
    index = {}
    for i, s in ss.items():
        for k in s["keywords"]:
            index.setdefault(k, set()).add(i)
    for t, n in notes.items():
        index.setdefault(t, set()).update(n["papers"])
    squash = lambda k: re.sub(r"s$", "", k.replace("-", ""))
    same = {squash(x) for x in slugs}
    words = {w for x in slugs for w in name_words(x)}
    kinds = {"same": [], "word": [], "papers": []}
    for k, ids in index.items():
        if k in slugs:
            continue
        shared = len(ids & topic_ids)
        row = (-shared, -len(ids), k, shared, len(ids))
        if squash(k) in same:
            kinds["same"].append(row)
        elif words & name_words(k):
            kinds["word"].append(row)
        elif shared >= 2 and shared * 2 >= len(topic_ids):
            kinds["papers"].append(row)

    def show(rows):
        for _, _, k, shared, n in sorted(rows)[:8]:
            own = " (own note)" if k in notes else (f" (alias of note {alias_of[k]})" if k in alias_of else "")
            out.append(f"  {k}  {n} paper{'s' if n != 1 else ''}, {shared} shared{own}")
        if not rows:
            out.append("  none")
    for key, head in (("same", "Same name, spelled differently"), ("word", "Names sharing a word"),
                      ("papers", "On at least half of the topic's papers")):
        rows = kinds[key]
        out += ["", f"{head} ({len(rows)}{', 8 shown' if len(rows) > 8 else ''}):"]
        show(rows)
    rq = block_list(pfm, "review_questions")
    if rq and topic_ids:
        out += ["", f"Review questions the topic's summaries cite: {qcites(ss, [i for i in topic_ids if i in ss], len(rq))}"]

    # the note as it stands, for drafting
    if note:
        text = "\n\n".join(f"## {k}\n{v}" for k, v in note["sections"].items() if k in CONTENT)
        cut = text[:2000] + (" …" if len(text) > 2000 else "")
        out += ["", f"Note sections: {', '.join(note['sections']) or 'none'}."]
        if obs and obs.is_file():
            _, ob = split(obs.read_text())
            osec = body_sections(ob)
            edited = [k for k in CONTENT if k in note["sections"] and osec.get(k) != note["sections"][k]]
            own = [k for k in osec if k not in note["sections"] and k not in OWNED]
            out.append(f"Obsidian copy: edited by hand, and replaced on a rebuild: {', '.join(edited) or 'none'}; "
                       f"the researcher's own sections, kept: {', '.join(own) or 'none'}.")
        elif a.vault:
            out.append("Obsidian copy: not built yet.")
        out += ["", f"Note text ({len(text)} characters{', cut to 2000' if len(text) > 2000 else ''}):", cut]
    elif kind == "obsidian-only":
        _, ob = split(obs.read_text())
        text = "\n\n".join(f"## {k}\n{v}" for k, v in body_sections(ob).items() if k not in OWNED)
        out += ["", f"Obsidian note text ({len(text)} characters{', cut to 2000' if len(text) > 2000 else ''}):",
                text[:2000] + (" …" if len(text) > 2000 else "")]

    if a.snapshot:
        f = snapshot_path(root, a.snapshot)
        if f.is_file():
            n = len(json.loads(f.read_text())["records"])
            out += ["", f"Snapshot: kept the existing {DEEP_DIVE}/{f.name} ({n} records)."]
        else:
            f.parent.mkdir(exist_ok=True)
            f.write_text(json.dumps({"id": a.snapshot, "topic": slug, "aliases": aliases,
                                     "note_papers": members, "records": sorted(ps),
                                     "summaries": sorted(ss)}, indent=1) + "\n")
            out += ["", f"Snapshot: wrote {DEEP_DIVE}/{f.name} ({len(ps)} records)."]
    print("\n".join(out))
    return 0


def since(a, root, ps, ss, notes, slug, slugs, snap, out, pfm):
    then, now = set(snap["records"]), set(ps)
    new, gone = sorted(now - then), sorted(then - now)
    ft = [ps[i]["full_text"] for i in new]
    note = notes.get(slug)
    out += ["", f"Since deep-dive {snap['id']}:",
            f"Note papers: {len(snap['note_papers'])} at the snapshot, {len(note['papers']) if note else 0} now.",
            f"Records: {len(then)} at the snapshot, {len(now)} now: {len(new)} new ({ft.count('full')} full text, "
            f"{ft.count('abstract-only')} abstract-only), {len(gone)} gone{' (' + ', '.join(gone) + ')' if gone else ''}."]
    warn = [f"{i} ({ps[i]['extraction_warning']})" for i in new if ps[i]["extraction_warning"]]
    out.append(f"Extraction warnings on new records: {', '.join(warn) or 'none'}.")
    done = [i for i in new if i in ss]
    todo = [i for i in new if i not in ss]
    out.append(f"New records summarized: {len(done)} of {len(new)}" +
               (f"; not yet: {', '.join(todo)}." if 0 < len(todo) <= 10 else "."))
    older = sorted(i for i in now & then if i not in ss)
    out.append(f"Older records without a summary: {', '.join(older) or 'none'}.")
    if done:
        carry = [i for i in done if any(k in ss[i]["keywords"] for k in slugs)]
        named = mentions({i: ss[i] for i in done}, slugs)
        neither = [i for i in done if i not in carry and i not in named]
        out += ["", f"New summaries carrying the slug{' or an alias' if slugs[1:] else ''} ({len(carry)}):"]
        out += [f"  {i} {ss[i]['title']}" for i in carry] or ["  none"]
        out += [f"New summaries naming it untagged ({len(named)}):"]
        out += [f"  - {i} — {ss[i]['title']}: \"{t}\"" for i, t in named.items()] or ["  none"]
        out += [f"New summaries doing neither ({len(neither)}): {', '.join(neither) or 'none'}."]
        other = []
        for t, n in sorted(notes.items()):
            if t == slug:
                continue
            hit = [i for i in done if any(k in ss[i]["keywords"] for k in [t] + n["aliases"])]
            if hit:
                out_of = len([i for i in hit if i not in n["papers"]])
                other.append(f"{t} {len(hit)} ({out_of} not in its note)")
        out.append(f"Other topic notes the new summaries carry: {', '.join(other) or 'none'}.")
        rq = block_list(pfm, "review_questions")
        if rq:
            out.append(f"Review questions the new summaries cite: {qcites(ss, done, len(rq))}.")
    print("\n".join(out))
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
    d.add_argument("--since", help="a topic deep-dive's id: list what its search saved untagged")
    t = sub.add_parser("topic")
    t.add_argument("path", type=Path)
    t.add_argument("--topic", required=True, help="slug, or slug:alias,alias")
    t.add_argument("--profile", type=Path, required=True, help="the vault's profile")
    t.add_argument("--vault", type=Path, help="<root>/obsidian_vault/<vault id>/")
    t.add_argument("--snapshot", help="a deep-dive id: record the vault as it is now")
    t.add_argument("--since", help="a deep-dive id: report against its snapshot")
    a = ap.parse_args()
    if not a.path.is_dir():
        print(json.dumps({"error": f"not a directory: {a.path}"}))
        return 2
    a.path = a.path.resolve()
    try:
        return {"merge": cmd_merge, "summaries": cmd_summaries, "keywords": cmd_keywords, "digest": cmd_digest,
                "topic": cmd_topic}[a.cmd](a)
    except ValueError as e:
        print(f"error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
