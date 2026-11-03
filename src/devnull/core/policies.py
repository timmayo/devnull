"""Bot players used to test the slice headlessly. Not part of the game."""

from __future__ import annotations

from devnull.core.sim import Sim


def idle(sim: Sim) -> list[str]:
    """Works and does nothing else. Should stay safe; should not win."""
    return ["work", "work"]


def careful(sim: Sim) -> list[str]:
    """Slow organizer: builds trust, attends, backs off when hot."""
    s = sim.state
    if s["heat"] > 15 or s["case_file"] > 30:
        return ["lay_low", "work"]
    if s["cash"] < 150:
        return ["work", "work"]
    if s["trust"] < 40:
        return ["meet", "attend"]
    return ["attend", "work"]


def activist(sim: Sim) -> list[str]:
    """Balanced: builds trust, then posts and leaks while managing heat."""
    s = sim.state
    if s["heat"] > 25 or s["case_file"] > 40:
        return ["lay_low", "work"]
    if s["cash"] < 100:
        return ["work", "work"]
    if s["trust"] < 30:
        return ["meet", "attend"]
    if s["heat"] < 12 and sim.can_do("leak"):
        return ["leak", "feed"]
    return ["feed", "attend"]


def reckless(sim: Sim) -> list[str]:
    """Leaks and posts constantly with no regard for heat."""
    s = sim.state
    if s["cash"] < 0:
        return ["work", "work"]
    if sim.can_do("leak"):
        return ["leak", "feed"]
    return ["meet", "feed"]


POLICIES = {"idle": idle, "careful": careful, "activist": activist, "reckless": reckless}
