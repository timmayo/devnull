"""Coupling check for data/world_state.yaml.

Reads every variable's `driven_by` and `affects` text and every action's
`reads` / `writes` list, links them by name, and reports:

  * orphans: variables nothing drives, or that affect nothing
  * bad action references (typos in `reads` / `writes`)
  * a group-to-group coupling matrix (--matrix)

This is a name-matching heuristic, not a parser of meaning. It misses links
written in words that do not contain another variable's name. Treat the
output as a prompt to review, not as a verdict.

Spec flags the checker understands:
  exogenous: true       set from outside the model (calendar, city file)
  fixed: <value>        constant
  terminal: true        read by the interface only
  infrastructure: true  engine plumbing (turn, seed)

Usage (from the repo root):
    python tools/coupling_check.py
    python tools/coupling_check.py --edges
    python tools/coupling_check.py --matrix
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "data" / "world_state.yaml"

# Top-level keys that are not variable groups.
NON_VARIABLE_GROUPS = {
    "schema_version", "fail_soft_states", "endings", "vertical_slice", "actions",
}

# Extra phrases that resolve to a variable id.
ALIASES = {
    "world_meters.public_opinion_ai": ["public opinion"],
    "world_meters.ai_capability": ["ai capability", "capability clock"],
    "player.legibility": ["legibility", "legibility floor"],
    "player.time_energy": ["time energy"],
    "world_meters.info_integrity": ["info integrity", "information integrity"],
    "world_meters.power_grid_strain": ["power grid strain", "grid strain"],
    "community.local_anger": ["local anger"],
    "nsa.analytic_capacity": ["analytic capacity"],
    "nsa.collection_coverage": ["collection coverage"],
    "police.camera_alpr_coverage": ["camera alpr coverage", "camera coverage"],
    "police.case_file_on_player": ["case file"],
    "super_pacs.war_chest": ["war chest"],
    "city_council.capture_level": ["capture level", "council capture"],
    "data_center_site.stage": ["site stage"],
    "government.incumbents_control": ["incumbents control", "incumbents"],
    "government.loop_stance": ["loop stance"],
    "government.agency_budgets": ["agency budgets"],
    "npcs.trust": ["npc trust"],
    "npcs.exposure": ["npc exposure"],
    "npcs.knowledge": ["npc knowledge"],
    "npcs.agenda": ["npc agenda"],
    "npcs.loyalty_vs_leverage": ["loyalty vs leverage"],
    "natsec_flag.active": ["natsec flag"],
    "win_durability.repeal_preemption_threat": ["repeal preemption threat"],
    "player.fail_soft_state": ["fail soft state"],
}

# Variables whose bare name is too generic to match on; use aliases only.
NO_NAME_PHRASE = {
    "meta.turn", "meta.date", "meta.event_flags", "meta.rng_seed",
    "npcs.trust", "npcs.exposure", "npcs.knowledge", "npcs.agenda",
    "data_center_site.stage", "natsec_flag.active",
}


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def collect(schema: dict) -> dict[str, dict]:
    variables: dict[str, dict] = {}
    for group, body in schema.items():
        if group in NON_VARIABLE_GROUPS or not isinstance(body, dict):
            continue
        for name, spec in body.items():
            if isinstance(spec, dict) and ("range" in spec or "derived" in spec):
                variables[f"{group}.{name}"] = spec
    return variables


def phrases_for(var_id: str) -> list[str]:
    name = var_id.split(".", 1)[1]
    out = set(norm(a) for a in ALIASES.get(var_id, []))
    if var_id not in NO_NAME_PHRASE:
        out.add(norm(name))
    return sorted(out)


def texts(spec: dict, key: str) -> list[str]:
    value = spec.get(key)
    if value is None:
        return []
    if isinstance(value, list):
        return [norm(v) for v in value]
    return [norm(value)]


def find_refs(text: str, variables: dict[str, dict], exclude: str) -> set[str]:
    """Longest phrase first; a matched span cannot be matched again."""
    candidates = []
    for vid in variables:
        if vid == exclude:
            continue
        for phrase in phrases_for(vid):
            candidates.append((phrase, vid))
    candidates.sort(key=lambda c: len(c[0]), reverse=True)
    padded = f" {text} "
    hits: set[str] = set()
    for phrase, vid in candidates:
        needle = f" {phrase} "
        idx = padded.find(needle)
        if idx != -1:
            hits.add(vid)
            padded = padded[:idx] + " " * len(needle) + padded[idx + len(needle):]
    return hits


def build_edges(variables: dict[str, dict]) -> set[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    for vid, spec in variables.items():
        for t in texts(spec, "affects"):
            for other in find_refs(t, variables, vid):
                edges.add((vid, other))
        for t in texts(spec, "driven_by") + texts(spec, "derived"):
            for other in find_refs(t, variables, vid):
                edges.add((other, vid))
    return edges


def action_edges(schema: dict, variables: dict[str, dict]):
    edges: set[tuple[str, str]] = set()
    bad: list[str] = []
    for verb, spec in (schema.get("actions") or {}).items():
        node = f"action.{verb}"
        for w in spec.get("writes", []):
            if w in variables:
                edges.add((node, w))
            else:
                bad.append(f"{node} writes unknown variable {w}")
        for r in spec.get("reads", []):
            if r in variables:
                edges.add((r, node))
            else:
                bad.append(f"{node} reads unknown variable {r}")
    return edges, bad


def ending_inputs(schema: dict, variables: dict[str, dict]) -> set[str]:
    out: set[str] = set()
    for check in (schema.get("endings") or {}).get("checks", []):
        c = str(check)
        for vid in variables:
            group, name = vid.split(".", 1)
            if c == vid or c == name or c == group:
                out.add(vid)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edges", action="store_true", help="print every edge")
    ap.add_argument("--matrix", action="store_true", help="print group-to-group matrix")
    ap.add_argument("--schema", type=Path, default=SCHEMA)
    args = ap.parse_args()

    schema = yaml.safe_load(args.schema.read_text(encoding="utf-8"))
    variables = collect(schema)
    var_edges = build_edges(variables)
    act_edges, bad = action_edges(schema, variables)
    edges = var_edges | act_edges
    endings = ending_inputs(schema, variables)

    out_deg = Counter(a for a, _ in edges)
    in_deg = Counter(b for _, b in edges)

    def skip_drivers(spec: dict) -> bool:
        return bool(spec.get("exogenous") or spec.get("fixed") is not None
                    or spec.get("infrastructure"))

    def skip_effects(vid: str, spec: dict) -> bool:
        return bool(spec.get("terminal") or spec.get("infrastructure")
                    or vid in endings)

    no_drivers = sorted(v for v, s in variables.items()
                        if in_deg[v] == 0 and not skip_drivers(s))
    no_effects = sorted(v for v, s in variables.items()
                        if out_deg[v] == 0 and not skip_effects(v, s))

    print(f"variables: {len(variables)}   actions: {len(schema.get('actions') or {})}"
          f"   edges: {len(edges)} ({len(var_edges)} schema, {len(act_edges)} action)")
    if bad:
        print("\nBad action references:")
        for b in bad:
            print(f"  {b}")
    print(f"\nNothing drives these ({len(no_drivers)}):")
    for v in no_drivers:
        print(f"  {v}")
    print(f"\nThese affect nothing ({len(no_effects)}):")
    for v in no_effects:
        print(f"  {v}")

    if args.edges:
        print("\nEdges (driver -> driven):")
        for a, b in sorted(edges):
            print(f"  {a} -> {b}")

    if args.matrix:
        groups = sorted({v.split(".", 1)[0] for v in variables}
                        | {"action"})
        counts: Counter = Counter()
        for a, b in edges:
            counts[(a.split(".", 1)[0], b.split(".", 1)[0])] += 1
        print("\nGroup matrix (row drives column; cell = number of links):\n")
        print("| from \\ to | " + " | ".join(groups) + " |")
        print("|---|" + "---|" * len(groups))
        for g in groups:
            row = [str(counts[(g, h)]) if counts[(g, h)] else "" for h in groups]
            print(f"| **{g}** | " + " | ".join(row) + " |")

    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
