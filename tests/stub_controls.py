"""Three stub controls: each returns the outcome its profile asks for, without AWS behaviour.

They live in tests/, never in the package. They cover the `error` and `not_tested` mappings that
the real controls only reach through failures.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from controlproof.controls import Control, ControlContext, typed_params
from controlproof.evidence import EvidenceStore
from controlproof.model import ControlResult, Method, Observation, RunRecord, Status
from controlproof.output import render_run
from controlproof.profile import Profile, load_profile
from controlproof.runner import prepare, run_controls
from fake_aws import FakeAws

FIXTURES = Path(__file__).parent / "fixtures"
TOOL_VERSION = "0.0.0"
ACCOUNT = "123456789012"
REGIONS = ("us-east-1",)
START = {
    "stub-run-a": datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC),
    "stub-run-b": datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC),
}


class StubParams(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    outcome: Status


class _Stub(Control):
    permissions: ClassVar[tuple[str, ...]] = ()
    Params: ClassVar[type[BaseModel]] = StubParams

    def run(self, ctx: ControlContext) -> ControlResult:
        outcome = typed_params(ctx, StubParams).outcome
        started = ctx.clock()
        subject = f"arn:aws:s3:::stub-{self.id}"
        refs: tuple[str, ...] = ()
        if outcome in (Status.PASS, Status.FAIL):
            refs = (ctx.aws.call("stub", "Check", Control=self.id, Outcome=outcome.value).ref,)
        summary = {
            Status.PASS: f"Stub check of {subject} met the expected state.",
            Status.FAIL: f"Stub check of {subject} did not meet the expected state.",
            Status.ERROR: "Stub check raised an error before any evidence was collected.",
            Status.NOT_TESTED: "Stub check was not run: exercise controls need --allow-exercise.",
        }[outcome]
        observation = Observation(
            summary=summary, subjects=(subject,) if refs else (), evidence_refs=refs
        )
        return self.result(ctx, started, outcome, [observation], refs)


class StubAccountManagement(_Stub):
    id = "ac-2"
    title = "Account Management"
    method = Method.INSPECT


class StubLeastPrivilege(_Stub):
    id = "ac-6"
    title = "Least Privilege"
    method = Method.SIMULATE


class StubCryptographicProtection(_Stub):
    id = "sc-13"
    title = "Cryptographic Protection"
    method = Method.EXERCISE


STUBS: dict[str, type[Control]] = {
    c.id: c for c in (StubAccountManagement, StubLeastPrivilege, StubCryptographicProtection)
}
TITLES = {cid: c.title for cid, c in STUBS.items()}
METHODS = {cid: c.method for cid, c in STUBS.items()}


def ticking_clock(start: datetime) -> Iterator[datetime]:
    moment = start
    while True:
        yield moment
        moment += timedelta(seconds=1)


def stub_run(name: str) -> tuple[RunRecord, Profile, EvidenceStore]:
    profile = load_profile(FIXTURES / f"{name}.yaml", STUBS)
    ticks = ticking_clock(START[name])
    clock = lambda: next(ticks)  # noqa: E731
    evidence = EvidenceStore()
    run = run_controls(
        prepare(profile, STUBS),
        profile_id=profile.id,
        account=ACCOUNT,
        regions=REGIONS,
        aws=FakeAws(evidence, clock),
        evidence=evidence,
        clock=clock,
        tool_version=TOOL_VERSION,
    )
    return run, profile, evidence


def render_stub(name: str) -> dict[str, bytes]:
    run, profile, evidence = stub_run(name)
    return render_run(run, profile, TITLES, METHODS, evidence.files())
