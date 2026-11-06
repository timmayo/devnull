#!/usr/bin/env python3
"""cmdview.py - build one web page that shows the whole command table, so you can look at it instead of the YAML.

    python tools/cmdview.py                  writes docs/command_viewer.html
    python tools/cmdview.py --open           ... and opens it in your browser
    python tools/cmdview.py --out FILE

The page is a single self-contained file (no internet, no server). Rebuild it after you change data/.
It shows: every command by group with what it needs and costs, every game variable with what needs it and what
changes it, the path a player must take to unlock any command, who answers each action (data/responses.yaml), and a health list (check problems, dead ends).
Read-only: you still edit the YAML files and rebuild.
"""
from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from devnull.core import commands as ct  # noqa: E402
from devnull.core.commands import read_yaml  # noqa: E402

DATA = ROOT / "data"
PERSON = ct.PERSON_PREFIX


# ---------------------------------------------------------------- reading the rules

def load_sources() -> dict[str, Any]:
    rules = read_yaml(DATA / "slice_rules.yaml")
    people = read_yaml(DATA / "people.yaml")
    research = read_yaml(DATA / "research.yaml") if (DATA / "research.yaml").exists() else {}
    rules["people"] = people
    return {"rules": rules, "people": people, "research": research}


def state_keys(src: dict[str, Any]) -> list[str]:
    """The game's real state variables (what a live command may test)."""
    try:
        from devnull.core.sim import Sim
        rules = dict(src["rules"])
        rules["research"] = src["research"]
        for key, name in (("market_tape", "market"), ("news", "news")):
            if (DATA / f"{name}.yaml").exists():
                rules[key] = read_yaml(DATA / f"{name}.yaml")
        return sorted(Sim(seed=1, rules=rules).state)
    except Exception:                       # the viewer must still build if the sim cannot
        return sorted(src["rules"].get("start", {}))


# ---------------------------------------------------------------- what changes what

def _effect(spec: dict[str, Any]) -> tuple[str, str]:
    """(direction, text) for one effect block: {bias, terms, set, p, delay, if}."""
    if "set" in spec:
        v = spec["set"]
        text = f"set to {v:g}" if isinstance(v, (int, float)) else f"set to {v}"
        if spec.get("p") is not None and spec["p"] < 1:
            text += f" ({spec['p'] * 100:.0f}% chance)"
        return ("up" if (isinstance(v, (int, float)) and v > 0) else "down" if v == 0 else "set"), text
    bias = spec.get("bias", 0) or 0
    terms = list((spec.get("terms") or {}))
    d = "up" if bias > 0 else "down" if bias < 0 else "varies"
    text = f"{bias:+g}" if bias else "varies"
    if terms:
        text += " (depends on " + ", ".join(terms) + ")"
    if spec.get("delay"):
        text += f", arrives in {spec['delay'][0]}-{spec['delay'][1]} days"
    if spec.get("if"):
        text += ", only if " + ", ".join(f"{k}>={v}" for k, v in spec["if"].items())
    return d, text


def effects_index(src: dict[str, Any], cmds: dict[str, Any]) -> list[dict[str, Any]]:
    """Every rule that changes a game value: {var, by (command or None), dir, how, via}."""
    rules, people, research = src["rules"], src["people"], src["research"]
    by_rule: dict[str, list[str]] = {}
    for k, c in cmds.items():
        if not ct.is_planned(c) and c.get("rule"):
            by_rule.setdefault(str(c["rule"]), []).append(k)
    out: list[dict[str, Any]] = []

    def add(var: str, by: str | None, d: str, how: str, via: str = "") -> None:
        out.append({"var": var, "by": by, "dir": d, "how": how, "via": via})

    for name, a in (rules.get("actions") or {}).items():
        for by in by_rule.get(name, []):
            for var, spec in (a.get("effects") or {}).items():
                d, text = _effect(spec or {})
                add(var, by, d, text)
    for item, sp in (rules.get("shop") or {}).items():
        for by in by_rule.get(f"shop.{item}", []):
            if sp.get("flag"):
                add(sp["flag"], by, "up", "set to 1 (you now own it)")
            add("cash", by, "down", f"-{sp.get('price', 0):g}")
            for var, n in (sp.get("risk") or {}).items():
                add(var, by, "up", f"{n:+g}")
    rc = (by_rule.get("research") or [None])[0]
    for topic, t in (research.get("topics") or {}).items():
        add(f"sk_{topic}", rc, "up", "level 1-3 as you study it", f"research {topic}")
        for lvl, L in (t.get("levels") or {}).items():
            for var, n in (L.get("add") or {}).items():
                add(var, rc, "up", f"{n:+g} at level {lvl}", f"research {topic}")
            for var, n in (L.get("set") or {}).items():
                add(var, rc, "up", f"set to {n:g} at level {lvl}", f"research {topic}")
    for pa, spec in (people.get("people_actions") or {}).items():
        for by in by_rule.get(f"people_actions.{pa}", []):
            for outcome in ("success", "fail", "backfire"):
                blk = spec.get(outcome) or {}
                for var, e in (blk.get("person") or {}).items():
                    d, text = _effect(e or {})
                    add(f"{PERSON}{var}", by, d, f"{text} ({outcome})")
                for var, e in (blk.get("player") or {}).items():
                    d, text = _effect(e or {})
                    add(var, by, d, f"{text} ({outcome})")
    # values derived from the people you know (Sim._refresh_derived)
    meets = [k for k in cmds if cmds[k].get("rule", "").startswith("people_actions.") and not ct.is_planned(cmds[k])]
    for var in ("trust", "press_trust", "techie_trust"):
        for by in meets:
            if any(e["var"] == f"{PERSON}trust" and e["by"] == by and e["dir"] == "up" for e in out):
                add(var, by, "up", "through the people you know", "derived")
    for by in by_rule.get("attend", []):
        add("people_n", by, "up", "you may meet someone at a meeting", "derived")
    for var, w in (rules.get("world") or {}).items():
        d, text = _effect(w if isinstance(w, dict) else {})
        add(var, None, d if d != "varies" else "drift", "moves on its own every day", "world")
    lad = rules.get("ladder") or {}
    if lad.get("var"):
        add(lad["var"], None, "up", f"rises when {lad.get('source', '?')} is high", "investigation ladder")
    for var, n in ((rules.get("lawsuit") or {}).get("win") or {}).items():
        add(var, None, "up" if n > 0 else "down", f"{n:+g} when a lawsuit is won", "court")
    el = rules.get("election") or {}
    for var, spec in el.items():
        d, text = _effect(spec or {})
        add(var, None, d, "changes at each election", "election")
    for k, h in ((src["people"].get("hooks")) or {}).items():
        for by in meets:
            if str(by).split("_", 1)[-1] in (h.get("actions") or []):
                add(k, by, "up", f"{h.get('p', 0) * 100:.0f}% chance when a {'/'.join(h.get('types', []))} trusts you", "hook")
    return out


# ---------------------------------------------------------------- the data blob

def responses_blob() -> dict[str, Any]:
    """data/responses.yaml for the page: who watches, what each can do, and how likely each action is to draw them."""
    from devnull.core import responses as rsp
    f = DATA / "responses.yaml"
    if not f.exists():
        return {"watchers": [], "footprints": []}
    resp = read_yaml(f)
    watchers = []
    for wid, w in resp["watchers"].items():
        share = dict(rsp.odds(resp, wid))
        watchers.append({"id": wid, "title": w.get("title", wid), "attention": w.get("attention") or {},
                         "responses": [{"id": str(r["id"]), "msg": r.get("msg", ""), "effects": r.get("effects") or {},
                                        "if": r.get("if") or {}, "weight": r.get("weight", 1),
                                        "share": share[str(r["id"])]} for r in w.get("responses") or []]})
    return {"watchers": watchers, "footprints": [{"key": k, "odds": dict(v or {})} for k, v in resp["footprints"].items()]}


def footprint_keys(c: dict[str, Any], gen: dict[str, str] | None) -> list[str]:
    """The keys the game looks up for this command, most specific first (see core/responses.py)."""
    if gen:
        return [f"{gen['verb']}.{gen['item']}", gen["verb"]]
    return [c["name"]]


def build(deep: bool = True) -> dict[str, Any]:
    data = ct.load_file(DATA / "commands")
    src = load_sources()
    keys = state_keys(src)
    problems = ct.check(data, rules=src["rules"] if deep else None, state_keys=keys if deep else None)
    cmds, gates, variables = data["commands"], data["gates"], data.get("variables") or {}

    def cond_json(spec: Any) -> list[dict[str, Any]]:
        res = []
        for c in ct.conditions(spec, gates, variables):
            res.append({"label": c.label, "when": dict(c.when), "scope": c.scope, "gate": c.gate,
                        "special": c.special, "planned": c.planned, "hint": c.hint})
        return res

    out_cmds = []
    generated = data.get("_generated") or {}
    catalog_file = {"shop": "data/slice_rules.yaml", "people_actions": "data/people.yaml"}
    for k, c in cmds.items():
        gen = generated.get(k)
        out_cmds.append({
            "name": k, "group": c["group"], "live": not ct.is_planned(c), "desc": ct.description_of(c),
            "syntax": c.get("syntax") or k, "aliases": [str(a) for a in ct.as_list(c.get("aliases"))],
            "parent": c.get("parent") or (gen or {}).get("verb"), "screen": c.get("screen"), "contexts": ct.contexts_of(c),
            "requires": cond_json(c.get("requires")), "hidden": cond_json(c.get("hidden_until")),
            "hours": ct.cmd_hours(c), "money": ct.cmd_money(c), "handler": c.get("handler"), "rule": c.get("rule"),
            "file": (f"{catalog_file[gen['catalog']]}  ›  {gen['catalog']}  ›  {gen['item']}" if gen
                     else f"data/commands/{data.get('_files', {}).get(k, '')}" if data.get("_files", {}).get(k) else ""),
            "gen": gen, "items": c.get("items"), "always": bool(c.get("always_available")),
            "locked_message": c.get("locked_message"), "online": bool(c.get("online")),
            "examples": c.get("examples") or [],
        })
    resp = responses_blob()
    fp = {f["key"]: f["odds"] for f in resp["footprints"]}
    for oc in out_cmds:
        for key in footprint_keys(oc, oc["gen"]):
            if key in fp:
                oc["footprint"] = {"key": key, "odds": fp[key]}
                break
    fx = effects_index(src, cmds)
    start = src["rules"].get("start") or {}
    all_vars: dict[str, dict[str, Any]] = {}

    def var(v: str) -> dict[str, Any]:
        return all_vars.setdefault(v, {"name": v, "live": v in keys or v.startswith(PERSON), "start": start.get(v),
                                       "hint": "", "person": v.startswith(PERSON)})

    for k in keys:
        var(k)
    for name in variables:
        if not str(name).endswith("*"):
            var(name)
    for c in out_cmds:
        for cond in c["requires"] + c["hidden"]:
            for w in cond["when"]:
                var(f"{PERSON}{w}" if cond["scope"] == "person" else w)
    for e in fx:
        var(e["var"])
    for v in all_vars.values():
        v["hint"] = ct.hint_for(variables, v["name"], "N")
    return {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "groups": [{"id": g, **{kk: vv for kk, vv in (d or {}).items()}}
                   for g, d in sorted(data["groups"].items(), key=lambda kv: (kv[1] or {}).get("order", 999))],
        "contexts": [{"id": c, "description": (d or {}).get("description", "")} for c, d in data["contexts"].items()],
        "gates": {g: {"description": (d or {}).get("description", ""), "planned": bool((d or {}).get("planned")),
                      "special": (d or {}).get("special"), "when": (d or {}).get("when") or {}} for g, d in gates.items()},
        "commands": out_cmds, "variables": sorted(all_vars.values(), key=lambda v: v["name"]),
        "effects": fx, "problems": problems, "deep": deep, "responses": resp,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "command_viewer.html")
    ap.add_argument("--open", action="store_true", help="open the page in your browser")
    args = ap.parse_args()
    blob = build()
    template = (Path(__file__).with_name("cmdview_template.html")).read_text(encoding="utf-8")
    html = template.replace("/*DATA*/null", json.dumps(blob, separators=(",", ":"), default=str).replace("</", "<\\/"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8", newline="\n")
    live = sum(1 for c in blob["commands"] if c["live"])
    print(f"wrote {args.out}  ({len(blob['commands'])} commands, {live} live, {len(blob['variables'])} variables, "
          f"{len(blob['problems'])} problem(s))")
    if args.open:
        webbrowser.open(args.out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
