"""Validate every example output in examples/ against its JSON Schema.

Layout (ADR-0003):
    examples/<format>/*.json              example outputs of one format
    schemas/<format>.schema.json          the project's schema for that format (required)
    schemas/official/<format>.schema.json the standard's own schema, where one exists (optional)

Every example is validated against the project schema and, when present, the official schema.
Exit codes: 0 all examples valid, 1 a schema is missing or invalid, or an example fails.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from jsonschema.exceptions import SchemaError
from jsonschema.validators import validator_for


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def schema_errors(schema_path: Path, instance: Any) -> list[str]:
    schema = load_json(schema_path)
    validator_cls = validator_for(schema)
    try:
        validator_cls.check_schema(schema)
    except SchemaError as exc:
        return [f"schema {schema_path} is not a valid JSON Schema: {exc.message}"]
    validator = validator_cls(schema, format_checker=validator_cls.FORMAT_CHECKER)
    return [
        f"{'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(instance), key=lambda e: list(map(str, e.path)))
    ]


def validate(examples_dir: Path, schemas_dir: Path) -> tuple[int, list[str]]:
    """Return (number of example files checked, problems found)."""
    problems: list[str] = []
    checked = 0
    if not examples_dir.is_dir():
        return 0, problems
    for stray in sorted(examples_dir.glob("*.json")):
        problems.append(f"{stray}: example outputs must live in examples/<format>/")
    for format_dir in sorted(p for p in examples_dir.iterdir() if p.is_dir()):
        own = schemas_dir / f"{format_dir.name}.schema.json"
        official = schemas_dir / "official" / f"{format_dir.name}.schema.json"
        if not own.is_file():
            problems.append(f"{format_dir}: no schema at {own}")
            continue
        for example in sorted(format_dir.glob("*.json")):
            checked += 1
            instance = load_json(example)
            for schema_path in (own, official):
                if schema_path.is_file():
                    for error in schema_errors(schema_path, instance):
                        problems.append(f"{example} vs {schema_path}: {error}")
    return checked, problems


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate example outputs against schemas.")
    parser.add_argument("--examples", type=Path, default=Path("examples"))
    parser.add_argument("--schemas", type=Path, default=Path("schemas"))
    args = parser.parse_args(argv)

    checked, problems = validate(args.examples, args.schemas)
    for problem in problems:
        print(problem)
    print(f"validated {checked} example file(s); {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
