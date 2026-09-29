import copy
from typing import Any

import pytest
from pydantic import ValidationError

from controlproof.oscal.models import assessment_plan, assessment_results
from generate_oscal_models import main
from test_validation import PLAN, RESULTS


def test_committed_models_match_a_fresh_generation() -> None:
    assert main(["--check"]) == 0


def test_models_accept_the_minimal_documents() -> None:
    assessment_results.Model.model_validate(RESULTS)
    assessment_plan.Model.model_validate(PLAN)


@pytest.mark.parametrize("path", [(), ("results", 0), ("metadata",)])
def test_models_reject_unknown_keys(path: tuple[str | int, ...]) -> None:
    doc: dict[str, Any] = copy.deepcopy(RESULTS)
    node: Any = doc["assessment-results"]
    for step in path:
        node = node[step]
    node["relevent-evidence"] = []
    with pytest.raises(ValidationError):
        assessment_results.Model.model_validate(doc)


def test_python_field_names_serialize_as_oscal_names() -> None:
    doc: dict[str, Any] = copy.deepcopy(RESULTS)
    doc["assessment-results"]["import_ap"] = doc["assessment-results"].pop("import-ap")
    model = assessment_results.Model.model_validate(doc)
    assert model.model_dump(mode="json", by_alias=True, exclude_none=True) == RESULTS


def test_models_round_trip_to_the_same_json() -> None:
    model = assessment_results.Model.model_validate(RESULTS)
    assert model.model_dump(mode="json", by_alias=True, exclude_none=True) == RESULTS
