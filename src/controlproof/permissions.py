"""The read-only IAM policy controlproof needs (ADR-0009 §8).

Built from the permissions each control declares plus the account check. `docs/iam-readonly.json`
is this policy for every shipped control; a test keeps them in step.
"""

from collections.abc import Iterable
from typing import Any

from controlproof.controls import Control

# Current IAM policy language version (SPEC_NOTES §5.8).
POLICY_LANGUAGE_VERSION = "2012-10-17"
ACCOUNT_CHECK = ("sts:GetCallerIdentity",)


def readonly_policy(controls: Iterable[type[Control]]) -> dict[str, Any]:
    actions = sorted({*ACCOUNT_CHECK, *(a for c in controls for a in c.permissions)})
    return {
        "Version": POLICY_LANGUAGE_VERSION,
        "Statement": [
            {
                "Sid": "ControlproofReadOnly",
                "Effect": "Allow",
                "Action": actions,
                "Resource": "*",
            }
        ],
    }
