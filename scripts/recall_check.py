#!/usr/bin/env python3
"""The stage-4 recall check: does the paper vault hold what a precise query for
the profile's core category finds? Discovery's own queries cannot answer that,
since a paper they never retrieved leaves no trace. Stdlib only; prints JSON.

  probe <paper_vault_path> --profile P [--probe Q ...] [--max 60]
        [--cache F] [--offline]
      Runs each recall probe (the profile's `recall_probes`, or the --probe
      queries given instead) on PubMed (E-utilities, relevance order) and
      arXiv (export API; the probe translated mechanically), within the
      profile's `date_window_years`. Matches each source's top --max hits
      against the records in <paper_vault_path> and its .merged/ by the key
      ladder in templates/paper-identity-spec.md, and checks `seed_papers`
      the same way. Reports per probe and source the hit count, the hits
      already in the vault, and a numbered list of the missing ones (one
      number per paper across all probes). A probe matching more than --max
      is flagged too_broad; a source that fails reports its error, never 0.

  add <paper_vault_path> [--pmid ID ...] [--arxiv ID ...] [--no-fetch]
        [--cache F] [--offline]
      Saves the chosen hits as records in the "Saved paper file" format of
      the identity spec (filename, collision suffix, header from the API
      metadata, the abstract as the body, full_text: abstract-only), skipping
      any paper already in the vault, then runs scripts/fetch_fulltext.py's
      open-access rungs on each new record unless --no-fetch.

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
OS_NS = "{http://a9.com/-/spec/opensearch/1.1/}"
# A PubMed field tag may contain spaces ([MeSH Terms]), so a token takes it whole.
TOKEN_RE = re.compile(r'"[^"]*"(?:\[[^\]]*\])?|\(|\)|[^\s()"\[]+(?:\[[^\]]*\])?')
ARXIV_ID_RE = re.compile(r"^(?:arxiv:)?(\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?$", re.I)
FOLD = str.maketrans({"ø": "o", "ł": "l", "đ": "d", "ð": "d", "þ": "th", "ß": "ss",
                      "æ": "ae", "œ": "oe", "ı": "i"})


# ---------------------------------------------------------------- http

class Api:
    """GETs through an optional URL-keyed cache. NCBI's api_key, if set, is
    added after the cache key is taken, so it never lands in a cache file."""

    def __init__(self, path, offline):
        self.path, self.offline, self.dirty, self.last = path, offline, False, {}
        self.data = json.loads(path.read_text()) if path and path.is_file() else {}

    def text(self, url, accept=None):
        if url in self.data:
            return self.data[url]
        if self.offline:
            raise NetError("not in the cache (--offline)")
        host = urllib.parse.urlsplit(url).netloc
        wait = 3.0 if "arxiv" in host else 0.4   # arXiv asks for 3 s between calls; NCBI 3/s
        if host in self.last:
            time.sleep(max(0.0, wait - (time.time() - self.last[host])))
        real = url
        if "ncbi.nlm.nih.gov" in host and os.environ.get("NCBI_API_KEY"):
            real += "&api_key=" + urllib.parse.quote(os.environ["NCBI_API_KEY"])
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
            raise NetError(f"HTTP {status}" + (" (arXiv's query API refusing uncached requests; rerun later)"
                                                if status == 406 and "arxiv" in host else ""))
        text = body.decode("utf-8", "replace")
        if self.path:
            self.data[url], self.dirty = text, True
        return text

    def save(self):
        if self.dirty:
            self.path.write_text(json.dumps(self.data, indent=0, sort_keys=True, ensure_ascii=False) + "\n")


def qs(**kw):
    return urllib.parse.urlencode(kw)


# ---------------------------------------------------------------- sources

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


def parse_arxiv(xml_text):
    """arXiv id -> metadata, plus the total hit count."""
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
    total = root.findtext(f"{OS_NS}totalResults")
    return out, int(total) if total and total.isdigit() else len(out)


def pubmed_search(api, query, n):
    res = json.loads(api.text(f"{ESEARCH}?" + qs(db="pubmed", term=query, retmax=n, sort="relevance",
                                                  retmode="json", tool="second-brain-researcher")))
    r = res.get("esearchresult", {})
    if "ERROR" in r:
        raise NetError(f"PubMed: {r['ERROR']}")
    ids = r.get("idlist", [])
    meta = efetch(api, ids)
    return int(r.get("count", 0)), [meta[i] for i in ids if i in meta]


def efetch(api, pmids):
    if not pmids:
        return {}
    return parse_efetch(api.text(f"{EFETCH}?" + qs(db="pubmed", id=",".join(pmids), retmode="xml",
                                                   tool="second-brain-researcher")))


def arxiv_search(api, query, n):
    got, total = parse_arxiv(api.text(f"{ARXIV_API}?" + qs(search_query=query, start=0, max_results=n,
                                                           sortBy="relevance", sortOrder="descending")))
    return total, list(got.values())


def arxiv_query(q):
    """PubMed boolean syntax -> arXiv's: a phrase or term searches all fields,
    AND/OR/parentheses stay, NOT becomes ANDNOT, a field tag or truncation
    star is dropped, and adjacent terms are ANDed as PubMed would."""
    out = []
    for t in TOKEN_RE.findall(q):
        t = re.sub(r"\[[^\]]*\]$", "", t)
        if t in ("(", ")", "AND", "OR"):
            tok = t
        elif t == "NOT":
            tok = "ANDNOT"
        else:
            t = t.strip('"').rstrip("*").strip()
            if not t:
                continue
            tok = f"all:{t}" if re.fullmatch(r"[A-Za-z0-9]+", t) else f'all:"{t}"'
        if out and (out[-1] == ")" or out[-1].startswith("all:")) and (tok == "(" or tok.startswith("all:")):
            out.append("AND")
        out.append(tok)
    return " ".join(out)


def windowed(q, years, source):
    if not years:
        return q
    if source == "pubmed":
        return f'({q}) AND ("{date.today().year - years}"[Date - Publication] : "3000"[Date - Publication])'
    d = date.today()
    lo = d.replace(year=d.year - years, day=28 if (d.month, d.day) == (2, 29) else d.day)
    return f"({q}) AND submittedDate:[{lo:%Y%m%d}0000 TO {d:%Y%m%d}2359]"


# ---------------------------------------------------------------- vault

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


def probes_of(fm):
    """recall_probes items, unquoted by YAML's rules: a probe carries double
    quotes, so it is written single-quoted, and block_list's stripping would
    eat a phrase's closing quote."""
    b = re.search(r"^recall_probes:.*\n((?:[ \t]+.*\n)*)", fm, re.M)
    out = []
    for ln in (b.group(1).splitlines() if b else []):
        v = ln.strip()
        if not v.startswith("- "):
            continue
        v = v[2:].strip()
        if len(v) >= 2 and v[0] == v[-1] == "'":
            v = v[1:-1].replace("''", "'")
        elif len(v) >= 2 and v[0] == v[-1] == '"':
            v = json.loads(v)
        if v:
            out.append(v)
    return out


def short(h):
    first = h["authors"][0] if h["authors"] else ""
    t = h["title"]
    return {"pmid": h["pmid"], "arxiv_id": h["arxiv_id"], "doi": h["doi"], "year": h["year"],
            "first_author": surname(first) if first else "",
            "title": t if len(t) <= 100 else t[:99] + "…"}


# ---------------------------------------------------------------- probe

def cmd_probe(a, api):
    pfm, _ = split(a.profile.read_text())
    pfm = pfm or ""
    drafted = bool(a.probe)
    probes = a.probe or probes_of(pfm)
    if not probes:
        print(json.dumps({"error": "the profile has no recall_probes and no --probe was given"}))
        return 2
    w = scalar(pfm, "date_window_years").split("#")[0].strip()
    years = int(w) if w.isdigit() else 3
    vault = known(a.path)
    missing, results = [], []
    for n, q in enumerate(probes, 1):
        row = {"probe": n, "query": q}
        for src, run, query in (("pubmed", pubmed_search, windowed(q, years, "pubmed")),
                                ("arxiv", arxiv_search, windowed(arxiv_query(q), years, "arxiv"))):
            try:
                count, hits = run(api, query, a.max)
            except (NetError, ET.ParseError, ValueError) as e:
                row[src] = {"query": query, "error": str(e)}
                continue
            r = {"query": query, "count": count, "checked": len(hits), "in_vault": [], "missing": []}
            for rank, h in enumerate(hits, 1):
                i, key = match(h, vault)
                if i:
                    r["in_vault"].append({"rank": rank, "id": i, "key": key})
                    continue
                prev = next((m for m in missing if same(h, m["hit"])[0]), None)
                if prev is None:
                    prev = {"n": len(missing) + 1, "hit": h, "found_by": []}
                    missing.append(prev)
                prev["found_by"].append(f"probe {n} {src} #{rank}")
                r["missing"].append(prev["n"])
            if count > a.max:
                r["too_broad"] = True
            row[src] = r
        results.append(row)
    seeds = []
    for s in listval(pfm, "seed_papers"):
        i, key = match(seed_ident(s), vault)
        seeds.append({"seed": s, "in_vault": i, **({"key": key} if i else {})})
    print(json.dumps({
        "vault_papers": sum(1 for i, _ in vault if not i.startswith(MERGED)),
        "date_window_years": years,
        "probes_from": "--probe (drafted by the pipeline)" if drafted else "profile recall_probes",
        "probes": results,
        "missing": [{"n": m["n"], **short(m["hit"]), "found_by": m["found_by"]} for m in missing],
        "seed_papers": seeds,
    }, indent=1, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------- add

def surname(name):
    """The identity spec's surname slug: the part after the final space, or
    before the comma of "Last, First"; accents folded; a-z only."""
    s = name.split(",")[0] if "," in name else name.strip().split(" ")[-1]
    s = unicodedata.normalize("NFKD", s.lower().translate(FOLD))
    return re.sub(r"[^a-z]", "", s.encode("ascii", "ignore").decode())


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
    body = h["abstract"] or "(PubMed and arXiv returned no abstract for this paper.)"
    return "---\n" + "\n".join(ln.rstrip() for ln in lines) + "\n---\n\n## Abstract\n\n" + body + "\n"


def cmd_add(a, api):
    if not (a.pmid or a.arxiv):
        print(json.dumps({"error": "give at least one --pmid or --arxiv"}))
        return 2
    hits, not_found = [], []
    try:
        pm = efetch(api, [p.strip() for p in a.pmid])
        hits += [pm[p] for p in a.pmid if p in pm]
        not_found += [f"pmid:{p}" for p in a.pmid if p not in pm]
        ax = [re.sub(r"v\d+$", "", x.strip()) for x in a.arxiv]
        if ax:
            got, _ = parse_arxiv(api.text(f"{ARXIV_API}?" + qs(id_list=",".join(ax), max_results=len(ax))))
            hits += [got[x] for x in ax if x in got]
            not_found += [f"arxiv:{x}" for x in ax if x not in got]
    except (NetError, ET.ParseError) as e:
        print(json.dumps({"error": f"metadata lookup failed: {e}"}))
        return 1
    root = a.path
    vault = known(root)
    saved, skipped = [], []
    for h in hits:
        want = f"pmid:{h['pmid']}" if h["pmid"] else f"arxiv:{h['arxiv_id']}"
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
        rec = {"requested": want, "id": stem, "file": f.name, "full_text": "abstract-only"}
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
    p = sub.add_parser("probe")
    p.add_argument("path", type=Path)
    p.add_argument("--profile", type=Path, required=True)
    p.add_argument("--probe", action="append", default=[], help="a query to run instead of the profile's")
    p.add_argument("--max", type=int, default=60)
    d = sub.add_parser("add")
    d.add_argument("path", type=Path)
    d.add_argument("--pmid", action="append", default=[])
    d.add_argument("--arxiv", action="append", default=[])
    d.add_argument("--no-fetch", action="store_true")
    for s in (p, d):
        s.add_argument("--cache", type=Path)
        s.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    if not a.path.is_dir():
        print(json.dumps({"error": f"not a directory: {a.path}"}))
        return 2
    if a.cmd == "probe" and not a.profile.is_file():
        print(json.dumps({"error": f"no such profile: {a.profile}"}))
        return 2
    if a.offline and not (a.cache and a.cache.is_file()):
        print(json.dumps({"error": "--offline needs an existing --cache file"}))
        return 2
    a.path = a.path.resolve()
    api = Api(a.cache, a.offline)
    try:
        return cmd_probe(a, api) if a.cmd == "probe" else cmd_add(a, api)
    finally:
        api.save()


if __name__ == "__main__":
    sys.exit(main())
