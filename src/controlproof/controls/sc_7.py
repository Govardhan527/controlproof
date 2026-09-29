"""SC-7 Boundary Protection: no security group opens an admin port to the whole internet.

ADR-0007 row 10. AWS basis: Config rules restricted-ssh and restricted-common-ports (SPEC_NOTES
§5.6). A rule matches when its source is 0.0.0.0/0 or ::/0 and it covers an admin port: protocol
"-1" covers every port; tcp or udp cover FromPort..ToPort.
"""

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from controlproof.controls import Control, ControlContext, typed_params
from controlproof.model import ControlResult, Method

WORLD = {"CidrIp": "0.0.0.0/0", "CidrIpv6": "::/0"}
PORTED_PROTOCOLS = frozenset({"tcp", "udp", "6", "17"})


class AdminPortsParams(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    admin_ports: tuple[int, ...] = Field(default=(22, 3389), min_length=1)


def open_ports(permission: dict[str, Any], ports: tuple[int, ...]) -> list[int]:
    sources = [r.get("CidrIp") for r in permission.get("IpRanges", [])] + [
        r.get("CidrIpv6") for r in permission.get("Ipv6Ranges", [])
    ]
    if not any(source in WORLD.values() for source in sources):
        return []
    protocol = str(permission.get("IpProtocol"))
    if protocol == "-1":
        return list(ports)
    if protocol in PORTED_PROTOCOLS:
        low, high = int(permission.get("FromPort", -1)), int(permission.get("ToPort", -1))
        return [port for port in ports if low <= port <= high]
    return []


class AdminPortsClosed(Control):
    id = "sc-7"
    title = "Boundary Protection"
    method = Method.INSPECT
    permissions = ("ec2:DescribeSecurityGroups",)
    Params: ClassVar[type[BaseModel]] = AdminPortsParams

    def run(self, ctx: ControlContext) -> ControlResult:
        params = typed_params(ctx, AdminPortsParams)
        started = ctx.clock()
        refs: list[str] = []
        checked_groups: list[str] = []
        failures: list[tuple[str, str]] = []
        for region in ctx.regions:
            for page in ctx.aws.paginate("ec2", "DescribeSecurityGroups", region=region):
                refs.append(page.ref)
                for group in page.data.get("SecurityGroups", []):
                    subject = f"{region}/{group['GroupId']}"
                    checked_groups.append(subject)
                    exposed = sorted(
                        {
                            p
                            for rule in group.get("IpPermissions", [])
                            for p in open_ports(rule, params.admin_ports)
                        }
                    )
                    if exposed:
                        ports = ", ".join(map(str, exposed))
                        failures.append(
                            (
                                subject,
                                f"security group {group['GroupId']} "
                                f"({group.get('GroupName', '')}) in {region} "
                                f"opens port(s) {ports} to the internet",
                            )
                        )

        wanted = ", ".join(map(str, params.admin_ports))
        return self.outcome(
            ctx,
            started,
            checked=(
                f"Checked {len(checked_groups)} security group(s) in {', '.join(ctx.regions)} "
                f"for internet access to port(s) {wanted}."
            ),
            subjects=checked_groups,
            failures=sorted(failures),
            refs=refs,
        )
