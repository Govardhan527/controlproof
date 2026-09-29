"""Controls: one module per control, each declaring its id, title, method and permissions."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from controlproof.model import ControlResult, Method


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


class Control(ABC):
    id: ClassVar[str]
    title: ClassVar[str]
    method: ClassVar[Method]
    permissions: ClassVar[tuple[str, ...]]
    Params: ClassVar[type[BaseModel]] = NoParams

    @abstractmethod
    def run(self, ctx: ControlContext) -> ControlResult:
        """Test the control and return its result. Never return `pass` without evidence."""
