"""IA-5(1) Password-based Authentication: the account password policy meets the profile.

ADR-0007 row 5. AWS basis: Config rule iam-password-policy; the defaults below are that rule's
documented defaults (SPEC_NOTES §5.8). No custom policy (NoSuchEntity) is a failure.
"""

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from controlproof.controls import Control, ControlContext, typed_params
from controlproof.model import ControlResult, Method


class PasswordPolicyParams(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    minimum_length: int = Field(default=14, ge=6, le=128)
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_symbols: bool = True
    require_numbers: bool = True
    reuse_prevention: int = Field(default=24, ge=1, le=24)
    max_age_days: int | None = Field(default=90, ge=1, le=1095)


def shortfalls(policy: dict[str, Any], params: PasswordPolicyParams) -> list[str]:
    found = []
    length = policy.get("MinimumPasswordLength", 0)
    if length < params.minimum_length:
        found.append(f"minimum length {length} is below {params.minimum_length}")
    for wanted, field, label in (
        (params.require_uppercase, "RequireUppercaseCharacters", "uppercase letters"),
        (params.require_lowercase, "RequireLowercaseCharacters", "lowercase letters"),
        (params.require_symbols, "RequireSymbols", "symbols"),
        (params.require_numbers, "RequireNumbers", "numbers"),
    ):
        if wanted and not policy.get(field, False):
            found.append(f"does not require {label}")
    reuse = policy.get("PasswordReusePrevention")
    if reuse is None or reuse < params.reuse_prevention:
        found.append(f"reuse prevention {reuse or 'off'} is below {params.reuse_prevention}")
    if params.max_age_days is not None:
        age = policy.get("MaxPasswordAge") if policy.get("ExpirePasswords") else None
        if age is None or age > params.max_age_days:
            found.append(f"maximum password age {age or 'none'} exceeds {params.max_age_days} days")
    return found


class PasswordPolicy(Control):
    id = "ia-5.1"
    title = "Password-based Authentication"
    method = Method.INSPECT
    permissions = ("iam:GetAccountPasswordPolicy",)
    Params: ClassVar[type[BaseModel]] = PasswordPolicyParams

    def run(self, ctx: ControlContext) -> ControlResult:
        params = typed_params(ctx, PasswordPolicyParams)
        started = ctx.clock()
        response = ctx.aws.call(
            "iam", "GetAccountPasswordPolicy", expected_errors=("NoSuchEntity",)
        )
        if response.error_code is not None:
            failures = [("", "no account password policy is set, so IAM's default policy applies")]
        else:
            failures = [
                ("", f"password policy {text}")
                for text in shortfalls(response.data["PasswordPolicy"], params)
            ]
        return self.outcome(
            ctx,
            started,
            checked="Checked the IAM account password policy against the profile's requirements.",
            subjects=[],
            failures=failures,
            refs=[response.ref],
        )
