#!/usr/bin/env python3
"""cmdtree.py - draw the command table (data/commands/) as a tree, and check it.

Usage examples:
    python tools\\cmdtree.py                      # tree by group
    python tools\\cmdtree.py -d                   # with details
    python tools\\cmdtree.py --view context       # context > group > command
    python tools\\cmdtree.py --view needs         # requirement > commands that use it (cash>=300, person.trust>=25 ...)
    python tools\\cmdtree.py -g hack              # only one group
    python tools\\cmdtree.py --status planned     # only planned (or implemented) commands
    python tools\\cmdtree.py -c shell             # only one context
    python tools\\cmdtree.py --check              # validate the file
    python tools\\cmdtree.py --check --deep       # also check rule references and that live commands only use real game values
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from devnull.core.commands import (check as check_data, load_file, is_planned, cmd_hours, cmd_money,  # noqa: E402
                                   contexts_of, description_of, conditions, read_yaml)  # (the game runs the same checks)

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
    script_dir = Path(__file__).resolve().parent
    for p in (Path.cwd() / "data" / "commands", script_dir.parent / "data" / "commands"):
        if p.is_dir():
            return p
    sys.exit("data/commands/ not found. Use -f to give the folder.")


def load(path):
    return load_file(path)  # a folder (or one file); commands come back as a dict keyed by name


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


def cond_labels(data, spec):
    return [x.label for x in conditions(spec, data["gates"], data.get("variables") or {})]


def command_node(name, c, details, data=None):
    label = cyan(str(name))
    aliases = [str(a) for a in as_list(c.get("aliases"))]
    if aliases:
        label += dim(f" ({', '.join(aliases)})")
    req = cond_labels(data, c.get("requires")) if data else [str(r) for r in as_list(c.get("requires"))]
    if req:
        label += " " + yellow(f"[requires: {', '.join(req)}]")
    hid = cond_labels(data, c.get("hidden_until")) if data else [str(r) for r in as_list(c.get("hidden_until"))]
    if hid:
        label += " " + magenta(f"[hidden until: {', '.join(hid)}]")
    if is_planned(c):
        label += " " + red("[planned]")
    cost = ", ".join(x for x in (f"{cmd_hours(c):g}h" if cmd_hours(c) else "",
                                 f"${cmd_money(c):g}" if cmd_money(c) else "") if x)
    if cost:
        label += dim(f" ({cost})")
    if description_of(c):
        label += dim(f" - {description_of(c)}")

    kids = []
    if details:
        if c.get("syntax"):
            kids.append((f"syntax:   {c['syntax']}", []))
        kids.append((f"contexts: {', '.join(contexts_of(c))}", []))
        if data and data.get("_files", {}).get(name):
            kids.append((f"file:     {data['_files'][name]}", []))
        if c.get("status"):
            kids.append((f"status:   {c['status']}", []))
        if c.get("args"):
            kids.append(("args:     " + " ".join(fmt_arg(a) for a in c["args"]), []))
        if c.get("handler"):
            kids.append((f"handler:  {c['handler']}", []))
        for key in ("screen", "online", "type", "rule", "risk", "always_available", "locked_message"):
            if key in c:
                kids.append((f"{key}: {c[key]}", []))
        for ex in as_list(c.get("examples")):
            kids.append((f"example:  {ex.get('cmd')}", [(dim(str(ex.get('shows'))), [])]))
    return (label, kids)


def group_label(gid, g, count):
    title = g.get("title", gid) if g else "(not defined in groups)"
    desc = f" - {g['description']}" if g and g.get("description") else ""
    return f"{bold(title)} {dim(f'[{gid}]')} {dim(f'({count})')}{dim(desc)}"


# ---------------------------------------------------------------- views

def filter_commands(data, only_group, only_context, only_status=None):
    out = {}
    for name, c in data["commands"].items():
        c = c or {}
        if only_group and c.get("group") != only_group:
            continue
        if only_context and only_context not in contexts_of(c):
            continue
        if only_status and (("planned" if is_planned(c) else "implemented") != only_status):
            continue
        out[name] = c
    return out


def view_group(data, cmds, details):
    """Commands by group. A command with a `parent` is drawn under it, whatever its own group."""
    groups = data["groups"]
    kids_of = {}
    for n, c in cmds.items():
        if c.get("parent") in cmds:
            kids_of.setdefault(c["parent"], []).append(n)

    def node(n, c):
        label, kids = command_node(n, c, details, data)
        return (label, kids + [node(k, cmds[k]) for k in kids_of.get(n, [])])

    def is_root(c):
        return c.get("parent") not in cmds

    nodes = []
    seen = set()
    for gid, g in sorted_groups(groups):
        members = [(n, c) for n, c in cmds.items() if c.get("group") == gid and is_root(c)]
        count = sum(1 for c in cmds.values() if c.get("group") == gid)
        seen.update(n for n, _ in members)
        if not count and (len(cmds) != len(data["commands"])):
            continue  # hide empty groups when filtering
        kids = [node(n, c) for n, c in members] or [(dim("(no commands)"), [])]
        nodes.append((group_label(gid, g, count), kids))
    orphans = [(n, c) for n, c in cmds.items() if n not in seen and is_root(c)]
    if orphans:
        nodes.append((red("(ungrouped / unknown group)") + dim(f" ({len(orphans)})"), [node(n, c) for n, c in orphans]))
    return "commands", nodes


def view_context(data, cmds, details):
    nodes = []
    for ctx, info in data["contexts"].items():
        in_ctx = {n: c for n, c in cmds.items()
                  if str(ctx) in contexts_of(c)}
        if not in_ctx:
            continue
        _, gnodes = view_group(data, in_ctx, details)
        desc = (info or {}).get("description")
        label = bold(str(ctx)) + (dim(f" - {desc}") if desc else "") + dim(f" ({len(in_ctx)})")
        nodes.append((label, gnodes))
    return "contexts", nodes


def view_needs(data, cmds, details):
    """Requirement > the commands that use it. Inline conditions (cash>=300) and named gates both appear."""
    gates, variables = data["gates"], data.get("variables") or {}
    uses = {}                                   # label -> [(command name, command, 'requires' | 'hidden_until')]
    for n, c in cmds.items():
        for f in ("requires", "hidden_until"):
            for x in conditions(c.get(f), gates, variables):
                uses.setdefault(x.label, []).append((n, c, f))
    def sort_key(label):
        g = gates.get(label)
        return (0 if g is not None else 1, label)
    nodes = []
    for label in sorted(uses, key=sort_key):
        members = uses[label]
        g = gates.get(label)
        shown = yellow(label)
        if g is not None:
            shown += (red(" [planned]") if g.get("planned") else "") + (dim(f" - {g['description']}") if g.get("description") else "")
        nodes.append((shown + dim(f" ({len({n for n, _, _ in members})})"),
                      [command_node(n, c, details, data) for n, c, _ in members]))
    free = [(n, c) for n, c in cmds.items() if not as_list(c.get("requires"))]
    if free:
        nodes.append((bold("(no requirement - always usable)") + dim(f" ({len(free)})"),
                      [command_node(n, c, details, data) for n, c in free]))
    return "needs", nodes


view_gate = view_needs                          # the old name


# ---------------------------------------------------------------- drawing

def draw(nodes, prefix=""):
    for i, (label, kids) in enumerate(nodes):
        last = i == len(nodes) - 1
        print(prefix + ("└── " if last else "├── ") + label)
        draw(kids, prefix + ("    " if last else "│   "))


# ---------------------------------------------------------------- checks

def check(data, deep=False):
    """Structural checks, shared with the game (devnull.core.commands.check). `deep` also loads the rules to
    check `rule:` references, that every rule has a command, and that live commands only test real game values."""
    rules = state_keys = None
    if deep:
        from devnull.core.sim import Sim
        data_dir = Path(__file__).resolve().parents[1] / "data"
        rules = read_yaml(data_dir / "slice_rules.yaml")
        rules["people"] = read_yaml(data_dir / "people.yaml")
        for key, name in (("market_tape", "market"), ("research", "research"), ("news", "news")):
            if (data_dir / f"{name}.yaml").exists():
                rules[key] = read_yaml(data_dir / f"{name}.yaml")
        state_keys = set(Sim(seed=1, rules=rules).state)
    return check_data(data, rules=rules, state_keys=state_keys)


# ---------------------------------------------------------------- main

def main():
    global USE_COLOR
    ap = argparse.ArgumentParser(description="Draw the command table (data/commands/) as a tree, and check it.")
    ap.add_argument("-f", "--file", help="the commands folder (default: data/commands)")
    ap.add_argument("--view", choices=["group", "context", "needs", "gate"], default="group",
                    help="gate is the old name for needs")
    ap.add_argument("-d", "--details", action="store_true", help="show syntax, args, handler, etc.")
    ap.add_argument("-g", "--group", help="only this group")
    ap.add_argument("-c", "--context", help="only this context")
    ap.add_argument("--status", choices=["planned", "implemented"], help="only commands with this status")
    ap.add_argument("--check", action="store_true", help="validate and exit (no tree)")
    ap.add_argument("--deep", action="store_true", help="with --check: also check rule references and coverage")
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
    problems = check(data, deep=args.deep)

    if not args.check:
        cmds = filter_commands(data, args.group, args.context, args.status)
        view = {"group": view_group, "context": view_context, "needs": view_needs, "gate": view_needs}[args.view]
        root, nodes = view(data, cmds, args.details)
        print(bold(f"{root}") + dim(f"  ({path})"))
        draw(nodes)
        print()
        planned = sum(1 for c in data["commands"].values() if is_planned(c))
        print(dim(f"{len(data['commands'])} commands ({len(data['commands']) - planned} implemented, {planned} planned), "
                  f"{len(data['groups'])} groups, {len(data['gates'])} named gates, {len(data.get('variables') or {})} variables, "
                  f"{len(data['contexts'])} contexts"))

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
