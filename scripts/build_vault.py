#!/usr/bin/env python3
"""Materialize one problem's records into its Obsidian vault. Stdlib only;
prints a JSON report on stdout.

  build_vault.py --profile P --records <paper_vault_path> \\
                 --vault <root>/obsidian_vault/<problem-id>/ \\
                 [--rebuilt-topics a,b] [--offline] [--dry-run]

Writes the problem note, one note per paper record (summaries/*.md), per topic
record (topics/*.md) and per repo record (repos/*.md), and the wikilinks
between them, all as paths from the vault root: [[papers/<id>|Title]],
[[topics/<slug>]], [[repos/<owner>-<name>]], [[<problem-id>]].

On a re-run it merges, never overwrites. A note is split into frontmatter,
preamble and `##` sections; only the sections this script owns are replaced,
and every other section stays verbatim in its position:

  problem note  ## Papers, ## Topics, ## Repos
  paper note    ## Links, ## Citation, ## Related, and the repo link lines
                in ## Code notes (its prose is left alone)
  topic note    ## Papers; for a --rebuilt-topics slug also ## Summary,
                ## Across the papers, ## Core technical details and
                ## Relevance to the problem
  repo note     ## Papers

In frontmatter the vault's value wins for every key except `related_notes`
and `related_basis` on a paper (the linker's output) and, on a rebuilt topic,
`paper_count`, `papers` and `aliases`. A key only the record has is added.

BibTeX comes from arXiv's own metadata: one batched query-API request, with
OAI-PMH per id as the fallback, cached in <paper_vault_path>/.vault/arxiv_meta.json.
An entry is never built from any other field. --offline uses the cache only.

Exit 0 on success, 2 on bad input (with {"error": ...}).
"""
import argparse, json, re, sys, time, unicodedata, urllib.error, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from check_vault import split
from link_papers import block, block_list, scalar

ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_OAI = "https://oaipmh.arxiv.org/oai"
OAI = {"o": "http://arxiv.org/OAI/arXiv/"}
ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
ARXIV_ID_RE = re.compile(r"^(\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})$")
KEY_RE = re.compile(r"^([A-Za-z_][\w-]*):")
REPO_LINE_RE = re.compile(r"^\s*- \[\[repos/[^\]]*\]\]\s*$")
FENCE_RE = re.compile(r"^(```|~~~)")

REQUIRED = {
    "all": ["id", "created", "status", "close_field_terms", "keywords_of_interest",
            "cross_project_linking"],
    "problem": ["domain", "data_modality", "cohort_description", "task", "reference_standard",
                "current_approach", "observed_failure_mode", "generalized_methodology_terms"],
    "topic": ["review_scope", "review_purpose", "review_questions"],
}
TOPIC_CONTENT = ["Summary", "Across the papers", "Core technical details", "Relevance to the problem"]
ORDER = {
    "problem": ["Papers", "Topics", "Repos"],
    "paper": ["Code notes", "Links", "Citation", "Related"],
    "topic": TOPIC_CONTENT + ["Papers"],
    "repo": ["Papers"],
}


# ---------------------------------------------------------------- frontmatter

def unquote(fm, key):
    v = scalar(fm, key)
    raw = re.search(rf"^{key}:[ \t]*(.*)$", fm, re.M)
    if raw and raw.group(1).strip().startswith('"'):
        v = v.replace('\\"', '"').replace("\\\\", "\\")
    return v


def listval(fm, key):
    """A list field in block style or inline `[a, b]` style."""
    v = scalar(fm, key)
    if v.startswith("["):
        return [x.strip().strip("\"'") for x in v.strip("[]").split(",") if x.strip()]
    return block_list(fm, key)


def entries(fm):
    """[[key or None, text]]: each top-level key with its indented lines."""
    out = []
    for ln in fm.splitlines(keepends=True):
        m = KEY_RE.match(ln)
        if m or not out:
            out.append([m.group(1) if m else None, ln])
        else:
            out[-1][1] += ln
    return out


def merge_fm(vault_fm, record_fm, owned):
    rec = {k: t for k, t in entries(record_fm) if k}
    ents = entries(vault_fm)
    have = {k for k, _ in ents if k}
    for e in ents:
        if e[0] in owned and e[0] in rec:
            e[1] = rec[e[0]]
    add = [t for k, t in entries(record_fm) if k and k not in have]
    return "".join(t for _, t in ents) + "".join(add)


# ---------------------------------------------------------------- sections

def sections(body):
    """(preamble, [[name, text]]) split at `## ` headings outside code fences."""
    pre, secs, fence = "", [], False
    for ln in body.splitlines(keepends=True):
        if FENCE_RE.match(ln):
            fence = not fence
        if not fence and ln.startswith("## "):
            secs.append([ln[3:].strip(), ln])
        elif secs:
            secs[-1][1] += ln
        else:
            pre += ln
    return pre, secs


def render(name, content):
    return f"## {name}\n\n{content.strip(chr(10))}\n\n"


def upsert(secs, name, text, order):
    """Replace section `name`, or insert it next to its owned neighbours."""
    for s in secs:
        if s[0] == name:
            s[1] = text
            return
    i = order.index(name)
    names = [s[0] for s in secs]
    for prev in reversed(order[:i]):
        if prev in names:
            secs.insert(names.index(prev) + 1, [name, text])
            return
    for nxt in order[i + 1:]:
        if nxt in names:
            secs.insert(names.index(nxt), [name, text])
            return
    secs.append([name, text])


def assemble(fm, pre, secs):
    parts = [pre] + [s[1] for s in secs]
    out = ""
    for p in parts:
        if out and p and not out.endswith("\n\n"):
            out += "\n" if out.endswith("\n") else "\n\n"
        out += p
    out = out.strip("\n")
    head = f"---\n{fm}---\n\n" if fm is not None else ""
    return head + out + "\n"


# ---------------------------------------------------------------- citations

def ascii_token(value):
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", folded.lower())


def bib_escape(text):
    out = text.replace("\\", "\x00")
    for ch, rep in [("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"), ("_", r"\_"),
                    ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"),
                    ("^", r"\textasciicircum{}")]:
        out = out.replace(ch, rep)
    return out.replace("\x00", r"\textbackslash{}")


def bibtex(entries_by_id):
    """{arxiv id: entry text}, in the format of arxiv-mcp-server's
    export_citations: key = first-author surname + year + first title word,
    made unique with a, b, … in arXiv-id order."""
    out, used = {}, set()
    for aid in sorted(entries_by_id):
        p = entries_by_id[aid]
        year = p["published"][:4] if p["published"][:4].isdigit() else ""
        surname = ascii_token(p["authors"][0].split()[-1]) if p["authors"] and p["authors"][0].split() else ""
        word = next((t for t in (ascii_token(w) for w in p["title"].split()) if t), "")
        base = f"{surname}{year}{word}" or "arxiv"
        key, n = base, 0
        while key in used:
            n += 1
            suf, k = "", n
            while k:
                k, r = divmod(k - 1, 26)
                suf = chr(97 + r) + suf
            key = base + suf
        used.add(key)
        fields = []
        if p["title"]:
            fields.append(("title", bib_escape(p["title"])))
        if p["authors"]:
            fields.append(("author", " and ".join(bib_escape(a) for a in p["authors"])))
        if year:
            fields.append(("year", year))
        fields += [("eprint", aid), ("archivePrefix", "arXiv")]
        if p["categories"]:
            fields.append(("primaryClass", p["categories"][0]))
        fields.append(("url", f"https://arxiv.org/abs/{aid}"))
        body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields)
        out[aid] = f"@misc{{{key},\n{body}\n}}"
    return out


def parse_atom(xml_text):
    got = {}
    for e in ET.fromstring(xml_text).findall("a:entry", ATOM):
        idt = e.findtext("a:id", "", ATOM)
        if "/abs/" not in idt:
            continue
        aid = re.sub(r"v\d+$", "", idt.split("/abs/")[-1])
        cats = [c.get("term") for c in e.findall("arxiv:primary_category", ATOM) if c.get("term")]
        cats += [c.get("term") for c in e.findall("a:category", ATOM) if c.get("term") not in cats]
        got[aid] = {
            "title": " ".join((e.findtext("a:title", "", ATOM)).split()),
            "authors": [" ".join(n.split()) for n in
                        (a.findtext("a:name", "", ATOM) for a in e.findall("a:author", ATOM)) if n],
            "published": e.findtext("a:published", "", ATOM),
            "categories": cats,
        }
    return got


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "second-brain-researcher/build_vault"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode()


def parse_oai(xml_text):
    e = ET.fromstring(xml_text).find(".//o:arXiv", OAI)
    if e is None:
        return None
    names = []
    for a in e.findall("o:authors/o:author", OAI):
        parts = [a.findtext(f"o:{k}", "", OAI).strip() for k in ("forenames", "keyname", "suffix")]
        names.append(" ".join(p for p in parts if p))
    return {"title": " ".join(e.findtext("o:title", "", OAI).split()),
            "authors": names,
            "published": e.findtext("o:created", "", OAI),
            "categories": e.findtext("o:categories", "", OAI).split()}


def fetch_arxiv(ids, cache):
    """Fill `cache` for ids not in it. One batched query-API request per 100
    ids; when that endpoint refuses (on 2026-09-24 it answered HTTP 406 to
    every uncached request), one OAI-PMH GetRecord per id instead. arXiv asks for 3 s between
    requests. Returns (fetched ids, error or None)."""
    todo = sorted(i for i in ids if i not in cache)
    fetched, err = [], None
    for n in range(0, len(todo), 100):
        chunk = todo[n:n + 100]
        if n:
            time.sleep(3)
        try:
            got = parse_atom(get(f"{ARXIV_API}?id_list={','.join(chunk)}&max_results={len(chunk)}"))
        except (urllib.error.URLError, TimeoutError, ET.ParseError) as e:
            err, got = f"query API: {e}", {}
        for aid in chunk:
            if aid in got:
                cache[aid] = got[aid]
                fetched.append(aid)
    for aid in (i for i in todo if i not in cache):
        time.sleep(3)
        try:
            rec = parse_oai(get(f"{ARXIV_OAI}?verb=GetRecord&metadataPrefix=arXiv&identifier=oai:arXiv.org:{aid}"))
        except (urllib.error.URLError, TimeoutError, ET.ParseError) as e:
            err, rec = f"{err + '; ' if err else ''}OAI-PMH {aid}: {e}", None
        if rec:
            cache[aid] = rec
            fetched.append(aid)
    return fetched, (err if any(i not in cache for i in todo) else None)


def arxiv_id(fm):
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([^\s?#]+?)(?:v\d+)?(?:\.pdf)?/?$", scalar(fm, "url"))
    aid = m.group(1) if m else ""
    return aid if ARXIV_ID_RE.match(aid) else ""


# ---------------------------------------------------------------- records

def safe_title(t):
    return t.replace("|", "/").replace("[", "(").replace("]", ")").strip()


def plink(pid, papers):
    t = papers[pid]["title"]
    return f"[[papers/{pid}|{safe_title(t)}]]" if t else f"[[papers/{pid}]]"


def load(records, report):
    papers, topics, repos = {}, {}, {}
    for f in sorted((records / "summaries").glob("*.md")):
        text = f.read_text()
        fm, _ = split(text)
        stem = f.stem[:-len("_summary")] if f.stem.endswith("_summary") else f.stem
        if fm is None:
            report["invalid_records"].append({"file": f"summaries/{f.name}", "reason": "no frontmatter"})
            continue
        pid = scalar(fm, "id") or stem
        papers[pid] = {"text": text, "fm": fm, "title": unquote(fm, "title"),
                       "keywords": listval(fm, "keywords"), "related": block_list(fm, "related_notes"),
                       "basis": dict((ln.split(":", 1)[0].strip(), ln.split(":", 1)[1].strip().strip("\"'"))
                                     for ln in (block(fm, "related_basis") or (0, 0, []))[2][1:] if ":" in ln),
                       "arxiv": arxiv_id(fm)}
    for f in sorted((records / "topics").glob("*.md")):
        text = f.read_text()
        fm, _ = split(text)
        if fm is None:
            report["invalid_records"].append({"file": f"topics/{f.name}", "reason": "no frontmatter"})
            continue
        slug = scalar(fm, "keyword") or f.stem
        topics[slug] = {"text": text, "fm": fm, "aliases": listval(fm, "aliases"),
                        "papers": block_list(fm, "papers")}
    for f in sorted((records / "repos").glob("*.md")):
        text = f.read_text()
        fm, _ = split(text)
        if fm is None:
            report["invalid_records"].append({"file": f"repos/{f.name}", "reason": "no frontmatter"})
            continue
        repos[scalar(fm, "id") or f.stem] = {"text": text, "fm": fm,
                                             "papers": listval(fm, "related_papers")}
    saved = {f.stem for f in records.glob("*.md")}
    report["papers_without_summary"] = sorted(saved - set(papers))
    return papers, topics, repos


def check_profile(profile, vault):
    text = profile.read_text()
    fm, _ = split(text)
    if fm is None:
        return None, "profile has no frontmatter"
    ptype = scalar(fm, "profile_type") or "problem"
    if ptype not in ("problem", "topic"):
        return None, f"profile_type must be problem or topic, not {ptype!r}"
    missing = []
    for key in REQUIRED["all"] + REQUIRED[ptype]:
        if not re.search(rf"^{key}:", fm, re.M):
            missing.append(key)
        elif not scalar(fm, key) and not block(fm, key)[2][1:] and \
                key not in ("generalized_methodology_terms", "cross_project_linking"):
            missing.append(key)
    if missing:
        return None, f"profile ({ptype}) is missing required fields: {', '.join(missing)}"
    pid = scalar(fm, "id")
    if not re.match(r"^[a-z0-9][a-z0-9._]*(?:-[a-z0-9._]+)+$", pid):
        return None, f"profile id {pid!r} is not a filesystem-safe kebab-case id"
    if vault.name != pid:
        return None, (f"vault path must end in the problem id {pid!r}, not {vault.name!r}: "
                      f"pass <root>/obsidian_vault/{pid}/")
    if vault.exists() and not vault.is_dir():
        return None, f"vault path exists and is not a directory: {vault}"
    return {"id": pid, "type": ptype, "text": text, "fm": fm}, None


# ---------------------------------------------------------------- notes

def code_notes(text, links):
    """Replace the repo link lines of a ## Code notes section where they stand
    (appended when there are none yet); the prose around them is untouched."""
    lines = text.splitlines(keepends=True)
    idx = [i for i, ln in enumerate(lines) if REPO_LINE_RE.match(ln)]
    new = [f"{ln}\n" for ln in links]
    if idx:
        first = idx[0]
        out = [ln for i, ln in enumerate(lines) if i not in idx]
        out[first:first] = new
        if not new and 0 < first < len(out) and not out[first - 1].strip() and not out[first].strip():
            del out[first]
    else:
        out = ["".join(lines).rstrip("\n") + "\n"] + (["\n"] + new if new else [])
    return "".join(out).rstrip("\n") + "\n\n"


def write_note(path, kind, record_text, owned_sections, owned_fm, st, code_links=None):
    """Create or merge one note. owned_sections: {name: content or None};
    None removes the section. code_links: repo link lines for a paper's
    ## Code notes."""
    order = ORDER[kind]
    new = not path.exists()
    old = "" if new else path.read_text()
    rfm, rbody = split(record_text)
    if new:
        fm, body = rfm, rbody
    else:
        vfm, body = split(old)
        fm = rfm if vfm is None else merge_fm(vfm, rfm or "", owned_fm)
    pre, secs = sections(body)
    before = {n: t for n, t in secs}
    if code_links is not None:
        cn = next((s for s in secs if s[0] == "Code notes"), None)
        if cn or code_links:
            upsert(secs, "Code notes", code_notes(cn[1] if cn else "## Code notes\n", code_links), order)
    for name, content in owned_sections.items():
        if content is None:
            secs = [s for s in secs if s[0] != name]
        else:
            upsert(secs, name, render(name, content), order)
    out = assemble(fm, pre, secs)
    after = {n: t for n, t in secs}
    changed = sorted(n for n in set(before) | set(after)
                     if before.get(n, "").strip() != after.get(n, "").strip())
    if out == old:
        st["unchanged"] += 1
        return
    if not st["dry_run"]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(out)
    rel = path.relative_to(st["vault"]).as_posix()
    if new:
        st["created"][rel.split("/")[0] if "/" in rel else "problem"] += 1
    else:
        st["merged"].append({"note": rel, "sections": changed,
                             **({"frontmatter": True} if split(old)[0] != fm else {})})


def related(p, papers, report, pid):
    groups = {"Cites / cited by": [], "Shared references": [], "Similar content": [], "Other": []}
    for other in p["related"]:
        if other not in papers:
            report["dropped_unknown_ids"].append({"note": f"papers/{pid}", "field": "related_notes", "id": other})
            continue
        basis = p["basis"].get(other, "")
        m = re.match(r"(shared-references|similar-content)\s*\(([\d.]+)\)", basis)
        if basis == "direct-citation":
            groups["Cites / cited by"].append((0, other, plink(other, papers)))
        elif m and m.group(1) == "shared-references":
            groups["Shared references"].append((-int(m.group(2)), other, f"{plink(other, papers)} ({m.group(2)} shared)"))
        elif m:
            groups["Similar content"].append((-float(m.group(2)), other, f"{plink(other, papers)} ({m.group(2)})"))
        else:
            groups["Other"].append((0, other, plink(other, papers)))
    out = []
    for head, items in groups.items():
        if not items:
            continue
        note = "Estimated from title and abstract similarity; not a citation.\n\n" if head == "Similar content" else ""
        lines = "".join(f"- {t}\n" for _, _, t in sorted(items, key=lambda x: (x[0], x[1])))
        out.append(f"### {head}\n\n{note}{lines}")
    return "\n".join(out) if out else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", required=True, type=Path)
    ap.add_argument("--records", required=True, type=Path, help="the problem's paper_vault_path")
    ap.add_argument("--vault", required=True, type=Path, help="<root>/obsidian_vault/<problem-id>/")
    ap.add_argument("--rebuilt-topics", default="", help="comma-separated slugs written or deepened this run")
    ap.add_argument("--offline", action="store_true", help="BibTeX from the cache only; no network")
    ap.add_argument("--dry-run", action="store_true", help="report what would change; write nothing")
    a = ap.parse_args()

    for p, what in ((a.profile, "profile"), (a.records, "records directory")):
        if not p.exists():
            print(json.dumps({"error": f"{what} not found: {p}"}))
            return 2
    vault = a.vault.resolve()
    prof, err = check_profile(a.profile, vault)
    if err:
        print(json.dumps({"error": err}))
        return 2
    pid = prof["id"]
    rebuilt = [s.strip() for s in a.rebuilt_topics.split(",") if s.strip()]

    report = {"invalid_records": [], "dropped_unknown_ids": []}
    papers, topics, repos = load(a.records.resolve(), report)
    if not papers:
        print(json.dumps({"error": f"no paper records in {a.records / 'summaries'}"}))
        return 2
    st = {"vault": vault, "dry_run": a.dry_run, "unchanged": 0, "merged": [],
          "created": {"problem": 0, "papers": 0, "topics": 0, "repos": 0}}

    # citations: one batched request for every paper with an arXiv id
    state = a.records.resolve() / ".vault"
    cache_f = state / "arxiv_meta.json"
    cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}
    want = sorted({p["arxiv"] for p in papers.values() if p["arxiv"]})
    fetched, fetch_err = ([], None) if a.offline else fetch_arxiv(want, cache)
    if fetched and not a.dry_run:
        state.mkdir(parents=True, exist_ok=True)
        cache_f.write_text(json.dumps(cache, indent=1, sort_keys=True))
    bib = bibtex({i: cache[i] for i in want if i in cache})

    # repo -> papers, and the reverse for ## Code notes
    code = {}
    for rid, r in repos.items():
        for x in r["papers"]:
            if x in papers:
                code.setdefault(x, []).append(rid)

    # problem note
    pl = "".join(f"- {plink(x, papers)}\n" for x in sorted(papers))
    owned = {"Papers": pl}
    if topics:
        owned["Topics"] = "".join(f"- [[topics/{t}]]\n" for t in sorted(topics))
    if repos:
        owned["Repos"] = "".join(f"- [[repos/{r}]]\n" for r in sorted(repos))
    write_note(vault / f"{pid}.md", "problem", prof["text"], owned, set(), st)

    # topic slug and alias -> topic, for paper -> topic links
    by_kw = {}
    for t, rec in sorted(topics.items()):
        for k in [t] + rec["aliases"]:
            by_kw.setdefault(k, t)

    for x, p in sorted(papers.items()):
        tl = []
        for k in p["keywords"]:
            t = by_kw.get(k)
            if t and t not in tl:
                tl.append(t)
        owned = {"Links": f"- [[{pid}]]\n" + "".join(f"- [[topics/{t}]]\n" for t in tl),
                 "Related": related(p, papers, report, x)}
        if p["arxiv"] in bib:  # else any existing section is left as found
            owned["Citation"] = f"```bibtex\n{bib[p['arxiv']]}\n```"
        write_note(vault / "papers" / f"{x}.md", "paper", p["text"], owned,
                   {"related_notes", "related_basis"}, st,
                   code_links=[f"- [[repos/{r}]]" for r in sorted(code.get(x, []))])

    for t, rec in sorted(topics.items()):
        keep = []
        for x in rec["papers"]:
            if x in papers:
                keep.append(x)
            else:
                report["dropped_unknown_ids"].append({"note": f"topics/{t}", "field": "papers", "id": x})
        owned = {"Papers": "".join(f"- {plink(x, papers)}\n" for x in keep) or "No paper in this vault carries this keyword.\n"}
        fm_owned = set()
        if t in rebuilt:
            _, rsecs = sections(split(rec["text"])[1])
            for name, text in rsecs:
                if name in TOPIC_CONTENT:
                    owned[name] = text.split("\n", 1)[1] if "\n" in text else ""
            fm_owned = {"paper_count", "papers", "aliases"}
        write_note(vault / "topics" / f"{t}.md", "topic", rec["text"], owned, fm_owned, st)

    for r, rec in sorted(repos.items()):
        keep = []
        for x in rec["papers"]:
            if x in papers:
                keep.append(x)
            else:
                report["dropped_unknown_ids"].append({"note": f"repos/{r}", "field": "related_papers", "id": x})
        owned = {"Papers": "".join(f"- {plink(x, papers)}\n" for x in keep) or "No paper in this vault names this repository.\n"}
        write_note(vault / "repos" / f"{r}.md", "repo", rec["text"], owned, set(), st)

    no_cite = [x for x, p in sorted(papers.items()) if p["arxiv"] and p["arxiv"] not in bib]
    print(json.dumps({
        "vault": str(vault),
        "profile_type": prof["type"],
        "dry_run": a.dry_run,
        "notes": {"papers": len(papers), "topics": len(topics), "repos": len(repos)},
        "created": st["created"],
        "merged": st["merged"],
        "unchanged": st["unchanged"],
        "rebuilt_topics": [t for t in rebuilt if t in topics],
        "rebuilt_topics_without_record": [t for t in rebuilt if t not in topics],
        "citations": {"arxiv_papers": len(want), "written": len(want) - len(no_cite),
                      "fetched_now": len(fetched), "missing": no_cite,
                      **({"fetch_error": fetch_err} if fetch_err else {}),
                      **({"offline": True} if a.offline else {})},
        "dropped_unknown_ids": report["dropped_unknown_ids"],
        "papers_without_summary": report["papers_without_summary"],
        "invalid_records": report["invalid_records"],
    }, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
