"""Pass and fail fixtures for every control, against the moto fake (ADR-0009 §1 unit tier).

Each run also checks that every AWS call the control made is covered by its declared
permissions, and that every evidence reference it cites was stored.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
import pytest

import aws_scenarios as scenario
from conftest import REGION
from controlproof.controls import Control, ControlContext
from controlproof.controls.ac_2 import AccountManagement
from controlproof.controls.au_2 import MultiRegionTrail
from controlproof.controls.ia_2_2 import MfaForConsoleUsers
from controlproof.controls.ia_5_1 import PasswordPolicy
from controlproof.controls.registry import REGISTRY
from controlproof.controls.sc_7 import AdminPortsClosed
from controlproof.controls.sc_28 import EbsEncryptionByDefault
from controlproof.controls.sc_28_1 import S3DefaultKmsEncryption
from controlproof.controls.si_7_1 import LogFileValidation
from controlproof.evidence import EvidenceStore
from controlproof.model import ControlResult, Status
from controlproof.providers import ProviderError
from controlproof.providers.aws import OPERATION_ACTIONS, AwsProvider

pytestmark = pytest.mark.usefixtures("moto")


def run(
    control_type: type[Control],
    params: dict[str, Any] | None = None,
    *,
    days_later: int = 0,
    regions: tuple[str, ...] = (REGION,),
) -> ControlResult:
    now = datetime.now(UTC).replace(microsecond=0) + timedelta(days=days_later)
    evidence = EvidenceStore()
    provider = AwsProvider(boto3.Session(), evidence, lambda: now, regions[0], max_attempts=1)
    control = control_type()
    ctx = ControlContext(
        "20260929T120000Z",
        lambda: now,
        "0.0.0",
        control.Params.model_validate(params or {}),
        provider,
        regions,
    )
    result = control.run(ctx)
    assert {OPERATION_ACTIONS[call] for call in provider.calls} <= set(control_type.permissions)
    assert all(ref in evidence for ref in result.evidence_refs)
    assert result.evidence_refs, "a pass or fail always cites evidence"
    return result


def text(result: ControlResult) -> str:
    return " ".join(o.summary for o in result.observations)


def test_every_shipped_control_is_tested_here() -> None:
    tested = {
        AccountManagement,
        MfaForConsoleUsers,
        PasswordPolicy,
        EbsEncryptionByDefault,
        S3DefaultKmsEncryption,
        MultiRegionTrail,
        LogFileValidation,
        AdminPortsClosed,
    }
    assert set(REGISTRY.values()) == tested


def test_declared_permissions_are_real_actions() -> None:
    known = set(OPERATION_ACTIONS.values())
    for control in REGISTRY.values():
        assert set(control.permissions) <= known, control.id


# ac-2 Account Management


def test_ac_2_passes_with_recently_created_credentials() -> None:
    scenario.console_user("alice", mfa=True)
    scenario.api_user("svc")
    assert run(AccountManagement).status is Status.PASS


def test_ac_2_fails_on_an_unused_console_password() -> None:
    scenario.console_user("alice", mfa=True)
    result = run(AccountManagement, days_later=200)
    assert result.status is Status.FAIL
    assert "console password of alice unused" in text(result)


def test_ac_2_fails_on_an_unused_access_key_and_names_only_its_last_four_characters() -> None:
    key = scenario.api_user("svc")
    result = run(AccountManagement, days_later=200)
    assert result.status is Status.FAIL
    assert f"access key ending {key[-4:]}" in text(result)
    assert key not in text(result)


def test_ac_2_ignores_inactive_keys() -> None:
    key = scenario.api_user("svc")
    boto3.client("iam", region_name=REGION).update_access_key(
        UserName="svc", AccessKeyId=key, Status="Inactive"
    )
    assert run(AccountManagement, days_later=200).status is Status.PASS


def test_ac_2_limit_is_a_parameter() -> None:
    scenario.api_user("svc")
    assert run(AccountManagement, {"max_unused_days": 365}, days_later=200).status is Status.PASS


def test_ac_2_with_no_users_passes_and_says_why() -> None:
    result = run(AccountManagement)
    assert result.status is Status.PASS
    assert "No IAM users exist" in text(result)


# ia-2.2 MFA for console users


def test_ia_2_2_passes_when_console_users_have_mfa() -> None:
    scenario.console_user("alice", mfa=True)
    scenario.api_user("svc")
    assert run(MfaForConsoleUsers).status is Status.PASS


def test_ia_2_2_fails_for_a_console_user_without_mfa() -> None:
    scenario.console_user("alice", mfa=True)
    scenario.console_user("bob", mfa=False)
    result = run(MfaForConsoleUsers)
    assert result.status is Status.FAIL
    assert "bob has a console password but no MFA device" in text(result)
    assert "alice has" not in text(result)


# ia-5.1 Password policy


def test_ia_5_1_fails_without_a_password_policy() -> None:
    result = run(PasswordPolicy)
    assert result.status is Status.FAIL
    assert "no account password policy is set" in text(result)


def test_ia_5_1_passes_with_the_aws_config_defaults() -> None:
    scenario.password_policy()
    assert run(PasswordPolicy).status is Status.PASS


def test_ia_5_1_lists_every_shortfall() -> None:
    scenario.password_policy(
        MinimumPasswordLength=8, RequireSymbols=False, PasswordReusePrevention=5
    )
    result = run(PasswordPolicy)
    assert result.status is Status.FAIL
    for expected in (
        "minimum length 8 is below 14",
        "does not require symbols",
        "reuse prevention 5 is below 24",
    ):
        assert expected in text(result)


def test_ia_5_1_thresholds_are_parameters() -> None:
    scenario.password_policy(MinimumPasswordLength=8)
    assert run(PasswordPolicy, {"minimum_length": 8}).status is Status.PASS


# sc-28 EBS encryption by default


def test_sc_28_passes_when_enabled() -> None:
    scenario.ebs_default_encryption()
    assert run(EbsEncryptionByDefault).status is Status.PASS


def test_sc_28_fails_in_any_region_where_it_is_off() -> None:
    scenario.ebs_default_encryption()
    result = run(EbsEncryptionByDefault, regions=(REGION, "eu-west-1"))
    assert result.status is Status.FAIL
    assert "off in eu-west-1" in text(result)
    assert f"off in {REGION}" not in text(result)


# sc-28.1 S3 default KMS encryption


def test_sc_28_1_passes_for_kms_and_dsse_buckets() -> None:
    scenario.bucket("cp-kms-bucket", "aws:kms")
    scenario.bucket("cp-dsse-bucket", "aws:kms:dsse")
    assert run(S3DefaultKmsEncryption).status is Status.PASS


def test_sc_28_1_fails_for_an_sse_s3_bucket() -> None:
    scenario.bucket("cp-kms-bucket", "aws:kms")
    scenario.bucket("cp-sse-s3-bucket", "AES256")
    result = run(S3DefaultKmsEncryption)
    assert result.status is Status.FAIL
    assert "bucket cp-sse-s3-bucket defaults to AES256" in text(result)


def test_sc_28_1_with_no_buckets_passes_and_says_why() -> None:
    assert "No S3 buckets exist" in text(run(S3DefaultKmsEncryption))


def test_sc_28_1_raises_when_moto_reports_no_configuration() -> None:
    # moto still answers ServerSideEncryptionConfigurationNotFoundError for a plain bucket, where
    # real AWS applies SSE-S3 (SPEC_NOTES §5.1, §5.7). Any such error must surface, never pass.
    scenario.bucket("cp-plain-bucket", None)
    with pytest.raises(ProviderError, match="ServerSideEncryptionConfigurationNotFoundError"):
        run(S3DefaultKmsEncryption)


# au-2 multi-Region trail


def select_all_management_events(trail: str) -> None:
    boto3.client("cloudtrail", region_name=REGION).put_event_selectors(
        TrailName=trail,
        EventSelectors=[{"ReadWriteType": "All", "IncludeManagementEvents": True}],
    )


def test_au_2_passes_for_a_logging_multi_region_trail_with_all_management_events() -> None:
    scenario.trail("org-trail", multi_region=True, logging=True, validation=True)
    select_all_management_events("org-trail")
    assert run(MultiRegionTrail).status is Status.PASS


def test_au_2_passes_from_another_region_through_the_shadow_trail() -> None:
    scenario.trail("org-trail", multi_region=True, logging=True, validation=True)
    select_all_management_events("org-trail")
    assert run(MultiRegionTrail, regions=("eu-west-1",)).status is Status.PASS


def test_au_2_fails_when_the_trail_is_not_logging() -> None:
    scenario.trail("org-trail", multi_region=True, logging=False, validation=True)
    select_all_management_events("org-trail")
    assert "is not logging" in text(run(MultiRegionTrail))


def test_au_2_fails_without_explicit_management_event_selection() -> None:
    scenario.trail("org-trail", multi_region=True, logging=True, validation=True)
    assert "does not log all read and write management events" in text(run(MultiRegionTrail))


def test_au_2_fails_for_write_only_management_events() -> None:
    scenario.trail("org-trail", multi_region=True, logging=True, validation=True)
    boto3.client("cloudtrail", region_name=REGION).put_event_selectors(
        TrailName="org-trail",
        EventSelectors=[{"ReadWriteType": "WriteOnly", "IncludeManagementEvents": True}],
    )
    assert run(MultiRegionTrail).status is Status.FAIL


def test_au_2_accepts_advanced_selectors_for_all_management_events() -> None:
    scenario.trail("org-trail", multi_region=True, logging=True, validation=True)
    boto3.client("cloudtrail", region_name=REGION).put_event_selectors(
        TrailName="org-trail",
        AdvancedEventSelectors=[
            {
                "Name": "mgmt",
                "FieldSelectors": [{"Field": "eventCategory", "Equals": ["Management"]}],
            }
        ],
    )
    assert run(MultiRegionTrail).status is Status.PASS


@pytest.mark.parametrize("multi_region", [False, None])
def test_au_2_fails_without_a_multi_region_trail(multi_region: bool | None) -> None:
    if multi_region is not None:
        scenario.trail("local-trail", multi_region=False, logging=True, validation=True)
    result = run(MultiRegionTrail)
    assert result.status is Status.FAIL
    assert "no multi-Region trail exists" in text(result)


# si-7.1 log file validation


def test_si_7_1_passes_when_every_trail_validates() -> None:
    scenario.trail("org-trail", multi_region=True, logging=True, validation=True)
    assert run(LogFileValidation).status is Status.PASS


def test_si_7_1_fails_for_a_trail_without_validation() -> None:
    scenario.trail("org-trail", multi_region=True, logging=True, validation=True)
    scenario.trail("side-trail", multi_region=False, logging=True, validation=False)
    result = run(LogFileValidation)
    assert result.status is Status.FAIL
    assert "trail side-trail does not validate" in text(result)


def test_si_7_1_fails_with_no_trail() -> None:
    assert "no CloudTrail trail exists" in text(run(LogFileValidation))


# sc-7 admin ports


def test_sc_7_passes_for_the_default_security_group() -> None:
    assert run(AdminPortsClosed).status is Status.PASS


@pytest.mark.parametrize(
    ("port", "cidr", "protocol"),
    [(22, "0.0.0.0/0", "tcp"), (3389, "::/0", "tcp"), (-1, "0.0.0.0/0", "-1")],
)
def test_sc_7_fails_for_admin_ports_open_to_the_internet(
    port: int, cidr: str, protocol: str
) -> None:
    group = scenario.open_security_group("open-admin", port=port, cidr=cidr, protocol=protocol)
    result = run(AdminPortsClosed)
    assert result.status is Status.FAIL
    assert f"security group {group}" in text(result)


@pytest.mark.parametrize(("port", "cidr"), [(22, "10.0.0.0/8"), (443, "0.0.0.0/0")])
def test_sc_7_passes_for_private_or_non_admin_rules(port: int, cidr: str) -> None:
    scenario.open_security_group("web", port=port, cidr=cidr)
    assert run(AdminPortsClosed).status is Status.PASS


def test_sc_7_ports_are_a_parameter() -> None:
    scenario.open_security_group("web", port=443)
    assert run(AdminPortsClosed, {"admin_ports": [443]}).status is Status.FAIL
