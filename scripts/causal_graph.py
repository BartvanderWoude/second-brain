#!/usr/bin/env python3
"""Deterministic steps of a causal-graph run (CAUSAL_GRAPH_DESIGN.md), over the
files templates/causal-claims-spec.md defines. Stdlib only. Every report is
compact JSON on stdout; exit 0 on a result, 2 on bad input with {"error": ...}.

  plan <paper_vault> [--redo] [--solo-kb 60]
      Plans causal-claim-extractor dispatches for the records without a claims
      file, as stage_prep.py summaries plans the summarizer: a record over
      --solo-kb alone (with read_until when it has a references heading), the
      rest in batches of up to BATCH. --redo plans every record.

  check <paper_vault>
      Validates every claims/<id>.json against the spec and checks each quote
      against its record's body. Moves the claims and prevalences whose quote
      fails to `rejected`, rewriting only the files that change. Idempotent.

  exclude <paper_vault> --profile P
      Moves every record matching an entry of the profile's exclude_papers
      (DOI, PMID, PMCID, arXiv id or exact title) into .excluded/, and its
      claims file into .excluded/claims/.

  names <paper_vault> --variables V [--new-only] --out F
      Writes names.txt: every raw variable name in the kept claims,
      prevalences and measurements. --new-only: only the names V does not map
      yet. V need not exist.

  pairs <paper_vault> --variables V --profile P --out F
      Writes pairs.json: the pairs of the top pair_search_k nodes with no kept
      claim between them, each with a PubMed query.

  upstream <paper_vault> --variables V --profile P --out F
      Writes upstream.json: the top upstream_search_k causes of the target,
      each with a PubMed query for reviews of its risk factors and a fallback
      for primary studies in the setting (from setting_terms).

  assemble <paper_vault> --variables V --profile P --out D
      Grades the claims, builds the strict and the full DAG and the evidence
      report, and writes <id>.dag.yaml, <id>.full.dag.yaml and
      <id>.evidence.md into D (<id> is the profile's id).

Choices the design leaves open, made here:
- A claims file that breaks the spec (a missing or unknown key, a wrong value,
  no record of that id) is invalid as a whole: `check` reports it and leaves
  it alone, and the other commands skip it (`assemble` lists it under
  warnings). `check`'s claims_rejected and by_paper count every rejected entry,
  claims and prevalences together, as they stand in the files.
- Quote check: the dashes made `-` are U+2010-U+2015 and U+2212; a line-end
  hyphen keeps the hyphen and loses the line break ("0.5-\\n0.98" reads
  "0.5-0.98"). The 400-character limit applies to the quote as written.
- `exclude` reports an entry that matches a record already in .excluded/ as
  excluded, with id `.excluded/<id>`; a record moved onto an existing
  .excluded/ file replaces it.
- `names --new-only` also leaves out the names in variables.json's
  `unmapped`: the harmonizer has judged them already.
- `pairs` ranks only nodes with at least one kept claim. A query block lists
  the node's name and aliases, normalized, most-used first (papers using the
  name), the name first among equals, at most 8; a term with anything but
  letters, digits and `*` is quoted.
- `upstream` ranks the causes of the target (nodes other than the target
  with a kept claim into it that shows an effect: direction increases,
  decreases or unclear; a node whose only claims into the target say `none`
  is not a cause)
  by the same support as `pairs`: papers with a kept claim touching the node,
  any claim. Its node block is `pairs`' terms in the title ([ti]), and so is
  its risk block, so a review must name the cause and its risk factors in
  its title; a paper on the cause as a risk factor for something else
  usually names the outcome too, and the agent screens it out. The setting
  block ([tiab]) holds the
  profile's setting_terms in the order written, normalized and deduplicated,
  each quoted as in `pairs`, with no cap on their number; a setting_terms
  that is not a list is an error. With no causes it writes `entries: []`.
- variables.json: a node needs `name`; its other keys default to empty. An
  unknown key, a name or level claimed by two nodes or levels, or a missing
  target node is an error (exit 2).
- Grades: a meta-analysis with an empty meta_analysis_of is speculative; a
  pooled cohort counts as adjusted or not by the claim's `adjusted`.
- Levels are looked up only on a node that has levels; on a node without
  them a claim's level fields are ignored. A null level is not a level that
  fails to map. A two-level or ordinal effect's claim about its first level is
  flipped; an ordinal cause's claim is flipped when its level is below its
  reference, and read as given when only one of the two is known.
- Sign: the edge's highest-grade claims are those that give a sign. A tie
  among them is a conflict when it is at the edge's highest grade (otherwise
  contrary claims could never reach that grade). For a map, a level whose
  claims disagree is left out. A per-level value is |ln(ratio)| for OR, RR,
  HR, |value| for beta_std and d, else 1, signed by the claim's direction.
- Conflicts and support are judged per comparison: per (level, reference)
  pair for a nominal cause, per effect level for a nominal effect, one
  comparison otherwise. A claim against its comparison's direction is
  contrary; claims that give no sign always support.
- Strength: from the supporting claims with a value, the highest-grade ones.
- Each graph keeps only the target's ancestors (decided with the researcher
  after the design): after cycles are broken, an edge stays when its effect
  is the target or has a path into it, so causes of causes stay and a
  variable that leads nowhere near the target goes. Dropped edges are
  `off_path` in the report and listed in the evidence report.
- Evidence: papers by grade, best first, then year, oldest first, then id.
- Edges into the target come first, then the rest, each by name; nodes are
  the target, then the rest by name. The full graph is named
  "<target> (full)". The report's date is SOURCE_DATE_EPOCH's when set
  (reproducible output), else today's.
"""
import argparse, json, math, os, re, statistics, sys, unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from graphlib import CycleError, TopologicalSorter
from itertools import combinations
from pathlib import Path

import graphcreator
from check_vault import split
from find_papers import EXCLUDED, seed_ident
from link_papers import listval, scalar
from stage_prep import BATCH, papers, read_until, same

CLAIMS = "claims"
DESIGNS = ("rct", "mendelian-randomization", "meta-analysis", "cohort", "case-control", "cross-sectional",
           "mechanistic", "animal", "review", "other")
DIRECTIONS = ("increases", "decreases", "none", "unclear")
EXISTS = ("increases", "decreases", "unclear")
LANGUAGES = ("causal", "association")
MEASURES = ("OR", "RR", "HR", "beta_std", "d", "other")
RATIOS = ("OR", "RR", "HR")
SCALES = ("category", "per_sd", "per_unit")
VAR_TYPES = ("categorical", "ordinal", "continuous", "discrete")
PAPER_KEYS = ("paper_id", "profile_id", "design", "design_detail", "meta_analysis_of", "population",
              "setting_match", "presents_dag", "claims", "prevalences", "measurements", "rejected")
CLAIM_KEYS = ("cause", "effect", "cause_level", "cause_reference", "effect_level", "direction", "language",
              "adjusted", "measure", "scale", "value", "ci", "quote", "section")
PREV_KEYS = ("variable", "level", "proportion", "quote", "section")
MEAS_KEYS = ("variable", "var_type", "levels", "unit")
VAR_KEYS = ("target", "nodes", "unmapped")
NODE_KEYS = ("name", "aliases", "var_type", "levels", "level_map", "unit", "description", "measurement_note")
GRADES = {3: "established", 2: "probable", 1: "suggested", 0: "speculative"}
STRICT = 2              # the strict DAG keeps edges graded probable or better
QUOTE_MAX = 400
NAMES_QUOTE = 160       # quote length in names.txt
DEFAULT_K = 15
DEFAULT_MAX_PAPERS = 40
DEFAULT_UP_K = 5
DEFAULT_UP_MAX_PAPERS = 15
MAX_TERMS = 8           # terms per node in a pair query
TOP_UNMAPPED = 10
DESIGN_BLOCK = ('(cohort[tiab] OR "risk factor*"[tiab] OR "odds ratio"[tiab] OR "mendelian randomi*"[tiab] '
                'OR meta-analysis[tiab])')
RISK_BLOCK = ('("risk factor*"[ti] OR determinant*[ti] OR etiolog*[ti] OR aetiolog*[ti] OR predictor*[ti]'
              ' OR "factors associated with"[ti])')
REVIEW_BLOCK = '("systematic review"[tiab] OR meta-analys*[tiab] OR "umbrella review"[tiab])'
NAMES_HEADER = "# papers | name | cause, effect | levels | quote"
DASHES = re.compile("[‐-―−]")
D_PER_LN = math.sqrt(3) / math.pi   # d = |ln(OR)| * sqrt(3) / pi


class Bad(Exception):
    """Bad input: exit 2 with {"error": ...}."""


def report(obj):
    print(json.dumps(obj, indent=1, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------- text

def norm(s):
    """Name matching: NFKC, case folding, whitespace collapsed."""
    return " ".join(unicodedata.normalize("NFKC", s).casefold().split())


def norm_text(s):
    """The quote check's normalization, for the paper text and the quote."""
    s = unicodedata.normalize("NFKC", s).replace("­", "")
    s = DASHES.sub("-", s)
    s = re.sub(r"-[ \t]*\r?\n\s*", "-", s)
    return " ".join(s.split()).casefold()


def quote_problem(quote, text):
    """None when the quote is found in the normalized text, else the reason."""
    if not quote.strip():
        return "quote empty"
    if len(quote) > QUOTE_MAX:
        return "quote too long"
    frags = [f.strip() for f in norm_text(quote).split("...")]
    frags = [f for f in frags if f]
    if not frags:
        return "quote empty"
    pos = 0
    for f in frags:
        i = text.find(f, pos)
        if i < 0:
            return "quote not found"
        pos = i + len(f)
    return None


def one_line(s):
    return " ".join(s.split())


def num(x):
    return f"{x:g}"


def plural(n, word, many=None):
    return f"{n} {word if n == 1 else many or word + 's'}"


# ---------------------------------------------------------------- profile

def load_profile(path):
    if not path.is_file():
        raise Bad(f"no such profile: {path}")
    fm, _ = split(path.read_text(encoding="utf-8"))
    if fm is None:
        raise Bad(f"profile has no frontmatter: {path}")
    return fm


def causal(fm, path):
    out = {"id": scalar(fm, "id"), "target": scalar(fm, "causal_target"), "setting": scalar(fm, "causal_setting")}
    if not out["target"]:
        raise Bad(f"not a causal profile (no causal_target): {path}")
    if not out["id"]:
        raise Bad(f"profile has no id: {path}")
    return out


def int_field(fm, key, default):
    v = scalar(fm, key).split(" #")[0].strip()
    if not v:
        return default
    if not re.fullmatch(r"\d+", v) or int(v) < 1:
        raise Bad(f"{key} is not a positive integer: {v}")
    return int(v)


# ---------------------------------------------------------------- claims files

def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def opt_text(v):
    return v is None or isinstance(v, str)


def keys(obj, want, where, errs):
    if not isinstance(obj, dict):
        errs.append(f"{where} is not an object")
        return False
    for k in want:
        if k not in obj:
            errs.append(f"{where}: no {k}")
    for k in obj:
        if k not in want:
            errs.append(f"{where}: unknown key {k}")
    return all(k in obj for k in want)


def check_claim(c, where, errs):
    if not keys(c, CLAIM_KEYS, where, errs):
        return
    for k in ("cause", "effect"):
        if not isinstance(c[k], str) or not c[k].strip():
            errs.append(f"{where}: {k} is not a name")
    for k in ("cause_level", "cause_reference", "effect_level"):
        if not opt_text(c[k]):
            errs.append(f"{where}: {k} is not text or null")
    for k, words in (("direction", DIRECTIONS), ("language", LANGUAGES)):
        if c[k] not in words:
            errs.append(f"{where}: {k} {c[k]!r} is not one of {', '.join(words)}")
    for k, words in (("measure", MEASURES), ("scale", SCALES)):
        if c[k] is not None and c[k] not in words:
            errs.append(f"{where}: {k} {c[k]!r} is not one of {', '.join(words)} or null")
    if not isinstance(c["adjusted"], bool):
        errs.append(f"{where}: adjusted is not true or false")
    if c["value"] is not None and not is_num(c["value"]):
        errs.append(f"{where}: value is not a number or null")
    ci = c["ci"]
    if ci is not None and not (isinstance(ci, list) and len(ci) == 2 and all(is_num(x) for x in ci)):
        errs.append(f"{where}: ci is not [lo, hi] or null")
    for k in ("quote", "section"):
        if not isinstance(c[k], str):
            errs.append(f"{where}: {k} is not text")


def check_prevalence(p, where, errs):
    if not keys(p, PREV_KEYS, where, errs):
        return
    if not isinstance(p["variable"], str) or not p["variable"].strip():
        errs.append(f"{where}: variable is not a name")
    if not isinstance(p["level"], str):
        errs.append(f"{where}: level is not text")
    if not is_num(p["proportion"]) or not 0 <= p["proportion"] <= 1:
        errs.append(f"{where}: proportion is not a number from 0 to 1")
    for k in ("quote", "section"):
        if not isinstance(p[k], str):
            errs.append(f"{where}: {k} is not text")


def check_measurement(m, where, errs):
    if not keys(m, MEAS_KEYS, where, errs):
        return
    if not isinstance(m["variable"], str) or not m["variable"].strip():
        errs.append(f"{where}: variable is not a name")
    if m["var_type"] is not None and m["var_type"] not in VAR_TYPES:
        errs.append(f"{where}: var_type {m['var_type']!r} is not one of {', '.join(VAR_TYPES)} or null")
    if not (isinstance(m["levels"], list) and all(isinstance(x, str) for x in m["levels"])):
        errs.append(f"{where}: levels is not a list of text")
    if not opt_text(m["unit"]):
        errs.append(f"{where}: unit is not text or null")


def validate(d, stem, recs):
    """The ways a claims file breaks the spec, in order; [] when it does not."""
    errs = []
    if not keys(d, PAPER_KEYS, "file", errs):
        return errs
    if d["paper_id"] != stem:
        errs.append(f"paper_id {d['paper_id']!r} is not the file's stem")
    if stem not in recs:
        errs.append("no record of that id in the vault")
    for k in ("profile_id", "design_detail", "population"):
        if not isinstance(d[k], str):
            errs.append(f"{k} is not text")
    if d["design"] not in DESIGNS:
        errs.append(f"design {d['design']!r} is not one of {', '.join(DESIGNS)}")
    if not (isinstance(d["meta_analysis_of"], list) and all(x in DESIGNS for x in d["meta_analysis_of"])):
        errs.append("meta_analysis_of is not a list of designs")
    for k in ("setting_match", "presents_dag"):
        if not isinstance(d[k], bool):
            errs.append(f"{k} is not true or false")
    for k, fn in (("claims", check_claim), ("prevalences", check_prevalence), ("measurements", check_measurement)):
        if not isinstance(d[k], list):
            errs.append(f"{k} is not a list")
            continue
        for n, x in enumerate(d[k]):
            fn(x, f"{k}[{n}]", errs)
    if not isinstance(d["rejected"], list):
        errs.append("rejected is not a list")
    else:
        for n, x in enumerate(d["rejected"]):
            if not isinstance(x, dict) or x.get("kind") not in ("claim", "prevalence") \
                    or not isinstance(x.get("reason"), str):
                errs.append(f"rejected[{n}] has no kind (claim or prevalence) and reason")
    return errs


def load_claims(root):
    """(records, claims data by paper id for the valid files, ["file: reason"] for the others)"""
    recs = papers(root)
    good, bad = {}, []
    folder = root / CLAIMS
    for f in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            bad.append(f"{f.name}: not JSON ({e})")
            continue
        errs = validate(d, f.stem, recs)
        if errs:
            bad.append(f"{f.name}: {errs[0]}" + (f" (and {len(errs) - 1} more)" if len(errs) > 1 else ""))
        else:
            good[f.stem] = d
    return recs, good, bad


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- variables.json

class Variables:
    def __init__(self, path):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            raise Bad(f"variables file is not JSON: {path}: {e}")
        where = f"variables file {path.name}"
        if not isinstance(data, dict):
            raise Bad(f"{where}: not an object")
        extra = [k for k in data if k not in VAR_KEYS]
        if extra or "target" not in data or "nodes" not in data:
            raise Bad(f"{where}: needs target and nodes (and unmapped), got {', '.join(sorted(data))}")
        if not isinstance(data["target"], str) or not isinstance(data["nodes"], list):
            raise Bad(f"{where}: target is not text or nodes is not a list")
        self.target = data["target"]
        self.nodes, self.by, self.level_of = {}, {}, {}
        for n, node in enumerate(data["nodes"]):
            if not isinstance(node, dict) or not isinstance(node.get("name"), str) or not node["name"].strip():
                raise Bad(f"{where}: nodes[{n}] has no name")
            name = node["name"]
            bad = [k for k in node if k not in NODE_KEYS]
            if bad:
                raise Bad(f"{where}: node {name!r}: unknown key {bad[0]}")
            if name in self.nodes:
                raise Bad(f"{where}: node {name!r} twice")
            nd = {"name": name, "aliases": node.get("aliases") or [], "var_type": node.get("var_type"),
                  "levels": node.get("levels") or [], "level_map": node.get("level_map") or {},
                  "unit": node.get("unit"), "description": node.get("description"),
                  "measurement_note": node.get("measurement_note")}
            if not all(isinstance(x, str) for x in nd["aliases"] + nd["levels"]):
                raise Bad(f"{where}: node {name!r}: aliases or levels are not text")
            if nd["var_type"] is not None and nd["var_type"] not in VAR_TYPES:
                raise Bad(f"{where}: node {name!r}: var_type {nd['var_type']!r} is not one of {', '.join(VAR_TYPES)}")
            if not isinstance(nd["level_map"], dict):
                raise Bad(f"{where}: node {name!r}: level_map is not a map")
            for k in ("unit", "description", "measurement_note"):
                if not opt_text(nd[k]):
                    raise Bad(f"{where}: node {name!r}: {k} is not text or null")
            self.nodes[name] = nd
            for raw in [name] + nd["aliases"]:
                other = self.by.setdefault(norm(raw), name)
                if other != name:
                    raise Bad(f"{where}: the name {raw!r} belongs to nodes {other!r} and {name!r}")
            levels = {}
            for lv in nd["levels"]:
                levels.setdefault(norm(lv), lv)
            for lv, raws in nd["level_map"].items():
                if lv not in nd["levels"] or not isinstance(raws, list) or not all(isinstance(r, str) for r in raws):
                    raise Bad(f"{where}: node {name!r}: level_map entry {lv!r} is not a level with a list of names")
                for raw in raws:
                    other = levels.setdefault(norm(raw), lv)
                    if other != lv:
                        raise Bad(f"{where}: node {name!r}: the level {raw!r} maps to {other!r} and {lv!r}")
            self.level_of[name] = levels
        if self.target not in self.nodes:
            raise Bad(f"{where}: no node named the target {self.target!r}")
        um = data.get("unmapped") or []
        if not isinstance(um, list) or not all(isinstance(x, str) for x in um):
            raise Bad(f"{where}: unmapped is not a list of text")
        self.unmapped = {norm(x) for x in um}

    def node(self, raw):
        return self.by.get(norm(raw))

    def level(self, node, raw):
        """The canonical level `raw` maps to on `node`, or None."""
        return self.level_of[node].get(norm(raw))


def variables(path, target=None):
    if not path.is_file():
        raise Bad(f"no such variables file: {path}")
    v = Variables(path)
    if target is not None and v.target != target:
        raise Bad(f"variables file target {v.target!r} is not the profile's causal_target {target!r}")
    return v


# ---------------------------------------------------------------- plan

def cmd_plan(a):
    root = a.path
    ps = papers(root)
    todo = [i for i in sorted(ps) if a.redo or not (root / CLAIMS / f"{i}.json").exists()]
    solo, small = [], []
    for i in todo:
        p = ps[i]
        if p["bytes"] > a.solo_kb * 1024:
            ru = read_until(p["text"])
            solo.append({"papers": [i], **({"read_until": ru} if ru else {})})
        else:
            small.append(i)
    batches = [{"papers": small[n:n + BATCH]} for n in range(0, len(small), BATCH)]
    return report({"to_extract": len(todo), "skipped_existing": len(ps) - len(todo),
                   "dispatch_count": len(solo) + len(batches), "dispatches": solo + batches})


# ---------------------------------------------------------------- check

def cmd_check(a):
    root = a.path
    recs, files, bad = load_claims(root)
    kept = rejected = 0
    by_paper, dag = {}, []
    for pid, d in files.items():
        text = norm_text(split(recs[pid]["text"])[1])
        moved = []
        for kind, key in (("claim", "claims"), ("prevalence", "prevalences")):
            keep = []
            for c in d[key]:
                why = quote_problem(c["quote"], text)
                if why:
                    moved.append({**c, "kind": kind, "reason": why})
                else:
                    keep.append(c)
            d[key] = keep
        if moved:
            d["rejected"] = d["rejected"] + moved
            write_json(root / CLAIMS / f"{pid}.json", d)
        kept += len(d["claims"])
        if d["rejected"]:
            by_paper[pid] = len(d["rejected"])
            rejected += len(d["rejected"])
        if d["presents_dag"]:
            dag.append(pid)
    missing = [i for i in recs if not (root / CLAIMS / f"{i}.json").exists()]
    return report({"papers": len(files), "claims_kept": kept, "claims_rejected": rejected, "by_paper": by_paper,
                   "invalid": bad, "missing": missing, "presents_dag": dag})


# ---------------------------------------------------------------- exclude

def cmd_exclude(a):
    root = a.path
    entries = listval(load_profile(a.profile), "exclude_papers")
    aside = root / EXCLUDED
    excluded, not_found = [], []
    for e in entries:
        ident = seed_ident(e)
        hits = [(i, key) for i, p in papers(root).items() for ok, key in [same(ident, p)] if ok]
        for i, key in hits:
            (aside / CLAIMS).mkdir(parents=True, exist_ok=True)
            os.replace(root / f"{i}.md", aside / f"{i}.md")
            if (root / CLAIMS / f"{i}.json").exists():
                os.replace(root / CLAIMS / f"{i}.json", aside / CLAIMS / f"{i}.json")
            excluded.append({"id": i, "matched": key})
        if hits:
            continue
        prior = [(i, key) for i, p in (papers(aside).items() if aside.is_dir() else ())
                 for ok, key in [same(ident, p)] if ok]
        excluded += [{"id": f"{EXCLUDED}/{i}", "matched": key} for i, key in prior]
        if not prior:
            not_found.append(e)
    return report({"excluded": excluded, "not_found": not_found})


# ---------------------------------------------------------------- names

def name_usage(files):
    """normalized name -> papers, cause and effect counts, levels, first quotes"""
    use = defaultdict(lambda: {"papers": set(), "cause": 0, "effect": 0, "levels": set(),
                               "quote": None, "pquote": None})
    for pid in sorted(files):
        d = files[pid]
        for c in d["claims"]:
            for side, lvs in (("cause", (c["cause_level"], c["cause_reference"])), ("effect", (c["effect_level"],))):
                u = use[norm(c[side])]
                u["papers"].add(pid)
                u[side] += 1
                u["levels"].update(norm(x) for x in lvs if x is not None and x.strip())
                if u["quote"] is None:
                    u["quote"] = c["quote"]
        for p in d["prevalences"]:
            u = use[norm(p["variable"])]
            u["papers"].add(pid)
            if p["level"].strip():
                u["levels"].add(norm(p["level"]))
            if u["pquote"] is None:
                u["pquote"] = p["quote"]
        for m in d["measurements"]:
            u = use[norm(m["variable"])]
            u["papers"].add(pid)
            u["levels"].update(norm(x) for x in m["levels"] if x.strip())
    return use


def cmd_names(a):
    _, files, _ = load_claims(a.path)
    use = name_usage(files)
    known = set()
    if a.new_only and a.variables.is_file():
        v = variables(a.variables)
        known = set(v.by) | v.unmapped
    lines = []
    for name in sorted(use, key=lambda n: (-len(use[n]["papers"]), n)):
        if name in known:
            continue
        u = use[name]
        q = u["quote"] if u["quote"] is not None else u["pquote"]
        q = one_line(q)[:NAMES_QUOTE] if q is not None and q.strip() else "-"
        levels = "; ".join(sorted(u["levels"])) or "-"
        lines.append(f"{len(u['papers'])} | {name} | cause {u['cause']}, effect {u['effect']} | levels: {levels} | {q}")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("\n".join([NAMES_HEADER] + lines) + "\n", encoding="utf-8")
    return report({"names": len(lines), "written": str(a.out)})


# ---------------------------------------------------------------- pairs

def term(t, field="tiab"):
    t = re.sub(r'["\[\]]', "", t).strip()
    return (t if re.fullmatch(r"[\w*]+", t) else f'"{t}"') + f"[{field}]"


def block(v, node, use, field="tiab"):
    terms = list(dict.fromkeys(norm(x) for x in [node] + v.nodes[node]["aliases"]))
    terms = [t for t in terms if t]
    terms.sort(key=lambda t: -len(use[t]["papers"]) if t in use else 0)
    return "(" + " OR ".join(term(t, field) for t in terms[:MAX_TERMS]) + ")"


def support_of(v, files):
    """(support: node -> the papers with a kept claim touching it; linked: the
    node pairs with a kept claim between them; causes: the nodes with a kept
    claim into the target that shows an effect (not `none`); rank: the sort key, most support first, ties by name)"""
    support, linked, causes = defaultdict(set), set(), set()
    for pid, d in files.items():
        for c in d["claims"]:
            x, y = v.node(c["cause"]), v.node(c["effect"])
            for n in (x, y):
                if n:
                    support[n].add(pid)
            if x and y and x != y:
                linked.add(frozenset((x, y)))
                if y == v.target and c["direction"] in EXISTS:
                    causes.add(x)
    return support, linked, causes, lambda n: (-len(support[n]), n.casefold(), n)


def cmd_pairs(a):
    fm = load_profile(a.profile)
    prof = causal(fm, a.profile)
    v = variables(a.variables, prof["target"])
    k = int_field(fm, "pair_search_k", DEFAULT_K)
    max_papers = int_field(fm, "pair_search_max_papers", DEFAULT_MAX_PAPERS)
    _, files, _ = load_claims(a.path)
    support, linked, _, rank = support_of(v, files)
    top = sorted((n for n in v.nodes if n != v.target and support[n]), key=rank)[:k]
    use = name_usage(files)
    pairs, already = [], 0
    for x, y in combinations(top, 2):
        if frozenset((x, y)) in linked:
            already += 1
            continue
        x, y = sorted((x, y), key=rank)
        q = f"{block(v, x, use)} AND {block(v, y, use)}"
        pairs.append({"a": x, "b": y, "support": len(support[x]) + len(support[y]), "query": q,
                      "narrow": f"{q} AND {DESIGN_BLOCK}"})
    pairs.sort(key=lambda p: (-p["support"], p["a"].casefold(), p["b"].casefold()))
    pairs = [{"n": n, **p} for n, p in enumerate(pairs, 1)]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    write_json(a.out, {"k": k, "max_papers": max_papers, "pairs": pairs})
    return report({"k": k, "pairs": len(pairs), "already_linked": already, "written": str(a.out)})


# ---------------------------------------------------------------- upstream

def setting_block(fm):
    """The OR block of the profile's setting_terms, or None without any."""
    raw = scalar(fm, "setting_terms").split(" #")[0].strip()
    if raw and not raw.startswith("["):
        raise Bad(f"setting_terms is not a list: {raw}")
    terms = [t for t in dict.fromkeys(norm(x) for x in listval(fm, "setting_terms")) if t]
    return "(" + " OR ".join(term(t) for t in terms) + ")" if terms else None


def cmd_upstream(a):
    fm = load_profile(a.profile)
    prof = causal(fm, a.profile)
    v = variables(a.variables, prof["target"])
    k = int_field(fm, "upstream_search_k", DEFAULT_UP_K)
    max_papers = int_field(fm, "upstream_search_max_papers", DEFAULT_UP_MAX_PAPERS)
    setting = setting_block(fm)
    _, files, _ = load_claims(a.path)
    support, _, causes, rank = support_of(v, files)
    use = name_usage(files)
    entries = []
    for n, x in enumerate(sorted(causes, key=rank)[:k], 1):
        node = f"{block(v, x, use, 'ti')} AND {RISK_BLOCK}"
        entries.append({"n": n, "a": x, "support": len(support[x]), "query": f"{node} AND {REVIEW_BLOCK}",
                        "fallback": f"{node} AND {setting}" if setting else None})
    a.out.parent.mkdir(parents=True, exist_ok=True)
    write_json(a.out, {"k": k, "max_papers": max_papers, "entries": entries})
    return report({"k": k, "entries": len(entries), "written": str(a.out)})


# ---------------------------------------------------------------- grades

def design_grade(design, adjusted):
    if design in ("rct", "mendelian-randomization"):
        return 3
    if design == "cohort":
        return 2 if adjusted else 1
    if design in ("case-control", "cross-sectional"):
        return 1
    return 0


def claim_grade(d, c):
    """(grade, how it was reached)"""
    design = d["design"]
    if design == "meta-analysis":
        pooled = d["meta_analysis_of"]
        how = "meta-analysis of " + (", ".join(pooled) if pooled else "unstated designs")
        if pooled and all(x in ("rct", "mendelian-randomization", "cohort") for x in pooled):
            g = 3
        else:
            g = min((design_grade(x, c["adjusted"]) for x in pooled), default=0)
    else:
        g = design_grade(design, c["adjusted"])
        how = design + (", adjusted" if c["adjusted"] else ", unadjusted") if design == "cohort" else design
    if not d["setting_match"]:
        g, how = max(g - 1, 0), how + ", other setting"
    else:
        how += ", same setting"
    return g, how


# ---------------------------------------------------------------- signs

def leveled(node):
    """A node whose levels orient a claim: categorical with exactly two levels,
    or ordinal with two or more."""
    n = len(node["levels"])
    return node["var_type"] == "categorical" and n == 2 or node["var_type"] == "ordinal" and n >= 2


def nominal(node):
    return node["var_type"] == "categorical" and len(node["levels"]) >= 3


def shape(cause, effect):
    if nominal(cause) and nominal(effect):
        return "none"
    if nominal(effect):
        return "effect"
    if nominal(cause):
        return "levels"
    return "word"


MISS = object()


def mapped(v, node, raw):
    """The canonical level, None when absent, MISS when it does not map."""
    if raw is None or not raw.strip():
        return None
    lv = v.level(node, raw)
    return MISS if lv is None else lv


def cause_flip(v, node, c):
    """+1, -1, or None when the cause's levels give no sign."""
    nd = v.nodes[node]
    if not leveled(nd):
        return 1
    lv, rf = mapped(v, node, c["cause_level"]), mapped(v, node, c["cause_reference"])
    if lv is MISS or rf is MISS:
        return None
    idx = nd["levels"].index
    if lv is not None and rf is not None:
        if lv == rf:
            return None
        return 1 if idx(lv) > idx(rf) else -1
    if nd["var_type"] == "ordinal":
        return 1
    if lv is not None:
        return 1 if idx(lv) == 1 else -1
    if rf is not None:
        return 1 if idx(rf) == 0 else -1
    return 1


def effect_flip(v, node, c):
    nd = v.nodes[node]
    if not leveled(nd):
        return 1
    el = mapped(v, node, c["effect_level"])
    if el is MISS:
        return None
    return -1 if el is not None and nd["levels"].index(el) == 0 else 1


def magnitude(c):
    if c["value"] is not None and c["measure"] in RATIOS and c["value"] > 0:
        return abs(math.log(c["value"])), "ln"
    if c["value"] is not None and c["measure"] in ("beta_std", "d"):
        return abs(c["value"]), "value"
    return 1.0, "direction"


def orient(v, e, c):
    """The claim's comparison key and its direction (+1/-1) on that key, or
    (None, None) when it gives no sign. For a nominal cause the key is the
    (level, reference) pair in level order."""
    if c["direction"] not in ("increases", "decreases"):
        return None, None
    base = 1 if c["direction"] == "increases" else -1
    cause, effect = v.nodes[e.cause], v.nodes[e.effect]
    if e.shape == "none":
        return None, None
    if e.shape == "effect":
        el, cf = mapped(v, e.effect, c["effect_level"]), cause_flip(v, e.cause, c)
        if el is None or el is MISS or cf is None:
            return None, None
        return el, base * cf
    ef = effect_flip(v, e.effect, c)
    if ef is None:
        return None, None
    if e.shape == "levels":
        lv, rf = mapped(v, e.cause, c["cause_level"]), mapped(v, e.cause, c["cause_reference"])
        if lv in (None, MISS) or rf in (None, MISS) or lv == rf:
            return None, None
        s = base * ef
        if cause["levels"].index(lv) > cause["levels"].index(rf):
            lv, rf, s = rf, lv, -s
        return (lv, rf), s
    cf = cause_flip(v, e.cause, c)
    if cf is None:
        return None, None
    return "", base * cf * ef


# ---------------------------------------------------------------- edges

def strength_of(c):
    """(d, label) or (None, why not)"""
    if c["value"] is None:
        return None, "no estimate"
    if c["scale"] == "per_unit":
        return None, "per-unit estimate"
    if c["measure"] in RATIOS and c["scale"] in ("category", "per_sd") and c["value"] > 0:
        return abs(math.log(c["value"])) * D_PER_LN, c["measure"]
    if c["measure"] in ("beta_std", "d"):
        return abs(c["value"]), "standardized beta" if c["measure"] == "beta_std" else "d"
    return None, "no convertible estimate"


def band(d):
    if d < 0.1:
        return None
    return "small" if d < 0.3 else "medium" if d < 0.6 else "large"


class Edge:
    def __init__(self, v, cause, effect, claims):
        self.cause, self.effect, self.claims = cause, effect, claims   # claims: dicts with pid, c, g, how, d
        self.shape = shape(v.nodes[cause], v.nodes[effect])
        ex = [x for x in claims if x["c"]["direction"] in EXISTS]
        self.exists = bool(ex)
        if not ex:
            return
        self.top = max(x["g"] for x in ex)
        for x in claims:
            x["key"], x["s"] = orient(v, self, x["c"])
        oriented = [x for x in ex if x["key"] is not None]
        # per comparison: its direction from its own top-grade claims, or a tie
        self.decided, ties = {}, {}
        for key in dict.fromkeys(x["key"] for x in oriented):
            mine = [x for x in oriented if x["key"] == key]
            g = max(x["g"] for x in mine)
            dirs = {x["s"] for x in mine if x["g"] == g}
            if len(dirs) == 1:
                self.decided[key] = dirs.pop()
            else:
                ties[key] = g
        for x in claims:
            if x["c"]["direction"] == "none":
                x["role"] = "no effect"
            elif x["key"] is not None and x["key"] in self.decided and x["s"] != self.decided[x["key"]]:
                x["role"] = "contrary"
            else:
                x["role"] = "supports"
        nones = [x for x in claims if x["role"] == "no effect" and x["g"] >= self.top]
        tied = [k for k, g in ties.items() if g >= self.top]
        self.conflict = bool(nones or tied)
        self.conflict_why = [f"{x['pid']} reports no effect (grade {x['g']})" for x in nones] + \
            ["claims at grade {} disagree on the direction{}".format(
                ties[k], f" for {k[0]} against {k[1]}" if isinstance(k, tuple) else f" for {k}" if k else "")
             for k in tied]
        self.grade = max(self.top - 1, 0) if self.conflict else self.top
        self.support = [x for x in claims if x["role"] == "supports"]
        self.against = [x for x in claims if x["role"] != "supports"]
        self.sign, self.sign_how = self.decide_sign(v, oriented)
        self.decide_strength()
        self.papers = self.paper_order()

    def decide_sign(self, v, oriented):
        if self.shape == "none":
            return None, "none: both ends are nominal"
        if not oriented:
            why = "no claim gives a direction" if all(x["c"]["direction"] == "unclear" for x in self.claims
                                                     if x["c"]["direction"] in EXISTS) \
                else "the claims' levels do not map to the nodes' levels"
            return None, f"none: {why}"
        g = max(x["g"] for x in oriented)
        top = [x for x in oriented if x["g"] == g]
        n = plural(len(top), "claim")
        if self.shape == "word":
            dirs = {x["s"] for x in top}
            if len(dirs) > 1:
                return None, f"none: the {n} at grade {g} disagree"
            word = "positive" if dirs.pop() > 0 else "negative"
            return word, f"{word}, from {n} at grade {g}"
        if self.shape == "effect":
            sign = {}
            for lv in v.nodes[self.effect]["levels"]:
                dirs = {x["s"] for x in top if x["key"] == lv}
                if len(dirs) == 1:
                    sign[lv] = "positive" if dirs.pop() > 0 else "negative"
            if not sign:
                return None, f"none: the {n} at grade {g} disagree"
            return sign, f"per level of {self.effect}, from {n} at grade {g}"
        # a nominal cause: per level against the reference most claims use
        levels = v.nodes[self.cause]["levels"]
        refs = Counter()
        for x in top:
            lv, rf = self.raw_pair(v, x["c"])
            refs[rf] += 1
        ref = sorted(refs, key=lambda r: (-refs[r], levels.index(r)))[0]
        vals = defaultdict(list)
        kinds = set()
        for x in top:
            lv, rf = self.raw_pair(v, x["c"])
            mag, kind = magnitude(x["c"])
            kinds.add(kind)
            s = (1 if x["c"]["direction"] == "increases" else -1) * effect_flip(v, self.effect, x["c"])
            if rf == ref:
                vals[lv].append(s * mag)
            elif lv == ref:
                vals[rf].append(-s * mag)
        per = {ref: 0.0}
        for lv in levels:
            xs = vals.get(lv)
            if xs and (all(x > 0 for x in xs) or all(x < 0 for x in xs)):
                per[lv] = statistics.median(xs)
        mean = statistics.fmean(per.values())
        centred = {lv: per[lv] - mean for lv in levels if lv in per}
        sign = {lv: "positive" if c > 0 else "negative" for lv, c in centred.items() if abs(c) > 1e-12}
        scale = "log scale" if kinds == {"ln"} else "direction only" if kinds == {"direction"} else "mixed scales"
        how = (f"per level of {self.cause}, from {n} at grade {g}, against reference {ref} ({scale}): "
               + ", ".join(f"{lv} {num(round(per[lv], 2))}" for lv in levels if lv in per)
               + f"; centred on their mean {num(round(mean, 2))}")
        return (sign or None), how

    def raw_pair(self, v, c):
        return v.level(self.cause, c["cause_level"]), v.level(self.cause, c["cause_reference"])

    def decide_strength(self):
        """Sets strength (a band or None), strength_how (for the report),
        strength_note (for the edge's note) and d_parts [(claim, d, label)]."""
        self.d_parts, why = [], "no estimate"
        valued = [x for x in self.support if x["c"]["value"] is not None]
        if valued:
            g = max(x["g"] for x in valued)
            parts = [(x, *strength_of(x["c"])) for x in valued if x["g"] == g]
            self.d_parts = [(x, d, label) for x, d, label in parts if d is not None]
            why = " and ".join(sorted({label for _, _, label in parts})) + " only"
        if not self.d_parts:
            self.strength, self.strength_how, self.strength_note = None, f"none: {why}", f"no strength ({why})"
            return
        med = statistics.median(d for _, d, _ in self.d_parts)
        counts = Counter(label for _, _, label in self.d_parts)
        order = ("OR", "RR", "HR", "standardized beta", "d")
        what = ", ".join(plural(counts[k], k, k if k == "d" else k + "s") for k in order if counts[k])
        read = [k for k in ("RR", "HR") if counts[k]]
        read = f"; {' and '.join(read)} read as an OR" if read else ""
        med_txt = f"{'median ' if len(self.d_parts) > 1 else ''}d {num(round(med, 2))}"
        self.strength = band(med)
        if self.strength is None:
            self.strength_how = f"none: {med_txt} from {what}, below 0.1{read}"
            self.strength_note = f"no strength ({med_txt} from {what}, below 0.1{read})"
        else:
            self.strength_how = f"{self.strength}: {med_txt} from {what}{read}"
            self.strength_note = f"strength from {what} ({med_txt}{read})"

    def paper_order(self):
        best = {}
        for x in self.support:
            best[x["pid"]] = max(best.get(x["pid"], 0), x["g"])
        return sorted(best, key=lambda p: (-best[p], self.year(p), p)), best

    def year(self, pid):
        return self.years.get(pid, 9999)

    def note(self, designs, setting):
        pids, _ = self.papers
        count = Counter(designs[p] for p in pids)
        ds = ", ".join(f"{count[d]} {d}" for d in sorted(count, key=lambda d: (-count[d], DESIGNS.index(d))))
        other = sum(1 for p in pids if not setting[p])
        parts = [GRADES[self.grade], ds or "no supporting design",
                 plural(len(pids), "paper") + (f", {other} outside the setting" if other else "")]
        if self.conflict:
            parts.append("conflict, one grade lower")
        elif self.against:
            parts.append(f"no conflict (weaker contrary evidence from {plural(len({x['pid'] for x in self.against}), 'paper')})")
        else:
            parts.append("no conflict")
        parts.append(self.strength_note)
        return "; ".join(parts)


def edge_order(target):
    return lambda k: (k[1] != target, k[0].casefold(), k[1].casefold(), k)


def break_cycles(edges, label):
    """Drops each directed cycle's worst-supported edge until none is left.
    Returns the kept edge keys and the drops."""
    kept = sorted(edges, key=lambda k: (k[0].casefold(), k[1].casefold(), k))
    drops = []
    while True:
        ts = TopologicalSorter()
        for a, b in kept:
            ts.add(b, a)
        try:
            ts.prepare()
            return kept, drops
        except CycleError as err:
            cyc = err.args[1]
        steps = list(zip(cyc, cyc[1:]))
        if all(s in edges and s in kept for s in steps):
            path = cyc
        else:
            steps = [(b, a) for a, b in steps]
            path = list(reversed(cyc))
        e = lambda k: edges[k]
        low = min((e(k).grade, len(e(k).papers[0])) for k in steps)
        worst = max((k for k in steps if (e(k).grade, len(e(k).papers[0])) == low),
                    key=lambda k: (k[0].casefold(), k[1].casefold(), k))
        kept.remove(worst)
        drops.append({"graph": label, "from": worst[0], "to": worst[1], "grade": e(worst).grade,
                      "papers": len(e(worst).papers[0]), "cycle": path})


# ---------------------------------------------------------------- assemble

def ancestors_only(keys, target):
    """(kept, dropped): an edge stays when its effect is the target or one of
    the target's ancestors in this graph, so the graph holds the target's
    causes, their causes, and the edges among them, and nothing downstream of
    a cause that leads nowhere near the target. `keys` must be acyclic."""
    into = defaultdict(set)
    for a, b in keys:
        into[b].add(a)
    keep, todo = {target}, [target]
    while todo:
        for a in into[todo.pop()]:
            if a not in keep:
                keep.add(a)
                todo.append(a)
    kept = [k for k in keys if k[1] in keep]
    return kept, [k for k in keys if k[1] not in keep]


def ident(rec, pid):
    if rec["pmid"]:
        return f"PMID:{rec['pmid']}"
    if rec["doi"]:
        return f"doi:{rec['doi']}"
    if rec["arxiv_id"]:
        return f"arXiv:{rec['arxiv_id']}"
    return f"vault:{pid}"


def year_of(rec, pid):
    y = scalar(rec["fm"], "year") if rec["fm"] else ""
    y = y if y.isdigit() else pid[:4]
    return int(y) if y.isdigit() else 9999


def shares_of(v, files):
    """node -> (shares or None, used [(pid, level, p)], unused [(pid, raw level, p, why)])"""
    got = defaultdict(lambda: defaultdict(list))
    used, unused = defaultdict(list), defaultdict(list)
    for pid in sorted(files):
        d = files[pid]
        for p in d["prevalences"]:
            node = v.node(p["variable"])
            if node is None:
                continue
            lv = v.level(node, p["level"]) if v.nodes[node]["levels"] else None
            if not d["setting_match"]:
                unused[node].append((pid, p["level"], p["proportion"], "other setting"))
            elif lv is None:
                unused[node].append((pid, p["level"], p["proportion"], "level does not map"))
            else:
                got[node][lv].append(p["proportion"])
                used[node].append((pid, lv, p["proportion"]))
    out = {}
    for node, nd in v.nodes.items():
        levels, med = nd["levels"], {lv: statistics.median(xs) for lv, xs in got[node].items()}
        shares, how = None, None
        if nd["var_type"] in ("categorical", "ordinal") and len(levels) >= 2 and med:
            if len(levels) == 2 and len(med) == 1:
                (lv, p), = med.items()
                other = levels[1 - levels.index(lv)]
                med[other] = 1 - p
                how = f"{other}: the complement"
            if len(med) == len(levels):
                shares = [med[lv] for lv in levels]
            else:
                how = "not written: " + ", ".join(lv for lv in levels if lv not in med) + " without a value"
        out[node] = (shares, used[node], unused[node], how)
    return out


def node_dict(v, name, shares, warnings):
    nd = v.nodes[name]
    out = {"name": name}
    if name == v.target:
        out["role"] = "outcome"
    if nd["var_type"]:
        out["var_type"] = nd["var_type"]
    if nd["levels"]:
        if nd["var_type"] in ("categorical", "ordinal"):
            out["levels"] = nd["levels"]
            if shares:
                out["shares"] = shares
        else:
            warnings.append(f"node {name!r}: levels on a node that is not categorical or ordinal, left out")
    if nd["description"]:
        out["description"] = nd["description"]
    if nd["unit"]:
        if nd["var_type"] in ("continuous", "discrete"):
            out["unit"] = nd["unit"]
        else:
            warnings.append(f"node {name!r}: a unit on a node that is not continuous or discrete, left out")
    return out


def edge_dict(e, recs, note):
    out = {"from": e.cause, "to": e.effect}
    if e.sign:
        out["sign"] = e.sign
    if e.strength:
        out["strength"] = e.strength
    out["evidence"] = [ident(recs[p], p) for p in e.papers[0]]
    out["note"] = note
    return out


def build(a):
    """Everything assemble computes: (profile, graphs, report, evidence lines)."""
    root = a.path
    prof = causal(load_profile(a.profile), a.profile)
    v = variables(a.variables, prof["target"])
    recs, files, bad = load_claims(root)
    warnings = [f"invalid claims file: {b}" for b in bad]
    designs = {pid: d["design"] for pid, d in files.items()}
    setting = {pid: d["setting_match"] for pid, d in files.items()}
    years = {pid: year_of(recs[pid], pid) for pid in files}

    by_pair, lost, lost_claims, self_loops = defaultdict(list), Counter(), 0, 0
    for pid in sorted(files):
        for c in files[pid]["claims"]:
            x, y = v.node(c["cause"]), v.node(c["effect"])
            if not x or not y:
                lost_claims += 1
                for raw, n in ((c["cause"], x), (c["effect"], y)):
                    if not n:
                        lost[norm(raw)] += 1
                continue
            if x == y:
                self_loops += 1
                continue
            g, how = claim_grade(files[pid], c)
            by_pair[(x, y)].append({"pid": pid, "c": c, "g": g, "how": how})
    if self_loops:
        warnings.append(f"{plural(self_loops, 'claim')} with cause and effect on one node, left out")

    Edge.years = years
    edges, no_effect = {}, {}
    for key in sorted(by_pair, key=edge_order(v.target)):
        e = Edge(v, *key, by_pair[key])
        (edges if e.exists else no_effect)[key] = e
    notes = {k: e.note(designs, setting) for k, e in edges.items()}

    strict_keys, strict_drops = break_cycles({k: e for k, e in edges.items() if e.grade >= STRICT}, "strict")
    full_keys, full_drops = break_cycles(edges, "full")
    strict_keys, strict_off = ancestors_only(strict_keys, v.target)
    full_keys, full_off = ancestors_only(full_keys, v.target)
    strict_keys = sorted(strict_keys, key=edge_order(v.target))
    full_keys = sorted(full_keys, key=edge_order(v.target))
    off_path = [{"graph": g, "from": a, "to": b} for g, ks in (("strict", strict_off), ("full", full_off))
                for a, b in sorted(ks, key=edge_order(v.target))]
    shares = shares_of(v, files)

    graphs = {}
    for label, ks, title in (("strict", strict_keys, prof["target"]), ("full", full_keys, f"{prof['target']} (full)")):
        names = {v.target} | {n for k in ks for n in k}
        order = [v.target] + sorted((n for n in names if n != v.target), key=lambda n: (n.casefold(), n))
        node_warn = []
        graphs[label] = {"schema": graphcreator.SCHEMA, "name": title,
                         "nodes": [node_dict(v, n, shares[n][0], node_warn) for n in order],
                         "edges": [edge_dict(edges[k], recs, notes[k]) for k in ks]}
        if label == "full":
            warnings += node_warn
        errs, warns = graphcreator.validate(graphs[label])
        if errs:
            raise Bad(f"{label} graph is invalid: " + "; ".join(errs))
        warnings += [f"{label}: {w}" for w in warns]

    into = [sum(1 for k in ks if k[1] == v.target) for ks in (strict_keys, full_keys)]
    if not into[1]:
        warnings.insert(0, f"no claim into the target {v.target!r}")
    excluded = papers(root / EXCLUDED) if (root / EXCLUDED).is_dir() else {}
    dag = [pid for pid in sorted(files) if files[pid]["presents_dag"]]
    rep = {
        "nodes": [len(graphs["strict"]["nodes"]), len(graphs["full"]["nodes"])],
        "edges": [len(strict_keys), len(full_keys)],
        "target_edges": into,
        "cycle_drops": [{k: d[k] for k in ("graph", "from", "to", "grade", "papers")} for d in strict_drops + full_drops],
        "off_path": off_path,
        "unmapped_claims": lost_claims,
        "top_unmapped": [[n, c] for n, c in sorted(lost.items(), key=lambda t: (-t[1], t[0]))[:TOP_UNMAPPED]],
        "presents_dag": dag,
        "excluded": len(excluded),
        "warnings": warnings,
    }
    ctx = {"prof": prof, "v": v, "recs": recs, "files": files, "edges": edges, "no_effect": no_effect,
           "strict": set(strict_keys), "full": set(full_keys), "drops": strict_drops + full_drops,
           "off_path": off_path,
           "shares": shares, "lost": lost, "excluded": excluded, "dag": dag, "bad": bad, "notes": notes,
           "graphs": graphs}
    return prof, graphs, rep, evidence(ctx)


def run_date():
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch and epoch.isdigit():
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).date().isoformat()
    return date.today().isoformat()


# ---------------------------------------------------------------- the evidence report

def claim_line(ctx, x, edge):
    c, pid = x["c"], x["pid"]
    rec = ctx["recs"][pid]
    def side(name, *levels):
        lv = [l for l in levels if l]
        return name + (f" [{' vs '.join(lv)}]" if lv else "")
    verb = {"increases": "increases", "decreases": "decreases", "none": "has no effect on",
            "unclear": "affects (direction unclear)"}[c["direction"]]
    est = ""
    if c["value"] is not None:
        est = f"{c['measure'] or 'estimate'} {num(c['value'])}"
        if c["ci"]:
            est += f" (95% CI {num(c['ci'][0])} to {num(c['ci'][1])})"
        if c["scale"]:
            est += {"category": ", per category", "per_sd": ", per SD", "per_unit": ", per unit"}[c["scale"]]
    est = "; ".join(t for t in (est, "adjusted" if c["adjusted"] else "unadjusted") if t)
    return (f"  - {pid} ({ident(rec, pid)}; {x['how']}; grade {x['g']}; {x['role']}): "
            f"{side(c['cause'], c['cause_level'], c['cause_reference'])} {verb} "
            f"{side(c['effect'], c['effect_level'])}; {est}. \"{one_line(c['quote'])}\" ({c['section'] or 'no section'})")


def edge_block(ctx, k, e, where, h="###"):
    out = [f"{h} {k[0]} → {k[1]}", "", f"- In: {where}"]
    best = max((x for x in e.claims if x["c"]["direction"] in EXISTS), key=lambda x: x["g"])
    tops = sorted({x["pid"] for x in e.claims if x["c"]["direction"] in EXISTS and x["g"] == e.top})
    grade = f"{GRADES[e.grade]} ({e.grade})"
    if e.conflict:
        grade += f": best claims {GRADES[e.top]} ({e.top}), one lower on a conflict"
    else:
        grade += f": best claim{'s' if len(tops) > 1 else ''} {', '.join(tops)} ({best['how']})"
    out.append(f"- Grade: {grade}")
    if e.conflict:
        out.append("- Conflict: " + "; ".join(e.conflict_why))
    elif e.against:
        out.append("- Conflict: none; weaker contrary claims: " + ", ".join(
            f"{x['pid']} (grade {x['g']}, {x['c']['direction']})" for x in e.against))
    else:
        out.append("- Conflict: none")
    sign = e.sign if not isinstance(e.sign, dict) else "{" + ", ".join(f"{k}: {s}" for k, s in e.sign.items()) + "}"
    out.append(f"- Sign: {e.sign_how if not e.sign or isinstance(e.sign, str) else sign + ', ' + e.sign_how}")
    strength = e.strength_how
    if e.d_parts:
        strength += " (" + ", ".join(f"{x['pid']} {x['c']['measure']} {num(x['c']['value'])}: d {num(round(d, 2))}"
                                     for x, d, _ in e.d_parts) + ")"
    out.append(f"- Strength: {strength}")
    out.append(f"- Evidence: {', '.join(ident(ctx['recs'][p], p) for p in e.papers[0]) or 'none'}")
    out.append(f"- Note: {ctx['notes'][k]}")
    out.append("- Claims:")
    out += [claim_line(ctx, x, e) for x in sorted(e.claims, key=lambda x: (-x["g"], x["pid"]))]
    return out + [""]


def evidence(ctx):
    prof, v, files, edges = ctx["prof"], ctx["v"], ctx["files"], ctx["edges"]
    pid_ = prof["id"]
    g = ctx["graphs"]
    lines = []
    if not any(k[1] == v.target for k in ctx["full"]):
        lines += [f"**No claim into the target ({v.target}):** the graphs hold no edge into it. "
                  "Check that variables.json maps every synonym of the target.", ""]
    kept = sum(len(d["claims"]) for d in files.values())
    lines += [
        f"# Causal graph evidence: {pid_}", "",
        f"- Target: {prof['target']}",
        f"- Setting: {prof['setting'] or 'not given'}",
        f"- Assembled: {run_date()}",
        f"- Papers: {len(files)} with a claims file, {kept} kept claims; {len(ctx['excluded'])} excluded",
        f"- Strict graph: `{pid_}.dag.yaml`, edges graded probable or better: "
        f"{plural(len(g['strict']['nodes']), 'node')}, {plural(len(g['strict']['edges']), 'edge')}",
        f"- Full graph: `{pid_}.full.dag.yaml`, every supported edge: "
        f"{plural(len(g['full']['nodes']), 'node')}, {plural(len(g['full']['edges']), 'edge')}", "",
        "Grades: established (3) for an RCT, a Mendelian randomization study, or a meta-analysis of those and "
        "cohorts; probable (2) for an adjusted cohort; suggested (1) for a case-control, cross-sectional or "
        "unadjusted cohort study; speculative (0) for the rest. A claim from outside the setting counts one grade "
        "lower; an edge counts one grade lower when contrary or no-effect claims reach its best grade.", "",
        "## Nodes", ""]
    in_g = lambda n: ", ".join(lab for lab, ks in (("strict", ctx["strict"]), ("full", ctx["full"]))
                               if n == v.target or any(n in k for k in ks)) or "neither graph (no edge)"
    order = [v.target] + sorted((n for n in v.nodes if n != v.target), key=lambda n: (n.casefold(), n))
    for n in order:
        nd = v.nodes[n]
        sh, used, unused, how = ctx["shares"][n]
        lines += [f"### {n}" + (" (target)" if n == v.target else ""), "", f"- In: {in_g(n)}"]
        lines.append(f"- Aliases: {', '.join(nd['aliases']) or 'none'}")
        typ = nd["var_type"] or "no type"
        if nd["levels"]:
            typ += "; levels: " + ", ".join(nd["levels"])
        if nd["unit"]:
            typ += f"; unit: {nd['unit']}"
        lines.append(f"- Type: {typ}")
        if sh or used or unused:
            txt = "[" + ", ".join(num(round(s, 3)) for s in sh) + "]" if sh else "none"
            src = defaultdict(list)
            for pid, lv, p in used:
                src[lv].append(f"{num(p)} ({pid})")
            parts = [f"{lv}: " + ("median of " if len(src[lv]) > 1 else "") + ", ".join(src[lv])
                     for lv in nd["levels"] if src[lv]]
            if how:
                parts.append(how)
            lines.append(f"- Shares: {txt}" + (" from " + "; ".join(parts) if parts else ""))
            for pid, raw, p, why in unused:
                lines.append(f"  - not used: {raw} {num(p)} ({pid}, {why})")
        if nd["description"]:
            lines.append(f"- Description: {nd['description']}")
        if nd["measurement_note"]:
            lines.append(f"- Measurement: {nd['measurement_note']}")
        lines.append("")

    lines += ["## Edges", ""]
    if not ctx["full"]:
        lines += ["None.", ""]
    for k in sorted(ctx["full"], key=edge_order(v.target)):
        lines += edge_block(ctx, k, edges[k], "strict and full" if k in ctx["strict"] else "full only")

    lines += ["## Dropped", "", "### Below the strict threshold", ""]
    below = [k for k in sorted(edges, key=edge_order(v.target)) if edges[k].grade < STRICT]
    full_off = {(d["from"], d["to"]) for d in ctx["off_path"] if d["graph"] == "full"}
    lines += [f"- {a} → {b}: {GRADES[edges[(a, b)].grade]} ({edges[(a, b)].grade}), below probable"
              + ("" if (a, b) in ctx["full"] else
                 "; also dropped from the full graph (" + ("leads nowhere near the target" if (a, b) in full_off
                                                           else "cycle") + ")")
              for a, b in below] or ["None."]
    lines += ["", "### Leading nowhere near the target", ""]
    lines += [f"- {d['graph']} graph: {d['from']} → {d['to']}: {d['to']} has no path into the target"
              for d in ctx["off_path"]] or ["None."]
    lines += ["", "### Cycles", ""]
    if not ctx["drops"]:
        lines += ["None.", ""]
    for d in ctx["drops"]:
        e = edges[(d["from"], d["to"])]
        lines.append(f"- {d['graph']} graph: {d['from']} → {d['to']} dropped from the cycle "
                     f"{' → '.join(d['cycle'])}: the worst-supported edge ({GRADES[d['grade']]} ({d['grade']}), "
                     f"{plural(d['papers'], 'supporting paper')})")
    if ctx["drops"]:
        lines.append("")
    for k in dict.fromkeys((d["from"], d["to"]) for d in ctx["drops"]):
        if k not in ctx["full"]:
            lines += edge_block(ctx, k, edges[k], "neither graph (cycle)", "####")

    lines += ["## Not used", "", "### Unmapped names", ""]
    lines += [f"- {n}: {plural(c, 'claim')}" for n, c in sorted(ctx["lost"].items(), key=lambda t: (-t[1], t[0]))] \
        or ["None."]
    lines += ["", "### Claims of no effect on pairs without an edge", ""]
    lines += [f"- {a} → {b}: " + ", ".join(f"{x['pid']} (grade {x['g']})" for x in e.claims)
              for (a, b), e in ctx["no_effect"].items()] or ["None."]
    lines += ["", "### Quote-check rejections", ""]
    rej = []
    for pid in sorted(files):
        r = files[pid]["rejected"]
        if r:
            why = Counter(f"{x['kind']}: {x['reason']}" for x in r)
            rej.append(f"- {pid}: {len(r)} (" + ", ".join(f"{n} {w}" for w, n in sorted(why.items())) + ")")
    lines += rej or ["None."]
    lines += ["", "### Excluded papers", ""]
    lines += [f"- {i}: {p['title']} ({ident(p, i)})" for i, p in ctx["excluded"].items()] or ["None."]
    lines += ["", "### Papers that draw a DAG of the target", ""]
    lines += [f"- {i}: {ctx['recs'][i]['title']} ({ident(ctx['recs'][i], i)}). If it is the source of the "
              "expert graph, add it to exclude_papers and assemble again." for i in ctx["dag"]] or ["None."]
    if ctx["bad"]:
        lines += ["", "### Invalid claims files", ""] + [f"- {b}" for b in ctx["bad"]]
    return lines


def cmd_assemble(a):
    prof, graphs, rep, lines = build(a)
    a.out.mkdir(parents=True, exist_ok=True)
    try:
        strict, full = graphcreator.dump(graphs["strict"]), graphcreator.dump(graphs["full"])
    except ValueError as e:
        raise Bad(str(e))
    (a.out / f"{prof['id']}.dag.yaml").write_text(strict, encoding="utf-8")
    (a.out / f"{prof['id']}.full.dag.yaml").write_text(full, encoding="utf-8")
    (a.out / f"{prof['id']}.evidence.md").write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    return report(rep)


# ---------------------------------------------------------------- command

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("path", type=Path)
    p.add_argument("--redo", action="store_true")
    p.add_argument("--solo-kb", type=int, default=60)
    sub.add_parser("check").add_argument("path", type=Path)
    e = sub.add_parser("exclude")
    e.add_argument("path", type=Path)
    e.add_argument("--profile", type=Path, required=True)
    n = sub.add_parser("names")
    n.add_argument("path", type=Path)
    n.add_argument("--variables", type=Path, required=True)
    n.add_argument("--new-only", action="store_true")
    n.add_argument("--out", type=Path, required=True)
    for cmd in ("pairs", "upstream", "assemble"):
        q = sub.add_parser(cmd)
        q.add_argument("path", type=Path)
        q.add_argument("--variables", type=Path, required=True)
        q.add_argument("--profile", type=Path, required=True)
        q.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if not a.path.is_dir():
        print(json.dumps({"error": f"not a directory: {a.path}"}))
        return 2
    try:
        return {"plan": cmd_plan, "check": cmd_check, "exclude": cmd_exclude, "names": cmd_names,
                "pairs": cmd_pairs, "upstream": cmd_upstream, "assemble": cmd_assemble}[a.cmd](a)
    except Bad as err:
        print(json.dumps({"error": str(err)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
