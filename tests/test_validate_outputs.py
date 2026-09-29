import json
from pathlib import Path
from typing import Any

import pytest

from validate_outputs import main

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["schema_version"],
    "properties": {"schema_version": {"type": "string"}},
}


def write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def run(tmp_path: Path) -> int:
    return main(["--examples", str(tmp_path / "examples"), "--schemas", str(tmp_path / "schemas")])


def test_missing_examples_dir_validates_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(tmp_path) == 0
    assert "validated 0 example file(s)" in capsys.readouterr().out


def test_valid_example_passes(tmp_path: Path) -> None:
    write(tmp_path / "schemas" / "run-record.schema.json", SCHEMA)
    write(tmp_path / "examples" / "run-record" / "ok.json", {"schema_version": "1.0.0"})
    assert run(tmp_path) == 0


def test_invalid_example_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write(tmp_path / "schemas" / "run-record.schema.json", SCHEMA)
    write(tmp_path / "examples" / "run-record" / "bad.json", {"schema_version": 1})
    assert run(tmp_path) == 1
    assert "schema_version: 1 is not of type 'string'" in capsys.readouterr().out


def test_official_schema_is_applied_too(tmp_path: Path) -> None:
    write(tmp_path / "schemas" / "report.schema.json", SCHEMA)
    write(
        tmp_path / "schemas" / "official" / "report.schema.json",
        {**SCHEMA, "required": ["schema_version", "uuid"]},
    )
    write(tmp_path / "examples" / "report" / "a.json", {"schema_version": "1.0.0"})
    assert run(tmp_path) == 1


def test_official_schema_alone_is_enough(tmp_path: Path) -> None:
    write(tmp_path / "schemas" / "official" / "oscal-x.schema.json", SCHEMA)
    write(tmp_path / "examples" / "oscal-x" / "a.json", {"schema_version": "1.0.0"})
    assert run(tmp_path) == 0


def test_unicode_property_patterns_are_supported(tmp_path: Path) -> None:
    write(tmp_path / "schemas" / "tok.schema.json", {"type": "string", "pattern": r"^\p{L}+$"})
    write(tmp_path / "examples" / "tok" / "ok.json", "Grüße")
    write(tmp_path / "examples" / "tok" / "bad.json", "abc1")
    assert run(tmp_path) == 1


def test_format_without_schema_fails(tmp_path: Path) -> None:
    write(tmp_path / "examples" / "orphan" / "a.json", {})
    assert run(tmp_path) == 1


def test_stray_example_outside_a_format_dir_fails(tmp_path: Path) -> None:
    write(tmp_path / "examples" / "loose.json", {})
    assert run(tmp_path) == 1


def test_invalid_schema_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write(tmp_path / "schemas" / "x.schema.json", {"type": 12})
    write(tmp_path / "examples" / "x" / "a.json", {})
    assert run(tmp_path) == 1
    assert "is not a valid JSON Schema" in capsys.readouterr().out


def test_a_run_directory_is_checked_file_by_file(tmp_path: Path) -> None:
    write(tmp_path / "schemas" / "run-record.schema.json", SCHEMA)
    write(tmp_path / "schemas" / "evidence-record.schema.json", SCHEMA)
    run_dir = tmp_path / "examples" / "runs" / "r1"
    write(run_dir / "run.json", {"schema_version": "1.1.0"})
    write(run_dir / "evidence" / "abc.json", {"schema_version": "1.0.0"})
    assert run_count(tmp_path) == (2, [])
    write(run_dir / "evidence" / "bad.json", {"schema_version": 3})
    assert run(tmp_path) == 1


def test_an_unknown_file_in_a_run_directory_fails(tmp_path: Path) -> None:
    write(tmp_path / "examples" / "runs" / "r1" / "notes.json", {})
    assert run(tmp_path) == 1


def run_count(tmp_path: Path) -> tuple[int, list[str]]:
    from validate_outputs import validate

    return validate(tmp_path / "examples", tmp_path / "schemas")
