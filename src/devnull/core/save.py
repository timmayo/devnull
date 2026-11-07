"""Save and load a run. No UI code here.

A save is one JSON file holding everything that changes during play: the day, the state values, the
people (including what is hidden from the player), pending results, the log, the market path and the
random generator itself, so a loaded run plays out exactly as the unsaved one would have.

Not saved: the rules and city data. They are read from the data files again on load, so a data fix
reaches old saves. If a newer game added a state value, it starts at its default.

Where saves live (override with the DEVNULL_SAVES environment variable):
    Windows   %APPDATA%\\devnull\\saves
    other     ~/.local/share/devnull/saves
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from devnull import __version__
from devnull.core.sim import Person, Sim

SAVE_VERSION = 2          # 2: adds `setup` (the player's setup choices)
AUTOSAVE = "autosave"
DEFAULT_NAME = "quicksave"
_NAME = re.compile(r"[A-Za-z0-9_-]{1,40}")


class SaveError(Exception):
    """Something the player can be told in one sentence."""


# ---------------------------------------------------------------- where

def save_dir() -> Path:
    env = os.environ.get("DEVNULL_SAVES")
    if env:
        return Path(env)
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "devnull" / "saves"
    return Path.home() / ".local" / "share" / "devnull" / "saves"


def clean_name(name: str | None) -> str:
    name = (name or DEFAULT_NAME).strip()
    if name.lower().endswith(".json"):
        name = name[:-5]
    if not _NAME.fullmatch(name):
        raise SaveError("A save name can use letters, numbers, - and _ (up to 40 characters).")
    return name


def path_for(name: str | None, folder: Path | None = None) -> Path:
    return (folder or save_dir()) / f"{clean_name(name)}.json"


# ---------------------------------------------------------------- JSON with dates

def _encode(o: Any) -> Any:
    if isinstance(o, datetime):
        return {"__datetime__": o.isoformat()}
    if isinstance(o, date):
        return {"__date__": o.isoformat()}
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    raise TypeError(f"cannot save {type(o).__name__}")


def _decode(d: dict[str, Any]) -> Any:
    if "__date__" in d and len(d) == 1:
        return date.fromisoformat(d["__date__"])
    if "__datetime__" in d and len(d) == 1:
        return datetime.fromisoformat(d["__datetime__"])
    return d


# ---------------------------------------------------------------- snapshot / restore

def snapshot(sim: Sim, city_id: str) -> dict[str, Any]:
    """Everything needed to rebuild `sim`, as plain data."""
    rng = sim.rng.getstate()
    return {
        "game": "devnull",
        "save_version": SAVE_VERSION,
        "game_version": __version__,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "city": city_id,
        "seed": sim.seed,
        "setup": sim.setup,
        "start_date": sim.start_date,
        "max_turns_override": sim.max_turns_override,
        "show_all": sim.show_all,
        "turn": sim.turn,
        "hours_left": sim.hours_left,
        "began": sim._began,
        "ending": sim.ending,
        "state": sim.state,
        "history": sim.history,
        "pending": [list(p) for p in sim.pending],
        "log": [list(e) for e in sim.log],
        "election_log": [list(e) for e in sim.election_log],
        "people": [asdict(p) for p in sim.people],
        "next_cid": sim._next_cid,
        "unlocked": sorted(sim.unlocked),
        "new_unlocks": list(sim.new_unlocks),
        "prices": sim.prices,
        "price_change": sim.price_change,
        "prices_real": sim.prices_real,
        "skill_xp": sim.skill_xp,
        "quotes": sim.quotes,
        "feed": sim.feed,
        "rng": [rng[0], list(rng[1]), rng[2]],
    }


def restore(data: dict[str, Any], rules: dict[str, Any], events: list[dict[str, Any]] | None = None,
            city: dict[str, Any] | None = None) -> Sim:
    """Rebuild a Sim from `snapshot` data. `events` are the city's dated events and `city` its whole file
    (both read fresh from the city file, so a fix reaches old saves; a save without `setup` gets the defaults)."""
    if data.get("game") != "devnull":
        raise SaveError("That file is not a /dev/null save.")
    if int(data.get("save_version", 0)) > SAVE_VERSION:
        raise SaveError("That save is from a newer version of the game. Update the game first.")
    sim = Sim(seed=data["seed"], rules=rules, start_date=data["start_date"],
              max_turns_override=data.get("max_turns_override"), events=events or [],
              city=city, setup=data.get("setup"), quotes=data.get("quotes") or {}, feed=data.get("feed") or {})
    sim.show_all = bool(data.get("show_all"))
    sim.turn = int(data["turn"])
    sim.hours_left = data["hours_left"]
    sim._began = bool(data["began"])
    sim.ending = data.get("ending")
    sim.state = {**sim.state, **data["state"]}   # new values keep their default
    sim.history = [dict(h) for h in data["history"]]
    sim.pending = [(int(p[0]), p[1], p[2]) for p in data["pending"]]
    sim.log = [(int(e[0]), e[1], e[2]) for e in data["log"]]
    sim.election_log = [(int(e[0]), float(e[1])) for e in data["election_log"]]
    sim.people = [Person(**p) for p in data["people"]]
    sim._next_cid = int(data["next_cid"])
    sim.unlocked = set(data["unlocked"])
    sim.new_unlocks = list(data.get("new_unlocks") or [])
    sim.prices = dict(data["prices"])
    sim.price_change = dict(data["price_change"])
    sim.prices_real = bool(data["prices_real"])
    sim.skill_xp = dict(data["skill_xp"])
    r = data["rng"]
    sim.rng.setstate((r[0], tuple(r[1]), r[2]))
    return sim


# ---------------------------------------------------------------- files

def write(sim: Sim, city_id: str, name: str | None = None, folder: Path | None = None) -> Path:
    """Save to <folder>/<name>.json. Written to a temp file first, so a crash never leaves half a save."""
    path = path_for(name, folder)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(snapshot(sim, city_id), default=_encode, indent=None, separators=(",", ":"))
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".save-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except OSError as e:
        raise SaveError(f"Could not save to {path}: {e.strerror or e}") from e
    return path


def read(name: str | None, folder: Path | None = None) -> dict[str, Any]:
    path = path_for(name, folder)
    if not path.exists():
        raise SaveError(f"No save called '{clean_name(name)}'.")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f, object_hook=_decode)
    except (OSError, ValueError) as e:
        raise SaveError(f"'{clean_name(name)}' is damaged and cannot be read.") from e


def list_saves(folder: Path | None = None) -> list[dict[str, Any]]:
    """Newest first. Each item: name, saved_at, day, date, city, cash. Damaged files are skipped."""
    folder = folder or save_dir()
    if not folder.is_dir():
        return []
    out = []
    for p in folder.glob("*.json"):
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f, object_hook=_decode)
            if d.get("game") != "devnull":
                continue
            out.append({"name": p.stem, "saved_at": d.get("saved_at", ""), "mtime": p.stat().st_mtime,
                        "day": int(d["turn"]) + 1, "date": d["start_date"] + _days(int(d["turn"])),
                        "city": d.get("city", "?"), "cash": d["state"].get("cash", 0)})
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return sorted(out, key=lambda x: x["mtime"], reverse=True)


def _days(n: int) -> timedelta:
    return timedelta(days=n)
