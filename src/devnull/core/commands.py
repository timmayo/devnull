"""The command table: load data/commands.yaml, check it, resolve what the player types.

No game state lives here and no UI code. The file format is documented at the top of
data/commands.yaml. `tools/cmdtree.py --check` and the game's startup both call `check()`.

`commands:` in the file is a list of `- name: ...` entries. `load_file` turns it into a dict keyed by name,
so everything below works with `data["commands"][name]`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Collection, Iterable, Mapping

import yaml

# What a `scope: person` gate can look at (see Sim.person_action_visible).
PERSON_KEYS = {"meetings", "trust", "bond", "leverage", "owes"}
GATE_SPECIALS = {"admin"}


class CommandFileError(ValueError):
    """commands.yaml has problems. The message lists them."""


# ---------------------------------------------------------------- loading

def as_list(v: Any) -> list[Any]:
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple)) else [v]


def commands_by_name(raw: Any) -> tuple[dict[str, Any], list[str]]:
    """`commands:` as a dict keyed by name, plus any problems found while reading it.
    The file lists commands as `- name: x`; a mapping of name -> entry is accepted too."""
    problems: list[str] = []
    if isinstance(raw, dict):
        return dict(raw), problems
    out: dict[str, Any] = {}
    for i, c in enumerate(as_list(raw), 1):
        if not isinstance(c, dict) or not c.get("name"):
            problems.append(f"commands entry #{i} has no `name`")
            continue
        name = c["name"]
        if name in out:
            problems.append(f"command '{name}' is listed more than once")
            continue
        out[name] = {k: v for k, v in c.items() if k != "name"}
    return out, problems


def load_file(path: Path | str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    for section in ("contexts", "gates", "groups", "commands"):
        data.setdefault(section, {})
        if data[section] is None:
            data[section] = {}
    data["commands"], data["_load_problems"] = commands_by_name(data["commands"])
    return data


DEFAULT_CONTEXTS = ["world"]
STATUSES = ("planned", "implemented")


def is_planned(c: Mapping[str, Any] | None) -> bool:
    """Planned unless `status: implemented` (the default), so a command is never live by accident."""
    c = c or {}
    if "planned" in c:                       # older files
        return bool(c["planned"])
    return c.get("status", "planned") != "implemented"


def cmd_hours(c: Mapping[str, Any] | None) -> float:
    cost = (c or {}).get("cost")
    return (cost.get("hours", 0) or 0) if isinstance(cost, dict) else 0


def cmd_money(c: Mapping[str, Any] | None) -> float:
    cost = (c or {}).get("cost")
    return (cost.get("money", 0) or 0) if isinstance(cost, dict) else 0


def contexts_of(c: Mapping[str, Any] | None) -> list[str]:
    return [str(x) for x in as_list((c or {}).get("contexts"))] or list(DEFAULT_CONTEXTS)


def description_of(c: Mapping[str, Any] | None) -> str:
    return str((c or {}).get("description") or (c or {}).get("summary") or "")


def typed_word(key: str, c: Mapping[str, Any]) -> str:
    """The first word the player types. Sub-entries (meet_coffee, buy_vpn) share their parent word."""
    syntax = str(c.get("syntax") or key).split()
    return syntax[0].lower() if syntax else str(key).lower()


# ---------------------------------------------------------------- checks

def check(data: Mapping[str, Any], handlers: Collection[str] | None = None,
          rules: Mapping[str, Any] | None = None, state_keys: Collection[str] | None = None) -> list[str]:
    """Return a list of problems (empty = fine).

    handlers    names of the Python functions that exist; each non-planned command must use one.
    rules       the loaded slice rules; `rule:` references must exist and every rule needs an entry.
    state_keys  the game's state variables; gate `when` keys must be among them.
    """
    problems: list[str] = list(data.get("_load_problems") or [])
    groups, contexts, gates, cmds = data["groups"], data["contexts"], data["gates"], data["commands"]

    for gname, g in gates.items():
        g = g or {}
        scope = g.get("scope")
        if scope not in (None, "person"):
            problems.append(f"gate {gname}: unknown scope {scope!r}")
        if g.get("special"):
            if g["special"] not in GATE_SPECIALS:
                problems.append(f"gate {gname}: unknown special {g['special']!r}")
            continue
        if g.get("planned"):                    # its variable may not exist in the game yet
            when = g.get("when")
            if when is not None and not isinstance(when, dict):
                problems.append(f"gate {gname}: `when` must be a set of variable: number pairs")
            continue
        when = g.get("when")
        if not isinstance(when, dict) or not when:
            if not g.get("planned"):
                problems.append(f"gate {gname}: no `when` (add one, or mark the gate planned: true)")
            continue
        for k, v in when.items():
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                problems.append(f"gate {gname}: `{k}` must be a number, got {v!r}")
            if scope == "person" and k not in PERSON_KEYS:
                problems.append(f"gate {gname}: {k!r} is not something a person has ({', '.join(sorted(PERSON_KEYS))})")
            if scope != "person" and state_keys is not None and k not in state_keys:
                problems.append(f"gate {gname}: unknown state variable {k!r}")

    owners: dict[str, str] = {}
    words = {str(k) for k, c in cmds.items() if typed_word(str(k), c or {}) == str(k)}
    for key, c in cmds.items():
        c = c or {}
        name = str(key)
        if not isinstance(key, str):
            problems.append(f"command key {key!r} is not text (quote it in the YAML)")
        planned = is_planned(c)
        if c.get("status") is not None and c["status"] not in STATUSES:
            problems.append(f"{name}: status must be one of {', '.join(STATUSES)}, got {c['status']!r}")
        if c.get("group") not in groups:
            problems.append(f"{name}: unknown group {c.get('group')!r}")
        if not planned and not c.get("handler"):
            problems.append(f"{name}: no handler")
        if not planned and handlers is not None and c.get("handler") and c["handler"] not in handlers:
            problems.append(f"{name}: handler {c['handler']!r} does not exist")
        for ctx in contexts_of(c):
            if ctx not in contexts:
                problems.append(f"{name}: unknown context {ctx!r}")
        for field_ in ("requires", "hidden_until"):
            for g in as_list(c.get(field_)):
                if g not in gates:
                    problems.append(f"{name}: unknown gate {g!r} in {field_}")
                elif not planned and (gates[g] or {}).get("planned"):
                    problems.append(f"{name}: gate {g!r} is planned but this command is live")
        if c.get("parent") and c["parent"] not in cmds:
            problems.append(f"{name}: parent {c['parent']!r} is not a command")
        elif c.get("parent") and not planned and is_planned(cmds[c["parent"]]):
            problems.append(f"{name}: parent {c['parent']!r} is planned but this command is live")
        word = typed_word(name, c)
        if word != name and word not in words:
            problems.append(f"{name}: syntax starts with {word!r}, which is not a command")
        cost = c.get("cost")
        if cost is not None:
            if not isinstance(cost, dict):
                problems.append(f"{name}: cost must look like {{ hours: 2, money: 15 }}, got {cost!r}")
            else:
                for k, v in cost.items():
                    if k not in ("hours", "money"):
                        problems.append(f"{name}: cost has unknown part {k!r} (use hours and money)")
                    elif not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
                        problems.append(f"{name}: cost {k} must be a number of 0 or more, got {v!r}")
        ex = c.get("examples")
        if ex is not None:
            if not isinstance(ex, list) or not all(isinstance(e, dict) and e.get("cmd") and e.get("shows") for e in ex):
                problems.append(f"{name}: examples must be a list of {{ cmd, shows }} pairs")
        if not planned and c.get("rule") and rules is not None:
            if not rule_exists(rules, str(c["rule"])):
                problems.append(f"{name}: rule {c['rule']!r} not found in the rules data")

        for t in [name] + as_list(c.get("aliases")):
            if not isinstance(t, str):
                problems.append(f"{name}: alias {t!r} parsed as {type(t).__name__} - quote it in the YAML "
                                f"(e.g. \"no\", \"yes\", \"on\", \"off\" become booleans)")
                continue
            if t in owners and owners[t] != name:
                problems.append(f"{name}: '{t}' collides with command '{owners[t]}'")
            owners[t] = name

    for gid in groups:
        if not any((c or {}).get("group") == gid for c in cmds.values()):
            problems.append(f"group '{gid}' has no commands")

    if rules is not None:
        have = {str(c.get("rule")) for c in cmds.values() if c and c.get("rule") and not is_planned(c)}
        for a in rules.get("actions", {}):
            if a not in have:
                problems.append(f"rules action '{a}' has no command (add one with rule: {a})")
        for i in rules.get("shop", {}):
            if f"shop.{i}" not in have:
                problems.append(f"shop item '{i}' has no command (add one with rule: shop.{i})")
        for a in ((rules.get("people") or {}).get("people_actions") or {}):
            if f"people_actions.{a}" not in have:
                problems.append(f"people action '{a}' has no command (add one with rule: people_actions.{a})")
    return problems


def rule_exists(rules: Mapping[str, Any], ref: str) -> bool:
    if ref.startswith("shop."):
        return ref[5:] in rules.get("shop", {})
    if ref.startswith("people_actions."):
        return ref[15:] in ((rules.get("people") or {}).get("people_actions") or {})
    return ref in rules.get("actions", {})


# ---------------------------------------------------------------- legacy shape

def to_legacy(data: Mapping[str, Any]) -> dict[str, Any]:
    """The old commands.yaml shape (usage, hours, help, unlock, needs ...) that apply_commands,
    the `commands` screen and the doc generator read. Planned commands are left out."""
    gates = data["gates"]

    def merged(names: Iterable[str]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for n in names:
            out.update((gates[n] or {}).get("when") or {})
        return out

    legacy: dict[str, Any] = {}
    for key, c in data["commands"].items():
        if is_planned(c):
            continue
        hidden = as_list(c.get("hidden_until"))
        if any((gates[n] or {}).get("special") == "admin" for n in hidden):
            unlock: Any = "admin"
        elif hidden:
            unlock = merged(hidden)
        else:
            unlock = "admin" if c["group"] == "admin" else "day1"
        e: dict[str, Any] = {"group": c["group"], "usage": c.get("syntax") or key, "hours": cmd_hours(c),
                             "unlock": unlock, "help": description_of(c), "screen": c.get("screen")}
        if c.get("requires"):
            e["needs"] = merged(as_list(c["requires"]))
        if cmd_money(c):
            e["cost"] = cmd_money(c)
        for f in ("online", "type", "parent", "rule"):
            if f in c:
                e[f] = c[f]
        legacy[key] = e
    live_groups = {c["group"] for c in legacy.values()}
    groups = {k: {"title": g["title"], "note": g.get("description", "")}
              for k, g in sorted(data["groups"].items(), key=lambda kv: (kv[1].get("order", 999), kv[0]))
              if k in live_groups}
    return {"version": data.get("version", 1), "groups": groups, "commands": legacy}


# ---------------------------------------------------------------- resolving what the player types

@dataclass
class Resolution:
    key: str | None
    how: str = "unknown"                        # exact | alias | prefix | ambiguous | unknown
    matches: list[str] = field(default_factory=list)


class CommandSet:
    """The loaded command table: resolves words, checks contexts and gates."""

    def __init__(self, data: Mapping[str, Any]):
        self.data = data
        self.gates: Mapping[str, Any] = data["gates"]
        self.commands: dict[str, Any] = {k: v or {} for k, v in data["commands"].items()}
        # Only live commands the player can type: the key is the first word of its syntax.
        self.words: dict[str, dict[str, Any]] = {
            k: c for k, c in self.commands.items() if not is_planned(c) and typed_word(k, c) == k}
        self.aliases: dict[str, str] = {a: k for k, c in self.words.items() for a in as_list(c.get("aliases"))}

    # -- gates ---------------------------------------------------------
    def gate_ok(self, name: str, state: Mapping[str, float], admin: bool = False,
                person: Mapping[str, float] | None = None) -> bool:
        g = self.gates.get(name) or {}
        if g.get("special") == "admin":
            return admin
        when = g.get("when")
        if not when:
            return False                        # a planned gate with no rule never holds
        if g.get("scope") == "person":
            if person is None:
                return True                     # the handler checks these against the person
            return all(person.get(k, 0) >= v for k, v in when.items())
        return all(state.get(k, 0) >= v for k, v in when.items())

    def failing(self, names: Iterable[str], state: Mapping[str, float], admin: bool = False) -> list[str]:
        return [n for n in names if not self.gate_ok(n, state, admin)]

    # -- visibility ----------------------------------------------------
    def visible(self, key: str, state: Mapping[str, float], unlocked: Collection[str] = (),
                admin: bool = False) -> bool:
        c = self.words[key]
        if c.get("always_available"):
            return True
        if admin:
            return True
        if key in unlocked:                     # unlocks are sticky
            return True
        return not self.failing(as_list(c.get("hidden_until")), state, admin)

    def visible_keys(self, state: Mapping[str, float], unlocked: Collection[str] = (),
                     admin: bool = False) -> list[str]:
        return [k for k in self.words if self.visible(k, state, unlocked, admin)]

    # -- resolving -----------------------------------------------------
    def resolve(self, word: str, visible: Collection[str]) -> Resolution:
        """Exact name, then alias, then a unique prefix. Hidden commands do not exist for the player."""
        w = word.lower()
        if w in self.words and w in visible:
            return Resolution(w, "exact")
        a = self.aliases.get(w) or self.aliases.get(word)
        if a and a in visible:
            return Resolution(a, "alias")
        hits = [k for k in self.words if k in visible and k.startswith(w)]
        if len(hits) == 1:
            return Resolution(hits[0], "prefix", hits)
        if len(hits) > 1:
            return Resolution(None, "ambiguous", hits)
        return Resolution(None, "unknown")

    # -- may it run here and now? -------------------------------------
    def why_not(self, key: str, state: Mapping[str, float], context: str, admin: bool = False) -> str | None:
        """None if the command may run, else the hint to show. Contexts first, then `requires` gates."""
        c = self.words[key]
        ctxs = contexts_of(c)
        if context not in ctxs:
            return f"You can't do that from here (it works in: {', '.join(ctxs) or 'nowhere yet'})."
        bad = self.failing(as_list(c.get("requires")), state, admin)
        if bad:
            if c.get("locked_message"):
                return str(c["locked_message"])
            return " ".join(str((self.gates[n] or {}).get("hint") or (self.gates[n] or {}).get("description") or n)
                            for n in bad)
        return None

    def handler(self, key: str) -> str:
        return str(self.commands[key].get("handler"))
