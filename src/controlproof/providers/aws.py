"""The AWS provider: the only module that imports boto3 (the provider boundary).

Every call is checked against `OPERATION_ACTIONS` (the IAM action AWS authorises it with, from
SPEC_NOTES §5.8), recorded as redacted evidence, and turned into `ProviderError` on failure. A call
not in that table is refused before it is sent, so the documented read-only policy is complete.
"""

from collections.abc import Callable, Collection
from datetime import datetime
from typing import Any

import boto3
from botocore import xform_name
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from controlproof.canonical import jsonable
from controlproof.evidence import EvidenceRecord, EvidenceStore
from controlproof.providers import Captured, ProviderError

OPERATION_ACTIONS: dict[tuple[str, str], str] = {
    ("cloudtrail", "DescribeTrails"): "cloudtrail:DescribeTrails",
    ("cloudtrail", "GetEventSelectors"): "cloudtrail:GetEventSelectors",
    ("cloudtrail", "GetTrailStatus"): "cloudtrail:GetTrailStatus",
    ("ec2", "DescribeSecurityGroups"): "ec2:DescribeSecurityGroups",
    ("ec2", "GetEbsEncryptionByDefault"): "ec2:GetEbsEncryptionByDefault",
    ("iam", "GetAccessKeyLastUsed"): "iam:GetAccessKeyLastUsed",
    ("iam", "GetAccountPasswordPolicy"): "iam:GetAccountPasswordPolicy",
    ("iam", "GetLoginProfile"): "iam:GetLoginProfile",
    ("iam", "ListAccessKeys"): "iam:ListAccessKeys",
    ("iam", "ListMFADevices"): "iam:ListMFADevices",
    ("iam", "ListUsers"): "iam:ListUsers",
    ("s3", "GetBucketEncryption"): "s3:GetEncryptionConfiguration",
    ("s3", "ListBuckets"): "s3:ListAllMyBuckets",
    ("sts", "GetCallerIdentity"): "sts:GetCallerIdentity",
}
GLOBAL_SERVICES = frozenset({"iam", "s3", "sts"})


def _strip_metadata(response: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in response.items() if key != "ResponseMetadata"}


def _plain(response: dict[str, Any]) -> dict[str, Any]:
    """The response as plain JSON values (timestamps as ISO strings), unredacted."""
    plain = jsonable(response)
    if not isinstance(plain, dict):
        raise TypeError(f"expected a JSON object response, got {type(plain).__name__}")
    return plain


class AwsProvider:
    """Real AWS through boto3, with standard-mode retries and evidence for every call."""

    def __init__(
        self,
        session: boto3.Session,
        evidence: EvidenceStore,
        clock: Callable[[], datetime],
        default_region: str,
        max_attempts: int = 5,
    ) -> None:
        self._session = session
        self._evidence = evidence
        self._clock = clock
        self._default_region = default_region
        self._config = Config(retries={"mode": "standard", "max_attempts": max_attempts})
        self._clients: dict[tuple[str, str], Any] = {}
        self.calls: list[tuple[str, str]] = []

    def _client(self, service: str, region: str) -> Any:
        key = (service, region)
        if key not in self._clients:
            self._clients[key] = self._session.client(  # type: ignore[call-overload]
                service, region_name=region, config=self._config
            )
        return self._clients[key]

    def _region(self, service: str, region: str | None) -> str:
        return region or self._default_region

    def _record(
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
                region=None if service in GLOBAL_SERVICES else region,
                request={str(k): jsonable(v) for k, v in params.items()},
                response=jsonable(response),
                error=error,
                collected_at=self._clock(),
            )
        )

    def _check_allowed(self, service: str, operation: str) -> None:
        if (service, operation) not in OPERATION_ACTIONS:
            raise ProviderError(
                service, operation, None, "NotDeclared", "call not in OPERATION_ACTIONS"
            )
        self.calls.append((service, operation))

    def call(
        self,
        service: str,
        operation: str,
        *,
        region: str | None = None,
        expected_errors: Collection[str] = (),
        **params: Any,
    ) -> Captured:
        self._check_allowed(service, operation)
        where = self._region(service, region)
        method = getattr(self._client(service, where), xform_name(operation))
        try:
            response = _strip_metadata(method(**params))
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code, message = str(error.get("Code", "Unknown")), str(error.get("Message", ""))
            ref = self._record(
                service, operation, where, params, error={"code": code, "message": message}
            )
            if code in expected_errors:
                return Captured(ref=ref, error_code=code)
            raise ProviderError(service, operation, where, code, message) from exc
        except BotoCoreError as exc:
            raise ProviderError(service, operation, where, type(exc).__name__, str(exc)) from exc
        ref = self._record(service, operation, where, params, response)
        return Captured(ref=ref, data=_plain(response))

    def paginate(
        self, service: str, operation: str, *, region: str | None = None, **params: Any
    ) -> list[Captured]:
        self._check_allowed(service, operation)
        where = self._region(service, region)
        paginator = self._client(service, where).get_paginator(xform_name(operation))
        pages: list[Captured] = []
        try:
            for page in paginator.paginate(**params):
                response = _strip_metadata(page)
                ref = self._record(service, operation, where, params, response)
                pages.append(Captured(ref=ref, data=_plain(response)))
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code, message = str(error.get("Code", "Unknown")), str(error.get("Message", ""))
            self._record(
                service, operation, where, params, error={"code": code, "message": message}
            )
            raise ProviderError(service, operation, where, code, message) from exc
        except BotoCoreError as exc:
            raise ProviderError(service, operation, where, type(exc).__name__, str(exc)) from exc
        return pages

    @classmethod
    def from_environment(
        cls, evidence: EvidenceStore, clock: Callable[[], datetime], region: str
    ) -> "AwsProvider":
        """Use the standard credential chain (environment, profile, SSO, instance role)."""
        return cls(boto3.Session(), evidence, clock, region)

    def account_id(self) -> str:
        """The account the credentials belong to (`sts:GetCallerIdentity`)."""
        return str(self.call("sts", "GetCallerIdentity").data["Account"])


def default_region() -> str | None:
    """The Region the AWS SDK would use when none is given (AWS_REGION, config file, ...)."""
    region = boto3.Session().region_name
    return str(region) if region else None
