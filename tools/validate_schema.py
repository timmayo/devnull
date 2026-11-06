#!/usr/bin/env python3
"""validate_schema.py - check the shape of every file in data/commands/ against data/commands/schema.json.

    python tools/validate_schema.py

Catches a mistyped field name (hidden_untill), a number where text belongs, a missing description.
Needs the `jsonschema` package:  pip install jsonschema   (the check in tools/cmdtree.py needs nothing extra)
Exit code 0 = fine, 1 = problems.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    from jsonschema import Draft202012Validator
except ImportError:
    sys.exit("This check needs the jsonschema package. Run:  pip install jsonschema")

from devnull.core.commands import RESERVED_FILES, read_yaml  # noqa: E402

FOLDER = ROOT / "data" / "commands"
SINGLE = {"contexts": "contexts", "groups": "groups", "gates": "gates", "variables": "variables"}


def where(err) -> str:
    return "/".join(str(p) for p in err.absolute_path) or "(top)"


def main() -> int:
    schema = json.loads((FOLDER / "schema.json").read_text(encoding="utf-8"))
    problems: list[str] = []
    for path in sorted(FOLDER.glob("*.yaml")):
        kind = SINGLE.get(path.stem, "commandFile")
        data = read_yaml(path)
        if data is None:
            data = {} if kind != "commandFile" else []
        sub = {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": f"#/$defs/{kind}"}
        names: list[str] = []
        if kind == "commandFile" and isinstance(data, list):
            names = [str(c.get("name", f"#{i + 1}")) if isinstance(c, dict) else f"#{i + 1}" for i, c in enumerate(data)]
        for err in sorted(Draft202012Validator(sub).iter_errors(data), key=lambda e: list(map(str, e.absolute_path))):
            at = list(err.absolute_path)
            who = f" {names[at[0]]}" if names and at and isinstance(at[0], int) and at[0] < len(names) else ""
            field = "/".join(str(p) for p in at[1:]) if names else where(err)
            problems.append(f"{path.name}{who}{(': ' + field) if field else ''} - {err.message[:160]}")
    files = [p for p in FOLDER.glob("*.yaml") if p.stem not in RESERVED_FILES]
    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print("  -", p)
        return 1
    print(f"OK - {len(files)} command files and {len(SINGLE)} table files match schema.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
