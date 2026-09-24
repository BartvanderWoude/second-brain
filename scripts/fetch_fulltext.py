#!/usr/bin/env python3
"""Upgrade a saved paper record from abstract-only to full text, in place.

A record is a paper file in the "Saved paper file" format of
templates/paper-identity-spec.md: an identity header, then the abstract or the
paper's text. This script reads the ids from the header, finds an open-access
copy, and on success replaces the body and sets `full_text: full`,
`full_text_source` and `extraction_warning`. Open-access rungs, in order:

  europepmc-xml   Europe PMC full-text XML (the open-access PMC subset),
                  converted from JATS directly: no PDF, so no mangled digits
  pmc-bioc        NCBI's BioC text of a PMC article, which also covers the NIH
                  author manuscripts Europe PMC's XML endpoint does not serve
  arxiv-pdf       https://arxiv.org/pdf/<arxiv_id>
  s2-oa-pdf       Semantic Scholar's openAccessPdf
  unpaywall-pdf   Unpaywall's OA locations (needs UNPAYWALL_EMAIL)

Every download must start with %PDF- before Docling sees it: some sources answer
bots with an HTML page, and a download tool has saved exactly that as a .pdf.
Docling output under 10 KB is retried with OCR; output with substituted glyphs
for digits is retried with full-page OCR, and flagged if that does not help.

  --record FILE [FILE ...]       try the rungs for these records
  --record FILE --from-pdf PDF   convert a PDF already on disk (Sci-Hub, manual)
  --vault DIR                    every abstract-only record in DIR

One --record prints that record's report; several, or --vault, print
{"records": [...], "upgraded": [...], "still_abstract_only": [...]}.

Stdlib only (Docling runs as a subprocess). Prints a JSON report. Exit 0 whether
or not full text was found -- that is a result, not an error -- and 2 on bad input.
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, time
import urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from link_papers import FM_RE, norm_doi, s2_ident, scalar

UA = "second-brain-researcher/1.0 (research literature pipeline; open-access full-text fetch)"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
BIOC = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json"
S2 = "https://api.semanticscholar.org/graph/v1/paper"
UNPAYWALL = "https://api.unpaywall.org/v2"
MIN_BODY = 10_000   # below this a "full text" is an empty shell (scanned PDF, failed fetch)
GARBLE_MIN = 5      # substituted-glyph count that marks garbled digits


# ---------------------------------------------------------------- http

class NetError(Exception):
    pass


def get(url, accept=None, headers=None, timeout=60, tries=2):
    """(status, content-type, body). Retries 429/5xx and network errors with a
    growing wait; raises NetError when the host cannot be reached at all."""
    h = {"User-Agent": UA, **({"Accept": accept} if accept else {}), **(headers or {})}
    for n in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
                return r.status, r.headers.get("Content-Type", ""), r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and n + 1 < tries:
                time.sleep(3 * (n + 1))
                continue
            return e.code, "", b""
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if n + 1 < tries:
                time.sleep(3 * (n + 1))
                continue
            raise NetError(str(getattr(e, "reason", e)))


def attempt(rung, outcome, detail, **kw):
    """outcome: ok | no-oa (the source says there is no open copy) | located-failed
    (an open copy exists but could not be used) | error (unreachable) | skipped"""
    return {"rung": rung, "outcome": outcome, "detail": detail, **kw}


# ---------------------------------------------------------------- pdf -> md

def sniff(data):
    head = data[:1024]
    if b"%PDF-" in head:
        return "pdf"
    if not data:
        return "empty-response"
    if re.search(rb"<!doctype html|<html|<head|<body", head, re.I):
        return "html-not-pdf"
    return "not-a-pdf"


def garbled(md):
    """Count of glyphs PDF extraction substitutes for digits (seen: U+0376-U+037F
    for 0-9). The Private Use Area is not counted: fonts use it for bullets."""
    return sum(1 for c in md if 0x370 <= ord(c) <= 0x37F or c == "\ufffd")


def docling(pdf, tmp, mode):
    out = Path(tmp) / f"docling-{mode}"
    out.mkdir(exist_ok=True)
    flags = {"text": ["--no-ocr"], "ocr": ["--ocr"], "full_page": ["--ocr", "--ocr-mode", "full_page"]}[mode]
    subprocess.run(["docling", "convert", "--to", "md", "--image-export-mode", "placeholder",
                    *flags, "--output", str(out), str(pdf)],
                   capture_output=True, text=True, timeout=1800)
    f = out / (Path(pdf).stem + ".md")
    return f.read_text() if f.exists() else ""


def convert_pdf(pdf, tmp, rung):
    """An attempt: ok with markdown, or located-failed with the reason."""
    if not shutil.which("docling"):
        return attempt(rung, "located-failed", "docling not installed (uv tool install docling)",
                       docling_missing=True)
    md = docling(pdf, tmp, "text")
    if len(md.encode()) < MIN_BODY:  # born-digital assumption failed: a scanned PDF
        md = max(md, docling(pdf, tmp, "ocr"), key=len)
    warning = ""
    if garbled(md) >= GARBLE_MIN:
        redo = docling(pdf, tmp, "full_page")
        if len(redo.encode()) >= MIN_BODY and garbled(redo) < GARBLE_MIN:
            md = redo
        else:
            warning = "garbled-digits"
    if len(md.encode()) < MIN_BODY:
        return attempt(rung, "located-failed", f"conversion produced only {len(md.encode())} bytes")
    return attempt(rung, "ok", f"{len(md.encode())} bytes via Docling", markdown=md, warning=warning)


def fetch_pdf(url, tmp, rung):
    host = urllib.parse.urlparse(url).netloc
    try:
        st, _, data = get(url, accept="application/pdf,*/*;q=0.5", timeout=120)
    except NetError as e:
        return attempt(rung, "error", f"{host} unreachable: {e}")
    if st != 200:
        return attempt(rung, "located-failed", f"HTTP {st} from {host}")
    kind = sniff(data)
    if kind != "pdf":
        return attempt(rung, "located-failed", f"{kind} from {host}")
    pdf = Path(tmp) / f"{rung}.pdf"
    pdf.write_bytes(data)
    return convert_pdf(pdf, tmp, rung)


# ---------------------------------------------------------------- jats -> md

def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def child(el, name):
    return next((c for c in el if local(c.tag) == name), None)


def squash(t):
    return re.sub(r"\s+", " ", t or "")


def tex_of(el):
    """A formula's LaTeX from <tex-math>, else MathML alttext/text."""
    for d in el.iter():
        if local(d.tag) == "tex-math" and d.text:
            t = d.text
            m = re.search(r"\\begin\{document\}(.*)\\end\{document\}", t, re.S)
            t = (m.group(1) if m else t).strip()
            return re.sub(r"^\$+|\$+$", "", t).strip()
    for d in el.iter():
        if local(d.tag) == "math":
            return d.get("alttext") or squash("".join(d.itertext())).strip()
    return squash("".join(el.itertext())).strip()


def inline(el):
    parts = []

    def walk(e):
        n = local(e.tag)
        if n == "inline-formula":
            parts.append(f"${tex_of(e)}$")
        elif n == "disp-formula":
            parts.append(f"\n\n$$ {tex_of(e)} $$\n\n")
        elif n in ("list", "table-wrap", "fig"):
            parts.append("\n\n" + block(e) + "\n\n")
        elif n in ("sup", "sub"):
            t = squash("".join(e.itertext())).strip()
            parts.append(("^" if n == "sup" else "_") + (t if len(t) <= 1 else f"({t})"))
        else:
            parts.append(squash(e.text))
            for c in e:
                walk(c)
                parts.append(squash(c.tail))

    parts.append(squash(el.text))
    for c in el:
        walk(c)
        parts.append(squash(c.tail))
    return "\n".join(ln.strip() for ln in "".join(parts).strip().split("\n"))


def table_md(tw):
    out = []
    label, cap = child(tw, "label"), child(tw, "caption")
    head = " ".join(x for x in (inline(label) if label is not None else "",
                                inline(cap) if cap is not None else "") if x)
    if head:
        out.append(f"**{head}**")
    rows = [[inline(c).replace("|", "\\|").replace("\n", " ") for c in tr if local(c.tag) in ("th", "td")]
            for tr in tw.iter() if local(tr.tag) == "tr"]
    rows = [r for r in rows if r]
    if rows:
        w = max(len(r) for r in rows)
        rows = [r + [""] * (w - len(r)) for r in rows]
        out.append("\n".join(["| " + " | ".join(rows[0]) + " |", "|" + "---|" * w] +
                             ["| " + " | ".join(r) + " |" for r in rows[1:]]))
    foot = child(tw, "table-wrap-foot")
    if foot is not None:
        out.append(squash("".join(foot.itertext())).strip())
    return "\n\n".join(out)


def block(e):
    n = local(e.tag)
    if n == "p":
        return inline(e)
    if n == "list":
        return "\n".join("- " + " ".join(block(p) for p in item if local(p.tag) in ("p", "list"))
                         for item in e if local(item.tag) == "list-item")
    if n == "disp-formula":
        label = child(e, "label")
        return f"$$ {tex_of(e)} $$" + (f"  ({squash(label.text).strip()})" if label is not None and label.text else "")
    if n == "table-wrap":
        return table_md(e)
    if n == "fig":
        label, cap = child(e, "label"), child(e, "caption")
        text = " ".join(x for x in (inline(label) if label is not None else "",
                                    inline(cap) if cap is not None else "") if x)
        return f"[Figure: {text}]" if text else "[Figure]"
    return ""


def section(el, level, out):
    for c in el:
        n = local(c.tag)
        if n in ("title", "label", "sec-meta"):
            continue
        if n == "ref-list":  # under <back> in classic JATS, inside a <sec> in some Europe PMC XML
            title = child(c, "title")
            text = (inline(title).replace("\n", " ") if title is not None else "") or "References"
            if not (out and out[-1].startswith("#") and out[-1].lstrip("# ").lower() == text.lower()):
                out.append("#" * min(level, 6) + " " + text)
            refs = [r for r in c if local(r.tag) == "ref"]
            if refs:
                out.append("\n".join(f"{i}. {cite(r)}" for i, r in enumerate(refs, 1)))
            continue
        if n == "sec" or n in ("ack", "app", "boxed-text", "fn-group", "glossary", "notes"):
            title = child(c, "title")
            if title is not None and "".join(title.itertext()).strip():
                out.append("#" * min(level, 6) + " " + inline(title).replace("\n", " "))
            section(c, level + 1, out)
        elif n in ("app-group", "statement", "disp-quote", "def-list", "table-wrap-group", "fig-group"):
            section(c, level, out)
        else:
            b = block(c)
            if b:
                out.append(b)


def cite(ref):
    c = next((x for x in ref if local(x.tag) in ("mixed-citation", "element-citation", "citation")), None)
    if c is None:
        return squash("".join(ref.itertext())).strip()
    if local(c.tag) == "mixed-citation":
        return inline(c).replace("\n", " ")
    fields = []
    for x in c:
        if local(x.tag) == "person-group":
            names = [" ".join(squash("".join(p.itertext())).strip() for p in nm) for nm in x
                     if local(nm.tag) in ("name", "string-name")]
            fields.append(", ".join(names))
        elif local(x.tag) == "pub-id":
            fields.append(f"{x.get('pub-id-type', 'id')}:{squash(x.text).strip()}")
        else:
            fields.append(squash("".join(x.itertext())).strip())
    return ". ".join(f for f in fields if f)


def jats_to_md(data):
    """Markdown from Europe PMC / PMC JATS XML; None when it holds no body text."""
    root = ET.fromstring(data)
    body = next((e for e in root.iter() if local(e.tag) == "body"), None)
    if body is None or len(squash("".join(body.itertext())).strip()) < 500:
        return None
    out = []
    t = next((e for e in root.iter() if local(e.tag) == "article-title"), None)
    if t is not None:
        out.append("# " + inline(t).replace("\n", " "))
    abstracts = [e for e in root.iter() if local(e.tag) == "abstract"]
    ab = next((a for a in abstracts if not a.get("abstract-type")), abstracts[0] if abstracts else None)
    if ab is not None:
        out.append("## Abstract")
        section(ab, 3, out)
    section(body, 2, out)
    back = next((e for e in root.iter() if local(e.tag) == "back"), None)
    if back is not None:
        section(back, 2, out)
    return "\n\n".join(b for b in out if b.strip()) + "\n"


def bioc_to_md(data):
    """Markdown from a BioC JSON collection; None when it holds no body text."""
    try:
        coll = json.loads(data)
    except ValueError:  # the service answers a missing article with plain text
        return None
    coll = coll[0] if isinstance(coll, list) and coll else coll
    docs = coll.get("documents") if isinstance(coll, dict) else None
    if not docs:
        return None
    out, refs, abstract, body_chars = [], [], False, 0
    for p in docs[0].get("passages", []):
        inf, text = p.get("infons") or {}, squash(p.get("text")).strip()
        kind, sec = inf.get("type", ""), inf.get("section_type", "")
        if kind == "ref":
            names = [" ".join(v.split(":", 1)[-1] for v in inf[k].split(";"))
                     for k in sorted((k for k in inf if k.startswith("name_")), key=lambda k: int(k[5:]))]
            who = ", ".join(names[:3]) + (" et al." if len(names) > 3 else "")
            where = " ".join(x for x in (inf.get("source", ""), inf.get("year", "")) if x)
            refs.append(". ".join(x for x in (who, text, where) if x))
            continue
        if not text and kind != "table":
            continue
        if sec == "ABSTRACT" and not abstract:
            out.append("## Abstract")
            abstract = True
        if kind == "front":
            out.append("# " + text)
        elif kind.startswith("abstract_title"):
            out.append("### " + text)
        elif re.fullmatch(r"title(_\d+)?", kind):
            level = int(kind[6:]) if kind[6:].isdigit() else 1
            out.append("#" * min(level + 1, 6) + " " + text)
        elif kind == "table":
            try:
                out.append(table_md(ET.fromstring(inf["xml"])))
            except (KeyError, ET.ParseError):
                out.append(text)
        elif kind == "table_caption":
            out.append(f"**{text}**")
        elif kind == "fig_caption":
            out.append(f"[Figure: {text}]")
        else:
            out.append(text)
            if sec not in ("ABSTRACT", "TITLE"):
                body_chars += len(text)
    if body_chars < 500:
        return None
    if refs:
        out.append("## References")
        out.append("\n".join(f"{i}. {r}" for i, r in enumerate(refs, 1)))
    return "\n\n".join(b for b in out if b.strip()) + "\n"


# ---------------------------------------------------------------- rungs

def rung_europepmc(ids, tmp, found):
    rung = "europepmc-xml"
    pmcid = ids["pmcid"]
    try:
        if not pmcid:
            q = (f'DOI:"{ids["doi"]}"' if ids["doi"] else
                 f"EXT_ID:{ids['pmid']} AND SRC:MED" if ids["pmid"] else None)
            if not q:
                return attempt(rung, "skipped", "no DOI, PMID or PMCID")
            st, _, data = get(f"{EPMC}/search?" + urllib.parse.urlencode(
                {"query": q, "format": "json", "resultType": "lite", "pageSize": 1}))
            if st != 200:
                return attempt(rung, "error", f"Europe PMC search HTTP {st}")
            res = (json.loads(data).get("resultList") or {}).get("result") or []
            if not res or not res[0].get("pmcid"):
                return attempt(rung, "no-oa", "not in PubMed Central")
            pmcid = ids["pmcid"] = found["pmcid"] = res[0]["pmcid"]
            if res[0].get("isOpenAccess") != "Y" and res[0].get("inEPMC") != "Y":
                return attempt(rung, "no-oa", f"{pmcid} has no open full text")
        st, _, data = get(f"{EPMC}/{pmcid}/fullTextXML", accept="application/xml")
    except NetError as e:
        return attempt(rung, "error", f"Europe PMC unreachable: {e}")
    if st == 404:
        return attempt(rung, "no-oa", f"{pmcid}: no full-text XML")
    if st != 200:
        return attempt(rung, "error", f"{pmcid}: HTTP {st}")
    try:
        md = jats_to_md(data)
    except ET.ParseError as e:
        return attempt(rung, "located-failed", f"{pmcid}: unreadable XML ({e})")
    if md is None:
        return attempt(rung, "located-failed", f"{pmcid}: XML carries no body text")
    return attempt(rung, "ok", f"{pmcid}, {len(md.encode())} bytes", markdown=md, warning="")


def rung_bioc(ids, tmp, found):
    rung = "pmc-bioc"
    if not ids["pmcid"]:
        return attempt(rung, "skipped", "no PMCID")
    try:
        st, _, data = get(f"{BIOC}/{ids['pmcid']}/unicode", accept="application/json")
    except NetError as e:
        return attempt(rung, "error", f"NCBI BioC unreachable: {e}")
    if st == 404:
        return attempt(rung, "no-oa", f"{ids['pmcid']}: not in PMC's text-mining sets")
    if st != 200:
        return attempt(rung, "error", f"{ids['pmcid']}: HTTP {st}")
    md = bioc_to_md(data)
    if md is None:
        return attempt(rung, "no-oa", f"{ids['pmcid']}: not in PMC's text-mining sets")
    return attempt(rung, "ok", f"{ids['pmcid']}, {len(md.encode())} bytes", markdown=md, warning="")


def rung_arxiv(ids, tmp, found):
    if not ids["arxiv"]:
        return attempt("arxiv-pdf", "skipped", "no arXiv id")
    return fetch_pdf(f"https://arxiv.org/pdf/{ids['arxiv']}", tmp, "arxiv-pdf")


def s2_lookup(ids, found):
    """Semantic Scholar's record for the paper (externalIds, openAccessPdf),
    fetched once per record: (record or None, error detail or None)."""
    if "s2" not in found:
        key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        try:
            st, _, data = get(f"{S2}/{urllib.parse.quote(ids['s2'], safe=':/')}?fields=externalIds,openAccessPdf",
                              headers={"x-api-key": key} if key else None, tries=6)
            found["s2"] = (json.loads(data), None) if st == 200 else \
                (None, "not in Semantic Scholar" if st == 404 else f"Semantic Scholar HTTP {st}")
        except NetError as e:
            found["s2"] = (None, f"Semantic Scholar unreachable: {e}")
    return found["s2"]


def learn_ids(ids, found):
    """Fill the ids a record lacks from Semantic Scholar's externalIds. A record
    saved from Semantic Scholar often has no DOI or PMID in its header, and then
    the Europe PMC rung has nothing to look it up by, even when the paper is in PMC."""
    if not ids["s2"] or all(ids[k] for k in ("doi", "pmid", "pmcid", "arxiv")):
        return
    rec, _ = s2_lookup(ids, found)
    ext = (rec or {}).get("externalIds") or {}
    for k, v in (("doi", norm_doi(ext.get("DOI") or "")), ("pmid", str(ext.get("PubMed") or "")),
                 ("pmcid", f"PMC{ext['PubMedCentral']}" if ext.get("PubMedCentral") else ""),
                 ("arxiv", ext.get("ArXiv") or "")):
        if v and not ids[k]:
            ids[k] = found[k] = v


def rung_s2(ids, tmp, found):
    rung = "s2-oa-pdf"
    if not ids["s2"]:
        return attempt(rung, "skipped", "no identifier Semantic Scholar resolves")
    rec, problem = s2_lookup(ids, found)
    if rec is None:
        return attempt(rung, "no-oa" if problem == "not in Semantic Scholar" else "error", problem)
    url = (rec.get("openAccessPdf") or {}).get("url")
    if not url:
        return attempt(rung, "no-oa", "no open-access PDF listed")
    return fetch_pdf(url, tmp, rung)


def rung_unpaywall(ids, tmp, found):
    rung = "unpaywall-pdf"
    email = os.environ.get("UNPAYWALL_EMAIL") or os.environ.get("PAPER_SEARCH_MCP_UNPAYWALL_EMAIL")
    if not ids["doi"]:
        return attempt(rung, "skipped", "no DOI")
    if not email:
        return attempt(rung, "skipped", "UNPAYWALL_EMAIL not set")
    try:
        st, _, data = get(f"{UNPAYWALL}/{urllib.parse.quote(ids['doi'])}?" + urllib.parse.urlencode({"email": email}))
    except NetError as e:
        return attempt(rung, "error", f"Unpaywall unreachable: {e}")
    if st == 404:
        return attempt(rung, "no-oa", "DOI unknown to Unpaywall")
    if st != 200:
        return attempt(rung, "error", f"Unpaywall HTTP {st}")
    j = json.loads(data)
    if not j.get("is_oa"):
        return attempt(rung, "no-oa", "not open access")
    urls = []
    for loc in [j.get("best_oa_location") or {}] + (j.get("oa_locations") or []):
        u = loc.get("url_for_pdf")
        if u and u not in urls:
            urls.append(u)
    if not urls:
        return attempt(rung, "located-failed", "open access, but only a landing page is listed")
    last = None
    for u in urls[:3]:
        last = fetch_pdf(u, tmp, rung)
        if last["outcome"] == "ok":
            return last
    return last


RUNGS = (rung_europepmc, rung_bioc, rung_arxiv, rung_s2, rung_unpaywall)


# ---------------------------------------------------------------- record

def set_field(fm, key, value):
    line = f"{key}: {value}".rstrip() + "\n"
    if re.search(rf"^{key}:.*\n", fm, re.M):
        return re.sub(rf"^{key}:.*\n", lambda _: line, fm, count=1, flags=re.M)
    return fm + line


def ids_of(fm):
    url = scalar(fm, "url")
    m = re.search(r"arxiv\.org/(?:abs|pdf)/(.+?)(?:v\d+)?(?:\.pdf)?/?$", url)
    return {
        "doi": norm_doi(scalar(fm, "doi")),
        "pmid": scalar(fm, "pmid") or (re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", url) or [None, ""])[1],
        "pmcid": scalar(fm, "pmcid"),
        "arxiv": re.sub(r"v\d+$", "", scalar(fm, "arxiv_id")) or (m.group(1) if m else ""),
        "s2": s2_ident(fm),
    }


def process(path, force=False, from_pdf=None, from_xml=None, source="manual"):
    text = path.read_text()
    m = FM_RE.match(text)
    if not m:
        raise ValueError(f"{path.name} has no header; save it per templates/paper-identity-spec.md first")
    fm, body = m.group(1), text[m.end():]
    report = {"record": path.name, "id": scalar(fm, "id")}
    if scalar(fm, "full_text") == "full" and not (force or from_pdf or from_xml):
        return {**report, "full_text": "full", "full_text_source": scalar(fm, "full_text_source"),
                "changed": False, "attempts": [], "note": "already full text; pass --force to refetch"}

    found, attempts, win = {}, [], None
    with tempfile.TemporaryDirectory() as tmp:
        if from_pdf:
            data = Path(from_pdf).read_bytes()
            kind = sniff(data)
            win = convert_pdf(from_pdf, tmp, source) if kind == "pdf" else \
                attempt(source, "located-failed", f"{kind}: {Path(from_pdf).name} is not a PDF")
            attempts.append(win)
        elif from_xml:
            md = jats_to_md(Path(from_xml).read_bytes())
            win = attempt("europepmc-xml", "ok", "from file", markdown=md, warning="") if md else \
                attempt("europepmc-xml", "located-failed", "XML carries no body text")
            attempts.append(win)
        else:
            ids = ids_of(fm)
            learn_ids(ids, found)
            for rung in RUNGS:
                win = rung(ids, tmp, found)
                attempts.append(win)
                if win["outcome"] == "ok":
                    break

    fm2 = fm
    for key, field in (("doi", "doi"), ("pmid", "pmid"), ("pmcid", "pmcid"), ("arxiv", "arxiv_id")):
        if found.get(key) and not scalar(fm, field):
            fm2 = set_field(fm2, field, f'"{found[key]}"' if key == "pmid" else found[key])
    # paywalled describes the paper: an open copy located anywhere settles it
    # false; it becomes true only if blank and every source that answered said no.
    if not (from_pdf or from_xml):
        outcomes = {a["outcome"] for a in attempts}
        if outcomes & {"ok", "located-failed"}:
            fm2 = set_field(fm2, "paywalled", "false")
        elif "no-oa" in outcomes and "error" not in outcomes and not scalar(fm, "paywalled"):
            fm2 = set_field(fm2, "paywalled", "true")
    ok = win is not None and win["outcome"] == "ok"
    if ok:
        fm2 = set_field(fm2, "full_text", "full")
        fm2 = set_field(fm2, "full_text_source", win["rung"])
        fm2 = set_field(fm2, "extraction_warning", win.get("warning", ""))
        body = "\n" + win["markdown"].strip() + "\n"
    new = "---\n" + fm2 + "---\n" + body
    if new != text:
        path.write_text(new)
    report.update({
        "full_text": "full" if ok else scalar(fm2, "full_text") or "abstract-only",
        "full_text_source": scalar(fm2, "full_text_source"),
        "extraction_warning": scalar(fm2, "extraction_warning"),
        "paywalled": scalar(fm2, "paywalled"),
        "body_bytes": len(body.encode()),
        "changed": new != text,
        "attempts": [{k: v for k, v in a.items() if k not in ("markdown", "warning")} for a in attempts],
    })
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--record", type=Path, nargs="+", help="saved paper record(s)")
    g.add_argument("--vault", type=Path, help="every abstract-only record in this paper vault")
    ap.add_argument("--from-pdf", type=Path, help="with --record: convert this PDF instead of fetching")
    ap.add_argument("--source", default="manual", choices=["manual", "scihub-pdf"],
                    help="with --from-pdf: the full_text_source to record")
    ap.add_argument("--from-xml", type=Path, help=argparse.SUPPRESS)  # offline test of the JATS path
    ap.add_argument("--force", action="store_true", help="refetch records that already have full text")
    a = ap.parse_args()

    try:
        if a.record:
            for r in a.record:
                if not r.is_file():
                    raise ValueError(f"no such record: {r}")
            if (a.from_pdf or a.from_xml) and len(a.record) > 1:
                raise ValueError("--from-pdf and --from-xml take one --record")
            for extra in (a.from_pdf, a.from_xml):
                if extra and not extra.is_file():
                    raise ValueError(f"no such file: {extra}")
            if len(a.record) == 1:
                print(json.dumps(process(a.record[0], a.force, a.from_pdf, a.from_xml, a.source), indent=1))
                return 0
        elif a.from_pdf or a.from_xml:
            raise ValueError("--from-pdf and --from-xml take one --record, not --vault")
        elif not a.vault.is_dir():
            raise ValueError(f"not a directory: {a.vault}")
    except ValueError as e:
        print(json.dumps({"error": str(e)}))
        return 2

    reports = []
    if a.record:
        for f in a.record:  # one record's bad header must not cost the others theirs
            try:
                reports.append(process(f, a.force))
            except ValueError as e:
                reports.append({"record": f.name, "id": f.stem, "full_text": "unchanged", "error": str(e)})
    else:
        for f in sorted(a.vault.glob("*.md")):
            m = FM_RE.match(f.read_text())
            if not m or (scalar(m.group(1), "full_text") == "full" and not a.force):
                continue
            reports.append(process(f, a.force))
    print(json.dumps({
        "records": reports,
        "upgraded": [r["id"] for r in reports if r.get("changed") and r["full_text"] == "full"],
        "still_abstract_only": [r["id"] for r in reports if r["full_text"] != "full"],
    }, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
