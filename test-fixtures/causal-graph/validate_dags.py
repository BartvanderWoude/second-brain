#!/usr/bin/env python3
"""Rebuilds the two graphs `causal_graph.py assemble` wrote, checks each with
graphcreator.validate, and checks the written files are exactly
graphcreator.dump of those graphs. Nothing reads YAML back, so this is how the
suite knows the files on disk are valid graphcreator/0.1 graphs.

  validate_dags.py <paper_vault> <variables.json> <profile> <out dir>

No output and exit 0 when both graphs have no errors and match their files;
one line per problem and exit 1 otherwise. Warnings are not problems here:
assemble reports them itself.
"""
import sys
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import causal_graph, graphcreator  # noqa: E402

vault, variables, profile, out = (Path(x) for x in sys.argv[1:5])
prof, graphs, _, _ = causal_graph.build(Namespace(path=vault, variables=variables, profile=profile, out=out))
problems = []
for label, suffix in (("strict", ".dag.yaml"), ("full", ".full.dag.yaml")):
    errors, _ = graphcreator.validate(graphs[label])
    problems += [f"{label}: {e}" for e in errors]
    written = (out / f"{prof['id']}{suffix}").read_text(encoding="utf-8")
    if not errors and written != graphcreator.dump(graphs[label]):
        problems.append(f"{label}: {prof['id']}{suffix} is not the dump of the graph")
print("\n".join(problems), end="\n" if problems else "")
sys.exit(1 if problems else 0)
