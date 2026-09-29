"""Write the project's JSON Schemas from the pydantic contracts (ADR-0003).

generate_schemas.py           rewrite src/controlproof/schemas/<format>.schema.json
generate_schemas.py --check   exit 1 if a committed schema differs from its model
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from controlproof.model import SCHEMA_VERSION, RunRecord
from controlproof.output import Manifest
from controlproof.profile import Profile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "src" / "controlproof" / "schemas"
ID_BASE = "https://github.com/Govardhan527/controlproof/schemas"
FORMATS: dict[str, type[BaseModel]] = {
    "manifest": Manifest,
    "profile": Profile,
    "run-record": RunRecord,
}


def render(name: str, model: type[BaseModel]) -> str:
    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"{ID_BASE}/{name}/{SCHEMA_VERSION}",
        **model.model_json_schema(),
    }
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate JSON Schemas from the contracts.")
    parser.add_argument("--check", action="store_true", help="fail if committed schemas differ")
    args = parser.parse_args(argv)

    stale = []
    for name, model in FORMATS.items():
        path = OUTPUT / f"{name}.schema.json"
        text = render(name, model)
        if path.is_file() and path.read_text(encoding="utf-8") == text:
            continue
        stale.append(path)
        if not args.check:
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")
    if args.check:
        for path in stale:
            print(f"{path.relative_to(ROOT)} is out of date; run {Path(__file__).name}")
        return 1 if stale else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
