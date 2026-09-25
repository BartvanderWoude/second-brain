#!/usr/bin/env python3
"""Numbered candidate lists for the agents that screen papers, and saving the
chosen ones as records. A search tool that returns only its top hits, with no
total, cuts results off where nobody can see it; these commands say how much
there was and never drop the rest silently. Stdlib only.

  seeds <paper_vault_path> [--profile P]
      The vault's records, one line each (id, year, first author, title), for
      the citation chaser to pick its seeds from. With --profile, also the
      profile's `seed_papers` that are not in the vault.

  pubmed <paper_vault_path> --list NAME --query Q ... [--window N]
         [--max 300] [--top N]
      Runs each query on PubMed (E-utilities, relevance order) and reports its
      hit count. A query with at most --max hits is fetched whole. One with
      more is reported `too_broad` and not fetched -- split it and rerun --
      unless --top N is given, which fetches its top N and reports that as
      `top N of COUNT`. --window N adds a publication-date clause for the
      last N years; without it there is none.

  chase <paper_vault_path> --list NAME --seed ID ... [--max-citing 300]
      One hop of citation chasing through OpenAlex from the given vault
      records: every work a seed cites, and every work citing a seed. A seed
      is found by DOI, then PMID, then arXiv id, then exact title. A seed
      cited more than --max-citing times has its forward hop skipped and is
      reported `too_cited`. Candidates are ranked by how many seeds they link
      to.

  show <paper_vault_path> --list NAME N ...
      Candidates N... of a list with their abstracts.

  add <paper_vault_path> [--list NAME N ...] [--pmid ID ...] [--arxiv ID ...]
      [--no-fetch]
      Saves papers as records in the "Saved paper file" format of
      templates/paper-identity-spec.md: filename, collision suffix, header
      from the API metadata, the abstract as the body, full_text:
      abstract-only. A candidate with a PMID is saved from PubMed's metadata,
      one with an arXiv id from arXiv's, any other from OpenAlex's. Skips
      any paper already in the vault, then runs scripts/fetch_fulltext.py's
      open-access rungs on each new record unless --no-fetch.

Every list is <paper_vault_path>/.candidates/<NAME>.json; rerunning a name
replaces it. Candidate numbers carry on from list to list, so a number passed
to show or add with the wrong list name is refused rather than taken as
another paper. Papers already in the vault or its .merged/ are counted, never
listed. A list named core-* also leaves out the candidates of the run's other
core-* lists, so the chaser never screens a paper twice; --fresh (pubmed,
chase) deletes those lists first, at the start of a run.

--cache F keeps every API response in a JSON file keyed by URL and reuses it;
--offline answers from that cache only. Exit 0 on a result, 2 on bad input.
"""
import argparse, json, os, re, sys, time, unicodedata, urllib.parse
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from build_vault import ATOM, parse_atom
from check_vault import split
from fetch_fulltext import NetError, get, process
from link_papers import block_list, norm_doi, scalar
from stage_prep import MERGED, norm_title, papers, same

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
ARXIV_API = "https://export.arxiv.org/api/query"
OPENALEX = "https://api.openalex.org/works"
OS_NS = "{http://a9.com/-/spec/opensearch/1.1/}"
ARXIV_ID_RE = re.compile(r"^(?:arxiv:)?(\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?$", re.I)
ARXIV_DOI = "10.48550/arxiv."
FOLD = str.maketrans({"ø": "o", "ł": "l", "đ": "d", "ð": "d", "þ": "th", "ß": "ss",
                      "æ": "ae", "œ": "oe", "ı": "i"})
CANDIDATES = ".candidates"
EFETCH_BATCH = 200
OA_BATCH = 100          # OpenAlex refuses more OR-values per filter, and pages 100 at most
OA_SELECT = ("id,doi,ids,title,publication_year,type,authorships,primary_location,"
             "abstract_inverted_index,cited_by_count")
OA_SKIP_TYPES = {"paratext", "erratum", "retraction"}


# ---------------------------------------------------------------- http

class Api:
    """GETs through an optional URL-keyed cache. NCBI's and OpenAlex's API
    keys, if set, are added after the cache key is taken, so a key never
    lands in a cache file."""

    def __init__(self, path, offline):
        self.path, self.offline, self.dirty, self.last = path, offline, False, {}
        self.data = json.loads(path.read_text()) if path and path.is_file() else {}

    def text(self, url, accept=None):
        if url in self.data:
            return self.data[url]
        if self.offline:
            raise NetError("not in the cache (--offline)")
        host = urllib.parse.urlsplit(url).netloc
        # arXiv asks for 3 s between calls; NCBI allows 3/s; OpenAlex 10/s
        wait = 3.0 if "arxiv" in host else 0.4 if "ncbi" in host else 0.15
        if host in self.last:
            time.sleep(max(0.0, wait - (time.time() - self.last[host])))
        real = url
        if "ncbi.nlm.nih.gov" in host and os.environ.get("NCBI_API_KEY"):
            real += "&api_key=" + urllib.parse.quote(os.environ["NCBI_API_KEY"])
        if "openalex.org" in host and os.environ.get("OPENALEX_API_KEY"):
            real += "&api_key=" + urllib.parse.quote(os.environ["OPENALEX_API_KEY"])
        status, _, body = get(real, accept=accept)
        # arXiv's query API intermittently answers uncached requests with 406,
        # for minutes at a time, whatever the client sends
        for wait in ((10, 30) if "arxiv" in host else ()):
            if status != 406:
                break
            time.sleep(wait)
            status, _, body = get(real, accept=accept)
        self.last[host] = time.time()
        if status != 200:
            why = (" (arXiv's query API refusing uncached requests; rerun later)"
                   if status == 406 and "arxiv" in host else
                   " (OpenAlex's daily budget is spent; set OPENALEX_API_KEY or rerun tomorrow)"
                   if status == 429 and "openalex" in host else "")
            raise NetError(f"HTTP {status} from {host}{why}")
        text = body.decode("utf-8", "replace")
        if self.path:
            self.data[url], self.dirty = text, True
        return text

    def save(self):
        if self.dirty:
            self.path.write_text(json.dumps(self.data, indent=0, sort_keys=True, ensure_ascii=False) + "\n")


def qs(**kw):
    return urllib.parse.urlencode(kw)


# ---------------------------------------------------------------- pubmed

def itertext(el):
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def parse_efetch(xml_text):
    """PMID -> metadata, in the order PubMed returned them. Journal articles
    and book chapters (StatPearls and the like) keep their fields in
    different places."""
    out = {}
    for art in ET.fromstring(xml_text):
        if art.tag == "PubmedArticle":
            doc = art.find("MedlineCitation")
            a = doc.find("Article")
            title, pd = a.find("ArticleTitle"), a.find("Journal/JournalIssue/PubDate")
            venue, year = a.findtext("Journal/Title", ""), a.findtext("ArticleDate/Year")
            ids = art.findall("PubmedData/ArticleIdList/ArticleId")
        elif art.tag == "PubmedBookArticle":
            doc = a = art.find("BookDocument")
            title = a.find("ArticleTitle") if a.find("ArticleTitle") is not None else a.find("Book/BookTitle")
            pd, venue, year = a.find("Book/PubDate"), a.findtext("Book/BookTitle", ""), None
            ids = art.findall("PubmedBookData/ArticleIdList/ArticleId")
        else:
            continue
        pmid = doc.findtext("PMID", "").strip()
        authors = []
        for au in a.findall("AuthorList/Author"):
            last, coll = au.findtext("LastName"), au.findtext("CollectiveName")
            if last:
                authors.append(" ".join(f"{au.findtext('ForeName') or au.findtext('Initials') or ''} {last}".split()))
            elif coll:
                authors.append(" ".join(coll.split()))
        if pd is not None:
            year = pd.findtext("Year") or (re.search(r"\d{4}", pd.findtext("MedlineDate", "")) or [""])[0] or year
        ids = {x.get("IdType"): (x.text or "").strip() for x in ids}
        doi = ids.get("doi") or next((e.text for e in a.findall("ELocationID") if e.get("EIdType") == "doi"), "")
        paras = []
        for t in a.findall("Abstract/AbstractText"):
            body = itertext(t)
            if body:
                paras.append(f"{t.get('Label')}: {body}" if t.get("Label") else body)
        out[pmid] = {"source": "pubmed", "pmid": pmid, "arxiv_id": "", "pmcid": ids.get("pmc", "").upper(),
                     "doi": norm_doi(doi or ""), "title": re.sub(r"(?<!\.)\.$", "", itertext(title)),
                     "authors": authors, "year": year or "", "venue": " ".join(venue.split()),
                     "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "abstract": "\n\n".join(paras)}
    return out


def efetch(api, pmids):
    out = {}
    for n in range(0, len(pmids), EFETCH_BATCH):
        out.update(parse_efetch(api.text(f"{EFETCH}?" + qs(db="pubmed", id=",".join(pmids[n:n + EFETCH_BATCH]),
                                                            retmode="xml", tool="second-brain-researcher"))))
    return out


def esearch(api, query, n):
    res = json.loads(api.text(f"{ESEARCH}?" + qs(db="pubmed", term=query, retmax=n, sort="relevance",
                                                  retmode="json", tool="second-brain-researcher")))
    r = res.get("esearchresult", {})
    if "ERROR" in r:
        raise NetError(f"PubMed: {r['ERROR']}")
    return int(r.get("count", 0)), r.get("idlist", [])


def windowed(q, years):
    if not years:
        return q
    return f'({q}) AND ("{date.today().year - years}"[Date - Publication] : "3000"[Date - Publication])'


# ---------------------------------------------------------------- arxiv

def parse_arxiv(xml_text):
    """arXiv id -> metadata."""
    root = ET.fromstring(xml_text)
    base = parse_atom(xml_text)
    extra = {}
    for e in root.findall("a:entry", ATOM):
        idt = e.findtext("a:id", "", ATOM)
        if "/abs/" in idt:
            extra[re.sub(r"v\d+$", "", idt.split("/abs/")[-1])] = (
                " ".join(e.findtext("a:summary", "", ATOM).split()), e.findtext("arxiv:doi", "", ATOM))
    out = {}
    for aid, m in base.items():
        abstract, doi = extra.get(aid, ("", ""))
        out[aid] = {"source": "arxiv", "arxiv_id": aid, "pmid": "", "pmcid": "", "doi": norm_doi(doi or ""),
                    "title": m["title"], "authors": m["authors"], "year": m["published"][:4],
                    "venue": "arXiv", "url": f"https://arxiv.org/abs/{aid}", "abstract": abstract}
    return out


# ---------------------------------------------------------------- openalex

def wid(url):
    return (url or "").rsplit("/", 1)[-1]


def abstract_of(inv):
    if not inv:
        return ""
    pos = sorted((i, w) for w, idx in inv.items() for i in idx)
    return " ".join(w for _, w in pos)


def from_work(w):
    """An OpenAlex work as a hit, with the same keys a PubMed or arXiv hit has."""
    ids = w.get("ids") or {}
    doi = norm_doi(w.get("doi") or ids.get("doi") or "")
    arxiv = doi[len(ARXIV_DOI):] if doi.startswith(ARXIV_DOI) else ""
    pmcid = wid(ids.get("pmcid", "")).upper()
    loc = (w.get("primary_location") or {}).get("source") or {}
    return {"source": "openalex", "openalex": wid(w.get("id")), "doi": doi, "arxiv_id": arxiv,
            "pmid": wid(ids.get("pmid", "")), "pmcid": pmcid if pmcid.startswith("PMC") else "",
            "title": " ".join((w.get("title") or "").split()),
            "authors": [" ".join((a.get("author") or {}).get("display_name", "").split())
                        for a in w.get("authorships") or [] if (a.get("author") or {}).get("display_name")],
            "year": str(w.get("publication_year") or ""), "venue": " ".join((loc.get("display_name") or "").split()),
            "url": f"https://doi.org/{doi}" if doi else w.get("id", ""),
            "abstract": abstract_of(w.get("abstract_inverted_index")), "type": w.get("type") or ""}


def oa_filter(api, flt, values, select):
    """Every work matching filter `flt` for any of `values`: OR-ed in batches
    of the most values OpenAlex takes, each paged through to its end."""
    out = []
    for n in range(0, len(values), OA_BATCH):
        cursor = "*"
        while cursor:
            d = json.loads(api.text(f"{OPENALEX}?" + qs(filter=f"{flt}:" + "|".join(values[n:n + OA_BATCH]),
                                                        select=select, **{"per-page": 100}, cursor=cursor)))
            out += d.get("results", [])
            cursor = d.get("meta", {}).get("next_cursor") if d.get("results") else None
    return out


def resolve(api, seeds):
    """seed id -> OpenAlex work (id, ids, title, referenced_works,
    cited_by_count), by DOI, then PMID, then arXiv id, then exact title."""
    sel = "id,doi,ids,title,publication_year,referenced_works,cited_by_count"
    found = {}
    for flt, val in (("doi", lambda p: p["doi"]),
                     ("pmid", lambda p: p["pmid"]),
                     ("doi", lambda p: ARXIV_DOI + p["arxiv_id"].lower() if p["arxiv_id"] else "")):
        todo = {val(p): i for i, p in seeds.items() if i not in found and val(p)}
        if not todo:
            continue
        for w in oa_filter(api, flt, list(todo), sel):
            ids = w.get("ids") or {}
            k = norm_doi(w.get("doi") or "") if flt == "doi" else wid(ids.get("pmid", ""))
            if k in todo:
                found.setdefault(todo[k], w)
    for i, p in seeds.items():
        if i in found or not p["title"]:
            continue
        # a comma separates filters, so the title goes in as plain words
        words = " ".join(re.sub(r"[^\w\s]", " ", p["title"]).split())
        hits = [w for w in oa_filter(api, "title.search", [words], sel)
                if norm_title(w.get("title") or "") == norm_title(p["title"])]
        year = i[:4] if i[:4].isdigit() else ""
        hits.sort(key=lambda w: (str(w.get("publication_year")) != year, not w.get("doi")))
        if hits:
            found[i] = hits[0]
    return found


# ---------------------------------------------------------------- vault, lists

def known(root):
    """(id, record) for every saved paper, the vault's own before .merged/'s."""
    out = [(i, p) for i, p in papers(root).items()]
    if (root / MERGED).is_dir():
        out += [(f"{MERGED}/{i}", p) for i, p in papers(root / MERGED).items()]
    return out


def match(hit, vault):
    for i, p in vault:
        ok, key = same(hit, p)
        if ok:
            return i, key
    return None, None


def list_path(root, name):
    if not re.fullmatch(r"[A-Za-z0-9][\w.-]*", name):
        raise ValueError(f"bad list name: {name}")
    return root / CANDIDATES / f"{name}.json"


def load_list(root, name, numbers=()):
    """A list, after checking that every one of `numbers` is in it."""
    f = list_path(root, name)
    if not f.is_file():
        raise ValueError(f"no such list: {name}")
    lst = json.loads(f.read_text())
    have = {c["n"] for c in lst["candidates"]}
    for n in numbers:
        if n not in have:
            other = next((g.stem for g in sorted((root / CANDIDATES).glob("*.json"))
                          if any(c["n"] == n for c in json.loads(g.read_text())["candidates"])), None)
            raise ValueError(f"#{n} is not in list {name}" + (f"; it is in list {other}" if other else ""))
    return lst


def seen(root, name):
    """(label, hit) for every candidate of the run's other core-* lists."""
    if not name.startswith("core-") or not (root / CANDIDATES).is_dir():
        return []
    return [(f"{f.stem} #{c['n']}", c) for f in sorted((root / CANDIDATES).glob("core-*.json"))
            if f.stem != name for c in json.loads(f.read_text())["candidates"]]


def fresh(root, name):
    for f in (root / CANDIDATES).glob("core-*.json") if (root / CANDIDATES).is_dir() else ():
        if f.stem != name:
            f.unlink()


def save_list(root, name, data):
    f = list_path(root, name)
    f.parent.mkdir(exist_ok=True)
    f.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def surname(name):
    """The identity spec's surname slug: the part after the final space, or
    before the comma of "Last, First"; accents folded; a-z only."""
    s = name.split(",")[0] if "," in name else name.strip().split(" ")[-1]
    s = unicodedata.normalize("NFKD", s.lower().translate(FOLD))
    return re.sub(r"[^a-z]", "", s.encode("ascii", "ignore").decode())


def line(c):
    first = c["authors"][0] if c["authors"] else ""
    last = (first.split(",")[0] if "," in first else first.split(" ")[-1]) if first else "?"
    t = c["title"] if len(c["title"]) <= 150 else c["title"][:149] + "…"
    venue = f" [{c['venue'][:40]}]" if c.get("venue") else ""
    by = c["found_by"]
    by = ", ".join(by[:3]) + (f" +{len(by) - 3}" if len(by) > 3 else "")
    return f"{c['n']}. {c['year'] or '----'} {last} — {t}{venue} ({by})"


def listing(root, name, candidates, head, data):
    """Numbers the candidates, saves the list and prints it. Numbering carries
    on from the vault's other lists, so a number names one candidate in one
    list, and passing it with the wrong list name is an error, not a
    different paper."""
    last = max((c["n"] for f in (root / CANDIDATES).glob("*.json") if f.stem != name
                for c in json.loads(f.read_text())["candidates"]), default=0) \
        if (root / CANDIDATES).is_dir() else 0
    for n, c in enumerate(candidates, last + 1):
        c["n"] = n
    save_list(root, name, {**data, "candidates": candidates})
    print("\n".join(head))
    print(f"list {name}: {len(candidates)} candidates, in {CANDIDATES}/{name}.json")
    for c in candidates:
        print(line(c))


# ---------------------------------------------------------------- seeds

def seed_ident(s):
    s = s.strip()
    blank = {"doi": "", "arxiv_id": "", "pmid": "", "pmcid": "", "title": "", "source": ""}
    m = re.search(r"\b(10\.\d{4,9}/\S+)", s)
    if m:
        return {**blank, "doi": norm_doi(m.group(1).rstrip(".,;"))}
    m = ARXIV_ID_RE.match(s)
    if m:
        return {**blank, "arxiv_id": m.group(1), "source": "arxiv"}
    if re.fullmatch(r"(?:PMID:?\s*)?\d{5,9}", s, re.I):
        return {**blank, "pmid": re.sub(r"\D", "", s)}
    if re.fullmatch(r"PMC\d+", s, re.I):
        return {**blank, "pmcid": s.upper()}
    return {**blank, "title": s}


def listval(fm, key):
    v = scalar(fm, key).split(" #")[0].strip()
    if v.startswith("["):
        return [x.strip().strip("\"'") for x in v.strip("[]").split(",") if x.strip()]
    return block_list(fm, key)


def cmd_seeds(a, api):
    ps = papers(a.path)
    print(f"{len(ps)} records in the vault")
    for i, p in ps.items():
        fm = p["fm"] or ""
        first = i.split("_")[1] if i.count("_") else ""   # the filename's surname slug
        year = (scalar(fm, "year") if fm else "") or (i[:4] if i[:4].isdigit() else "----")
        t = p["title"] if len(p["title"]) <= 150 else p["title"][:149] + "…"
        print(f"{i} | {year} {first} — {t}")
    if a.profile:
        pfm, _ = split(a.profile.read_text())
        vault = known(a.path)
        want = listval(pfm or "", "seed_papers")
        miss = [s for s in want if not match(seed_ident(s), vault)[0]]
        print(f"seed_papers: {len(want)} in the profile, {len(miss)} not in the vault" if want else
              "seed_papers: none in the profile")
        for s in miss:
            print(f"  not in vault: {s}")
    return 0


# ---------------------------------------------------------------- pubmed

def cmd_pubmed(a, api):
    if a.fresh:
        fresh(a.path, a.list)
    vault, prior = known(a.path), seen(a.path, a.list)
    head, cands, queries = [], [], []
    for qn, q in enumerate(a.query, 1):
        query = windowed(q, a.window)
        row = {"q": qn, "query": query}
        try:
            count, ids = esearch(api, query, a.max)
            if count > a.max and a.top:
                ids = esearch(api, query, a.top)[1]
                row["top"] = a.top
            elif count > a.max:
                ids = []
                row["too_broad"] = True
            meta = efetch(api, ids) if ids else {}
        except (NetError, ET.ParseError, ValueError) as e:
            row["error"] = str(e)
            queries.append(row)
            head.append(f"q{qn}: ERROR {e} — not searched: {query}")
            continue
        in_vault = new = 0
        for rank, pmid in enumerate(ids, 1):
            h = meta.get(pmid)
            if h is None:
                continue
            if match(h, vault)[0]:
                in_vault += 1
                continue
            if match(h, prior)[0]:
                continue
            c = next((c for c in cands if c["pmid"] == pmid), None)
            if c is None:
                c = {**h, "found_by": []}
                cands.append(c)
                new += 1
            c["found_by"].append(f"q{qn}#{rank}")
        row.update(count=count, fetched=len(ids), in_vault=in_vault, new=new)
        queries.append(row)
        state = ("TOO BROAD, not fetched — split it and rerun" if row.get("too_broad") else
                 f"top {len(ids)} of {count} fetched" if row.get("top") else f"all {count} fetched")
        head.append(f"q{qn}: {count} hits, {state}; {in_vault} in vault, {new} new: {query}")
    listing(a.path, a.list, cands, head, {"name": a.list, "kind": "pubmed", "queries": queries})
    return 0


# ---------------------------------------------------------------- chase

def cmd_chase(a, api):
    root = a.path
    ps = papers(root)
    bad = [s for s in a.seed if s not in ps]
    if bad:
        print(json.dumps({"error": f"not a record in the vault: {', '.join(bad)}"}))
        return 2
    if a.fresh:
        fresh(root, a.list)
    seeds = {s: ps[s] for s in a.seed}
    try:
        work = resolve(api, seeds)
        wseed = {wid(w["id"]): s for s, w in work.items()}
        # backward: what the seeds cite
        refs = {}
        for s, w in work.items():
            for r in w.get("referenced_works") or []:
                refs.setdefault(wid(r), set()).add(s)
        found = {}
        for w in oa_filter(api, "openalex", sorted(refs), OA_SELECT):
            found.setdefault(wid(w["id"]), (w, set(), set()))[1].update(refs.get(wid(w["id"]), ()))
        # forward: what cites the seeds
        too_cited = {s: w.get("cited_by_count", 0) for s, w in work.items()
                     if (w.get("cited_by_count") or 0) > a.max_citing}
        fwd = sorted(wid(w["id"]) for s, w in work.items() if s not in too_cited and w.get("cited_by_count"))
        for w in oa_filter(api, "cites", fwd, OA_SELECT + ",referenced_works"):
            cited = {wseed[wid(r)] for r in w.get("referenced_works") or [] if wid(r) in wseed}
            found.setdefault(wid(w["id"]), (w, set(), set()))[2].update(cited)
    except (NetError, ValueError) as e:
        print(json.dumps({"error": f"OpenAlex: {e}"}))
        return 1
    vault, prior = known(root), seen(root, a.list)
    cands, skipped = [], {"in_vault": 0, "listed_before": 0, "type": 0, "no_title": 0}
    for w_id, (w, back, fwd_) in found.items():
        if w_id in wseed:
            continue
        h = from_work(w)
        if h["type"] in OA_SKIP_TYPES:
            skipped["type"] += 1
            continue
        if not h["title"]:
            skipped["no_title"] += 1
            continue
        if match(h, vault)[0]:
            skipped["in_vault"] += 1
            continue
        if match(h, prior)[0]:
            skipped["listed_before"] += 1
            continue
        dup = next((c for c in cands if same(h, c)[0]), None)
        if dup:
            dup["_back"] |= back
            dup["_fwd"] |= fwd_
            continue
        cands.append({**h, "_back": set(back), "_fwd": set(fwd_)})
    for c in cands:
        c["links"] = len(c["_back"] | c["_fwd"])
        c["found_by"] = [f"ref of {s}" for s in sorted(c.pop("_back"))] + [f"cites {s}" for s in sorted(c.pop("_fwd"))]
    cands.sort(key=lambda c: (-c["links"], -int(c["year"] or 0), c["title"].lower()))
    unresolved = [s for s in a.seed if s not in work]
    no_refs = [s for s, w in work.items() if not w.get("referenced_works")]
    head = [f"seeds: {len(a.seed)}, {len(work)} found in OpenAlex"
            + (f"; not found: {', '.join(unresolved)}" if unresolved else ""),
            f"backward: {len(refs)} works cited by the seeds" + (f"; no reference list in OpenAlex: {', '.join(no_refs)}"
                                                                   if no_refs else ""),
            f"forward: {sum(1 for v in found.values() if v[2])} works citing the seeds"
            + "".join(f"; TOO CITED, forward hop skipped: {s} ({n} citations)" for s, n in too_cited.items()),
            f"left out: {skipped['in_vault']} in vault, {skipped['listed_before']} in earlier core lists, "
            f"{skipped['type']} errata/paratext, {skipped['no_title']} untitled"]
    listing(root, a.list, cands, head, {
        "name": a.list, "kind": "chase", "seeds": {s: wid(w["id"]) for s, w in work.items()},
        "unresolved": unresolved, "too_cited": too_cited, "no_reference_list": no_refs, "left_out": skipped})
    return 0


# ---------------------------------------------------------------- show

def cmd_show(a, api):
    lst = load_list(a.path, a.list, a.n)
    by_n = {c["n"]: c for c in lst["candidates"]}
    for n in a.n:
        c = by_n[n]
        ids = ", ".join(f"{k} {c[k]}" for k in ("pmid", "doi", "arxiv_id") if c.get(k))
        au = ", ".join(c["authors"][:3]) + (" et al" if len(c["authors"]) > 3 else "")
        print(f"{line(c)}\n   {au}. {ids}\n   {c['abstract'] or '(no abstract available)'}\n")
    return 0


# ---------------------------------------------------------------- add

def filename(root, h):
    """(stem, None), or (None, existing stem) when the base name already holds
    this paper -- a skip, never a collision."""
    slugs = [surname(x) or "anon" for x in h["authors"][:2]] or ["anon"]
    base = "_".join([h["year"] or "nd"] + slugs)
    stem, n = base, 1
    while (root / f"{stem}.md").exists():
        if norm_title(title_of(root / f"{stem}.md")) == norm_title(h["title"]):
            return None, stem
        n += 1
        stem = f"{base}_{n}"
    return stem, None


def title_of(f):
    fm, body = split(f.read_text())
    t = scalar(fm, "title") if fm else ""
    return t.replace('\\"', '"') or next((ln.strip("# ").strip() for ln in body.splitlines() if ln.strip()), "")


def record(stem, h):
    q = lambda v: json.dumps(v, ensure_ascii=False)
    lines = [
        f"id: {stem}", f"title: {q(h['title'])}", f"authors: {q(h['authors'])}", f"year: {h['year']}",
        f"venue: {q(h['venue'])}", f"source: {h['source']}", f"url: {h['url']}", f"doi: {h['doi']}",
        f"arxiv_id: {h['arxiv_id']}", f"pmid: {q(h['pmid']) if h['pmid'] else ''}", f"pmcid: {h['pmcid']}",
        "paywalled:", "full_text: abstract-only", "full_text_source: none", "extraction_warning:",
    ]
    body = h["abstract"] or "(No abstract was available from the source's metadata.)"
    return "---\n" + "\n".join(ln.rstrip() for ln in lines) + "\n---\n\n## Abstract\n\n" + body + "\n"


def picked(a):
    """(requested, hit) per paper to save: list candidates by number, then
    --pmid and --arxiv. A list candidate with a PMID or an arXiv id takes that
    source's metadata; one with neither keeps OpenAlex's."""
    reqs, not_found = [], []
    lst = load_list(a.path, a.list, a.n) if a.list else None
    by_n = {c["n"]: c for c in lst["candidates"]} if lst else {}
    for n in a.n:
        c = by_n[n]
        want = (("pmid", c["pmid"]) if c["pmid"] and c["source"] != "pubmed" else
                ("arxiv", c["arxiv_id"]) if c["arxiv_id"] and not c["pmid"] else (None, None))
        reqs.append((f"{a.list} #{n}", c, want))
    reqs += [(f"pmid:{p.strip()}", None, ("pmid", p.strip())) for p in a.pmid]
    for x in a.arxiv:
        x = re.sub(r"v\d+$", "", x.strip())
        reqs.append((f"arxiv:{x}", None, ("arxiv", x)))
    pm = efetch(a.api, list(dict.fromkeys(v for _, _, (k, v) in reqs if k == "pmid")))
    ax_ids = list(dict.fromkeys(v for _, _, (k, v) in reqs if k == "arxiv"))
    ax = {}
    if ax_ids:
        try:
            ax = parse_arxiv(a.api.text(f"{ARXIV_API}?" + qs(id_list=",".join(ax_ids), max_results=len(ax_ids))))
        except (NetError, ET.ParseError):
            if any(c is None for _, c, (k, _) in reqs if k == "arxiv"):
                raise
    out = []
    for req, c, (k, v) in reqs:
        h = pm.get(v) if k == "pmid" else ax.get(v) if k == "arxiv" else c
        if h is None and c is not None:
            # PubMed or arXiv did not return it; OpenAlex's metadata is still the paper's own
            h = {**c, "source": "arxiv", "url": f"https://arxiv.org/abs/{v}"} if k == "arxiv" else c
        if h is None:
            not_found.append(req if c is None else f"{req} ({k}:{v})")
            continue
        if c is not None:
            h = {**h, "abstract": h["abstract"] or c["abstract"],
                 **{f: h[f] or c[f] for f in ("doi", "pmcid", "arxiv_id")}}
        out.append((req, h))
    return out, not_found


def cmd_add(a, api):
    if not (a.n or a.pmid or a.arxiv):
        print(json.dumps({"error": "give --list with candidate numbers, or --pmid / --arxiv"}))
        return 2
    if a.n and not a.list:
        print(json.dumps({"error": "candidate numbers need --list"}))
        return 2
    a.api = api
    try:
        hits, not_found = picked(a)
    except (NetError, ET.ParseError) as e:
        print(json.dumps({"error": f"metadata lookup failed: {e}"}))
        return 1
    root = a.path
    vault = known(root)
    saved, skipped = [], []
    for want, h in hits:
        i, key = match(h, vault)
        stem = None
        if not i:
            stem, i = filename(root, h)
            key = "title (filename)" if i else None
        if i:
            skipped.append({"requested": want, "in_vault": i, "key": key})
            continue
        f = root / f"{stem}.md"
        f.write_text(record(stem, h))
        vault.append((stem, h))
        rec = {"requested": want, "id": stem, "file": f.name, "title": h["title"], "doi": h["doi"],
               "pmid": h["pmid"], "source": h["source"], "full_text": "abstract-only"}
        if not a.no_fetch:
            try:
                r = process(f)
                rec.update({k: r.get(k) for k in ("full_text", "full_text_source", "paywalled", "extraction_warning")})
                rec["attempts"] = [f"{x['rung']}: {x['outcome']}" for x in r.get("attempts", [])]
            except (ValueError, NetError) as e:
                rec["fetch_error"] = str(e)
        saved.append(rec)
    print(json.dumps({
        "saved": saved,
        "skipped_existing": skipped,
        "not_found": not_found,
        "fetched": not a.no_fetch,
        "still_abstract_only": [r["id"] for r in saved if r["full_text"] != "full"],
    }, indent=1, ensure_ascii=False))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seeds")
    s.add_argument("path", type=Path)
    s.add_argument("--profile", type=Path)
    p = sub.add_parser("pubmed")
    p.add_argument("path", type=Path)
    p.add_argument("--list", required=True)
    p.add_argument("--query", action="append", required=True)
    p.add_argument("--window", type=int, default=0, help="years back; 0 or absent means no date clause")
    p.add_argument("--max", type=int, default=300)
    p.add_argument("--top", type=int, default=0, help="fetch the top N of a query over --max, and say so")
    c = sub.add_parser("chase")
    c.add_argument("path", type=Path)
    c.add_argument("--list", required=True)
    c.add_argument("--seed", action="append", required=True)
    c.add_argument("--max-citing", type=int, default=300)
    for x in (p, c):
        x.add_argument("--fresh", action="store_true", help="delete the other core-* lists first")
    w = sub.add_parser("show")
    w.add_argument("path", type=Path)
    w.add_argument("--list", nargs="+", required=True, metavar=("NAME", "N"))
    d = sub.add_parser("add")
    d.add_argument("path", type=Path)
    d.add_argument("--list", nargs="+", metavar=("NAME", "N"))
    d.add_argument("--pmid", action="append", default=[])
    d.add_argument("--arxiv", action="append", default=[])
    d.add_argument("--no-fetch", action="store_true")
    for x in (s, p, c, w, d):
        x.add_argument("--cache", type=Path)
        x.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    if not a.path.is_dir():
        print(json.dumps({"error": f"not a directory: {a.path}"}))
        return 2
    if getattr(a, "profile", None) and not a.profile.is_file():
        print(json.dumps({"error": f"no such profile: {a.profile}"}))
        return 2
    if a.offline and not (a.cache and a.cache.is_file()):
        print(json.dumps({"error": "--offline needs an existing --cache file"}))
        return 2
    if a.cmd in ("show", "add"):
        name, *nums = a.list or [None]
        if not all(n.isdigit() for n in nums) or (a.cmd == "show" and not nums):
            print(json.dumps({"error": "--list takes a list name, then candidate numbers"}))
            return 2
        a.list, a.n = name, [int(n) for n in nums]
    a.path = a.path.resolve()
    api = Api(a.cache, a.offline)
    run = {"seeds": cmd_seeds, "pubmed": cmd_pubmed, "chase": cmd_chase, "show": cmd_show, "add": cmd_add}[a.cmd]
    try:
        return run(a, api)
    except ValueError as e:
        print(json.dumps({"error": str(e)}))
        return 2
    finally:
        api.save()


if __name__ == "__main__":
    sys.exit(main())
