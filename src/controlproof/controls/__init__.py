"""Controls: one module per control, each declaring its id, title, method and permissions."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from controlproof.model import ControlResult, Method, Observation, Status
from controlproof.providers import AwsApi


class NoParams(BaseModel):
    """Parameters of a control that takes none; any key given is an error."""

    model_config = ConfigDict(frozen=True, extra="forbid")


@dataclass(frozen=True)
class ControlContext:
    """What a control may use while it runs. The clock is injected for determinism."""

    run_id: str
    clock: Callable[[], datetime]
    tool_version: str
    params: BaseModel
    aws: AwsApi
    regions: tuple[str, ...]


def typed_params[P: BaseModel](ctx: ControlContext, kind: type[P]) -> P:
    if not isinstance(ctx.params, kind):
        raise TypeError(f"expected {kind.__name__} params, got {type(ctx.params).__name__}")
    return ctx.params


class Control(ABC):
    id: ClassVar[str]
    title: ClassVar[str]
    method: ClassVar[Method]
    permissions: ClassVar[tuple[str, ...]]
    Params: ClassVar[type[BaseModel]] = NoParams

    @abstractmethod
    def run(self, ctx: ControlContext) -> ControlResult:
        """Test the control and return its result. Never return `pass` without evidence."""

    def result(
        self,
        ctx: ControlContext,
        started: datetime,
        status: Status,
        observations: Sequence[Observation],
        refs: Sequence[str],
    ) -> ControlResult:
        return ControlResult(
            control_id=self.id,
            method=self.method,
            status=status,
            observations=tuple(observations),
            evidence_refs=tuple(dict.fromkeys(refs)),
            started_at=started,
            ended_at=ctx.clock(),
            tool_version=ctx.tool_version,
        )

    def outcome(
        self,
        ctx: ControlContext,
        started: datetime,
        *,
        checked: str,
        subjects: Sequence[str],
        failures: Sequence[tuple[str, str]],
        refs: Sequence[str],
    ) -> ControlResult:
        """`pass` or `fail` with two observations: what was checked, and what failed.

        `failures` pairs a subject (or "" for an account-wide finding) with a description.
        Both observations cite every evidence file the control collected.
        """
        cited = tuple(dict.fromkeys(refs))
        observations = [
            Observation(summary=checked, subjects=tuple(sorted(set(subjects))), evidence_refs=cited)
        ]
        if failures:
            observations.append(
                Observation(
                    summary="; ".join(text for _, text in failures) + ".",
                    subjects=tuple(sorted({subject for subject, _ in failures if subject})),
                    evidence_refs=cited,
                )
            )
        status = Status.FAIL if failures else Status.PASS
        return self.result(ctx, started, status, observations, cited)
