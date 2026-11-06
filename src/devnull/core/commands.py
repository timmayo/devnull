"""The command table: load data/commands/, check it, resolve what the player types.

No game state lives here and no UI code. The file format is documented in data/commands/README.txt.
`tools/cmdtree.py --check` and the game's startup both call `check()`.

Layout of data/commands/ (one folder, so two people rarely edit the same file):
    contexts.yaml    where the player can be
    groups.yaml      how commands are grouped and ordered
    gates.yaml       the few named conditions worth a name (bundles, planned ideas, admin)
    variables.yaml   the vocabulary of game values a condition may test, and the hint shown when it fails
    <group>.yaml     one file per group: a list of `- name: ...` commands

A command says what it needs inline:   requires: { cash: 300, evidence: 20 }
A person condition has a prefix:       requires: { person.trust: 25 }
A named gate is just a string:         requires: [has_linux_laptop, { skills: 15 }]
The hint shown when a condition fails is generated from variables.yaml.

Everything below works with `data["commands"][name]`, a dict keyed by command name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Collection, Iterable, Mapping

import yaml

try:                                            # the C parser is ~50x faster; plain PyYAML is the fallback
    _Loader: Any = yaml.CSafeLoader
except AttributeError:                          # pragma: no cover
    _Loader = yaml.SafeLoader

# What a `person.<key>` condition can look at (see Sim.person_action_visible).
PERSON_KEYS = {"meetings", "trust", "bond", "leverage", "owes"}
PERSON_PREFIX = "person."
GATE_SPECIALS = {"admin"}
RESERVED_FILES = {"contexts", "groups", "gates", "variables"}


class CommandFileError(ValueError):
    """The command table has problems. The message lists them."""


# ---------------------------------------------------------------- loading

def as_list(v: Any) -> list[Any]:
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple)) else [v]


def read_yaml(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return yaml.load(f, Loader=_Loader)


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
    """Load the command table from a folder (the normal layout) or from one single YAML file."""
    path = Path(path)
    if path.is_dir():
        return _load_dir(path)
    data = read_yaml(path) or {}
    for section in ("contexts", "gates", "groups", "variables", "commands"):
        if data.get(section) is None:
            data[section] = {}
    data["commands"], data["_load_problems"] = commands_by_name(data["commands"])
    data["_files"] = {k: path.name for k in data["commands"]}
    return data


def _load_dir(root: Path) -> dict[str, Any]:
    problems: list[str] = []
    data: dict[str, Any] = {"version": 1, "contexts": {}, "groups": {}, "gates": {}, "variables": {},
                            "commands": {}, "_files": {}}
    for name in sorted(RESERVED_FILES):
        p = root / f"{name}.yaml"
        if not p.exists():
            if name in ("contexts", "groups"):
                problems.append(f"{root.name}/{name}.yaml is missing")
            continue
        got = read_yaml(p) or {}
        if not isinstance(got, dict):
            problems.append(f"{p.name}: must be a mapping of name -> entry")
            continue
        data[name] = got
    order = {g: i for i, (g, _) in enumerate(sorted(
        data["groups"].items(), key=lambda kv: ((kv[1] or {}).get("order", 999), str(kv[0]))))}
    files = [p for p in root.glob("*.yaml") if p.stem not in RESERVED_FILES]
    for p in sorted(files, key=lambda p: (order.get(p.stem, 999), p.stem)):   # group order, so the table reads in order
        group = p.stem
        if group not in data["groups"]:
            problems.append(f"{p.name}: there is no group '{group}' in groups.yaml (a file is one group)")
        raw = read_yaml(p)
        if isinstance(raw, dict) and "commands" in raw:
            raw = raw["commands"]
        cmds, probs = commands_by_name(raw)
        problems += [f"{p.name}: {x}" for x in probs]
        for name, c in cmds.items():
            if name in data["commands"]:
                problems.append(f"{p.name}: command '{name}' is already defined in {data['_files'][name]}")
                continue
            c = dict(c or {})
            if c.get("group") not in (None, group):
                problems.append(f"{p.name}: {name} says group {c['group']!r} but lives in the {group} file")
            c["group"] = group
            data["commands"][name] = c
            data["_files"][name] = p.name
    data["_load_problems"] = problems
    return data


DEFAULT_CONTEXTS = ["world"]
STATUSES = ("planned", "implemented")


def is_planned(c: Mapping[str, Any] | None) -> bool:
    """Planned unless `status: implemented`, so a command is never live by accident."""
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


# ---------------------------------------------------------------- conditions

def _num(n: Any) -> str:
    return f"{n:g}" if isinstance(n, (int, float)) and not isinstance(n, bool) else str(n)


@dataclass(frozen=True)
class Cond:
    """One thing that must hold. Either a named gate (`gate` is its name) or one inline `var: n` test."""
    label: str                                  # how it is drawn: "cash>=300", "person.trust>=25", or the gate name
    when: Mapping[str, float] = field(default_factory=dict)     # {var: minimum}, without the person. prefix
    scope: str = "state"                        # state | person
    special: str | None = None                  # admin: holds only in admin mode
    planned: bool = False                       # its variable is not in the game yet: never holds
    hint: str = ""
    gate: str | None = None


def default_hint(var: str, n: Any, person: bool) -> str:
    name = var.replace("_", " ")
    if person:
        return f"They do not have {name} {_num(n)}+ with you yet." if var != "leverage" \
            else "You have nothing on them to use."
    return f"Needs {name} {_num(n)}+."


def hint_for(variables: Mapping[str, Any], key: str, n: Any) -> str:
    """The text shown when `key >= n` fails. `key` is as written in the file (person.trust ...)."""
    v = variables.get(key) or {}
    template = v.get("hint") if isinstance(v, dict) else None
    if template:
        return str(template).replace("{n}", _num(n))
    person = key.startswith(PERSON_PREFIX)
    return default_hint(key[len(PERSON_PREFIX):] if person else key, n, person)


def conditions(spec: Any, gates: Mapping[str, Any], variables: Mapping[str, Any]) -> list[Cond]:
    """Turn a `requires` / `hidden_until` value into Cond objects. All of them must hold.
    A string is a named gate, a mapping is `{var: minimum}` (one Cond each), a list mixes both."""
    out: list[Cond] = []
    for item in as_list(spec):
        if isinstance(item, dict):
            for k, n in item.items():
                person = str(k).startswith(PERSON_PREFIX)
                var = str(k)[len(PERSON_PREFIX):] if person else str(k)
                out.append(Cond(label=f"{k}>={_num(n)}", when={var: n}, scope="person" if person else "state",
                                hint=hint_for(variables, str(k), n)))
        elif isinstance(item, str):
            g = gates.get(item)
            if g is None:                       # unknown gate: check() reports it; it never holds
                out.append(Cond(label=item, planned=True, gate=item, hint=item))
                continue
            when = dict(g.get("when") or {})
            out.append(Cond(label=item, when=when, scope=g.get("scope") or "state", special=g.get("special"),
                            planned=bool(g.get("planned")) or (not when and not g.get("special")),
                            hint=str(g.get("hint") or g.get("description") or item), gate=item))
        else:
            out.append(Cond(label=str(item), planned=True, hint=str(item)))
    return out


def cond_holds(c: Cond, state: Mapping[str, float], admin: bool = False,
               person: Mapping[str, float] | None = None) -> bool:
    if c.special == "admin":
        return admin
    if c.planned or not c.when:
        return False                            # a planned condition never holds
    if c.scope == "person":
        if person is None:
            return True                         # the handler checks these against the person
        return all(person.get(k, 0) >= v for k, v in c.when.items())
    return all(state.get(k, 0) >= v for k, v in c.when.items())


def merged_when(conds: Iterable[Cond]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for c in conds:
        out.update(c.when)
    return out


# ---------------------------------------------------------------- checks

def check(data: Mapping[str, Any], handlers: Collection[str] | None = None,
          rules: Mapping[str, Any] | None = None, state_keys: Collection[str] | None = None) -> list[str]:
    """Return a list of problems (empty = fine).

    handlers    names of the Python functions that exist; each non-planned command must use one.
    rules       the loaded slice rules; `rule:` references must exist and every rule needs an entry.
    state_keys  the game's state variables; a live command's conditions may only test these.
    """
    problems: list[str] = list(data.get("_load_problems") or [])
    groups, contexts, gates, cmds = data["groups"], data["contexts"], data["gates"], data["commands"]
    variables = data.get("variables") or {}

    for gname, g in gates.items():
        g = g or {}
        scope = g.get("scope")
        if scope not in (None, "person"):
            problems.append(f"gate {gname}: unknown scope {scope!r}")
        if g.get("special"):
            if g["special"] not in GATE_SPECIALS:
                problems.append(f"gate {gname}: unknown special {g['special']!r}")
            continue
        when = g.get("when")
        if when is None:
            if not g.get("planned"):
                problems.append(f"gate {gname}: no `when` (add one, or mark the gate planned: true)")
            continue
        if not isinstance(when, dict) or not when:
            problems.append(f"gate {gname}: `when` must be a set of variable: number pairs")
            continue
        for k, v in when.items():
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                problems.append(f"gate {gname}: `{k}` must be a number, got {v!r}")
            if scope == "person" and k not in PERSON_KEYS:
                problems.append(f"gate {gname}: {k!r} is not something a person has ({', '.join(sorted(PERSON_KEYS))})")
            if scope != "person" and state_keys is not None and not g.get("planned") and k not in state_keys:
                problems.append(f"gate {gname}: unknown state variable {k!r}")

    for vname, v in variables.items():
        if not isinstance(v, dict) and v is not None:
            problems.append(f"variable {vname}: must be a mapping (e.g. {{ hint: \"Needs {{n}}.\" }})")
        elif isinstance(v, dict) and v.get("hint") is not None and not isinstance(v["hint"], str):
            problems.append(f"variable {vname}: hint must be text")
        if str(vname).startswith(PERSON_PREFIX) and str(vname)[len(PERSON_PREFIX):] not in PERSON_KEYS:
            problems.append(f"variable {vname}: a person has only {', '.join(sorted(PERSON_KEYS))}")

    def check_spec(name: str, field_: str, spec: Any, planned: bool) -> None:
        for item in as_list(spec):
            if isinstance(item, str):
                if item not in gates:
                    problems.append(f"{name}: unknown gate {item!r} in {field_}")
                elif not planned and (gates[item] or {}).get("planned"):
                    problems.append(f"{name}: gate {item!r} is planned but this command is live")
            elif isinstance(item, dict):
                for k, n in item.items():
                    if not isinstance(n, (int, float)) or isinstance(n, bool):
                        problems.append(f"{name}: {field_} {k} must be a number, got {n!r}")
                    person = str(k).startswith(PERSON_PREFIX)
                    var = str(k)[len(PERSON_PREFIX):] if person else str(k)
                    if person and var not in PERSON_KEYS:
                        problems.append(f"{name}: {field_} {k!r} - a person has only {', '.join(sorted(PERSON_KEYS))}")
                    elif variables and str(k) not in variables:
                        problems.append(f"{name}: {field_} uses {k!r}, which is not in variables.yaml (typo? or add it)")
                    elif not planned and not person and state_keys is not None and var not in state_keys:
                        problems.append(f"{name}: live command tests {k!r}, which is not a game variable yet")
            else:
                problems.append(f"{name}: {field_} entries must be a gate name or {{ variable: number }}, got {item!r}")

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
            check_spec(name, field_, c.get(field_), planned)
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
    """The flat shape (usage, hours, help, unlock, needs ...) that apply_commands and the `commands`
    screen read. Planned commands are left out."""
    gates, variables = data["gates"], data.get("variables") or {}

    legacy: dict[str, Any] = {}
    for key, c in data["commands"].items():
        if is_planned(c):
            continue
        hidden = conditions(c.get("hidden_until"), gates, variables)
        if any(x.special == "admin" for x in hidden):
            unlock: Any = "admin"
        elif hidden:
            unlock = merged_when(hidden)
        else:
            unlock = "admin" if c["group"] == "admin" else "day1"
        e: dict[str, Any] = {"group": c["group"], "usage": c.get("syntax") or key, "hours": cmd_hours(c),
                             "unlock": unlock, "help": description_of(c), "screen": c.get("screen")}
        if c.get("requires"):
            e["needs"] = merged_when(conditions(c["requires"], gates, variables))
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
    """The loaded command table: resolves words, checks contexts and conditions."""

    def __init__(self, data: Mapping[str, Any]):
        self.data = data
        self.gates: Mapping[str, Any] = data["gates"]
        self.variables: Mapping[str, Any] = data.get("variables") or {}
        self.commands: dict[str, Any] = {k: v or {} for k, v in data["commands"].items()}
        # Only live commands the player can type: the key is the first word of its syntax.
        self.words: dict[str, dict[str, Any]] = {
            k: c for k, c in self.commands.items() if not is_planned(c) and typed_word(k, c) == k}
        self.aliases: dict[str, str] = {a: k for k, c in self.words.items() for a in as_list(c.get("aliases"))}
        self._requires = {k: conditions(c.get("requires"), self.gates, self.variables) for k, c in self.commands.items()}
        self._hidden = {k: conditions(c.get("hidden_until"), self.gates, self.variables) for k, c in self.commands.items()}
        self.group_order: list[str] = [k for k, _ in sorted(
            data["groups"].items(), key=lambda kv: (kv[1].get("order", 999), kv[0]))]

    # -- conditions ----------------------------------------------------
    def requires(self, key: str) -> list[Cond]:
        return self._requires[key]

    def hidden_until(self, key: str) -> list[Cond]:
        return self._hidden[key]

    @staticmethod
    def failing(conds: Iterable[Cond], state: Mapping[str, float], admin: bool = False) -> list[Cond]:
        return [c for c in conds if not cond_holds(c, state, admin)]

    # -- visibility ----------------------------------------------------
    def visible(self, key: str, state: Mapping[str, float], unlocked: Collection[str] = (),
                admin: bool = False) -> bool:
        """Works for any live command, including sub-entries such as buy_vpn that have no word of their own."""
        c = self.commands[key]
        if c.get("always_available"):
            return True
        if admin:
            return True
        if key in unlocked:                     # unlocks are sticky
            return True
        return not self.failing(self._hidden[key], state, admin)

    def visible_keys(self, state: Mapping[str, float], unlocked: Collection[str] = (),
                     admin: bool = False) -> list[str]:
        return [k for k in self.words if self.visible(k, state, unlocked, admin)]

    def children(self, key: str) -> list[str]:
        """Live sub-entries drawn under `key` (meet_coffee under meet), in table order."""
        return [k for k, c in self.commands.items() if c.get("parent") == key and not is_planned(c)]

    def by_screen(self, screen: str, top_level: bool = True) -> list[str]:
        """Live commands listed on one section of the in-game `commands` screen, in group order then
        table order. Sub-entries are left out unless top_level is False."""
        rank = {g: i for i, g in enumerate(self.group_order)}
        keys = [k for k, c in self.commands.items()
                if not is_planned(c) and c.get("screen") == screen and not (top_level and c.get("parent"))]
        return sorted(keys, key=lambda k: rank.get(self.commands[k].get("group"), 999))

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
        """None if the command may run, else the hint to show. Contexts first, then `requires`."""
        c = self.words[key]
        ctxs = contexts_of(c)
        if context not in ctxs:
            return f"You can't do that from here (it works in: {', '.join(ctxs) or 'nowhere yet'})."
        bad = self.failing(self._requires[key], state, admin)
        if bad:
            if c.get("locked_message"):
                return str(c["locked_message"])
            return " ".join(x.hint for x in bad)
        return None

    def handler(self, key: str) -> str:
        return str(self.commands[key].get("handler"))
