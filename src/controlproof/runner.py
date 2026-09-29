"""Run a profile's controls and assemble the run record (ADR-0009 §7).

A control that raises, or whose AWS call fails, is recorded as `error` with the evidence it had
collected so far. It never becomes `pass`, and the rest of the run continues.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ValidationError

from controlproof.controls import Control, ControlContext
from controlproof.evidence import EvidenceStore, redact
from controlproof.model import ControlResult, Observation, RunRecord, Status
from controlproof.profile import Profile, ProfileError
from controlproof.providers import AwsApi, ProviderError


@dataclass(frozen=True)
class Planned:
    control: Control
    params: BaseModel


def prepare(profile: Profile, registry: Mapping[str, type[Control]]) -> list[Planned]:
    """Resolve and validate every control before anything runs. Raises `ProfileError`."""
    planned, problems = [], []
    for entry in sorted(profile.controls, key=lambda c: c.id):
        control_type = registry.get(entry.id)
        if control_type is None:
            problems.append(f"unknown control id {entry.id!r}")
            continue
        try:
            params = control_type.Params.model_validate(entry.params)
        except ValidationError as exc:
            detail = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
            problems.append(f"{entry.id} params: {detail}")
            continue
        planned.append(Planned(control_type(), params))
    if problems:
        raise ProfileError(f"profile {profile.id}: " + "; ".join(problems))
    return planned


def _errored(
    control: Control, ctx: ControlContext, started: datetime, summary: str, refs: tuple[str, ...]
) -> ControlResult:
    text = redact(summary)
    if not isinstance(text, str):  # redact keeps the type of its input
        raise TypeError("redacted summary is not text")
    return control.result(
        ctx, started, Status.ERROR, [Observation(summary=text, evidence_refs=refs)], refs
    )


def run_controls(
    planned: list[Planned],
    *,
    profile_id: str,
    account: str,
    regions: tuple[str, ...],
    aws: AwsApi,
    evidence: EvidenceStore,
    clock: Callable[[], datetime],
    tool_version: str,
) -> RunRecord:
    started = clock()
    run_id = started.strftime("%Y%m%dT%H%M%SZ")
    results = []
    for item in planned:
        mark = evidence.mark()
        control_started = clock()
        ctx = ControlContext(run_id, clock, tool_version, item.params, aws, regions)
        try:
            result = item.control.run(ctx)
            if (result.control_id, result.method) != (item.control.id, item.control.method):
                raise RuntimeError(f"returned a result for {result.control_id} ({result.method})")
        except ProviderError as exc:
            result = _errored(
                item.control,
                ctx,
                control_started,
                f"An AWS call failed, so the control could not be tested: {exc}",
                evidence.since(mark),
            )
        except Exception as exc:  # noqa: BLE001 - ADR-0009 §7: a control that raises must never pass
            result = _errored(
                item.control,
                ctx,
                control_started,
                f"The control raised {type(exc).__name__}: {exc}",
                evidence.since(mark),
            )
        results.append(result)
    return RunRecord(
        run_id=run_id,
        profile_id=profile_id,
        account=account,
        regions=regions,
        started_at=started,
        ended_at=clock(),
        tool_version=tool_version,
        results=tuple(results),
    )
