"""Data contracts for control results and runs (ADR-0008).

Invariants enforced here, so no caller can build a misleading record:
- a `pass` or `fail` needs at least one evidence hash; only `error` and `not_tested` may lack one;
- every result has at least one observation saying what was checked, or why it was not;
- an observation cites only evidence its own result holds;
- times are UTC and a result or run never ends before it starts;
- a run lists each control once, sorted by control id.
"""

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"


def _require_utc(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamps must be UTC")
    return value


ControlId = Annotated[str, StringConstraints(pattern=r"^[a-z]{2}-\d+(\.\d+)?$")]
"""An SP 800-53 Rev 5 control id in OSCAL form, for example `sc-28` or `ia-2.1`."""

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
RunId = Annotated[str, StringConstraints(pattern=r"^\d{8}T\d{6}Z$")]
Token = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]*$")]
UtcDatetime = Annotated[AwareDatetime, AfterValidator(_require_utc)]


class Status(StrEnum):
    PASS = "pass"  # noqa: S105 (a test outcome, not a password)
    FAIL = "fail"
    ERROR = "error"
    NOT_TESTED = "not_tested"


class Method(StrEnum):
    INSPECT = "inspect"
    SIMULATE = "simulate"
    EXERCISE = "exercise"


class Contract(BaseModel):
    """Base for every data contract: immutable, and unknown fields are errors."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Observation(Contract):
    summary: str = Field(min_length=1)
    subjects: tuple[str, ...] = ()
    evidence_refs: tuple[Sha256, ...] = ()


class ControlResult(Contract):
    control_id: ControlId
    method: Method
    status: Status
    observations: tuple[Observation, ...] = Field(min_length=1)
    evidence_refs: tuple[Sha256, ...]
    started_at: UtcDatetime
    ended_at: UtcDatetime
    tool_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.ended_at < self.started_at:
            raise ValueError("ended_at is before started_at")
        if self.status in (Status.PASS, Status.FAIL) and not self.evidence_refs:
            raise ValueError(f"a {self.status} result needs at least one evidence reference")
        cited = {ref for observation in self.observations for ref in observation.evidence_refs}
        if missing := sorted(cited - set(self.evidence_refs)):
            raise ValueError(f"observations cite evidence the result does not hold: {missing}")
        return self


class RunRecord(Contract):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    run_id: RunId
    profile_id: Token
    started_at: UtcDatetime
    ended_at: UtcDatetime
    tool_version: str = Field(min_length=1)
    results: tuple[ControlResult, ...]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.ended_at < self.started_at:
            raise ValueError("ended_at is before started_at")
        ids = [result.control_id for result in self.results]
        if ids != sorted(set(ids)):
            raise ValueError("results must list each control once, sorted by control id")
        return self
