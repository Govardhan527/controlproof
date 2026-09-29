"""docs/iam-readonly.json is the read-only policy for every shipped control (ADR-0009 §8).

Regenerate after adding a control with: CONTROLPROOF_UPDATE_GOLDEN=1 make test
"""

import os
from pathlib import Path

from controlproof.canonical import to_json
from controlproof.controls.registry import REGISTRY
from controlproof.permissions import readonly_policy

POLICY = Path(__file__).resolve().parents[1] / "docs" / "iam-readonly.json"


def test_documented_policy_matches_the_controls() -> None:
    expected = to_json(readonly_policy(REGISTRY.values()))
    if os.environ.get("CONTROLPROOF_UPDATE_GOLDEN") == "1":
        POLICY.write_bytes(expected)
    assert POLICY.read_bytes() == expected


def test_policy_covers_every_declared_permission_and_nothing_else() -> None:
    actions = set(readonly_policy(REGISTRY.values())["Statement"][0]["Action"])
    declared = {a for control in REGISTRY.values() for a in control.permissions}
    assert actions == declared | {"sts:GetCallerIdentity"}
