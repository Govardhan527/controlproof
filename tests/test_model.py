from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from controlproof.model import ControlResult, Method, Observation, RunRecord, Status

T0 = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)
SHA_A = "a" * 64
SHA_B = "b" * 64


def result(**changes: Any) -> ControlResult:
    fields: dict[str, Any] = {
        "control_id": "sc-28",
        "method": Method.INSPECT,
        "status": Status.PASS,
        "observations": (Observation(summary="checked", evidence_refs=(SHA_A,)),),
        "evidence_refs": (SHA_A,),
        "started_at": T0,
        "ended_at": T0 + timedelta(seconds=1),
        "tool_version": "0.0.0",
    }
    fields.update(changes)
    return ControlResult(**fields)


def run(*results: ControlResult) -> RunRecord:
    return RunRecord(
        run_id="20260929T120000Z",
        profile_id="p",
        started_at=T0,
        ended_at=T0 + timedelta(minutes=1),
        tool_version="0.0.0",
        results=results,
    )


def test_a_complete_result_is_valid() -> None:
    assert result().status is Status.PASS


@pytest.mark.parametrize("status", [Status.PASS, Status.FAIL])
def test_pass_or_fail_without_evidence_is_impossible(status: Status) -> None:
    with pytest.raises(ValidationError, match="needs at least one evidence reference"):
        result(status=status, evidence_refs=(), observations=(Observation(summary="x"),))


@pytest.mark.parametrize("status", [Status.ERROR, Status.NOT_TESTED])
def test_error_and_not_tested_may_lack_evidence(status: Status) -> None:
    assert result(status=status, evidence_refs=(), observations=(Observation(summary="x"),))


def test_a_result_needs_an_observation() -> None:
    with pytest.raises(ValidationError):
        result(observations=())


def test_observations_cite_only_the_results_evidence() -> None:
    with pytest.raises(ValidationError, match="does not hold"):
        result(observations=(Observation(summary="x", evidence_refs=(SHA_B,)),))


@pytest.mark.parametrize(
    "moment",
    [
        datetime(2026, 9, 29, 12, 0, 0),
        datetime(2026, 9, 29, 12, 0, 0, tzinfo=timezone(timedelta(hours=5))),
    ],
)
def test_times_must_be_utc(moment: datetime) -> None:
    with pytest.raises(ValidationError):
        result(started_at=moment)


def test_a_result_cannot_end_before_it_starts() -> None:
    with pytest.raises(ValidationError, match="before started_at"):
        result(ended_at=T0 - timedelta(seconds=1))


@pytest.mark.parametrize("control_id", ["SC-28", "sc-28(1)", "sc28", "sc-28.1.2", ""])
def test_control_ids_use_the_oscal_form(control_id: str) -> None:
    with pytest.raises(ValidationError):
        result(control_id=control_id)


def test_evidence_refs_are_sha256_hex() -> None:
    with pytest.raises(ValidationError):
        result(evidence_refs=("A" * 64,))


def test_contracts_are_frozen_and_closed() -> None:
    with pytest.raises(ValidationError):
        result().status = Status.FAIL  # type: ignore[misc]
    with pytest.raises(ValidationError):
        Observation(summary="x", note="extra")  # type: ignore[call-arg]


def test_runs_list_each_control_once_in_order() -> None:
    assert run(result(control_id="ac-2"), result(control_id="sc-28"))
    with pytest.raises(ValidationError, match="once, sorted"):
        run(result(control_id="sc-28"), result(control_id="ac-2"))
    with pytest.raises(ValidationError, match="once, sorted"):
        run(result(), result())


def test_a_run_cannot_end_before_it_starts() -> None:
    with pytest.raises(ValidationError, match="before started_at"):
        RunRecord(
            run_id="20260929T120000Z",
            profile_id="p",
            started_at=T0,
            ended_at=T0 - timedelta(seconds=1),
            tool_version="0.0.0",
            results=(),
        )
