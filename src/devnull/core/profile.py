"""What the game remembers about the player between runs: how many runs, the last city, how each ended.

One small JSON file next to the saves folder (%APPDATA%\\devnull\\profile.json on Windows). The opening
screen reads it: no file means this is the first time the game has been run on this PC.
Nothing here can break a game; every failure is swallowed and the game carries on without a profile.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from devnull.core.save import save_dir

MAX_RUNS_KEPT = 50


def profile_path() -> Path:
    return save_dir().parent / "profile.json"


def load() -> dict[str, Any] | None:
    """The profile, or None if the game has never been run here (or the file is unreadable)."""
    try:
        with open(profile_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) and isinstance(data.get("runs"), list) else None
    except (OSError, ValueError):
        return None


def _write(data: dict[str, Any]) -> None:
    try:
        p = profile_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        pass


def record_start(city_id: str, city_name: str, start: date) -> None:
    """A new run began. Creates the profile the first time."""
    data = load() or {"first_seen": date.today().isoformat(), "runs": []}
    data["runs"].append({"city": city_id, "city_name": city_name, "start": start.isoformat(),
                         "ending": None, "days": None})
    data["runs"] = data["runs"][-MAX_RUNS_KEPT:]
    data["total_runs"] = int(data.get("total_runs", 0)) + 1
    _write(data)


def record_end(ending: str, days: int) -> None:
    """The latest run finished with `ending` after `days` days."""
    data = load()
    if not data or not data["runs"]:
        return
    data["runs"][-1].update(ending=ending, days=days)
    _write(data)
