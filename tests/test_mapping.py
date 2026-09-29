import json
import re
import uuid
from typing import Any

import pytest

from controlproof.model import Status
from controlproof.oscal import mapping
from controlproof.oscal.models import assessment_results
from controlproof.validation import OscalValidationError
from stub_controls import ACCOUNT, METHODS, TITLES, stub_run


def documents(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    run, profile = stub_run(name)
    plan = mapping.build_assessment_plan(run, profile, TITLES, METHODS, ACCOUNT)
    results = mapping.build_assessment_results(run, profile, TITLES)
    return plan, results


def findings(results: dict[str, Any]) -> dict[str, dict[str, Any]]:
    found = results["assessment-results"]["results"][0]["findings"]
    return {f["target"]["target-id"].removesuffix("_obj"): f for f in found}


@pytest.mark.parametrize(
    ("name", "control_id", "state", "reason", "prop"),
    [
        ("stub-run-a", "ac-2", "satisfied", "pass", None),
        ("stub-run-a", "ac-6", "not-satisfied", "fail", None),
        ("stub-run-a", "sc-13", "not-satisfied", "other", "error"),
        ("stub-run-b", "sc-13", "not-satisfied", "other", "not_tested"),
    ],
)
def test_status_mapping(
    name: str, control_id: str, state: str, reason: str, prop: str | None
) -> None:
    target = findings(documents(name)[1])[control_id]["target"]
    assert target["status"] == {"state": state, "reason": reason}
    props = target.get("props", [])
    assert props == (
        [{"name": "controlproof-status", "ns": mapping.PROP_NS, "value": prop}] if prop else []
    )


def test_only_a_pass_is_satisfied() -> None:
    for name in ("stub-run-a", "stub-run-b"):
        run, _ = stub_run(name)
        by_id = findings(documents(name)[1])
        for result in run.results:
            satisfied = by_id[result.control_id]["target"]["status"]["state"] == "satisfied"
            assert satisfied == (result.status is Status.PASS)


def test_not_tested_wording() -> None:
    finding = findings(documents("stub-run-b")[1])["sc-13"]
    assert finding["title"] == "sc-13: not tested this run"


def test_no_text_claims_compliance() -> None:
    for name in ("stub-run-a", "stub-run-b"):
        for doc in documents(name):
            text = json.dumps(doc).lower()
            assert "compliant" not in text
            assert "not a statement of compliance" in text or "assessment-plan" in doc


def test_methods_follow_adr_0005() -> None:
    _, results = documents("stub-run-a")
    observations = results["assessment-results"]["results"][0]["observations"]
    by_control = {o["uuid"]: o["methods"] for o in observations}
    finding = findings(results)
    expected = {"ac-2": ["EXAMINE"], "ac-6": ["EXAMINE"], "sc-13": ["TEST"]}
    for control_id, methods in expected.items():
        related = finding[control_id]["related-observations"]
        assert [by_control[r["observation-uuid"]] for r in related] == [methods]


def test_links_between_documents_resolve() -> None:
    plan, results = documents("stub-run-a")
    assert results["assessment-results"]["import-ap"]["href"] == mapping.PLAN_HREF
    href = plan["assessment-plan"]["import-ssp"]["href"]
    resources = plan["assessment-plan"]["back-matter"]["resources"]
    assert [f"#{r['uuid']}" for r in resources] == [href]
    assert ACCOUNT in resources[0]["description"]
    result = results["assessment-results"]["results"][0]
    inventory = {item["uuid"] for item in result["local-definitions"]["inventory-items"]}
    observation_ids = {o["uuid"] for o in result["observations"]}
    for obs in result["observations"]:
        assert {s["subject-uuid"] for s in obs.get("subjects", [])} <= inventory
    for finding in result["findings"]:
        assert {r["observation-uuid"] for r in finding["related-observations"]} <= observation_ids


def test_every_uuid_is_version_5_and_unique() -> None:
    for name in ("stub-run-a", "stub-run-b"):
        for doc in documents(name):
            text = json.dumps(doc)
            values = re.findall(r'"(?:uuid|subject-uuid|observation-uuid)": "([^"]+)"', text)
            own = re.findall(r'"uuid": "([^"]+)"', text)
            assert len(own) == len(set(own))
            assert all(uuid.UUID(v).version == 5 for v in values)


def test_the_plan_covers_every_profiled_control() -> None:
    _, profile = stub_run("stub-run-a")
    plan, _ = documents("stub-run-a")
    activities = plan["assessment-plan"]["local-definitions"]["activities"]
    assert [a["title"].split()[0] for a in activities] == list(profile.control_ids)


def test_the_official_schema_catches_what_the_generated_model_misses() -> None:
    _, results = documents("stub-run-a")
    results["assessment-results"]["results"][0]["findings"][0]["target"]["status"]["state"] = (
        "error"
    )
    assessment_results.Model.model_validate(results)  # the generated model lets it through
    with pytest.raises(OscalValidationError):
        mapping._finish(results, assessment_results.Model, "assessment-results")


def test_a_run_without_results_still_maps_to_valid_oscal() -> None:
    run, profile = stub_run("stub-run-a")
    empty = run.model_copy(update={"results": ()})
    result = mapping.build_assessment_results(empty, profile, TITLES)["assessment-results"]
    assert "findings" not in result["results"][0]
    assert result["results"][0]["reviewed-controls"]  # the plan's controls are still listed
