"""Record AWS calls once, replay them byte-for-byte later (golden runs, ADR-0009 §9).

moto invents random ids and uses the wall clock, so a golden run from live moto would change on
every execution. Recording keeps the redacted request and response of every call; replaying feeds
them back through the same control code. A recording from the real sandbox can later replace the
moto one without code changes.
"""

import json
from collections import defaultdict, deque
from collections.abc import Callable, Collection
from datetime import datetime
from pathlib import Path
from typing import Any

from controlproof.canonical import jsonable, to_json
from controlproof.evidence import EvidenceRecord, EvidenceStore, redact
from controlproof.providers import AwsApi, Captured, ProviderError
from controlproof.providers.aws import GLOBAL_SERVICES


def _key(
    kind: str, service: str, operation: str, region: str | None, params: dict[str, Any]
) -> str:
    return json.dumps([kind, service, operation, region, redact(jsonable(params))], sort_keys=True)


class RecordingAws:
    """Wraps a live `AwsApi` and keeps a redacted copy of every call."""

    def __init__(self, inner: AwsApi) -> None:
        self.inner = inner
        self.entries: list[dict[str, Any]] = []

    def _entry(
        self,
        kind: str,
        service: str,
        operation: str,
        region: str | None,
        params: dict[str, Any],
        **outcome: Any,
    ) -> None:
        self.entries.append({"key": _key(kind, service, operation, region, params), **outcome})

    def call(
        self,
        service: str,
        operation: str,
        *,
        region: str | None = None,
        expected_errors: Collection[str] = (),
        **params: Any,
    ) -> Captured:
        try:
            captured = self.inner.call(
                service, operation, region=region, expected_errors=expected_errors, **params
            )
        except ProviderError as exc:
            self._entry(
                "call",
                service,
                operation,
                region,
                params,
                error={"code": exc.code, "message": redact(str(exc))},
            )
            raise
        if captured.error_code is not None:
            self._entry(
                "call",
                service,
                operation,
                region,
                params,
                error={"code": captured.error_code, "message": ""},
            )
        else:
            self._entry("call", service, operation, region, params, response=redact(captured.data))
        return captured

    def paginate(
        self, service: str, operation: str, *, region: str | None = None, **params: Any
    ) -> list[Captured]:
        pages = self.inner.paginate(service, operation, region=region, **params)
        self._entry(
            "paginate", service, operation, region, params, pages=[redact(p.data) for p in pages]
        )
        return pages

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(to_json(self.entries))


class ReplayAws:
    """Serves a recording in order; any call that was not recorded fails the test."""

    def __init__(
        self,
        path: Path,
        evidence: EvidenceStore,
        clock: Callable[[], datetime],
        default_region: str,
    ) -> None:
        self._queues: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
        for entry in json.loads(path.read_text(encoding="utf-8")):
            self._queues[entry["key"]].append(entry)
        self._evidence = evidence
        self._clock = clock
        self._default_region = default_region

    def _take(
        self, kind: str, service: str, operation: str, region: str | None, params: dict[str, Any]
    ) -> dict[str, Any]:
        queue = self._queues.get(_key(kind, service, operation, region, params))
        if not queue:
            raise AssertionError(f"unrecorded {kind}: {service}.{operation} {region} {params}")
        return queue.popleft()

    def _store(
        self,
        service: str,
        operation: str,
        region: str | None,
        params: dict[str, Any],
        response: Any = None,
        error: dict[str, str] | None = None,
    ) -> str:
        return self._evidence.add(
            EvidenceRecord(
                service=service,
                operation=operation,
                region=None if service in GLOBAL_SERVICES else (region or self._default_region),
                request={str(k): jsonable(v) for k, v in params.items()},
                response=response,
                error=error,
                collected_at=self._clock(),
            )
        )

    def call(
        self,
        service: str,
        operation: str,
        *,
        region: str | None = None,
        expected_errors: Collection[str] = (),
        **params: Any,
    ) -> Captured:
        entry = self._take("call", service, operation, region, params)
        if "error" in entry:
            error = entry["error"]
            ref = self._store(service, operation, region, params, error=error)
            if error["code"] in expected_errors:
                return Captured(ref=ref, error_code=error["code"])
            raise ProviderError(service, operation, region, error["code"], error["message"])
        return Captured(
            ref=self._store(service, operation, region, params, entry["response"]),
            data=entry["response"],
        )

    def paginate(
        self, service: str, operation: str, *, region: str | None = None, **params: Any
    ) -> list[Captured]:
        entry = self._take("paginate", service, operation, region, params)
        return [
            Captured(ref=self._store(service, operation, region, params, page), data=page)
            for page in entry["pages"]
        ]
