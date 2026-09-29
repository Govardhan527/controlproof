import json
from importlib.resources import files

from controlproof.validation import build_validator
from generate_schemas import FORMATS, ID_BASE, main


def test_committed_schemas_match_the_models() -> None:
    assert main(["--check"]) == 0


def test_schema_ids_carry_the_format_and_version() -> None:
    for name, (_, version) in FORMATS.items():
        path = files("controlproof") / "schemas" / f"{name}.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["$id"] == f"{ID_BASE}/{name}/{version}"
        build_validator(schema)  # each is a valid 2020-12 schema
