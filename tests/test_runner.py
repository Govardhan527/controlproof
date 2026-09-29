"""The runner never turns a failure to test into a pass (ADR-0009 §7)."""

from datetime import UTC, datetime
from typing import ClassVar

import pytest

from controlproof.controls import Control, ControlContext
from controlproof.evidence import ACCOUNT, EvidenceStore
from controlproof.model import ControlResult, Method, Status
from controlproof.profile import Profile, ProfileControl, ProfileError
from controlproof.providers import ProviderError
from controlproof.runner import prepare, run_controls
from fake_aws import FakeAws
from stub_controls import STUBS, StubAccountManagement

NOW = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)


class Raises(Control):
    id = "ac-5"
    title = "Separation of Duties"
    method = Method.INSPECT
    permissions: ClassVar[tuple[str, ...]] = ()

    def run(self, ctx: ControlContext) -> ControlResult:
        raise ValueError("unexpected response shape")


class FailsAfterACall(Control):
    id = "au-9"
    title = "Protection of Audit Information"
    method = Method.INSPECT
    permissions: ClassVar[tuple[str, ...]] = ()

    def run(self, ctx: ControlContext) -> ControlResult:
        ctx.aws.call("iam", "Probe")
        raise ProviderError(
            "iam",
            "GetAccountSummary",
            None,
            "AccessDenied",
            "arn:aws:iam::123456789012:user/x is not authorized",
        )


class ImpersonatesAnother(Control):
    id = "cm-5"
    title = "Access Restrictions for Change"
    method = Method.INSPECT
    permissions: ClassVar[tuple[str, ...]] = ()

    def run(self, ctx: ControlContext) -> ControlResult:
        return StubAccountManagement().run(
            ControlContext(
                ctx.run_id,
                ctx.clock,
                ctx.tool_version,
                StubAccountManagement.Params(outcome="pass"),
                ctx.aws,
                ctx.regions,
            )  # type: ignore[call-arg]
        )


REGISTRY: dict[str, type[Control]] = {
    **STUBS,
    "ac-5": Raises,
    "au-9": FailsAfterACall,
    "cm-5": ImpersonatesAnother,
}


def profile(*entries: tuple[str, dict[str, object]]) -> Profile:
    return Profile(
        schema_version="1.1.0",
        id="t",
        title="t",
        provider="aws",
        controls=tuple(ProfileControl(id=cid, params=params) for cid, params in entries),  # type: ignore[arg-type]
    )


def execute(*entries: tuple[str, dict[str, object]]) -> dict[str, ControlResult]:
    evidence = EvidenceStore()
    record = run_controls(
        prepare(profile(*entries), REGISTRY),
        profile_id="t",
        account="123456789012",
        regions=("us-east-1",),
        aws=FakeAws(evidence, lambda: NOW),
        evidence=evidence,
        clock=lambda: NOW,
        tool_version="0.0.0",
    )
    return {r.control_id: r for r in record.results}


def test_a_control_that_raises_is_an_error_and_the_run_continues() -> None:
    results = execute(("ac-5", {}), ("ac-2", {"outcome": "pass"}))
    assert results["ac-5"].status is Status.ERROR
    assert "raised ValueError: unexpected response shape" in results["ac-5"].observations[0].summary
    assert results["ac-2"].status is Status.PASS


def test_a_failed_aws_call_is_an_error_that_keeps_its_evidence_and_hides_the_account() -> None:
    result = execute(("au-9", {}))["au-9"]
    assert result.status is Status.ERROR
    assert len(result.evidence_refs) == 1
    summary = result.observations[0].summary
    assert "AccessDenied" in summary
    assert ACCOUNT in summary
    assert "123456789012" not in summary


def test_a_result_for_another_control_is_an_error() -> None:
    result = execute(("cm-5", {}))["cm-5"]
    assert result.status is Status.ERROR
    assert "returned a result for ac-2" in result.observations[0].summary


def test_results_are_in_control_id_order() -> None:
    results = execute(("sc-13", {"outcome": "pass"}), ("ac-2", {"outcome": "pass"}))
    assert list(results) == ["ac-2", "sc-13"]


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        (("zz-9", {}), "unknown control id 'zz-9'"),
        (("ac-2", {"outcome": "maybe"}), "ac-2 params: outcome"),
    ],
)
def test_prepare_rejects_bad_profiles_before_anything_runs(
    entry: tuple[str, dict[str, object]], message: str
) -> None:
    with pytest.raises(ProfileError, match=message):
        prepare(profile(entry), REGISTRY)
