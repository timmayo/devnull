"""Bot players used to test the slice headlessly. Not part of the game."""

from __future__ import annotations

from devnull.core.sim import Sim


TECH = ("techie",)
PRESS = ("local_reporter",)


def socialize(sim: Sim, types: tuple[str, ...] | None = None, cap: float = 60) -> list[str]:
    """Go to a meeting if there is one, and nurture the best matching contact."""
    cands = [c for c in sim.contacts
             if not c.hostile and c.trust < cap and (types is None or c.type in types)]
    acts: list[str] = []
    if cands:
        c = max(cands, key=lambda x: x.trust)
        if c.type == "techie" and c.trust >= 25 and sim.state["laptop"] < 1 and sim.state["lead_npc"] < 1:
            acts.append(f"meet {c.id} ask")
        else:
            acts.append(f"meet {c.id} " + ("coffee" if sim.state["cash"] >= 30 else "favor"))
    if sim.meetings_today():
        acts.append("attend")
    return acts


def laptop_plan(sim: Sim) -> list[str]:
    """Find and buy a way to fix the laptop, cheapest route first."""
    s = sim.state
    if s["laptop"] >= 1:
        return []
    if s["lead_npc"] and s["techie_trust"] >= 35 and s["cash"] >= 150:
        return ["upgrade_npc"]
    if s["lead_store"] and s["cash"] >= 420:
        return ["upgrade_store"]
    if not s["lead_store"]:
        return ["browse_store"]
    return []


def linux_plan(sim: Sim) -> list[str]:
    s = sim.state
    if s["os"] >= 1 or s["laptop"] < 1:
        return []
    if s["lead_linux"]:
        return ["install_linux"]
    return ["research linux"]


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
        return plan + socialize(sim, TECH)
    if s["cash"] < 150:
        return ["extra_shift"]
    if s["trust"] < 40:
        return socialize(sim)
    if s["evidence"] < 20:
        return ["records"] + socialize(sim)
    return socialize(sim) + ["extra_shift"]


def activist(sim: Sim) -> list[str]:
    """Balanced: fixes the laptop, builds trust and evidence, then posts and leaks."""
    s = sim.state
    if s["heat"] > 25 or s["case_file"] > 40:
        return ["lay_low"]
    if s["burnout"] > 55:
        return ["rest"]
    plan = laptop_plan(sim)
    if plan:
        return plan + socialize(sim, TECH)
    if s["cash"] < 100:
        return ["extra_shift"]
    if s["press_trust"] < 20:
        return socialize(sim, PRESS) or socialize(sim)
    if s["evidence"] < 25:
        return ["records", "trace" if s["evidence"] < 10 else "verify"]
    if s["heat"] < 12 and sim.can_do("leak"):
        return ["leak", "feed"]
    return ["feed"] + socialize(sim)


def lawyer(sim: Sim) -> list[str]:
    """The legal route: records, verification, a lawsuit, then negotiation. No sabotage."""
    s = sim.state
    if s["heat"] > 25 or s["case_file"] > 40:
        return ["lay_low"]
    if s["burnout"] > 55:
        return ["rest"]
    plan = laptop_plan(sim)
    if plan:
        return plan + socialize(sim, TECH)
    if s["filed"] == 0 and s["cash"] < 420:
        return ["extra_shift"]
    if s["trust"] < 40:
        return socialize(sim)
    if s["evidence"] < 30 or s["verified"] < 20:
        return ["records", "verify"]
    if s["filed"] == 0 and sim.can_do("file"):
        return ["file"]
    if s["terms"] < 40 and sim.can_do("negotiate"):
        return ["negotiate", "records"]
    if s["terms"] >= 1:
        return ["maintain", "records"]
    return ["records", "verify"]


def hacker(sim: Sim) -> list[str]:
    """Learns Linux, then breaches systems. Fast evidence, fast heat."""
    s = sim.state
    if s["heat"] > 40 or s["case_file"] > 55:
        return ["lay_low"]
    if s["burnout"] > 60:
        return ["rest"]
    plan = laptop_plan(sim)
    if plan:
        return plan + socialize(sim, TECH)
    if s["cash"] < 100:
        return ["extra_shift"]
    plan = linux_plan(sim)
    if plan:
        return plan + ["research linux"]
    if s["sk_network_security"] < 1:
        return ["research network_security", "research network_security"]
    if sim.can_do("hack") and s["evidence"] < 60:
        return ["hack"]
    if sim.can_do("leak"):
        return ["leak", "feed"]
    return ["research python"] + socialize(sim, TECH)


def reckless(sim: Sim) -> list[str]:
    """Posts and leaks constantly with no regard for heat."""
    s = sim.state
    if s["cash"] < 0:
        return ["extra_shift"]
    if sim.can_do("leak"):
        return ["leak", "feed"]
    return ["records", "feed"] if s["evidence"] < 10 else ["feed"] + socialize(sim, PRESS)


def schemer(sim: Sim) -> list[str]:
    """Works people: bribes the trusting, squeezes anyone it has leverage on."""
    s = sim.state
    if s["heat"] > 25 or s["case_file"] > 40:
        return ["lay_low"]
    if s["burnout"] > 55:
        return ["rest"]
    plan = laptop_plan(sim)
    if plan:
        return plan + socialize(sim, TECH)
    if s["cash"] < 100:
        return ["extra_shift"]
    live = [c for c in sim.contacts if not c.hostile]
    squeeze = [c for c in live if c.leverage >= 1]
    if squeeze:
        return [f"meet {squeeze[0].id} extort"]
    rich = [c for c in live if c.trust >= 10]
    if rich and s["cash"] >= 250:
        return [f"meet {max(rich, key=lambda c: c.trust).id} bribe"]
    if s["press_trust"] >= 20 and sim.can_do("leak") and s["heat"] < 12:
        return ["leak", "feed"]
    return socialize(sim) + ["records"]


POLICIES = {"idle": idle, "careful": careful, "activist": activist, "lawyer": lawyer,
            "hacker": hacker, "reckless": reckless, "schemer": schemer}
