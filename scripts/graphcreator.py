#!/usr/bin/env python3
r"""Validate a causal graph and write it as GraphCreator `graphcreator/0.1`
YAML, as templates/graphcreator-dag-format.md specifies. Stdlib only. No
reader: nothing in the plugin reads a .dag.yaml back.

A graph is a plain dict shaped like the YAML: `schema`, `name`, `locked`,
`nodes` (maps with name, role, var_type, levels, shares, description, unit,
form, pos) and `edges` (maps with from, to, sign, strength, evidence, note).

  validate(graph) -> (errors, warnings)
      Errors are what GraphCreator refuses (the format's "What a valid file
      guarantees"); warnings are what it only warns about.
  dump(graph) -> str
      The YAML text. Raises ValueError listing the errors when there are any.
  needs_quotes(text, flow=False) -> bool
      Whether `text` must be double-quoted; `flow` for an item of a flow
      collection (levels, sign-map keys).

As a command, for the fixture suite:

  graphcreator.py < graph.json             the YAML on stdout; warnings on
                                           stderr; exit 2 with the errors on
                                           stderr when the graph is invalid
  graphcreator.py --validate < graph.json  {"errors": [...], "warnings": [...]}
                                           exit 0 without errors, 1 with

Exit 2 on input that is not JSON.

Choices the format leaves open:
- A key whose value is null counts as absent, and so does an empty `levels`
  list: a continuous node may carry `levels: []` without being refused.
- Node names, `from` and `to` are compared after stripping spaces at both
  ends, as GraphCreator compares names, and written stripped, so an edge
  always names its node exactly as written. Other text is written as given.
- Text that is empty after stripping counts as empty and is left out (graph
  name, description, unit, note). `locked: false` is left out too.
- Values outside the format's word lists (role, var_type, form, sign words,
  strength), text that is not a string, shares and `pos` that are not finite
  numbers, and a `schema` other than graphcreator/0.1 are errors: the format
  defines no other values, so a writer must not produce them.
- The share-sum warning is judged on the written (rounded) shares, so it says
  what a reader of the file sees. Negative shares are judged as given.
- `pos` is written as whole numbers, rounded.
- A sign map is ordered by the levels of the node it is about (the effect
  when that is nominal, else the cause); keys that are not levels follow in
  the given order.
- `evidence` is a block list, one double-quoted item per line.
- Quoting is conservative: besides the YAML 1.1 forms (booleans, null,
  numbers, dates, `<<`, `=`) and YAML 1.2 numbers, any text that is empty,
  has spaces at either end, starts with an indicator character
  (-?:,[]{}#&*!|>'"%@`), contains `: ` or ` #`, ends with `:`, or holds a
  non-printable character, tab or line break is quoted; inside a flow
  collection also any text with , [ ] { } : or ? (PyYAML reads a ? inside
  flow text as a key indicator). Quoted text uses YAML's
  double-quoted escapes (\\, \", \n, \t, \r, \0, \xHH, \uHHHH, \UHHHHHHHH).
"""
import argparse, json, math, re, sys
from graphlib import CycleError, TopologicalSorter

SCHEMA = "graphcreator/0.1"

TOP_KEYS = ("schema", "name", "locked", "nodes", "edges")
NODE_KEYS = ("name", "role", "var_type", "levels", "shares", "description", "unit", "form", "pos")
EDGE_KEYS = ("from", "to", "sign", "strength", "evidence", "note")
ROLES = ("exposure", "outcome", "latent", "adjusted", "selected", "other")
VAR_TYPES = ("categorical", "ordinal", "continuous", "discrete")
LEVELED = ("categorical", "ordinal")
UNITED = ("continuous", "discrete")
FORMS = ("linear", "smooth", "threshold")
SIGNS = ("positive", "negative")
STRENGTHS = ("small", "medium", "large")
SHARE_TOLERANCE = 0.001

INDICATORS = "-?:,[]{}#&*!|>'\"%@`"
FLOW_CHARS = ",[]{}:?"
# Characters a plain scalar must not hold: everything outside YAML's printable
# set, plus tab, line breaks (CR, LF, NEL, LS, PS) and the byte-order mark.
UNSAFE = re.compile("[^\x20-\x7e\xa0-퟿-�\U00010000-\U0010ffff]|[  ﻿]")
RESOLVES = re.compile("|".join([
    # YAML 1.1 booleans and null, as the format lists them
    r"y|Y|yes|Yes|YES|n|N|no|No|NO|true|True|TRUE|false|False|FALSE"
    r"|on|On|ON|off|Off|OFF|null|Null|NULL|~",
    # YAML 1.1 integers: binary, octal, decimal, hex, sexagesimal
    r"[-+]?0b[0-1_]+|[-+]?0[0-7_]+|[-+]?(?:0|[1-9][0-9_]*)|[-+]?0x[0-9a-fA-F_]+"
    r"|[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+",
    # YAML 1.1 floats (the spec's form, a superset of PyYAML's)
    r"[-+]?(?:[0-9][0-9_]*)?\.[0-9._]*(?:[eE][-+]?[0-9]+)?"
    r"|[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\.[0-9_]*|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN)",
    # YAML 1.2 core numbers
    r"[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+|[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?",
    # YAML 1.1 timestamps
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
    r"|[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}(?:[Tt]|[ \t]+)[0-9]{1,2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]*)?"
    r"(?:[ \t]*(?:Z|[-+][0-9]{1,2}(?::[0-9]{2})?))?",
    # YAML 1.1 merge key and value key
    r"<<|=",
]))
ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "\r": "\\r", "\0": "\\0"}


# ---------------------------------------------------------------- text

def needs_quotes(text, flow=False):
    """True when `text` written plain would not read back as the same text in
    YAML 1.1 or 1.2, or is not allowed plain there."""
    if not text or text != text.strip() or UNSAFE.search(text):
        return True
    if text[0] in INDICATORS or ": " in text or " #" in text or text.endswith(":"):
        return True
    if flow and any(c in FLOW_CHARS for c in text):
        return True
    return bool(RESOLVES.fullmatch(text))


def quote(text):
    out = []
    for c in text:
        if c in ESCAPES:
            out.append(ESCAPES[c])
        elif UNSAFE.match(c):
            n = ord(c)
            out.append(f"\\x{n:02X}" if n < 0x100 else f"\\u{n:04X}" if n < 0x10000 else f"\\U{n:08X}")
        else:
            out.append(c)
    return '"' + "".join(out) + '"'


def scalar(text, flow=False):
    return quote(text) if needs_quotes(text, flow) else text


def share(x):
    r = round(float(x), 3)
    return str(int(r)) if r == int(r) else repr(r)


# ---------------------------------------------------------------- checks

def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _filled(text):
    return isinstance(text, str) and text.strip() != ""


def _levels(node):
    levels = node.get("levels")
    if isinstance(levels, (list, tuple)) and all(isinstance(x, str) for x in levels):
        return levels
    return []


def _nominal(node):
    return node.get("var_type") == "categorical" and len(_levels(node)) >= 3


def _has_levels_for_signs(node):
    return node.get("var_type") == "categorical" and len(_levels(node)) >= 2


def _sign_shape(cause, effect):
    """('none' | 'effect' | 'cause' | 'word', the levels a sign map is about),
    per the format's sign table, read in order."""
    if _nominal(cause) and _nominal(effect):
        return "none", _levels(effect)
    if _nominal(effect):
        return "effect", _levels(effect)
    if _has_levels_for_signs(cause):
        return "cause", _levels(cause)
    return "word", []


def _text(d, key, where, errors):
    v = d.get(key)
    if v is not None and not isinstance(v, str):
        errors.append(f"{where}: {key} is not text")


def _word(d, key, words, where, errors):
    v = d.get(key)
    if v is not None and v not in words:
        errors.append(f"{where}: {key} {v!r} is not one of {', '.join(words)}")


def _unknown(d, keys, where, errors):
    for k in d:
        if k not in keys:
            errors.append(f"{where}: unknown key {k!r}")


def _list(graph, key, errors):
    v = graph.get(key)
    if v is None:
        return []
    if not isinstance(v, (list, tuple)):
        errors.append(f"top level: {key} is not a list")
        return []
    return v


def _check_node(node, where, errors, warnings):
    _unknown(node, NODE_KEYS, where, errors)
    _word(node, "role", ROLES, where, errors)
    _word(node, "var_type", VAR_TYPES, where, errors)
    var_type = node.get("var_type")
    if var_type is None:
        warnings.append(f"{where}: no type")
    kind = f"a {var_type}" if var_type in VAR_TYPES else "an untyped"

    levels = node.get("levels")
    if levels is not None and not (isinstance(levels, (list, tuple)) and all(isinstance(x, str) for x in levels)):
        errors.append(f"{where}: levels is not a list of text")
        levels = None
    levels = levels or []
    if levels and var_type not in LEVELED:
        errors.append(f"{where}: levels on {kind} node")
    if var_type in LEVELED:
        if len(levels) < 2:
            warnings.append(f"{where}: fewer than two levels")
        seen = set()
        for level in levels:
            if level in seen:
                warnings.append(f"{where}: level {level!r} twice")
            seen.add(level)

    shares = node.get("shares")
    if shares is not None:
        if not (isinstance(shares, (list, tuple)) and all(_number(x) for x in shares)):
            errors.append(f"{where}: shares is not a list of numbers")
        elif not levels:
            errors.append(f"{where}: shares without levels")
        elif len(shares) != len(levels):
            errors.append(f"{where}: {len(shares)} shares for {len(levels)} levels")
        elif any(x < 0 for x in shares):
            errors.append(f"{where}: a negative share")
        else:
            total = sum(float(share(x)) for x in shares)
            if abs(total - 1) > SHARE_TOLERANCE + 1e-9:
                warnings.append(f"{where}: shares add up to {round(total, 3)}, not 1")

    _text(node, "description", where, errors)
    _text(node, "unit", where, errors)
    if _filled(node.get("unit")) and var_type not in UNITED:
        errors.append(f"{where}: unit on {kind} node")
    _word(node, "form", FORMS, where, errors)
    pos = node.get("pos")
    if pos is not None and not (isinstance(pos, (list, tuple)) and len(pos) == 2 and all(_number(x) for x in pos)):
        errors.append(f"{where}: pos is not two numbers")


def _check_sign(edge, where, errors):
    """True when the sign is absent or well formed."""
    sign = edge.get("sign")
    if sign is None or isinstance(sign, str) and sign in SIGNS:
        return True
    before = len(errors)
    if isinstance(sign, dict):
        for k, v in sign.items():
            if not isinstance(k, str):
                errors.append(f"{where}: sign key {k!r} is not text")
            if v not in SIGNS:
                errors.append(f"{where}: sign {v!r} for {k!r} is not one of {', '.join(SIGNS)}")
    elif isinstance(sign, str):
        errors.append(f"{where}: sign {sign!r} is not one of {', '.join(SIGNS)}")
    else:
        errors.append(f"{where}: sign is not a word or a map")
    return len(errors) == before


def _sign_fit(edge, cause, effect, where, warnings):
    sign = edge.get("sign")
    if sign is None or sign == {}:
        return
    shape, levels = _sign_shape(cause, effect)
    if shape == "none":
        warnings.append(f"{where}: a sign between two nominal nodes")
        return
    if shape == "word":
        if isinstance(sign, dict):
            warnings.append(f"{where}: a sign map where one word is expected")
        return
    about = edge["to"].strip() if shape == "effect" else edge["from"].strip()
    if isinstance(sign, str):
        if not (shape == "cause" and len(levels) == 2):
            warnings.append(f"{where}: one word where a sign map over the levels of {about!r} is expected")
        return
    for k in sign:
        if k not in levels:
            warnings.append(f"{where}: sign names {k!r}, not a level of {about!r}")


def _structure(graph):
    """(errors, warnings, nodes by stripped name, the edges that resolve, each
    as (edge, from, to, label, sign well formed))"""
    errors, warnings = [], []
    if not isinstance(graph, dict):
        return ["the graph is not a map"], [], {}, []
    _unknown(graph, TOP_KEYS, "top level", errors)
    schema = graph.get("schema")
    if schema is None:
        errors.append("schema is missing")
    elif schema != SCHEMA:
        errors.append(f"schema is {schema!r}, not {SCHEMA!r}")
    _text(graph, "name", "top level", errors)
    if graph.get("locked") is not None and not isinstance(graph["locked"], bool):
        errors.append("top level: locked is not true or false")
    nodes = _list(graph, "nodes", errors)
    edges = _list(graph, "edges", errors)

    by_name = {}
    for i, node in enumerate(nodes):
        where = f"nodes[{i}]"
        if not isinstance(node, dict):
            errors.append(f"{where} is not a map")
            continue
        name = node.get("name")
        if name is not None and not isinstance(name, str):
            errors.append(f"{where}: name is not text")
        elif not _filled(name):
            errors.append(f"{where}: name is missing or empty")
        else:
            name = name.strip()
            if name in by_name:
                errors.append(f"{where}: duplicate name {name!r}")
            else:
                by_name[name] = node
            where = f"node {name!r}"
        _check_node(node, where, errors, warnings)

    good, seen = [], set()
    for i, edge in enumerate(edges):
        where = f"edges[{i}]"
        if not isinstance(edge, dict):
            errors.append(f"{where} is not a map")
            continue
        ends = []
        for key in ("from", "to"):
            v = edge.get(key)
            if v is not None and not isinstance(v, str):
                errors.append(f"{where}: {key} is not text")
            elif not _filled(v):
                errors.append(f"{where}: {key} is missing or empty")
            else:
                ends.append(v.strip())
        resolved = len(ends) == 2
        if resolved:
            a, b = ends
            where = f"edge {a!r} -> {b!r}"
            for key, v in (("from", a), ("to", b)):
                if v not in by_name:
                    errors.append(f"{where}: {key} {v!r} is not a node")
                    resolved = False
            if a == b:
                errors.append(f"{where}: points from a node to itself")
                resolved = False
            elif (a, b) in seen:
                errors.append(f"{where}: appears twice")
                resolved = False
            seen.add((a, b))
        _unknown(edge, EDGE_KEYS, where, errors)
        sign_ok = _check_sign(edge, where, errors)
        _word(edge, "strength", STRENGTHS, where, errors)
        evidence = edge.get("evidence")
        if evidence is not None and not (isinstance(evidence, (list, tuple)) and all(isinstance(x, str) for x in evidence)):
            errors.append(f"{where}: evidence is not a list of text")
        _text(edge, "note", where, errors)
        if resolved:
            good.append((edge, a, b, where, sign_ok))

    sorter = TopologicalSorter()
    for name in by_name:
        sorter.add(name)
    for _, a, b, _, _ in good:
        sorter.add(b, a)
    try:
        sorter.prepare()
    except CycleError as e:
        errors.append("the edges form a directed cycle: " + " -> ".join(e.args[1]))

    has_causes = {b for _, _, b, _, _ in good}
    for name, node in by_name.items():
        if node.get("form") is not None and name not in has_causes:
            warnings.append(f"node {name!r}: a form on a node without causes")
    for edge, a, b, where, sign_ok in good:
        if sign_ok:
            _sign_fit(edge, by_name[a], by_name[b], where, warnings)
    return errors, warnings, by_name, good


def validate(graph):
    """(errors, warnings) per the format's "What a valid file guarantees":
    errors are what GraphCreator refuses (unknown keys, duplicate or empty
    names, dangling or self or duplicate edges, cycles, levels/unit/shares
    on the wrong type); warnings are what it only warns about."""
    errors, warnings, _, _ = _structure(graph)
    return errors, warnings


# ---------------------------------------------------------------- writing

def _node_lines(node):
    lines = [f"name: {scalar(node['name'].strip())}"]
    if node.get("role") not in (None, "other"):
        lines.append(f"role: {node['role']}")
    if node.get("var_type") is not None:
        lines.append(f"var_type: {node['var_type']}")
    levels = node.get("levels") or []
    if levels:
        lines.append("levels: [" + ", ".join(scalar(x, flow=True) for x in levels) + "]")
    if node.get("shares") is not None:
        lines.append("shares: [" + ", ".join(share(x) for x in node["shares"]) + "]")
    for key in ("description", "unit"):
        if _filled(node.get(key)):
            lines.append(f"{key}: {scalar(node[key])}")
    if node.get("form") is not None:
        lines.append(f"form: {node['form']}")
    if node.get("pos") is not None:
        lines.append("pos: [" + ", ".join(str(int(round(x))) for x in node["pos"]) + "]")
    return lines


def _edge_lines(edge, a, b, by_name):
    lines = [f"from: {scalar(a)}", f"to: {scalar(b)}"]
    sign = edge.get("sign")
    if isinstance(sign, str):
        lines.append(f"sign: {sign}")
    elif sign:
        _, levels = _sign_shape(by_name[a], by_name[b])
        keys = [x for x in levels if x in sign] + [k for k in sign if k not in levels]
        keys = list(dict.fromkeys(keys))
        lines.append("sign: {" + ", ".join(f"{scalar(k, flow=True)}: {sign[k]}" for k in keys) + "}")
    if edge.get("strength") is not None:
        lines.append(f"strength: {edge['strength']}")
    if edge.get("evidence"):
        lines.append("evidence:")
        lines.extend(f"  - {quote(x)}" for x in edge["evidence"])
    if _filled(edge.get("note")):
        lines.append(f"note: {scalar(edge['note'])}")
    return lines


def _item(lines):
    return ["  - " + lines[0]] + ["    " + ln for ln in lines[1:]]


def dump(graph):
    """The graph as graphcreator/0.1 YAML text. Raises ValueError listing the
    errors when validate() finds any. Keys in the format's order; empty text,
    `role: other`, empty evidence and empty sign maps left out; `levels` and
    `shares` and sign maps in flow style, sign-map keys in level order;
    evidence always double-quoted; any text a YAML 1.1 reader would read as
    something else (the format's list: booleans, null, YAML 1.1 numbers,
    dates) or that YAML 1.2 requires quoted, double-quoted; shares rounded to
    3 decimals, a share of 1 written `1`."""
    errors, _, by_name, good = _structure(graph)
    if errors:
        raise ValueError("invalid graph:\n" + "\n".join(f"- {e}" for e in errors))
    out = [f"schema: {SCHEMA}"]
    if _filled(graph.get("name")):
        out.append(f"name: {scalar(graph['name'])}")
    if graph.get("locked"):
        out.append("locked: true")
    nodes = graph.get("nodes") or []
    out.append("nodes:" if nodes else "nodes: []")
    for node in nodes:
        out.extend(_item(_node_lines(node)))
    out.append("edges:" if good else "edges: []")
    for edge, a, b, _, _ in good:
        out.extend(_item(_edge_lines(edge, a, b, by_name)))
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- command

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--validate", action="store_true",
                    help='print {"errors", "warnings"} as JSON instead of the YAML')
    args = ap.parse_args()
    try:
        graph = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"input is not JSON: {e}"}))
        return 2
    errors, warnings = validate(graph)
    if args.validate:
        print(json.dumps({"errors": errors, "warnings": warnings}, indent=2, ensure_ascii=False))
        return 1 if errors else 0
    try:
        text = dump(graph)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
