"""SI-7(1) Integrity Checks: every trail validates its log files, and at least one trail exists.

ADR-0007 row 9. AWS basis: Config rule cloud-trail-log-file-validation-enabled (SPEC_NOTES §5.6).
Trails are listed in every profiled Region (shadow trails included) and de-duplicated by ARN.
With no trail there are no audit logs whose integrity could be checked, so that fails.
"""

from controlproof.controls import Control, ControlContext
from controlproof.model import ControlResult, Method


class LogFileValidation(Control):
    id = "si-7.1"
    title = "Integrity Checks"
    method = Method.INSPECT
    permissions = ("cloudtrail:DescribeTrails",)

    def run(self, ctx: ControlContext) -> ControlResult:
        started = ctx.clock()
        refs: list[str] = []
        trails: dict[str, dict[str, object]] = {}
        for region in ctx.regions:
            described = ctx.aws.call(
                "cloudtrail", "DescribeTrails", region=region, includeShadowTrails=True
            )
            refs.append(described.ref)
            for trail in described.data.get("trailList", []):
                trails.setdefault(str(trail["TrailARN"]), trail)

        failures = [
            (arn, f"trail {trail['Name']} does not validate its log files")
            for arn, trail in sorted(trails.items())
            if trail.get("LogFileValidationEnabled") is not True
        ]
        if not trails:
            failures = [("", f"no CloudTrail trail exists in {', '.join(ctx.regions)}")]
        return self.outcome(
            ctx,
            started,
            checked=(
                f"Checked log file validation on {len(trails)} trail(s) "
                f"in {', '.join(ctx.regions)}."
            ),
            subjects=sorted(trails),
            failures=failures,
            refs=refs,
        )
