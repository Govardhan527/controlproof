"""Redaction and evidence storage (ADR-0009 §6). Proves no secret reaches a stored file."""

import hashlib
import json
from datetime import UTC, datetime, timedelta, timezone

import pytest

from controlproof.canonical import iso, jsonable, parse_time
from controlproof.evidence import ACCOUNT, REDACTED, EvidenceRecord, EvidenceStore, redact

T0 = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)
SECRETS = {
    "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYSYNTHETIC",
    "SessionToken": "FwoGZXIvYXdzEBYaDSYNTHETICTOKEN",
    "Password": "Synthetic-Passw0rd!",
    "PrivateKey": "-----BEGIN PRIVATE KEY-----SYNTHETIC",
    "CertificateBody": "-----BEGIN CERTIFICATE-----SYNTHETIC",
    "CertificateChain": "-----BEGIN CERTIFICATE-----CHAIN",
}
ACCESS_KEY = "AKIAIOSFODNN7SYNTH1X"
SESSION_KEY = "ASIAIOSFODNN7SYNTH2Y"
ACCOUNT_ID = "123456789012"


def record(response: object, error: dict[str, str] | None = None) -> EvidenceRecord:
    return EvidenceRecord(
        service="iam",
        operation="Synthetic",
        request={"UserName": "alice", "Arn": f"arn:aws:iam::{ACCOUNT_ID}:user/alice"},
        response=jsonable(response),
        error=error,
        collected_at=T0,
    )


def test_no_secret_survives_into_a_stored_file() -> None:
    response = {
        "Credentials": {**SECRETS, "AccessKeyId": ACCESS_KEY},
        "Nested": [{"Session": SESSION_KEY, "Owner": ACCOUNT_ID}],
        "Arn": f"arn:aws:iam::{ACCOUNT_ID}:role/admin",
        "PasswordLastUsed": "2026-09-01T00:00:00Z",
        "PasswordPolicy": {"MinimumPasswordLength": 14},
    }
    error = {
        "code": "AccessDenied",
        "message": f"arn:aws:iam::{ACCOUNT_ID}:user/x with {ACCESS_KEY} is not authorized",
    }
    store = EvidenceStore()
    ref = store.add(record(response, error))
    stored = store.files()[f"evidence/{ref}.json"].decode()

    for secret in [*SECRETS.values(), ACCESS_KEY, SESSION_KEY, ACCOUNT_ID]:
        assert secret not in stored
    data = json.loads(stored)
    assert data["response"]["Credentials"]["SecretAccessKey"] == REDACTED
    assert data["response"]["Credentials"]["AccessKeyId"] == f"[KEY:...{ACCESS_KEY[-4:]}]"
    assert data["response"]["Arn"] == f"arn:aws:iam::{ACCOUNT}:role/admin"
    assert data["request"]["Arn"] == f"arn:aws:iam::{ACCOUNT}:user/alice"
    assert ACCOUNT in data["error"]["message"]
    # Fields the controls need are kept: matching is by exact name, never by substring.
    assert data["response"]["PasswordLastUsed"] == "2026-09-01T00:00:00Z"
    assert data["response"]["PasswordPolicy"] == {"MinimumPasswordLength": 14}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1234567890123", "1234567890123"),  # 13 digits is not an account id
        ("12345678901", "12345678901"),
        (123456789012, 123456789012),  # numbers are not strings; only text is scanned
        ({"Password": None}, {"Password": None}),
        ({ACCOUNT_ID: "x"}, {ACCOUNT: "x"}),
    ],
)
def test_redaction_edges(value: object, expected: object) -> None:
    assert redact(value) == expected  # type: ignore[arg-type]


def test_store_hashes_the_redacted_bytes_and_deduplicates() -> None:
    store = EvidenceStore()
    mark = store.mark()
    first = store.add(record({"a": 1}))
    second = store.add(record({"a": 1}))
    other = store.add(record({"a": 2}))
    assert first == second != other
    assert store.since(mark) == (first, other)
    assert first in store
    assert "0" * 64 not in store
    for name, data in store.files().items():
        assert name == f"evidence/{hashlib.sha256(data).hexdigest()}.json"


def test_jsonable_converts_sdk_values() -> None:
    value = {"t": T0, "b": b"csv,text", "raw": b"\xff\xfe", "tup": (1, "x")}
    assert jsonable(value) == {
        "t": "2026-09-29T12:00:00Z",
        "b": "csv,text",
        "raw": "base64://4=",
        "tup": [1, "x"],
    }
    with pytest.raises(TypeError):
        jsonable({"s": {1, 2}})


def test_timestamps_round_trip() -> None:
    assert (
        iso(datetime(2026, 9, 29, 17, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))))
        == "2026-09-29T12:00:00Z"
    )
    assert parse_time("2026-09-29T12:00:00Z") == T0
    assert parse_time("2026-09-29T12:00:00+00:00") == T0
    with pytest.raises(ValueError, match="without timezone"):
        parse_time("2026-09-29T12:00:00")
