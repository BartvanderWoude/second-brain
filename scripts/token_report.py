#!/usr/bin/env python3
"""Token spend of one Claude Code session, per agent type. Stdlib only; a
development tool the pipeline never calls.

  token_report.py <session>.jsonl [--tools] [--json]

Reads the main transcript and every <session>/subagents/agent-*.jsonl, grouped
by the `agentType` in its .meta.json. The harness's `subagent_tokens` figure is
an agent's final context size, not what was billed: the cost of a turn is the
whole context it re-reads, so this sums usage over every turn. Streaming writes
one message over several lines, so usage is taken once per message id.

  weighted = input + W_write * cache_write + W_read * cache_read + W_out * output

with every model counted the same. --tools adds each group's tool calls by name.
"""
import argparse, json, sys
from collections import Counter
from pathlib import Path


def usage(path):
    """(usage per message id, tool-call Counter) for one transcript."""
    msgs, tools, seen_tools = {}, Counter(), set()
    for ln in path.open():
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if d.get("type") != "assistant":
            continue
        m = d.get("message") or {}
        mid = m.get("id") or d.get("uuid")
        if m.get("usage"):
            msgs[mid] = m["usage"]  # the last line of a streamed message is final
        for c in m.get("content") or []:
            if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("id") not in seen_tools:
                seen_tools.add(c.get("id"))
                tools[c.get("name", "?")] += 1
    return msgs, tools


def short(agent_type):
    return agent_type.split(":")[-1] if agent_type else "unknown"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session", type=Path, help="the session's main .jsonl transcript")
    ap.add_argument("--w-write", type=float, default=1.25)
    ap.add_argument("--w-read", type=float, default=0.1)
    ap.add_argument("--w-out", type=float, default=5.0)
    ap.add_argument("--tools", action="store_true", help="list each group's tool calls by name")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not a.session.is_file():
        print(json.dumps({"error": f"no such transcript: {a.session}"}))
        return 2

    sources = [("main thread", a.session)]
    sub = a.session.with_suffix("") / "subagents"
    for f in sorted(sub.glob("agent-*.jsonl")) if sub.is_dir() else []:
        meta = f.with_suffix(".meta.json")
        at = json.loads(meta.read_text()).get("agentType") if meta.exists() else None
        sources.append((short(at), f))

    groups = {}
    for name, f in sources:
        msgs, tools = usage(f)
        g = groups.setdefault(name, {"agents": 0, "turns": 0, "input": 0, "cache_write": 0,
                                     "cache_read": 0, "output": 0, "tools": Counter()})
        g["agents"] += name != "main thread"
        g["turns"] += len(msgs)
        g["tools"] += tools
        for u in msgs.values():
            g["input"] += u.get("input_tokens", 0)
            g["cache_write"] += u.get("cache_creation_input_tokens", 0)
            g["cache_read"] += u.get("cache_read_input_tokens", 0)
            g["output"] += u.get("output_tokens", 0)
    for g in groups.values():
        g["weighted"] = round(g["input"] + a.w_write * g["cache_write"] + a.w_read * g["cache_read"]
                              + a.w_out * g["output"])
    total = sum(g["weighted"] for g in groups.values()) or 1
    rows = sorted(groups.items(), key=lambda kv: -kv[1]["weighted"])

    if a.json:
        print(json.dumps({"weights": {"write": a.w_write, "read": a.w_read, "out": a.w_out},
                          "total_weighted": total,
                          "groups": {n: {**g, "tools": dict(g["tools"])} for n, g in rows}}, indent=1))
        return 0

    def m(x):
        return f"{x / 1e6:.2f}M" if x >= 1e5 else f"{x / 1e3:.1f}k"

    head = f"{'group':<34}{'agents':>7}{'turns':>7}{'cache wr':>10}{'cache rd':>10}{'output':>9}{'weighted':>10}{'share':>7}"
    print(head)
    print("-" * len(head))
    for n, g in rows:
        print(f"{n:<34}{g['agents'] or '-':>7}{g['turns']:>7}{m(g['cache_write']):>10}{m(g['cache_read']):>10}"
              f"{m(g['output']):>9}{m(g['weighted']):>10}{g['weighted'] / total:>7.0%}")
    print("-" * len(head))
    print(f"{'total':<34}{sum(g['agents'] for g in groups.values()):>7}{sum(g['turns'] for g in groups.values()):>7}"
          f"{'':>10}{'':>10}{'':>9}{m(total):>10}")
    print(f"weights: input 1, cache write {a.w_write}, cache read {a.w_read}, output {a.w_out}")
    if a.tools:
        for n, g in rows:
            if g["tools"]:
                print(f"\n{n}: " + ", ".join(f"{t} {c}" for t, c in g["tools"].most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
