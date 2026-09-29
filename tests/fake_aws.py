"""A canned `AwsApi` for tests that need evidence but no AWS behaviour (the M1 stubs)."""

from collections.abc import Callable, Collection
from datetime import datetime
from typing import Any

from controlproof.canonical import jsonable
from controlproof.evidence import EvidenceRecord, EvidenceStore
from controlproof.providers import Captured


class FakeAws:
    def __init__(self, evidence: EvidenceStore, clock: Callable[[], datetime]) -> None:
        self.evidence = evidence
        self.clock = clock

    def call(
        self,
        service: str,
        operation: str,
        *,
        region: str | None = None,
        expected_errors: Collection[str] = (),
        **params: Any,
    ) -> Captured:
        record = EvidenceRecord(
            service=service,
            operation=operation,
            region=region,
            request={k: jsonable(v) for k, v in params.items()},
            response={"ok": True},
            collected_at=self.clock(),
        )
        return Captured(ref=self.evidence.add(record), data={"ok": True})

    def paginate(
        self, service: str, operation: str, *, region: str | None = None, **params: Any
    ) -> list[Captured]:
        return [self.call(service, operation, region=region, **params)]
