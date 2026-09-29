"""IA-2(2) MFA to Non-privileged Accounts: every IAM user with a console password has MFA.

ADR-0007 row 4. AWS basis: Config rule mfa-enabled-for-iam-console-access (SPEC_NOTES §5.6).
A user has a console password exactly when GetLoginProfile succeeds (SPEC_NOTES §5.8).
"""

from controlproof.controls import Control, ControlContext
from controlproof.model import ControlResult, Method


class MfaForConsoleUsers(Control):
    id = "ia-2.2"
    title = "Multi-factor Authentication to Non-privileged Accounts"
    method = Method.INSPECT
    permissions = ("iam:GetLoginProfile", "iam:ListMFADevices", "iam:ListUsers")

    def run(self, ctx: ControlContext) -> ControlResult:
        started = ctx.clock()
        refs: list[str] = []
        users = []
        for page in ctx.aws.paginate("iam", "ListUsers"):
            refs.append(page.ref)
            users.extend(page.data.get("Users", []))

        console_users: list[str] = []
        failures: list[tuple[str, str]] = []
        for user in sorted(users, key=lambda u: str(u["UserName"])):
            name, arn = str(user["UserName"]), str(user["Arn"])
            login = ctx.aws.call(
                "iam", "GetLoginProfile", UserName=name, expected_errors=("NoSuchEntity",)
            )
            refs.append(login.ref)
            if login.error_code is not None:
                continue
            console_users.append(arn)
            devices = []
            for page in ctx.aws.paginate("iam", "ListMFADevices", UserName=name):
                refs.append(page.ref)
                devices.extend(page.data.get("MFADevices", []))
            if not devices:
                failures.append((arn, f"{name} has a console password but no MFA device"))

        checked = (
            f"Checked MFA devices for the {len(console_users)} of {len(users)} IAM user(s) "
            "that have a console password."
            if console_users
            else f"None of the {len(users)} IAM user(s) has a console password."
        )
        return self.outcome(
            ctx, started, checked=checked, subjects=console_users, failures=failures, refs=refs
        )
