"""AC-2 Account Management: no IAM credential sits unused past the profile's limit.

ADR-0007 row 1. AWS basis: Config rule iam-user-unused-credentials-check (SPEC_NOTES §5.6).
A console password counts from its last use, or from its creation if never used; an active access
key likewise (SPEC_NOTES §5.8: a null last-used value means never used since tracking began).
"""

from datetime import timedelta
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from controlproof.canonical import parse_time
from controlproof.controls import Control, ControlContext, typed_params
from controlproof.model import ControlResult, Method


class AccountManagementParams(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    max_unused_days: int = Field(default=90, ge=1)


class AccountManagement(Control):
    id = "ac-2"
    title = "Account Management"
    method = Method.INSPECT
    permissions = (
        "iam:GetAccessKeyLastUsed",
        "iam:GetLoginProfile",
        "iam:ListAccessKeys",
        "iam:ListUsers",
    )
    Params: ClassVar[type[BaseModel]] = AccountManagementParams

    def run(self, ctx: ControlContext) -> ControlResult:
        params = typed_params(ctx, AccountManagementParams)
        started = ctx.clock()
        limit = timedelta(days=params.max_unused_days)
        refs: list[str] = []
        users = []
        for page in ctx.aws.paginate("iam", "ListUsers"):
            refs.append(page.ref)
            users.extend(page.data.get("Users", []))

        failures: list[tuple[str, str]] = []
        for user in sorted(users, key=lambda u: str(u["UserName"])):
            name, arn = str(user["UserName"]), str(user["Arn"])
            login = ctx.aws.call(
                "iam", "GetLoginProfile", UserName=name, expected_errors=("NoSuchEntity",)
            )
            refs.append(login.ref)
            if login.error_code is None:
                last = user.get("PasswordLastUsed") or login.data["LoginProfile"]["CreateDate"]
                if started - parse_time(last) > limit:
                    failures.append((arn, f"console password of {name} unused since {last}"))
            for page in ctx.aws.paginate("iam", "ListAccessKeys", UserName=name):
                refs.append(page.ref)
                for key in page.data.get("AccessKeyMetadata", []):
                    if key["Status"] != "Active":
                        continue
                    used = ctx.aws.call(
                        "iam", "GetAccessKeyLastUsed", AccessKeyId=key["AccessKeyId"]
                    )
                    refs.append(used.ref)
                    last = used.data["AccessKeyLastUsed"].get("LastUsedDate") or key["CreateDate"]
                    if started - parse_time(last) > limit:
                        suffix = str(key["AccessKeyId"])[-4:]
                        failures.append(
                            (
                                arn,
                                f"active access key ending {suffix} of {name} unused since {last}",
                            )
                        )

        checked = (
            f"Checked the console passwords and active access keys of {len(users)} IAM user(s) "
            f"against a {params.max_unused_days}-day unused limit."
            if users
            else "No IAM users exist, so no user credential can be unused."
        )
        return self.outcome(
            ctx,
            started,
            checked=checked,
            subjects=[str(u["Arn"]) for u in users],
            failures=failures,
            refs=refs,
        )
