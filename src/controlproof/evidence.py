"""Evidence: every AWS response a control relies on, redacted, hashed and stored (ADR-0009 §6).

Redaction runs before hashing, so a stored evidence file never contains:
- the value of a secret field (`SECRET_FIELDS`, matched by exact name), replaced by `[REDACTED]`;
- an access key id (`AKIA...`, `ASIA...`), reduced to its last four characters;
- a 12-digit AWS account id, standalone or inside an ARN, replaced by `[ACCOUNT]`.
Field names such as `PasswordLastUsed` stay: matching is by exact name, never by substring.
"""

import hashlib
from typing import Literal

import regex
from pydantic import Field, JsonValue

from controlproof.canonical import to_json
from controlproof.model import Contract, UtcDatetime

EVIDENCE_VERSION: Literal["1.0.0"] = "1.0.0"
EVIDENCE_DIR = "evidence"
REDACTED = "[REDACTED]"
ACCOUNT = "[ACCOUNT]"
SECRET_FIELDS = frozenset(
    {
        "SecretAccessKey",
        "SessionToken",
        "Password",
        "PrivateKey",
        "CertificateBody",
        "CertificateChain",
    }
)
_ACCESS_KEY_ID = regex.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
_ACCOUNT_ID = regex.compile(r"(?<![0-9])[0-9]{12}(?![0-9])")


def _redact_text(text: str) -> str:
    text = _ACCESS_KEY_ID.sub(lambda m: f"[KEY:...{m.group(0)[-4:]}]", text)
    return _ACCOUNT_ID.sub(ACCOUNT, text)


def redact(value: JsonValue) -> JsonValue:
    """Return `value` with secrets, access key ids and account ids removed."""
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {
            _redact_text(key): (
                REDACTED if key in SECRET_FIELDS and item is not None else redact(item)
            )
            for key, item in value.items()
        }
    return value


class EvidenceRecord(Contract):
    schema_version: Literal["1.0.0"] = EVIDENCE_VERSION
    service: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    region: str | None = None
    request: dict[str, JsonValue]
    response: JsonValue = None
    error: dict[str, str] | None = None
    collected_at: UtcDatetime


class EvidenceStore:
    """Collects the evidence files of one run, keyed by the SHA-256 of their bytes."""

    def __init__(self) -> None:
        self._files: dict[str, bytes] = {}
        self._order: list[str] = []

    def add(self, record: EvidenceRecord) -> str:
        """Redact `record`, store it, and return its SHA-256."""
        error = (
            None if record.error is None else {k: _redact_text(v) for k, v in record.error.items()}
        )
        clean = record.model_copy(
            update={
                "request": redact(record.request),
                "response": redact(record.response),
                "error": error,
            }
        )
        data = to_json(clean.model_dump(mode="json"))
        digest = hashlib.sha256(data).hexdigest()
        self._files.setdefault(digest, data)
        self._order.append(digest)
        return digest

    def mark(self) -> int:
        """A position to pass to `since` later."""
        return len(self._order)

    def since(self, mark: int) -> tuple[str, ...]:
        """Every distinct evidence hash added after `mark`, in order."""
        return tuple(dict.fromkeys(self._order[mark:]))

    def __contains__(self, digest: object) -> bool:
        return digest in self._files

    def files(self) -> dict[str, bytes]:
        return {f"{EVIDENCE_DIR}/{digest}.json": data for digest, data in self._files.items()}
