"""Validate every example output in examples/ against its JSON Schema.

Layout (ADR-0003):
    examples/<format>/*.json                  example outputs of one format
    <schemas>/<format>.schema.json            the project's schema for that format
    <schemas>/official/<format>.schema.json   the standard's own schema, where one exists

Each format needs at least one of the two schemas; every example is validated against each one
present. OSCAL formats have only the official schema. Exit codes: 0 all examples valid, 1 a schema
is missing or invalid, or an example fails.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from jsonschema.exceptions import SchemaError

from controlproof.validation import build_validator, schema_errors

DEFAULT_SCHEMAS = Path("src/controlproof/schemas")


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def errors_against(schema_path: Path, instance: Any) -> list[str]:
    try:
        validator = build_validator(load_json(schema_path))
    except SchemaError as exc:
        return [f"schema {schema_path} is not a valid JSON Schema: {exc.message}"]
    return schema_errors(validator, instance)


def validate(examples_dir: Path, schemas_dir: Path) -> tuple[int, list[str]]:
    """Return (number of example files checked, problems found)."""
    problems: list[str] = []
    checked = 0
    if not examples_dir.is_dir():
        return 0, problems
    for stray in sorted(examples_dir.glob("*.json")):
        problems.append(f"{stray}: example outputs must live in examples/<format>/")
    for format_dir in sorted(p for p in examples_dir.iterdir() if p.is_dir()):
        candidates = (
            schemas_dir / f"{format_dir.name}.schema.json",
            schemas_dir / "official" / f"{format_dir.name}.schema.json",
        )
        present = [path for path in candidates if path.is_file()]
        if not present:
            problems.append(f"{format_dir}: no schema at {candidates[0]} or {candidates[1]}")
            continue
        for example in sorted(format_dir.glob("*.json")):
            checked += 1
            instance = load_json(example)
            for schema_path in present:
                for error in errors_against(schema_path, instance):
                    problems.append(f"{example} vs {schema_path}: {error}")
    return checked, problems


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate example outputs against schemas.")
    parser.add_argument("--examples", type=Path, default=Path("examples"))
    parser.add_argument("--schemas", type=Path, default=DEFAULT_SCHEMAS)
    args = parser.parse_args(argv)

    checked, problems = validate(args.examples, args.schemas)
    for problem in problems:
        print(problem)
    print(f"validated {checked} example file(s); {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
