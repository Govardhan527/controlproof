"""Validate every example output in examples/ against its JSON Schema.

Layout (ADR-0003):
    examples/<format>/*.json                  example outputs of one format
    examples/runs/<name>/                     a complete run directory (ADR-0008); each file is
                                              checked as the format its name implies
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
RUNS = "runs"
RUN_FILES = {
    "run.json": "run-record",
    "assessment-plan.json": "oscal-assessment-plan",
    "assessment-results.json": "oscal-assessment-results",
    "manifest.json": "manifest",
}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def errors_against(schema_path: Path, instance: Any) -> list[str]:
    try:
        validator = build_validator(load_json(schema_path))
    except SchemaError as exc:
        return [f"schema {schema_path} is not a valid JSON Schema: {exc.message}"]
    return schema_errors(validator, instance)


def schemas_for(format_name: str, schemas_dir: Path) -> list[Path]:
    candidates = (
        schemas_dir / f"{format_name}.schema.json",
        schemas_dir / "official" / f"{format_name}.schema.json",
    )
    return [path for path in candidates if path.is_file()]


def check_file(example: Path, schema_paths: list[Path]) -> list[str]:
    instance = load_json(example)
    return [
        f"{example} vs {schema_path}: {error}"
        for schema_path in schema_paths
        for error in errors_against(schema_path, instance)
    ]


def run_files(run_dir: Path) -> list[tuple[Path, str | None]]:
    """Each JSON file of a run directory with the format its name implies (None: unknown)."""
    files: list[tuple[Path, str | None]] = []
    for path in sorted(run_dir.rglob("*.json")):
        relative = path.relative_to(run_dir)
        if relative.parts[0] == "evidence" and len(relative.parts) == 2:
            files.append((path, "evidence-record"))
        else:
            files.append((path, RUN_FILES.get(str(relative))))
    return files


def validate(examples_dir: Path, schemas_dir: Path) -> tuple[int, list[str]]:
    """Return (number of example files checked, problems found)."""
    problems: list[str] = []
    checked = 0
    if not examples_dir.is_dir():
        return 0, problems
    for stray in sorted(examples_dir.glob("*.json")):
        problems.append(f"{stray}: example outputs must live in examples/<format>/")
    for format_dir in sorted(p for p in examples_dir.iterdir() if p.is_dir() and p.name != RUNS):
        present = schemas_for(format_dir.name, schemas_dir)
        if not present:
            problems.append(f"{format_dir}: no schema for format {format_dir.name!r}")
            continue
        for example in sorted(format_dir.glob("*.json")):
            checked += 1
            problems.extend(check_file(example, present))
    runs_dir = examples_dir / RUNS
    for run_dir in sorted(p for p in runs_dir.iterdir() if p.is_dir()) if runs_dir.is_dir() else []:
        for path, format_name in run_files(run_dir):
            present = schemas_for(format_name, schemas_dir) if format_name else []
            if not present:
                problems.append(f"{path}: not a known run file, or no schema for it")
                continue
            checked += 1
            problems.extend(check_file(path, present))
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
