import copy
import hashlib
from importlib.resources import files
from typing import Any

import pytest
from jsonschema.exceptions import SchemaError

from controlproof.validation import (
    OSCAL_VERSION,
    OscalValidationError,
    build_validator,
    check_oscal,
    oscal_errors,
)

# SHA-256 of the NIST release assets for OSCAL 1.2.3 (SPEC_NOTES §1).
OFFICIAL_SHA256 = {
    "oscal-assessment-results.schema.json": (
        "4034e2032332dbf597e59e0646ec16c2c31df992962490371e91f47b219ff42c"
    ),
    "oscal-assessment-plan.schema.json": (
        "ea687b9d0ab1d84c9cb11ee0a5e22b17956fe892ee93f5acca937bef81d23ea2"
    ),
}

METADATA = {
    "title": "t",
    "last-modified": "2026-09-29T00:00:00Z",
    "version": "1",
    "oscal-version": OSCAL_VERSION,
}
SELECTIONS = {"control-selections": [{"include-controls": [{"control-id": "sc-28"}]}]}
RESULTS: dict[str, Any] = {
    "assessment-results": {
        "uuid": "11111111-1111-4111-8111-111111111111",
        "metadata": METADATA,
        "import-ap": {"href": "assessment-plan.json"},
        "results": [
            {
                "uuid": "22222222-2222-5222-8222-222222222222",
                "title": "r",
                "description": "d",
                "start": "2026-09-29T00:00:00Z",
                "reviewed-controls": SELECTIONS,
            }
        ],
    }
}
PLAN: dict[str, Any] = {
    "assessment-plan": {
        "uuid": "44444444-4444-4444-8444-444444444444",
        "metadata": METADATA,
        "import-ssp": {"href": "#55555555-5555-4555-8555-555555555555"},
        "reviewed-controls": SELECTIONS,
    }
}


def result(doc: dict[str, Any]) -> dict[str, Any]:
    first: dict[str, Any] = doc["assessment-results"]["results"][0]
    return first


def test_official_schemas_are_the_nist_release_files() -> None:
    official = files("controlproof") / "schemas" / "official"
    for name, digest in OFFICIAL_SHA256.items():
        assert hashlib.sha256((official / name).read_bytes()).hexdigest() == digest


def test_minimal_documents_are_valid() -> None:
    assert oscal_errors(RESULTS, "assessment-results") == []
    assert oscal_errors(PLAN, "assessment-plan") == []
    check_oscal(RESULTS, "assessment-results")


def set_token(doc: dict[str, Any]) -> None:
    result(doc)["reviewed-controls"]["control-selections"][0]["include-controls"][0][
        "control-id"
    ] = "1 bad"


def set_v1_uuid(doc: dict[str, Any]) -> None:
    doc["assessment-results"]["uuid"] = "11111111-1111-1111-8111-111111111111"


def drop_timezone(doc: dict[str, Any]) -> None:
    result(doc)["start"] = "2026-09-29T00:00:00"


def drop_import_ap(doc: dict[str, Any]) -> None:
    del doc["assessment-results"]["import-ap"]


def set_error_state(doc: dict[str, Any]) -> None:
    result(doc)["findings"] = [
        {
            "uuid": "33333333-3333-4333-8333-333333333333",
            "title": "f",
            "description": "d",
            "target": {
                "type": "objective-id",
                "target-id": "sc-28_obj",
                "status": {"state": "error"},
            },
        }
    ]


@pytest.mark.parametrize(
    "mutate", [set_token, set_v1_uuid, drop_timezone, drop_import_ap, set_error_state]
)
def test_invalid_documents_are_rejected(mutate: Any) -> None:
    doc = copy.deepcopy(RESULTS)
    mutate(doc)
    errors = oscal_errors(doc, "assessment-results")
    assert errors
    with pytest.raises(OscalValidationError) as caught:
        check_oscal(doc, "assessment-results")
    assert caught.value.errors == errors


def test_unicode_letters_are_valid_tokens() -> None:
    doc = copy.deepcopy(RESULTS)
    result(doc)["reviewed-controls"]["control-selections"][0]["include-controls"][0][
        "control-id"
    ] = "ümlaut-1"
    assert oscal_errors(doc, "assessment-results") == []


def test_errors_name_the_failing_path() -> None:
    doc = copy.deepcopy(RESULTS)
    drop_timezone(doc)
    assert any(
        e.startswith("assessment-results/results/0/start:")
        for e in oscal_errors(doc, "assessment-results")
    )


def test_build_validator_handles_unicode_property_patterns() -> None:
    validator = build_validator({"type": "string", "pattern": r"^\p{L}+$"})
    assert validator.is_valid("Grüße")
    assert not validator.is_valid("abc1")
    assert validator.is_valid(12) is False  # type check still applies


def test_invalid_schema_is_rejected() -> None:
    with pytest.raises(SchemaError):
        build_validator({"type": 12})
    with pytest.raises(SchemaError):
        build_validator({"type": "string", "pattern": "(unclosed"})
