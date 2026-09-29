"""SC-28 Protection of Information at Rest: EBS encryption by default is on in every Region.

ADR-0007 row 6. AWS basis: Config rule ec2-ebs-encryption-by-default (SPEC_NOTES §5.6).
"""

from controlproof.controls import Control, ControlContext
from controlproof.model import ControlResult, Method


class EbsEncryptionByDefault(Control):
    id = "sc-28"
    title = "Protection of Information at Rest"
    method = Method.INSPECT
    permissions = ("ec2:GetEbsEncryptionByDefault",)

    def run(self, ctx: ControlContext) -> ControlResult:
        started = ctx.clock()
        refs: list[str] = []
        failures: list[tuple[str, str]] = []
        for region in ctx.regions:
            response = ctx.aws.call("ec2", "GetEbsEncryptionByDefault", region=region)
            refs.append(response.ref)
            if response.data.get("EbsEncryptionByDefault") is not True:
                failures.append((region, f"EBS encryption by default is off in {region}"))
        return self.outcome(
            ctx,
            started,
            checked=f"Checked EBS encryption by default in {', '.join(ctx.regions)}.",
            subjects=list(ctx.regions),
            failures=failures,
            refs=refs,
        )
