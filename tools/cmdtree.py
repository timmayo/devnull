#!/usr/bin/env python3
"""cmdtree.py - visualize commands.yaml as a tree.

Usage examples:
    python tools\\cmdtree.py                      # tree by group
    python tools\\cmdtree.py -d                   # with details
    python tools\\cmdtree.py --view context       # context > group > command
    python tools\\cmdtree.py --view gate          # gate > commands that need it
    python tools\\cmdtree.py -g hacking           # only one group
    python tools\\cmdtree.py -c shell             # only one context
    python tools\\cmdtree.py --check              # validate references only
"""
import argparse
import os
import sys
from pathlib import Path

import yaml

USE_COLOR = True


def paint(text, code):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


def bold(t):
    return paint(t, "1")


def dim(t):
    return paint(t, "2")


def cyan(t):
    return paint(t, "1;36")


def yellow(t):
    return paint(t, "33")


def magenta(t):
    return paint(t, "35")


def red(t):
    return paint(t, "1;31")


# ---------------------------------------------------------------- loading

def find_file(arg):
    if arg:
        return Path(arg)
    here = Path.cwd() / "commands.yaml"
    if here.exists():
        return here
    script_dir = Path(__file__).resolve().parent
    for p in (script_dir / "commands.yaml", script_dir.parent / "commands.yaml"):
        if p.exists():
            return p
    sys.exit("commands.yaml not found. Use -f to give the path.")


def load(path):
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("contexts", {})
    data.setdefault("gates", {})
    data.setdefault("groups", {})
    data.setdefault("commands", {})
    return data


# ---------------------------------------------------------------- helpers

def as_list(v):
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple)) else [v]


def sorted_groups(groups):
    return sorted(groups.items(), key=lambda kv: (kv[1].get("order", 999), str(kv[0])))


def fmt_arg(a):
    name = a.get("name", "?")
    typ = a.get("type", "?")
    s = f"{name}:{typ}"
    return f"<{s}>" if a.get("required") else f"[{s}]"


def command_node(name, c, details):
    label = cyan(str(name))
    aliases = [str(a) for a in as_list(c.get("aliases"))]
    if aliases:
        label += dim(f" ({', '.join(aliases)})")
    req = [str(r) for r in as_list(c.get("requires"))]
    if req:
        label += " " + yellow(f"[requires: {', '.join(req)}]")
    hid = [str(r) for r in as_list(c.get("hidden_until"))]
    if hid:
        label += " " + magenta(f"[hidden until: {', '.join(hid)}]")
    if c.get("summary"):
        label += dim(f" - {c['summary']}")

    kids = []
    if details:
        if c.get("syntax"):
            kids.append((f"syntax:   {c['syntax']}", []))
        if c.get("contexts"):
            kids.append((f"contexts: {', '.join(map(str, as_list(c['contexts'])))}", []))
        if c.get("args"):
            kids.append(("args:     " + " ".join(fmt_arg(a) for a in c["args"]), []))
        if c.get("handler"):
            kids.append((f"handler:  {c['handler']}", []))
        for key in ("time_cost", "risk", "always_available", "locked_message"):
            if key in c:
                kids.append((f"{key}: {c[key]}", []))
    return (label, kids)


def group_label(gid, g, count):
    title = g.get("title", gid) if g else "(not defined in groups)"
    return f"{bold(title)} {dim(f'[{gid}]')} {dim(f'({count})')}"


# ---------------------------------------------------------------- views

def filter_commands(data, only_group, only_context):
    out = {}
    for name, c in data["commands"].items():
        c = c or {}
        if only_group and c.get("group") != only_group:
            continue
        if only_context and only_context not in [str(x) for x in as_list(c.get("contexts"))]:
            continue
        out[name] = c
    return out


def view_group(data, cmds, details):
    groups = data["groups"]
    nodes = []
    seen = set()
    for gid, g in sorted_groups(groups):
        members = [(n, c) for n, c in cmds.items() if c.get("group") == gid]
        seen.update(n for n, _ in members)
        if not members and (len(cmds) != len(data["commands"])):
            continue  # hide empty groups when filtering
        kids = [command_node(n, c, details) for n, c in members] or [(dim("(no commands)"), [])]
        nodes.append((group_label(gid, g, len(members)), kids))
    orphans = [(n, c) for n, c in cmds.items() if n not in seen]
    if orphans:
        kids = [command_node(n, c, details) for n, c in orphans]
        nodes.append((red("(ungrouped / unknown group)") + dim(f" ({len(orphans)})"), kids))
    return "commands", nodes


def view_context(data, cmds, details):
    nodes = []
    for ctx, info in data["contexts"].items():
        in_ctx = {n: c for n, c in cmds.items()
                  if str(ctx) in [str(x) for x in as_list(c.get("contexts"))]}
        if not in_ctx:
            continue
        _, gnodes = view_group(data, in_ctx, details)
        desc = (info or {}).get("description")
        label = bold(str(ctx)) + (dim(f" - {desc}") if desc else "") + dim(f" ({len(in_ctx)})")
        nodes.append((label, gnodes))
    return "contexts", nodes


def view_gate(data, cmds, details):
    nodes = []
    for gate, info in data["gates"].items():
        members = [(n, c) for n, c in cmds.items()
                   if str(gate) in [str(x) for x in as_list(c.get("requires"))]]
        if not members:
            continue
        desc = (info or {}).get("description")
        label = yellow(str(gate)) + (dim(f" - {desc}") if desc else "") + dim(f" ({len(members)})")
        nodes.append((label, [command_node(n, c, details) for n, c in members]))
    free = [(n, c) for n, c in cmds.items() if not as_list(c.get("requires"))]
    if free:
        nodes.append((bold("(no gate - always usable)") + dim(f" ({len(free)})"),
                      [command_node(n, c, details) for n, c in free]))
    return "gates", nodes


# ---------------------------------------------------------------- drawing

def draw(nodes, prefix=""):
    for i, (label, kids) in enumerate(nodes):
        last = i == len(nodes) - 1
        print(prefix + ("└── " if last else "├── ") + label)
        draw(kids, prefix + ("    " if last else "│   "))


# ---------------------------------------------------------------- checks

def check(data):
    problems = []
    groups, contexts, gates = data["groups"], data["contexts"], data["gates"]
    names = {}  # token -> owner command

    for name, c in data["commands"].items():
        c = c or {}
        if not isinstance(name, str):
            problems.append(f"command key {name!r} is not text (quote it in the YAML)")
            name = str(name)
        if c.get("group") not in groups:
            problems.append(f"{name}: unknown group {c.get('group')!r}")
        if not c.get("handler"):
            problems.append(f"{name}: no handler")
        if not c.get("contexts"):
            problems.append(f"{name}: no contexts listed")
        for ctx in as_list(c.get("contexts")):
            if ctx not in contexts:
                problems.append(f"{name}: unknown context {ctx!r}")
        for key in ("requires", "hidden_until"):
            for g in as_list(c.get(key)):
                if g not in gates:
                    problems.append(f"{name}: unknown gate {g!r} in {key}")

        tokens = [name] + as_list(c.get("aliases"))
        for t in tokens:
            if not isinstance(t, str):
                problems.append(
                    f"{name}: alias {t!r} parsed as {type(t).__name__} - "
                    f"quote it in the YAML (e.g. \"no\", \"yes\", \"on\", \"off\" become booleans)")
                continue
            if t in names and names[t] != name:
                problems.append(f"{name}: '{t}' collides with command '{names[t]}'")
            names[t] = name

    for gid in groups:
        if not any((c or {}).get("group") == gid for c in data["commands"].values()):
            problems.append(f"group '{gid}' has no commands")
    return problems


# ---------------------------------------------------------------- main

def main():
    global USE_COLOR
    ap = argparse.ArgumentParser(description="Visualize commands.yaml as a tree.")
    ap.add_argument("-f", "--file", help="path to commands.yaml (default: auto-detect)")
    ap.add_argument("--view", choices=["group", "context", "gate"], default="group")
    ap.add_argument("-d", "--details", action="store_true", help="show syntax, args, handler, etc.")
    ap.add_argument("-g", "--group", help="only this group")
    ap.add_argument("-c", "--context", help="only this context")
    ap.add_argument("--check", action="store_true", help="validate and exit (no tree)")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()

    if args.no_color or not sys.stdout.isatty():
        USE_COLOR = False
    if os.name == "nt":
        os.system("")  # enables ANSI colors in Windows terminals
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    path = find_file(args.file)
    data = load(path)
    problems = check(data)

    if not args.check:
        cmds = filter_commands(data, args.group, args.context)
        view = {"group": view_group, "context": view_context, "gate": view_gate}[args.view]
        root, nodes = view(data, cmds, args.details)
        print(bold(f"{root}") + dim(f"  ({path})"))
        draw(nodes)
        print()
        print(dim(f"{len(data['commands'])} commands, {len(data['groups'])} groups, "
                  f"{len(data['gates'])} gates, {len(data['contexts'])} contexts"))

    if problems:
        print()
        print(red(f"{len(problems)} problem(s):"))
        for p in problems:
            print("  - " + p)
        sys.exit(1)
    elif args.check:
        print("OK - no problems found.")


if __name__ == "__main__":
    main()
