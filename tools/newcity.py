#!/usr/bin/env python3
"""newcity.py - start a new city: a city file with every field present, and the empty files it points to.

    python tools/newcity.py rochester_ny --name "Rochester" --state "New York"

Makes:
    cities/<id>.yaml                              from tools/city_template.yaml (every fact is VERIFY, every resource needs a URL)
    pools/<id>_real_officials_blocklist.txt       the real office-holders to keep generated names away from (empty)
    pools/<state>_surnames.txt                    surnames common in the state (only if no pool exists yet)
Then:  python tools/citycheck.py <id>   lists everything left to do.   Read cities/README.txt for the whole workflow.
Nothing is overwritten: if the city already exists this stops.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ID = re.compile(r"[a-z][a-z0-9_]{1,40}")


def state_slug(state: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", state.lower()).strip("_")


def scaffold(city_id: str, name: str, state: str, root: Path = ROOT) -> list[Path]:
    if not ID.fullmatch(city_id):
        raise SystemExit("The id is lowercase letters, numbers and _ (for example rochester_ny).")
    target = root / "cities" / f"{city_id}.yaml"
    if target.exists():
        raise SystemExit(f"{target} already exists. Nothing was changed.")
    slug = state_slug(state)
    text = (root / "tools" / "city_template.yaml").read_text(encoding="utf-8")
    for token, value in (("__ID__", city_id), ("__NAME__", name.replace('"', "'")), ("__STATE__", state.replace('"', "'")),
                         ("__STATE_SLUG__", slug)):
        text = text.replace(token, value)
    made = [target]
    target.write_text(text, encoding="utf-8", newline="\n")
    block = root / "pools" / f"{city_id}_real_officials_blocklist.txt"
    block.write_text(
        "# Real office-holders in this city, now and in the recent past. One per line: \"Given Surname\".\n"
        "# A generated name that matches a line here is rejected and re-rolled.\n"
        "# Fill this from the city's published rosters (see the roster resource in cities/%s.yaml) before release.\n" % city_id,
        encoding="utf-8", newline="\n")
    made.append(block)
    pool = root / "pools" / f"{slug}_surnames.txt"
    if not pool.exists():
        pool.write_text(f"# Surnames common in {state}, one per line (aim for 40 or more).\n", encoding="utf-8", newline="\n")
        made.append(pool)
    return made


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id", help="lowercase id, for example rochester_ny")
    ap.add_argument("--name", required=True, help='display name, for example "Rochester"')
    ap.add_argument("--state", required=True, help='state, for example "New York"')
    args = ap.parse_args()
    made = scaffold(args.id, args.name, args.state)
    for p in made:
        print("made", p.relative_to(ROOT))
    print(f"\nNext: give the URLs for each resource in cities/{args.id}.yaml (url: null = needed), fill the surname pool and the blocklist,"
          f"\nthen run  python tools/citycheck.py {args.id}  to see what is left.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
