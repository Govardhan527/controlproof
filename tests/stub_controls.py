"""Three stub controls for M1: each returns the outcome its profile asks for, without AWS.

They live in tests/, never in the package, and are replaced by real controls from M2 on.
"""

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from controlproof.controls import Control, ControlContext
from controlproof.model import ControlResult, Method, Observation, RunRecord, Status
from controlproof.output import render_run
from controlproof.profile import Profile, load_profile

FIXTURES = Path(__file__).parent / "fixtures"
TOOL_VERSION = "0.0.0"
ACCOUNT = "123456789012"
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
        assert isinstance(ctx.params, StubParams)
        outcome = ctx.params.outcome
        started = ctx.clock()
        subject = f"arn:aws:s3:::stub-{self.id}"
        evidence = hashlib.sha256(f"{self.id}:{outcome}".encode()).hexdigest()
        refs = (evidence,) if outcome in (Status.PASS, Status.FAIL) else ()
        summary = {
            Status.PASS: f"Stub check of {subject} met the expected state.",
            Status.FAIL: f"Stub check of {subject} did not meet the expected state.",
            Status.ERROR: "Stub check raised an error before any evidence was collected.",
            Status.NOT_TESTED: "Stub check was not run: exercise controls need --allow-exercise.",
        }[outcome]
        observation = Observation(
            summary=summary, subjects=(subject,) if refs else (), evidence_refs=refs
        )
        return ControlResult(
            control_id=self.id,
            method=self.method,
            status=outcome,
            observations=(observation,),
            evidence_refs=refs,
            started_at=started,
            ended_at=ctx.clock(),
            tool_version=ctx.tool_version,
        )


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


def stub_run(name: str) -> tuple[RunRecord, Profile]:
    profile = load_profile(FIXTURES / f"{name}.yaml", STUBS)
    ticks = ticking_clock(START[name])
    clock = lambda: next(ticks)  # noqa: E731
    started = clock()
    run_id = started.strftime("%Y%m%dT%H%M%SZ")
    results = []
    for entry in sorted(profile.controls, key=lambda c: c.id):
        control = STUBS[entry.id]()
        params = control.Params.model_validate(entry.params)
        results.append(control.run(ControlContext(run_id, clock, TOOL_VERSION, params)))
    run = RunRecord(
        run_id=run_id,
        profile_id=profile.id,
        started_at=started,
        ended_at=clock(),
        tool_version=TOOL_VERSION,
        results=tuple(results),
    )
    return run, profile


def render_stub(name: str) -> dict[str, bytes]:
    run, profile = stub_run(name)
    return render_run(run, profile, TITLES, METHODS, ACCOUNT)
