"""A city's rules and the player's setup choices. No UI code here.

Two blocks of a city file feed the simulation (cities/<id>.yaml):

    mechanics:  the city's real rules as numbers (records timing, local elections, ...). Each entry names
                the `real:` fact it comes from (`source_fact`).
    setup:      what the player chooses at the start: home neighborhood, day job, savings cushion. Each
                option carries effects on the daily rules (`daily:`) and on starting values (`state:`).
    start:      the city's own starting values, replacing the ones in data/slice_rules.yaml.
    daily:      the city's own daily rules (for example `upkeep`), replacing the baseline, by dotted path.

The first option of a group is the default unless one is marked `default: true`. Defaults must carry no
effects, so a run with no choices plays exactly like the baseline rules.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from typing import Any

GROUPS = ("neighborhood", "job", "cushion")        # the order the player is asked in


# ---------------------------------------------------------------- business days

def is_business_day(d: date) -> bool:
    return d.weekday() < 5


def add_business_days(d: date, n: int) -> date:
    """`n` business days after `d` (Monday to Friday; holidays are ignored)."""
    while n > 0:
        d += timedelta(1)
        if is_business_day(d):
            n -= 1
    return d


def records_delay(today: date, rule: dict[str, Any], rng) -> int:
    """Days until the answer to a records request filed today arrives.

    An electronic request counts as received `receive_lag` business days after it is sent; the body must
    answer within `respond` business days of that, or issue one notice that adds up to `extension` more.
    Most answers land inside the first window; `extension_chance` of them use the extension.
    """
    lag = int(rule.get("receive_lag_business_days", 0))
    respond = int(rule["respond_business_days"])
    extension = int(rule.get("extension_business_days", 0))
    if extension and rng.random() < float(rule.get("extension_chance", 0.0)):
        lo, hi = lag + respond + 1, lag + respond + extension
    else:
        lo, hi = lag + 1, lag + respond
    n = rng.randint(lo, hi)
    return max(1, (add_business_days(today, n) - today).days)


# ---------------------------------------------------------------- reading a city file

def mechanics(city: dict[str, Any] | None) -> dict[str, Any]:
    return (city or {}).get("mechanics") or {}


def groups(city: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """{'neighborhood': {...}, 'job': {...}, 'cushion': {...}} for the groups the city defines."""
    s = (city or {}).get("setup") or {}
    return {g: s[g] for g in GROUPS if isinstance(s.get(g), dict) and s[g].get("options")}


def default_option(group: dict[str, Any]) -> dict[str, Any]:
    opts = group["options"]
    return next((o for o in opts if o.get("default")), opts[0])


def default_picks(city: dict[str, Any] | None) -> dict[str, str]:
    return {g: default_option(spec)["id"] for g, spec in groups(city).items()}


def option(city: dict[str, Any] | None, group: str, pick: str) -> dict[str, Any] | None:
    spec = groups(city).get(group)
    return next((o for o in (spec or {}).get("options", []) if o["id"] == pick), None)


def resolve(city: dict[str, Any] | None, picks: dict[str, str] | None) -> dict[str, str]:
    """Picks with a default filled in for anything missing or no longer in the city file (an old save)."""
    base = default_picks(city)
    for g, pick in (picks or {}).items():
        if g in base and option(city, g, pick) is not None:
            base[g] = pick
    return base


# ---------------------------------------------------------------- applying choices

def _bump(tree: dict[str, Any], path: str, delta: float) -> None:
    """Add `delta` to the number at a dotted path such as 'free_hours.workday'."""
    node = tree
    parts = path.split(".")
    for p in parts[:-1]:
        node = node[p]
    node[parts[-1]] += delta


def _set(tree: dict[str, Any], path: str, value: Any) -> None:
    node = tree
    parts = path.split(".")
    for p in parts[:-1]:
        node = node[p]
    node[parts[-1]] = value


def apply(rules: dict[str, Any], state: dict[str, float], city: dict[str, Any] | None,
          picks: dict[str, str] | None) -> dict[str, str]:
    """Change `rules['daily']` and `state` in place for the city and the player's picks.

    The caller passes its own copies: shared rules must never be changed. Order: the city's `start:`
    values replace the baseline, then each choice adds its deltas. Returns the picks actually used.
    """
    for var, value in ((city or {}).get("start") or {}).items():
        if var in state:
            state[var] = float(value)
    for path, value in ((city or {}).get("daily") or {}).items():
        _set(rules["daily"], path, value)
    used = resolve(city, picks)
    for g, pick in used.items():
        opt = option(city, g, pick) or {}
        for path, delta in (opt.get("daily") or {}).items():
            _bump(rules["daily"], path, delta)
        for var, delta in (opt.get("state") or {}).items():
            state[var] += delta
    return used


def start_skills(city: dict[str, Any] | None, picks: dict[str, str]) -> dict[str, int]:
    """Skill levels (1 beginner, 2 advanced, 3 expert) the choices start the player with."""
    out: dict[str, int] = {}
    for g, pick in picks.items():
        for skill, level in ((option(city, g, pick) or {}).get("skills") or {}).items():
            out[skill] = max(level, out.get(skill, 0))
    return out


def private_rules(rules: dict[str, Any]) -> dict[str, Any]:
    """A copy of `rules` that a run may change: shallow, except `daily`, which setup edits."""
    mine = dict(rules)
    mine["daily"] = deepcopy(rules["daily"])
    return mine


def describe(city: dict[str, Any] | None, picks: dict[str, str]) -> list[tuple[str, str, str]]:
    """[(group, option name, one-line blurb)] for the status screen."""
    out = []
    for g in GROUPS:
        opt = option(city, g, picks.get(g, ""))
        if opt:
            out.append((g, opt["name"], opt.get("blurb", "")))
    return out
