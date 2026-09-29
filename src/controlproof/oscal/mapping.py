"""Map a run record to OSCAL 1.2.3 assessment-plan and assessment-results (ADR-0005, ADR-0008).

Each document is built as plain JSON, loaded through the generated model (unknown fields fail),
dumped from that model, and then checked against the official schema before it is returned.
"""

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from controlproof.evidence import EVIDENCE_DIR
from controlproof.model import ControlResult, Method, RunRecord, Status
from controlproof.oscal.models import assessment_plan, assessment_results
from controlproof.profile import Profile
from controlproof.validation import OSCAL_VERSION, OscalModel, check_oscal

NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/Govardhan527/controlproof")
PROP_NS = "https://github.com/Govardhan527/controlproof/ns/oscal"
PLAN_HREF = "assessment-plan.json"

OSCAL_METHOD = {Method.INSPECT: "EXAMINE", Method.SIMULATE: "EXAMINE", Method.EXERCISE: "TEST"}
FINDING_STATUS = {
    Status.PASS: ("satisfied", "pass"),
    Status.FAIL: ("not-satisfied", "fail"),
    Status.ERROR: ("not-satisfied", "other"),
    Status.NOT_TESTED: ("not-satisfied", "other"),
}
WORDING = {
    Status.PASS: "control test passed",
    Status.FAIL: "control test failed",
    Status.ERROR: "control test could not complete",
    Status.NOT_TESTED: "not tested this run",
}
RESULT_DESCRIPTION = (
    "Automated control tests run by controlproof. Each finding states whether the control test "
    "passed. This is evidence for an assessor, not a statement of compliance."
)


def oscal_uuid(run_id: str, kind: str, key: str = "") -> str:
    """A version-5 UUID that is the same for the same run, kind and key."""
    return str(uuid.uuid5(NAMESPACE, f"{run_id}/{kind}/{key}"))


def timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _metadata(run: RunRecord, title: str) -> dict[str, Any]:
    return {
        "title": title,
        "last-modified": timestamp(run.ended_at),
        "version": run.run_id,
        "oscal-version": OSCAL_VERSION,
    }


def _control_selection(control_ids: tuple[str, ...]) -> dict[str, Any]:
    return {"control-selections": [{"include-controls": [{"control-id": c} for c in control_ids]}]}


def _finish(document: dict[str, Any], model: type[BaseModel], name: OscalModel) -> dict[str, Any]:
    dumped = model.model_validate(document).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    check_oscal(dumped, name)
    return dumped


def build_assessment_plan(
    run: RunRecord,
    profile: Profile,
    titles: Mapping[str, str],
    methods: Mapping[str, Method],
) -> dict[str, Any]:
    """The minimal plan each run writes, so `import-ap` has a target (ADR-0005 items 2 and 5)."""
    ssp = oscal_uuid(run.run_id, "ssp-placeholder")
    activities = [
        {
            "uuid": oscal_uuid(run.run_id, "activity", control_id),
            "title": f"{control_id} {titles[control_id]}",
            "description": (
                f"controlproof control test for {control_id} using the "
                f"{methods[control_id]} method ({OSCAL_METHOD[methods[control_id]]})."
            ),
            "props": [{"name": "controlproof-method", "ns": PROP_NS, "value": methods[control_id]}],
            "related-controls": _control_selection((control_id,)),
        }
        for control_id in profile.control_ids
    ]
    document = {
        "assessment-plan": {
            "uuid": oscal_uuid(run.run_id, "assessment-plan"),
            "metadata": _metadata(run, f"controlproof assessment plan: {profile.title}"),
            "import-ssp": {"href": f"#{ssp}"},
            "local-definitions": {"activities": activities},
            "reviewed-controls": _control_selection(profile.control_ids),
            "back-matter": {
                "resources": [
                    {
                        "uuid": ssp,
                        "title": "No system security plan supplied",
                        "description": (
                            "controlproof ran without a system security plan. "
                            f"Assessed AWS account: {run.account}; "
                            f"Regions: {', '.join(run.regions)}."
                        ),
                    }
                ]
            },
        }
    }
    return _finish(document, assessment_plan.Model, "assessment-plan")


def _observations(run_id: str, result: ControlResult) -> list[dict[str, Any]]:
    observations = []
    for index, observation in enumerate(result.observations):
        entry: dict[str, Any] = {
            "uuid": oscal_uuid(run_id, "observation", f"{result.control_id}/{index}"),
            "description": observation.summary,
            "methods": [OSCAL_METHOD[result.method]],
            "collected": timestamp(result.ended_at),
        }
        if observation.subjects:
            entry["subjects"] = [
                {"subject-uuid": oscal_uuid(run_id, "subject", subject), "type": "inventory-item"}
                for subject in observation.subjects
            ]
        if observation.evidence_refs:
            entry["relevant-evidence"] = [
                {
                    "href": f"{EVIDENCE_DIR}/{ref}.json",
                    "description": f"Redacted AWS API response, SHA-256 {ref}",
                }
                for ref in observation.evidence_refs
            ]
        observations.append(entry)
    return observations


def _finding(run_id: str, result: ControlResult, title: str) -> dict[str, Any]:
    state, reason = FINDING_STATUS[result.status]
    target: dict[str, Any] = {
        "type": "objective-id",
        "target-id": f"{result.control_id}_obj",
        "status": {"state": state, "reason": reason},
    }
    if result.status in (Status.ERROR, Status.NOT_TESTED):
        target["props"] = [{"name": "controlproof-status", "ns": PROP_NS, "value": result.status}]
    return {
        "uuid": oscal_uuid(run_id, "finding", result.control_id),
        "title": f"{result.control_id}: {WORDING[result.status]}",
        "description": f"{result.control_id} {title}: {WORDING[result.status]} ({result.method}).",
        "target": target,
        "related-observations": [
            {"observation-uuid": oscal_uuid(run_id, "observation", f"{result.control_id}/{i}")}
            for i in range(len(result.observations))
        ],
    }


def build_assessment_results(
    run: RunRecord, profile: Profile, titles: Mapping[str, str]
) -> dict[str, Any]:
    subjects = sorted(
        {s for result in run.results for obs in result.observations for s in obs.subjects}
    )
    result: dict[str, Any] = {
        "uuid": oscal_uuid(run.run_id, "result"),
        "title": f"controlproof run {run.run_id}",
        "description": RESULT_DESCRIPTION,
        "start": timestamp(run.started_at),
        "end": timestamp(run.ended_at),
        "reviewed-controls": _control_selection(profile.control_ids),
        "observations": [obs for r in run.results for obs in _observations(run.run_id, r)],
        "findings": [_finding(run.run_id, r, titles[r.control_id]) for r in run.results],
    }
    if subjects:
        result["local-definitions"] = {
            "inventory-items": [
                {"uuid": oscal_uuid(run.run_id, "subject", s), "description": s} for s in subjects
            ]
        }
    if not result["observations"]:
        del result["observations"], result["findings"]
    document = {
        "assessment-results": {
            "uuid": oscal_uuid(run.run_id, "assessment-results"),
            "metadata": _metadata(run, f"controlproof assessment results: {profile.title}"),
            "import-ap": {"href": PLAN_HREF},
            "results": [result],
        }
    }
    return _finish(document, assessment_results.Model, "assessment-results")
