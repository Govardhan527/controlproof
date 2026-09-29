import json
from importlib.resources import files

from controlproof.model import SCHEMA_VERSION
from controlproof.validation import build_validator
from generate_schemas import FORMATS, ID_BASE, main


def test_committed_schemas_match_the_models() -> None:
    assert main(["--check"]) == 0


def test_schema_ids_carry_the_format_and_version() -> None:
    for name in FORMATS:
        path = files("controlproof") / "schemas" / f"{name}.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["$id"] == f"{ID_BASE}/{name}/{SCHEMA_VERSION}"
        build_validator(schema)  # each is a valid 2020-12 schema
