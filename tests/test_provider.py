"""The AWS provider boundary: evidence for every call, typed errors, declared calls only."""

import json
from datetime import UTC, datetime
from typing import Any

import boto3
import pytest
from botocore.exceptions import NoCredentialsError
from botocore.stub import Stubber

from conftest import REGION
from controlproof.evidence import ACCOUNT, EvidenceStore
from controlproof.providers import ProviderError
from controlproof.providers.aws import OPERATION_ACTIONS, AwsProvider, default_region

NOW = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)


def provider(store: EvidenceStore | None = None) -> AwsProvider:
    return AwsProvider(
        boto3.Session(), store or EvidenceStore(), lambda: NOW, REGION, max_attempts=1
    )


def stored(store: EvidenceStore, ref: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(store.files()[f"evidence/{ref}.json"])
    return data


@pytest.mark.usefixtures("moto")
def test_a_call_returns_plain_json_and_stores_redacted_evidence() -> None:
    boto3.client("iam", region_name=REGION).create_user(UserName="alice")
    store = EvidenceStore()
    pages = provider(store).paginate("iam", "ListUsers")
    user = pages[0].data["Users"][0]
    assert isinstance(user["CreateDate"], str)
    assert user["CreateDate"].endswith("Z")
    assert "123456789012" in user["Arn"]  # the control sees real values
    evidence = stored(store, pages[0].ref)
    assert evidence["response"]["Users"][0]["Arn"] == f"arn:aws:iam::{ACCOUNT}:user/alice"
    assert evidence["service"] == "iam"
    assert evidence["region"] is None
    assert "ResponseMetadata" not in evidence["response"]


def test_paginate_reads_every_page() -> None:
    # moto returns every IAM user in one page, so two real pages are served by botocore's Stubber.
    def user(name: str) -> dict[str, Any]:
        return {
            "Path": "/",
            "UserName": name,
            "UserId": f"AIDA{name.upper():0<17}",
            "Arn": f"arn:aws:iam::123456789012:user/{name}",
            "CreateDate": NOW,
        }

    store = EvidenceStore()
    aws = provider(store)
    with Stubber(aws._client("iam", REGION)) as stub:
        stub.add_response(
            "list_users", {"Users": [user("a1")], "IsTruncated": True, "Marker": "m1"}
        )
        stub.add_response(
            "list_users", {"Users": [user("a2")], "IsTruncated": False}, {"Marker": "m1"}
        )
        pages = aws.paginate("iam", "ListUsers")
    assert [u["UserName"] for p in pages for u in p.data["Users"]] == ["a1", "a2"]
    assert len({p.ref for p in pages}) == 2
    assert len(store.files()) == 2


@pytest.mark.usefixtures("moto")
def test_an_expected_error_is_returned_and_recorded() -> None:
    boto3.client("iam", region_name=REGION).create_user(UserName="alice")
    store = EvidenceStore()
    captured = provider(store).call(
        "iam", "GetLoginProfile", UserName="alice", expected_errors=("NoSuchEntity",)
    )
    assert captured.error_code == "NoSuchEntity"
    assert captured.data == {}
    assert stored(store, captured.ref)["error"]["code"] == "NoSuchEntity"


@pytest.mark.usefixtures("moto")
def test_an_unexpected_error_raises_with_its_code() -> None:
    with pytest.raises(ProviderError) as caught:
        provider().call("iam", "GetLoginProfile", UserName="nobody")
    assert caught.value.code == "NoSuchEntity"
    assert "iam.GetLoginProfile" in str(caught.value)


def test_an_undeclared_call_is_refused_before_it_is_sent() -> None:
    aws = provider()
    with pytest.raises(ProviderError, match="NotDeclared"):
        aws.call("iam", "DeleteUser", UserName="alice")
    with pytest.raises(ProviderError, match="NotDeclared"):
        aws.paginate("s3", "ListObjectsV2", Bucket="b")
    assert aws.calls == []


@pytest.mark.parametrize("code", ["AccessDenied", "Throttling"])
def test_access_denied_and_throttling_become_provider_errors(code: str) -> None:
    store = EvidenceStore()
    aws = provider(store)
    client = aws._client("iam", REGION)
    with Stubber(client) as stub:
        stub.add_client_error(
            "get_account_password_policy",
            service_error_code=code,
            service_message=f"{code} for arn:aws:iam::123456789012:user/x",
        )
        with pytest.raises(ProviderError) as caught:
            aws.call("iam", "GetAccountPasswordPolicy")
    assert caught.value.code == code
    (evidence,) = [json.loads(v) for v in store.files().values()]
    assert evidence["error"]["code"] == code
    assert "123456789012" not in evidence["error"]["message"]


def test_a_paginated_access_denied_becomes_a_provider_error() -> None:
    store = EvidenceStore()
    aws = provider(store)
    with Stubber(aws._client("iam", REGION)) as stub:
        stub.add_client_error("list_users", service_error_code="AccessDenied")
        with pytest.raises(ProviderError, match="AccessDenied"):
            aws.paginate("iam", "ListUsers")
    assert len(store.files()) == 1


def test_missing_credentials_become_a_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    aws = provider()

    class NoCredentials:
        def get_caller_identity(self) -> None:
            raise NoCredentialsError()

    monkeypatch.setattr(aws, "_client", lambda service, region: NoCredentials())
    with pytest.raises(ProviderError, match="NoCredentialsError"):
        aws.account_id()


@pytest.mark.usefixtures("moto")
def test_account_id_and_default_region() -> None:
    assert provider().account_id() == "123456789012"
    assert default_region() == REGION


def test_every_mapped_action_is_read_only_by_name() -> None:
    # SPEC_NOTES §5.8: every action in the table is classified non-write by AWS. This guards the
    # table against an accidental write verb being added without that check.
    for action in OPERATION_ACTIONS.values():
        verb = action.split(":", 1)[1]
        assert verb.startswith(("Describe", "Get", "List")), action
