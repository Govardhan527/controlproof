"""SC-28(1) Cryptographic Protection: every S3 bucket defaults to SSE-KMS or DSSE-KMS.

ADR-0007 row 7. AWS basis: Config rule s3-default-encryption-kms (SPEC_NOTES §5.6). Every bucket
has default encryption since 2023 (SPEC_NOTES §5.1), so the question is which kind. Any error
from GetBucketEncryption makes the control `error`, never `fail` or `pass` (SPEC_NOTES §5.8).
"""

from controlproof.controls import Control, ControlContext
from controlproof.model import ControlResult, Method

KMS_ALGORITHMS = frozenset({"aws:kms", "aws:kms:dsse"})


class S3DefaultKmsEncryption(Control):
    id = "sc-28.1"
    title = "Cryptographic Protection"
    method = Method.INSPECT
    permissions = ("s3:GetEncryptionConfiguration", "s3:ListAllMyBuckets")

    def run(self, ctx: ControlContext) -> ControlResult:
        started = ctx.clock()
        refs: list[str] = []
        buckets = []
        for page in ctx.aws.paginate("s3", "ListBuckets"):
            refs.append(page.ref)
            buckets.extend(page.data.get("Buckets", []))

        failures: list[tuple[str, str]] = []
        for bucket in sorted(buckets, key=lambda b: str(b["Name"])):
            name = str(bucket["Name"])
            response = ctx.aws.call(
                "s3", "GetBucketEncryption", region=bucket.get("BucketRegion"), Bucket=name
            )
            refs.append(response.ref)
            rules = response.data.get("ServerSideEncryptionConfiguration", {}).get("Rules", [])
            algorithms = sorted(
                {
                    str(rule["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"])
                    for rule in rules
                    if "ApplyServerSideEncryptionByDefault" in rule
                }
            )
            if not algorithms or not set(algorithms) <= KMS_ALGORITHMS:
                failures.append(
                    (
                        f"arn:aws:s3:::{name}",
                        f"bucket {name} defaults to {', '.join(algorithms) or 'no algorithm'}",
                    )
                )

        checked = (
            f"Checked the default encryption of {len(buckets)} S3 bucket(s) "
            "for SSE-KMS or DSSE-KMS."
            if buckets
            else "No S3 buckets exist, so no bucket can lack KMS default encryption."
        )
        return self.outcome(
            ctx,
            started,
            checked=checked,
            subjects=[f"arn:aws:s3:::{b['Name']}" for b in buckets],
            failures=failures,
            refs=refs,
        )
