"""The provider boundary: controls reach a cloud only through these interfaces."""

from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any, Protocol


class ProviderError(Exception):
    """A cloud API call failed. The control that made it reports `error`, never `pass`."""

    def __init__(self, service: str, operation: str, region: str | None, code: str, message: str):
        self.service = service
        self.operation = operation
        self.region = region
        self.code = code
        super().__init__(f"{service}.{operation} in {region or 'global'} failed: {code}: {message}")


@dataclass(frozen=True)
class Captured:
    """One API response (or an expected API error) and the hash of its stored evidence."""

    ref: str
    data: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None


class AwsApi(Protocol):
    """What a control may ask of AWS. Every call is recorded as evidence before it returns."""

    def call(
        self,
        service: str,
        operation: str,
        *,
        region: str | None = None,
        expected_errors: Collection[str] = (),
        **params: Any,
    ) -> Captured:
        """Make one call. An error code in `expected_errors` is returned, not raised."""
        ...

    def paginate(
        self, service: str, operation: str, *, region: str | None = None, **params: Any
    ) -> list[Captured]:
        """Read every page of a paginated call."""
        ...
