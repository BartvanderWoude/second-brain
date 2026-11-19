#!/usr/bin/env python3
"""Reads written .dag.yaml files back with PyYAML (a YAML 1.1 reader) and
checks each equals its input graph, less what the writer leaves out on
purpose (scripts/graphcreator.py's docstring): null values, empty text,
`role: other`, `locked: false`, empty levels, evidence and sign maps; names,
`from` and `to` stripped; shares rounded to 3 decimals; `pos` rounded to
whole numbers.

  roundtrip.py <graph.json> <written.dag.yaml> [<graph.json> <written.dag.yaml> ...]

No output and exit 0 when every pair matches; one line per mismatch and exit
1 otherwise. Without PyYAML it says so on stderr and exits 0.
"""
import json, sys

try:
    import yaml
except ImportError:
    print("roundtrip skipped: PyYAML is not installed", file=sys.stderr)
    sys.exit(0)


def filled(v):
    return isinstance(v, str) and v.strip() != ""


def node(n):
    out = {"name": n["name"].strip()}
    if n.get("role") not in (None, "other"):
        out["role"] = n["role"]
    for key in ("var_type", "form"):
        if n.get(key) is not None:
            out[key] = n[key]
    if n.get("levels"):
        out["levels"] = n["levels"]
    if n.get("shares") is not None:
        out["shares"] = [round(x, 3) for x in n["shares"]]
    for key in ("description", "unit"):
        if filled(n.get(key)):
            out[key] = n[key]
    if n.get("pos") is not None:
        out["pos"] = [int(round(x)) for x in n["pos"]]
    return out


def edge(e):
    out = {"from": e["from"].strip(), "to": e["to"].strip()}
    if e.get("sign"):
        out["sign"] = e["sign"]
    if e.get("strength") is not None:
        out["strength"] = e["strength"]
    if e.get("evidence"):
        out["evidence"] = e["evidence"]
    if filled(e.get("note")):
        out["note"] = e["note"]
    return out


def expected(g):
    out = {"schema": g["schema"]}
    if filled(g.get("name")):
        out["name"] = g["name"]
    if g.get("locked"):
        out["locked"] = True
    out["nodes"] = [node(n) for n in g.get("nodes") or []]
    out["edges"] = [edge(e) for e in g.get("edges") or []]
    return out


args = sys.argv[1:]
if not args or len(args) % 2:
    sys.exit("usage: roundtrip.py <graph.json> <written.dag.yaml> [...]")
bad = 0
for src, written in zip(args[::2], args[1::2]):
    with open(src, encoding="utf-8") as f:
        want = expected(json.load(f))
    with open(written, encoding="utf-8") as f:
        got = yaml.safe_load(f)
    if got != want:
        bad += 1
        print(f"{written}: read back as {got!r}, expected {want!r}")
sys.exit(1 if bad else 0)
