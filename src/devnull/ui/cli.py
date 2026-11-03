"""Plain command-line entry point (`devnull`). A placeholder front end.

A Textual-based terminal UI replaces this once the simulation has something
to show.
"""

from __future__ import annotations

import argparse
import random

from devnull import __version__
from devnull.core.world import load_schema, new_game, slice_variables


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="devnull", description="/dev/null: Know Your Enemy.")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed (default: random)")
    args = parser.parse_args(argv)

    seed = args.seed if args.seed is not None else random.randrange(2**31)
    schema = load_schema()
    world = new_game(seed, schema)

    print(f"/dev/null  v{__version__}")
    print("Know Your Enemy.")
    print(f"seed: {world.seed}   turn: {world.turn}")
    print()
    print("Vertical slice variables:")
    for key in slice_variables(schema):
        print(f"  {key:<45} {world.values[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
