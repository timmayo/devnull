"""Bot players used to test the slice headlessly. Not part of the game."""

from __future__ import annotations

from devnull.core.sim import Sim


def laptop_plan(sim: Sim) -> list[str]:
    """Find and buy a way to fix the laptop, cheapest route first."""
    s = sim.state
    if s["laptop"] >= 1:
        return []
    if s["lead_npc"] and s["trust"] >= 35 and s["cash"] >= 150:
        return ["upgrade_npc"]
    if s["lead_store"] and s["cash"] >= 350:
        return ["upgrade_store"]
    if not s["lead_store"]:
        return ["browse_store"]
    return []


def idle(sim: Sim) -> list[str]:
    """Goes to the day job and does nothing else. Should stay safe; should not win."""
    return []


def careful(sim: Sim) -> list[str]:
    """Slow organizer: builds trust, attends, backs off when hot, rests when worn down."""
    s = sim.state
    if s["heat"] > 15 or s["case_file"] > 30:
        return ["lay_low"]
    if s["burnout"] > 55:
        return ["rest"]
    plan = laptop_plan(sim)
    if plan:
        return plan + ["meet"]
    if s["cash"] < 150:
        return ["extra_shift"]
    if s["trust"] < 40:
        return ["meet", "attend"]
    return ["attend", "extra_shift"]


def activist(sim: Sim) -> list[str]:
    """Balanced: fixes the laptop, builds trust, then posts and leaks while managing heat."""
    s = sim.state
    if s["heat"] > 25 or s["case_file"] > 40:
        return ["lay_low"]
    if s["burnout"] > 55:
        return ["rest"]
    plan = laptop_plan(sim)
    if plan:
        return plan + ["meet"]
    if s["cash"] < 100:
        return ["extra_shift"]
    if s["trust"] < 30:
        return ["meet", "attend"]
    if s["heat"] < 12 and sim.can_do("leak"):
        return ["leak", "feed"]
    return ["feed", "attend"]


def reckless(sim: Sim) -> list[str]:
    """Leaks and posts constantly with no regard for heat."""
    s = sim.state
    if s["cash"] < 0:
        return ["extra_shift"]
    if sim.can_do("leak"):
        return ["leak", "feed"]
    return ["meet", "feed"]


POLICIES = {"idle": idle, "careful": careful, "activist": activist, "reckless": reckless}
