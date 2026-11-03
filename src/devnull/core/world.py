"""World state loading. Stub: reads the schema and builds an empty run.

The simulation proper (systems, couplings, turn loop) comes later. This file
only proves that data/world_state.yaml loads and that a run is reproducible
from a seed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCHEMA = REPO_ROOT / "data" / "world_state.yaml"


def load_schema(path: Path = DEFAULT_SCHEMA) -> dict[str, Any]:
    """Load the world state schema from YAML."""
    with open(path, encoding="utf-8") as f:
        schema = yaml.safe_load(f)
    if not isinstance(schema, dict) or "schema_version" not in schema:
        raise ValueError(f"{path} is not a valid world state schema")
    return schema


def slice_variables(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return variables tagged `slice: true`, keyed as 'group.variable'."""
    found: dict[str, dict[str, Any]] = {}
    for group, variables in schema.items():
        if not isinstance(variables, dict):
            continue
        for name, spec in variables.items():
            if isinstance(spec, dict) and spec.get("slice") is True:
                found[f"{group}.{name}"] = spec
    return found


@dataclass
class World:
    seed: int
    turn: int = 0
    rng: random.Random = field(default_factory=random.Random, repr=False)
    values: dict[str, Any] = field(default_factory=dict)


def new_game(seed: int, schema: dict[str, Any] | None = None) -> World:
    """Create a run. The same seed always gives the same starting world."""
    schema = schema or load_schema()
    world = World(seed=seed, rng=random.Random(seed))
    for key, spec in slice_variables(schema).items():
        start = spec.get("start")
        world.values[key] = start if isinstance(start, (int, float)) else None
    return world
