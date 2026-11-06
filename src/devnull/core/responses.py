"""The establishment answers back. No UI code here.

Every player action can draw a response from a watcher (Mega Corp, the AI, Government, FBI, NSA, a private
investigator ...). What each watcher does, and how likely each action is to draw it, lives in
data/responses.yaml; this module reads those rules and does the rolling. `Sim.act` calls `answers` once per
action and applies what it returns.

Pure functions: they take the rules, the state and a random generator, and change nothing.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Collection, Mapping

ATTENTION_MIN, ATTENTION_MAX = 0.25, 3.0
VERBS_WITH_ITEMS = ("attend", "meet", "research", "buy")


@dataclass(frozen=True)
class Answer:
    """One response that fired."""
    watcher: str
    title: str
    id: str
    msg: str
    effects: dict[str, float]
    action: str               # the footprint key that matched, e.g. "buy.vpn"


# ---------------------------------------------------------------- the rolling

def footprint_for(resp: Mapping[str, Any], keys: list[str]) -> tuple[str | None, Mapping[str, float]]:
    """The first key (most specific first) that has a footprint. (None, {}) = this action draws nothing."""
    table = resp.get("footprints") or {}
    for k in keys:
        if k in table:
            return k, table[k] or {}
    return None, {}


def attention(watcher: Mapping[str, Any], state: Mapping[str, float]) -> float:
    """How closely this watcher is looking right now, as a multiplier on every footprint."""
    spec = watcher.get("attention") or {}
    value = float(spec.get("bias", 1.0))
    for var, coef in (spec.get("terms") or {}).items():
        value += coef * state.get(var, 0.0)
    return max(ATTENTION_MIN, min(ATTENTION_MAX, value))


def chance(resp: Mapping[str, Any], watcher: str, base: float, state: Mapping[str, float]) -> float:
    return max(0.0, min(0.95, base * attention(resp["watchers"][watcher], state)))


def eligible(watcher: Mapping[str, Any], state: Mapping[str, float]) -> list[Mapping[str, Any]]:
    return [r for r in watcher.get("responses") or []
            if all(state.get(k, 0.0) >= v for k, v in (r.get("if") or {}).items())]


def draw(value: Any, rng: random.Random) -> float:
    """A number is exact; [low, high] is a random value in that range."""
    if isinstance(value, (list, tuple)):
        return round(rng.uniform(float(value[0]), float(value[1])), 1)
    return float(value)


def answers(resp: Mapping[str, Any] | None, state: Mapping[str, float], rng: random.Random,
            keys: list[str]) -> list[Answer]:
    """Who answers this action, and with what. Watchers are rolled in the order they appear in the file."""
    if not resp:
        return []
    key, fp = footprint_for(resp, keys)
    if key is None:
        return []
    out: list[Answer] = []
    for name, w in resp["watchers"].items():
        base = fp.get(name)
        if not base:
            continue
        if rng.random() >= chance(resp, name, base, state):
            continue
        pool = eligible(w, state)
        if not pool:
            continue
        pick = _pick(pool, rng)
        out.append(Answer(name, w.get("title", name), str(pick["id"]), str(pick.get("msg", "")),
                          {v: draw(x, rng) for v, x in (pick.get("effects") or {}).items()}, key))
    return out


def _pick(pool: list[Mapping[str, Any]], rng: random.Random) -> Mapping[str, Any]:
    total = sum(float(r.get("weight", 1)) for r in pool)
    x = rng.random() * total
    for r in pool:
        x -= float(r.get("weight", 1))
        if x <= 0:
            return r
    return pool[-1]


# ---------------------------------------------------------------- for the viewer and the docs

def odds(resp: Mapping[str, Any], watcher: str) -> list[tuple[str, float]]:
    """(response id, share of this watcher's answers) when every response is eligible."""
    rs = resp["watchers"][watcher].get("responses") or []
    total = sum(float(r.get("weight", 1)) for r in rs) or 1.0
    return [(str(r["id"]), float(r.get("weight", 1)) / total) for r in rs]


# ---------------------------------------------------------------- the checker

def _number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check(resp: Mapping[str, Any], state_keys: Collection[str] | None = None,
          rules: Mapping[str, Any] | None = None) -> list[str]:
    """Problems in data/responses.yaml (empty = fine). Game values are checked when `state_keys` is given."""
    problems: list[str] = []
    watchers = resp.get("watchers")
    table = resp.get("footprints")
    if not isinstance(watchers, dict) or not watchers:
        return ["responses.yaml: `watchers` must list at least one watcher"]
    if not isinstance(table, dict):
        return ["responses.yaml: `footprints` must be a mapping of action -> {watcher: chance}"]

    def real(var: str, where: str) -> None:
        if state_keys is not None and var not in state_keys:
            problems.append(f"{where}: '{var}' is not a value the game has")

    for name, w in watchers.items():
        w = w or {}
        if not w.get("title"):
            problems.append(f"watcher {name}: needs a `title`")
        att = w.get("attention") or {}
        if not isinstance(att, dict) or set(att) - {"bias", "terms"}:
            problems.append(f"watcher {name}: `attention` takes only `bias` and `terms`")
        else:
            if "bias" in att and not _number(att["bias"]):
                problems.append(f"watcher {name}: attention bias must be a number")
            for var, coef in (att.get("terms") or {}).items():
                real(var, f"watcher {name} attention")
                if not _number(coef):
                    problems.append(f"watcher {name}: attention term '{var}' must be a number")
        rs = w.get("responses")
        if not isinstance(rs, list) or not rs:
            problems.append(f"watcher {name}: needs at least one response")
            continue
        seen: set[str] = set()
        for i, r in enumerate(rs, 1):
            who = f"watcher {name}, response {r.get('id', f'#{i}') if isinstance(r, dict) else f'#{i}'}"
            if not isinstance(r, dict) or not r.get("id"):
                problems.append(f"watcher {name}: response #{i} has no `id`")
                continue
            if r["id"] in seen:
                problems.append(f"{who}: id is used twice")
            seen.add(r["id"])
            if set(r) - {"id", "weight", "if", "effects", "msg"}:
                problems.append(f"{who}: unknown field(s) {', '.join(sorted(set(r) - {'id', 'weight', 'if', 'effects', 'msg'}))}")
            if not _number(r.get("weight", 1)) or r.get("weight", 1) <= 0:
                problems.append(f"{who}: weight must be a number above 0")
            if not r.get("msg"):
                problems.append(f"{who}: needs a `msg` (what the player reads)")
            fx = r.get("effects")
            if not isinstance(fx, dict) or not fx:
                problems.append(f"{who}: needs `effects`")
                fx = {}
            for var, v in fx.items():
                real(var, who)
                ok = _number(v) or (isinstance(v, list) and len(v) == 2 and all(_number(x) for x in v) and v[0] <= v[1])
                if not ok:
                    problems.append(f"{who}: effect '{var}' must be a number or [low, high] with low <= high")
            for var, v in (r.get("if") or {}).items():
                real(var, f"{who} (if)")
                if not _number(v):
                    problems.append(f"{who}: `if` '{var}' must be a number")

    actions = set((rules or {}).get("actions") or {})
    items = {
        "buy": set((rules or {}).get("shop") or {}),
        "meet": set((((rules or {}).get("people") or {}).get("people_actions")) or {}),
        "research": set((((rules or {}).get("research") or {}).get("topics")) or {}),
    }
    used: set[str] = set()
    for key, fp in table.items():
        verb, _, item = str(key).partition(".")
        if rules is not None:
            if item:
                if verb not in VERBS_WITH_ITEMS:
                    problems.append(f"footprint '{key}': only {', '.join(VERBS_WITH_ITEMS)} take an item")
                elif verb in items and items[verb] and item not in items[verb]:
                    problems.append(f"footprint '{key}': there is no {verb} item called '{item}'")
            elif verb not in actions and verb not in VERBS_WITH_ITEMS:
                problems.append(f"footprint '{key}': not an action in the game")
        if not isinstance(fp, dict) or not fp:
            problems.append(f"footprint '{key}': must list at least one watcher (or leave the action out)")
            continue
        for who, p in fp.items():
            if who not in watchers:
                problems.append(f"footprint '{key}': '{who}' is not a watcher (use one of {', '.join(watchers)})")
            elif not _number(p) or not 0 < p <= 1:
                problems.append(f"footprint '{key}': chance for {who} must be above 0 and at most 1")
            else:
                used.add(who)
    for name in watchers:
        if name not in used:
            problems.append(f"watcher {name} is never used (no footprint lists it)")
    return problems
