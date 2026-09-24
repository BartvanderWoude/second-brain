#!/usr/bin/env python3
"""Compute paper-to-paper links for one problem's vault and write them into
each summary's `related_notes` / `related_basis` frontmatter.

Three kinds of link, from one Semantic Scholar batch request:
  direct-citation     one vault paper's references contain the other
  shared-references   the two share >= --min-shared references outside the vault
  similar-content     SPECTER2 (title + abstract) embeddings are close, for
                      pairs with no citation relation at all

Deterministic, symmetric and capped by construction. Stdlib only.
Prints a JSON report on stdout; exits 2 (with {"error": ...}) if the fetch fails.
"""
import argparse, itertools, json, math, os, re, sys, time, urllib.error, urllib.request
from pathlib import Path

S2_BATCH = "https://api.semanticscholar.org/graph/v1/paper/batch"
FIELDS = "title,externalIds,embedding.specter_v2,references.paperId"
BATCH_SIZE = 500
FM_RE = re.compile(r"\A---\n(.*?\n)---\n", re.S)


# ---------------------------------------------------------------- frontmatter

def scalar(fm, key):
    m = re.search(rf"^{key}:[ \t]*(.*)$", fm, re.M)
    if not m:
        return ""
    v = m.group(1).strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v


def block(fm, key):
    """(start, end, lines) of a top-level `key:` block and its indented lines."""
    m = re.search(rf"^{key}:.*\n(?:[ \t]+.*\n)*", fm, re.M)
    if not m:
        return None
    return m.start(), m.end(), m.group(0).splitlines()


def block_list(fm, key):
    b = block(fm, key)
    if not b:
        return []
    return [ln.strip()[2:].strip().strip("\"'") for ln in b[2][1:] if ln.strip().startswith("- ")]


def render_list(key, items):
    return f"{key}: []\n" if not items else f"{key}:\n" + "".join(f"  - {i}\n" for i in items)


def render_map(key, pairs):
    return f"{key}: {{}}\n" if not pairs else f"{key}:\n" + "".join(f"  {k}: {v}\n" for k, v in pairs)


def norm_doi(d):
    d = d.strip().lower()
    for p in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(p):
            d = d[len(p):]
    return d


def s2_ident(fm):
    """Semantic Scholar batch id from a frontmatter block, or None: an arXiv id,
    then a DOI, then a PMID, then a Semantic Scholar paper URL's 40-hex id."""
    url = scalar(fm, "url")
    m = re.search(r"arxiv\.org/(?:abs|pdf)/(.+?)(?:v\d+)?(?:\.pdf)?/?$", url)
    arxiv = re.sub(r"v\d+$", "", scalar(fm, "arxiv_id")) or (m.group(1) if m else "")
    doi = norm_doi(scalar(fm, "doi"))
    pmid = scalar(fm, "pmid") or (re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", url) or [None, ""])[1]
    s2 = re.search(r"semanticscholar\.org/paper/(?:[^/?#]+/)?([0-9a-f]{40})\b", url)
    return (f"arXiv:{arxiv}" if arxiv else
            f"DOI:{doi}" if doi else
            f"PMID:{pmid}" if pmid else
            s2.group(1) if s2 else None)


def load_vault(summaries):
    """One entry per summary. A summary with no identifier of its own falls back
    to the header of its paper file (summaries/<stem>_summary.md -> <stem>.md),
    and one with no `id` to <stem>, the paper id by the paper-identity spec."""
    papers = []
    for f in sorted(summaries.glob("*.md")):
        text = f.read_text()
        m = FM_RE.match(text)
        if not m:
            continue
        fm = m.group(1)
        stem = f.stem[:-len("_summary")] if f.stem.endswith("_summary") else f.stem
        s2id = s2_ident(fm)
        paper = summaries.parent / f"{stem}.md"
        if not s2id and paper.is_file():
            pm = FM_RE.match(paper.read_text())
            s2id = s2_ident(pm.group(1)) if pm else None
        papers.append({"file": f, "text": text, "id": scalar(fm, "id") or stem, "s2id": s2id,
                       "related": block_list(fm, "related_notes")})
    return papers


# ---------------------------------------------------------------- fetch

def fetch(ids, cache, refresh, budget_s):
    """Fill `cache` (s2id -> record or None) for ids not yet cached. Flat retry on
    429: the limit is a shared quota, so waiting longer does not help."""
    todo = [i for i in ids if refresh or cache.get(i) is None]
    key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    deadline = time.time() + budget_s
    for n in range(0, len(todo), BATCH_SIZE):
        chunk = todo[n:n + BATCH_SIZE]
        req = urllib.request.Request(
            f"{S2_BATCH}?fields={FIELDS}", data=json.dumps({"ids": chunk}).encode(),
            headers={"Content-Type": "application/json", **({"x-api-key": key} if key else {})})
        while True:
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    for i, rec in zip(chunk, json.load(r)):
                        cache[i] = rec
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 and e.code < 500:
                    raise RuntimeError(f"Semantic Scholar returned HTTP {e.code}")
            except (urllib.error.URLError, TimeoutError) as e:
                if time.time() > deadline:
                    raise RuntimeError(f"Semantic Scholar unreachable: {e}")
            if time.time() > deadline:
                raise RuntimeError(f"Semantic Scholar still rate-limiting after {budget_s}s; "
                                   "set SEMANTIC_SCHOLAR_API_KEY or retry later")
            time.sleep(1.5)
    return len(todo)


# ---------------------------------------------------------------- edges

def cosine(u, v):
    return sum(a * b for a, b in zip(u, v)) / math.sqrt(sum(a * a for a in u) * sum(b * b for b in v))


def compute(papers, cache, a):
    known = [p for p in papers if p["s2id"] and cache.get(p["s2id"])]
    rec = {p["id"]: cache[p["s2id"]] for p in known}
    pid = {i: r["paperId"] for i, r in rec.items()}
    vault_pids = set(pid.values())
    refs = {i: {x["paperId"] for x in (r.get("references") or []) if x.get("paperId")} for i, r in rec.items()}
    emb = {i: (r.get("embedding") or {}).get("vector") for i, r in rec.items()}
    emb = {i: v for i, v in emb.items() if v}

    ids = sorted(rec)
    citation = {}  # pair -> (rank key, basis)
    for x, y in itertools.combinations(ids, 2):
        if pid[y] in refs[x] or pid[x] in refs[y]:
            citation[(x, y)] = ((1, 0), "direct-citation")
        else:
            n = len((refs[x] & refs[y]) - vault_pids)
            if n >= a.min_shared:
                citation[(x, y)] = ((0, n), f'"shared-references ({n})"')

    # SPECTER2 cosines are compressed (0.76-0.97 on the calibration vault): the
    # floor separates fields, and the per-paper slots below keep only the best
    # neighbours, so no vault-relative percentile is needed (in a one-topic
    # vault it would climb above genuine neighbours).
    sims = {(x, y): cosine(emb[x], emb[y]) for x, y in itertools.combinations(sorted(emb), 2)}
    semantic = {pr: s for pr, s in sims.items() if pr not in citation and s >= a.sim_floor}

    # greedy in one global order; an edge lands on both papers or neither
    chosen, c_used, s_used = {}, {}, {}
    for pr, (k, basis) in sorted(citation.items(), key=lambda kv: (-kv[1][0][0], -kv[1][0][1], kv[0])):
        if all(c_used.get(i, 0) < a.citation_slots for i in pr):
            chosen[pr] = basis
            for i in pr:
                c_used[i] = c_used.get(i, 0) + 1
    for pr, s in sorted(semantic.items(), key=lambda kv: (-kv[1], kv[0])):
        if all(s_used.get(i, 0) < a.semantic_slots for i in pr):
            chosen[pr] = f'"similar-content ({s:.3f})"'
            for i in pr:
                s_used[i] = s_used.get(i, 0) + 1
    return chosen, set(rec), set(emb)


# ---------------------------------------------------------------- write

def rewrite(p, links, owned_before):
    """New file text: researcher entries kept in place, script entries replaced."""
    m = FM_RE.match(p["text"])
    fm = m.group(1)
    mine = set(owned_before)
    researcher = [r for r in p["related"] if r not in mine]
    computed = [i for i, _ in links]
    new_related = researcher + [i for i in computed if i not in researcher]
    owned_now = [i for i in computed if i not in researcher]
    stale = [i for i in p["related"] if i in mine and i not in computed]

    b = block(fm, "related_notes")
    new_rel = render_list("related_notes", new_related)
    new_basis = render_map("related_basis", links)
    if b:
        fm2 = fm[:b[0]] + new_rel + fm[b[1]:]
    else:
        fm2 = fm + new_rel
    bb = block(fm2, "related_basis")
    if bb:
        fm2 = fm2[:bb[0]] + new_basis + fm2[bb[1]:]
    else:
        at = block(fm2, "related_notes")[1]
        fm2 = fm2[:at] + new_basis + fm2[at:]
    return "---\n" + fm2 + "---\n" + p["text"][m.end():], owned_now, stale


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--summaries", required=True, type=Path)
    ap.add_argument("--state", required=True, type=Path, help="cache + ownership dir, e.g. <paper_vault_path>/.linker/")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="ignore cached Semantic Scholar data")
    ap.add_argument("--offline", action="store_true", help="use cached data only; never touch the network")
    ap.add_argument("--citation-slots", type=int, default=5)
    ap.add_argument("--semantic-slots", type=int, default=3)
    ap.add_argument("--min-shared", type=int, default=2)
    ap.add_argument("--sim-floor", type=float, default=0.90,
                    help="min SPECTER2 cosine for a content link; calibrated: same-field pairs "
                         "0.92-0.97, cross-field (CT imaging vs time-series) <= 0.861")
    ap.add_argument("--fetch-budget", type=int, default=600, help="seconds to keep retrying a rate-limited fetch")
    a = ap.parse_args()

    if not a.summaries.is_dir():
        print(json.dumps({"error": f"summaries directory not found: {a.summaries}"}))
        return 2
    papers = load_vault(a.summaries)
    cache_f, owned_f = a.state / "s2_cache.json", a.state / "owned.json"
    cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}
    owned = json.loads(owned_f.read_text()) if owned_f.exists() else {}

    t0 = time.time()
    fetched = 0
    if not a.offline:
        try:
            fetched = fetch([p["s2id"] for p in papers if p["s2id"]], cache, a.refresh, a.fetch_budget)
        except RuntimeError as e:
            print(json.dumps({"error": str(e)}))
            return 2
    fetch_s = round(time.time() - t0, 1)

    chosen, in_s2, with_emb = compute(papers, cache, a)
    per = {p["id"]: [] for p in papers}
    for (x, y), basis in chosen.items():
        per[x].append((y, basis))
        per[y].append((x, basis))

    changed, stale_total = 0, 0
    new_owned = {}
    for p in papers:
        links = sorted(per[p["id"]], key=lambda t: t[0])
        text, owned_now, stale = rewrite(p, links, owned.get(p["file"].name, []))
        new_owned[p["file"].name] = owned_now
        stale_total += len(stale)
        if text != p["text"]:
            changed += 1
            if not a.dry_run:
                p["file"].write_text(text)
    if not a.dry_run:
        a.state.mkdir(parents=True, exist_ok=True)
        cache_f.write_text(json.dumps(cache))
        owned_f.write_text(json.dumps(new_owned, indent=1, sort_keys=True))

    kinds = {"direct-citation": 0, "shared-references": 0, "similar-content": 0}
    for basis in chosen.values():
        kinds[basis.strip('"').split(" ")[0]] += 1
    print(json.dumps({
        "papers": len(papers),
        "no_identifier": [p["id"] for p in papers if not p["s2id"]],
        "not_in_s2": [p["id"] for p in papers if p["s2id"] and p["id"] not in in_s2],
        "no_content_links_possible": [p["id"] for p in papers if p["id"] in in_s2 and p["id"] not in with_emb],
        "embedding_coverage": f"{len(with_emb)}/{len(papers)}",
        "edges": kinds,
        "zero_edge_papers": [i for i, l in per.items() if not l],
        "similarity_floor": a.sim_floor,
        "stale_entries_removed": stale_total,
        "files_changed": changed,
        "papers_fetched": fetched,
        "fetch_seconds": fetch_s,
        "dry_run": a.dry_run,
    }, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
