"""AU-2 Event Logging: a multi-Region trail is logging read and write management events.

ADR-0007 row 8. AWS basis: Config rule multi-region-cloudtrail-enabled (SPEC_NOTES §5.6).
DescribeTrails in one Region also returns multi-Region trails homed elsewhere (shadow trails);
their status and selectors are read in the home Region, by ARN (SPEC_NOTES §5.5, §5.8).
A selector counts only if it explicitly includes all management events, read and write.
"""

from typing import Any

from controlproof.controls import Control, ControlContext
from controlproof.model import ControlResult, Method


def logs_all_management_events(selectors: dict[str, Any]) -> bool:
    for selector in selectors.get("EventSelectors", []):
        if (
            selector.get("IncludeManagementEvents") is True
            and selector.get("ReadWriteType") == "All"
        ):
            return True
    for selector in selectors.get("AdvancedEventSelectors", []):
        fields = {f["Field"]: f for f in selector.get("FieldSelectors", [])}
        category = fields.get("eventCategory", {})
        if category.get("Equals") == ["Management"] and "readOnly" not in fields:
            return True
    return False


class MultiRegionTrail(Control):
    id = "au-2"
    title = "Event Logging"
    method = Method.INSPECT
    permissions = (
        "cloudtrail:DescribeTrails",
        "cloudtrail:GetEventSelectors",
        "cloudtrail:GetTrailStatus",
    )

    def run(self, ctx: ControlContext) -> ControlResult:
        started = ctx.clock()
        described = ctx.aws.call(
            "cloudtrail", "DescribeTrails", region=ctx.regions[0], includeShadowTrails=True
        )
        refs = [described.ref]
        trails = sorted(
            (t for t in described.data.get("trailList", []) if t.get("IsMultiRegionTrail")),
            key=lambda t: str(t["TrailARN"]),
        )
        problems: list[tuple[str, str]] = []
        good = []
        for trail in trails:
            arn, home = str(trail["TrailARN"]), str(trail["HomeRegion"])
            status = ctx.aws.call("cloudtrail", "GetTrailStatus", region=home, Name=arn)
            selectors = ctx.aws.call("cloudtrail", "GetEventSelectors", region=home, TrailName=arn)
            refs += [status.ref, selectors.ref]
            if status.data.get("IsLogging") is not True:
                problems.append((arn, f"multi-Region trail {trail['Name']} is not logging"))
            elif not logs_all_management_events(selectors.data):
                problems.append(
                    (
                        arn,
                        f"multi-Region trail {trail['Name']} does not log all read and "
                        "write management events",
                    )
                )
            else:
                good.append(arn)

        failures = [] if good else (problems or [("", "no multi-Region trail exists")])
        return self.outcome(
            ctx,
            started,
            checked=(
                f"Checked {len(trails)} multi-Region trail(s) visible from {ctx.regions[0]} "
                "for logging of all management events."
            ),
            subjects=[str(t["TrailARN"]) for t in trails],
            failures=failures,
            refs=refs,
        )
