"""Known AWS states built in moto, for the controls' pass and fail fixtures."""

import json

import boto3

from conftest import REGION


def console_user(name: str, *, mfa: bool) -> None:
    client = boto3.client("iam", region_name=REGION)
    client.create_user(UserName=name)
    client.create_login_profile(UserName=name, Password="Synthetic-Passw0rd!")  # noqa: S106
    if mfa:
        serial = client.create_virtual_mfa_device(VirtualMFADeviceName=f"{name}-mfa")[
            "VirtualMFADevice"
        ]["SerialNumber"]
        client.enable_mfa_device(
            UserName=name,
            SerialNumber=serial,
            AuthenticationCode1="123456",
            AuthenticationCode2="654321",
        )


def api_user(name: str) -> str:
    client = boto3.client("iam", region_name=REGION)
    client.create_user(UserName=name)
    return str(client.create_access_key(UserName=name)["AccessKey"]["AccessKeyId"])


def password_policy(**overrides: object) -> None:
    settings: dict[str, object] = {
        "MinimumPasswordLength": 14,
        "RequireSymbols": True,
        "RequireNumbers": True,
        "RequireUppercaseCharacters": True,
        "RequireLowercaseCharacters": True,
        "MaxPasswordAge": 90,
        "PasswordReusePrevention": 24,
    }
    settings.update(overrides)
    boto3.client("iam", region_name=REGION).update_account_password_policy(**settings)


def ebs_default_encryption() -> None:
    boto3.client("ec2", region_name=REGION).enable_ebs_encryption_by_default()


def bucket(name: str, algorithm: str | None) -> None:
    client = boto3.client("s3", region_name=REGION)
    client.create_bucket(Bucket=name)
    if algorithm:
        default: dict[str, str] = {"SSEAlgorithm": algorithm}
        if algorithm.startswith("aws:kms"):
            default["KMSMasterKeyID"] = "alias/aws/s3"
        client.put_bucket_encryption(
            Bucket=name,
            ServerSideEncryptionConfiguration={
                "Rules": [{"ApplyServerSideEncryptionByDefault": default}]
            },
        )


def trail(name: str, *, multi_region: bool, logging: bool, validation: bool) -> None:
    bucket(f"{name}-logs", "AES256")
    boto3.client("s3", region_name=REGION).put_bucket_policy(
        Bucket=f"{name}-logs",
        Policy=json.dumps({"Version": "2012-10-17", "Statement": []}),
    )
    client = boto3.client("cloudtrail", region_name=REGION)
    client.create_trail(
        Name=name,
        S3BucketName=f"{name}-logs",
        IsMultiRegionTrail=multi_region,
        EnableLogFileValidation=validation,
    )
    if logging:
        client.start_logging(Name=name)


def open_security_group(
    name: str, *, port: int, cidr: str = "0.0.0.0/0", protocol: str = "tcp"
) -> str:
    ec2 = boto3.client("ec2", region_name=REGION)
    vpc = ec2.describe_vpcs()["Vpcs"][0]["VpcId"]
    group = ec2.create_security_group(GroupName=name, Description="synthetic", VpcId=vpc)["GroupId"]
    ip_range = (
        {"Ipv6Ranges": [{"CidrIpv6": cidr}]} if ":" in cidr else {"IpRanges": [{"CidrIp": cidr}]}
    )
    ec2.authorize_security_group_ingress(
        GroupId=group,
        IpPermissions=[{"IpProtocol": protocol, "FromPort": port, "ToPort": port, **ip_range}],
    )
    return str(group)
