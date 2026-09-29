# Decisions

Numbered ADRs: context, options, decision, consequence. Every dependency choice and every
interface change gets one. Status is `Proposed` until the owner approves, then `Accepted`.

## ADR-0001: Licence

- **Date:** 2026-09-29. **Status:** Accepted (the owner committed the licence).
- **Context:** M0 needs a licence.
- **Options:** Apache-2.0, for its express patent grant; MIT, which acvp-assay uses.
- **Decision:** Apache-2.0. The owner committed the Apache License 2.0 text as `LICENSE` in
  `19655b7 Initial commit` (2026-09-29). `pyproject.toml` declares `license = "Apache-2.0"`.
- **Consequence:** Contributions carry an express patent grant. Third-party code added later must
  be Apache-2.0 compatible.

## ADR-0002: Stack

- **Date:** 2026-09-29. **Status:** Accepted (owner approved 2026-09-29, including the (A) items).
- **Context:** The stack was planned up front. The OSCAL version the output must validate
  against is pinned here.
- **Core stack:** Python 3.12 (`.python-version`, `requires-python >=3.12`), uv, typer,
  pydantic v2, boto3, moto, jsonschema, Jinja2, ruff, mypy --strict, pytest, pytest-cov,
  pytest-socket, pip-audit, gitleaks, SHA-256 evidence manifest (sigstore signing is V2).
- **Further choices:**
  1. (A) **OSCAL 1.2.3**, the latest release (published 2026-08-07). Official schema:
     `oscal_assessment-results_schema.json` from the v1.2.3 GitHub release, SHA-256
     `4034e2032332dbf597e59e0646ec16c2c31df992962490371e91f47b219ff42c`. It is vendored in M1.
     Why not 1.2.1: 1.2.2 fixed the JSON PositiveInteger and NonNegativeInteger datatypes.
     Between 1.2.1 and 1.2.3 the assessment-results schema differs only in three added suggested
     `system-component` types (`region`, `zone`, `resource-container`). See SPEC_NOTES §1.
  2. (A) **Build backend `uv_build`** (`>=0.12.9,<0.13`): uv's own backend, no extra tool.
     Alternative: hatchling.
  3. (A) **Dev dependency `types-jsonschema`**: typeshed stubs so `mypy --strict` covers code that
     calls jsonschema. Alternative: `ignore_missing_imports`, which turns those calls into `Any`.
  4. **Add runtime dependencies late:** each is added in the milestone that first imports it
     (typer, pydantic and jsonschema in M1; boto3 and moto in M2; Jinja2 in M4). M0 ships with
     none. `jsonschema` is a dev dependency until then, used by `scripts/validate_outputs.py`.
  5. **CI installs with `uv sync --locked`**, which also fails when `uv.lock` is out of date with
     `pyproject.toml`. That is stricter than `--frozen`.
  6. **gitleaks runs from its release tarball** (v8.30.1, SHA-256 checked against the release's
     `checksums.txt`) instead of `gitleaks-action`. That keeps it independent of licence-key
     rules for organisation accounts and pinned without a third-party action.
     *Amendment (2026-09-29):* `.gitleaksignore` lists three findings by exact fingerprint
     (commit, file, rule, line): synthetic key-shaped strings in the redaction test of commit
     `57e7a7b`, already published. The test now builds such strings at runtime. Every other
     finding still fails CI, and new entries need owner approval.
  7. **pip-audit audits `uv export` output** (hashed requirements, `--disable-pip
     --require-hashes --strict`), so it audits exactly what `uv.lock` pins.
  8. **mypy covers `scripts/` as well as `src/`.**
  9. **The SBOM comes from `uv export --format cyclonedx1.5`** in `make release-dry` (uv 0.12.9
     supports it), so no extra SBOM tool is needed.
  10. **uv is pinned** to `>=0.12.9,<0.13` (`[tool.uv] required-version`, and `version` in CI).
- **Input for ADR-0002a (to be written in M1):** compliance-trestle v5.1.0 (2026-09-02) declares
  `OSCAL_VERSION = '1.2.1'` and `OSCAL_VERSION_REGEX = r'^1\.2\.[0-1]$'`
  (`trestle/oscal/__init__.py` at tag v5.1.0). Correction, 2026-09-29: a probe showed that
  trestle 5.1.0 models still parse a document with `oscal-version` 1.2.3. The constant does not
  block it, so trestle is a live option. See ADR-0002a.
- **Consequence:** The toolchain is reproducible from `uv.lock`, and CI and local runs use the same
  make targets. A change to any (A) item needs owner approval and an ADR update.

## ADR-0002a: OSCAL models

- **Date:** 2026-09-29. **Status:** Accepted (owner chose B on 2026-09-29).
- **Context:** M1 builds OSCAL assessment-results and a minimal assessment-plan (ADR-0005). The
  official 1.2.3 schemas are the contract either way: every emitted file is validated against
  them (SPEC_NOTES §1).
- **Evidence** (probes run 2026-09-29 on the minimal documents and four bad variants):

  | | A. compliance-trestle 5.1.0 | B. datamodel-code-generator 0.83.0 | C. Hand-written subset |
  |---|---|---|---|
  | Built from | OSCAL 1.2.1 models | the pinned 1.2.3 schema | the fields we emit |
  | Parses an `oscal-version` 1.2.3 doc | yes | yes | yes |
  | Rejects bad token, v1 UUID, no-timezone time | yes | yes, once `--type-mappings` maps date-time, email, uri and uri-reference to strings (the default output raised `TypeError` on every document) | only what we encode |
  | Rejects finding state `error` | yes | **no**: the generator drops enums inside `allOf` | yes, if encoded |
  | Runtime footprint | 39 distributions, including `paramiko`, `cryptography`, `bcrypt`, `pynacl`, `openpyxl`, `requests` | pydantic only; about 2,700 generated lines per model, committed | pydantic only; about 150 lines |
  | `mypy --strict` | not checked | passes on the generated file | ours to keep strict |
  | Where it sits relative to the plan | the planned first choice when it covers assessment-results cleanly (it does) | the planned fallback | not in the plan; needs this ADR |

- **Recommendation:** B. It matches the pinned version exactly and adds no runtime dependency.
  A regeneration script with the flags above makes it reproducible. Its looser enums are covered
  by the mandatory official-schema validation. A is stricter but brings a large supply chain,
  including SSH and crypto libraries, into a read-only security tool.
- **Decision:** B. Models are generated from the vendored 1.2.3 assessment-results and
  assessment-plan schemas by a committed script (`datamodel-code-generator` as a dev dependency,
  `--output-model-type pydantic_v2.BaseModel` and the `--type-mappings` above). The generated
  files are committed and every emitted document is still validated against the official schema.
- **Implementation note (2026-09-29):** the generated classes wrap each value in a root model
  and have generated names (for example `Timing2`), so the mapper builds plain JSON and loads it
  through the generated model. That load rejects unknown or misspelt fields. The model's dump is
  what gets written, after the official-schema check. The generated modules are left out of
  coverage (they are fully covered by import) and have their own ruff ignores.

## ADR-0003: Output schema versioning

- **Date:** 2026-09-29. **Status:** Accepted (owner approved 2026-09-29; it defines output file
  formats, a public interface).
- **Context:** Every output format needs a JSON Schema that CI checks. Assessors and CI pipelines
  will parse the outputs, so changes must be visible and deliberate.
- **Options:** (a) one tool version for everything; (b) an independent SemVer `schema_version` per
  output format; (c) date-based schema versions.
- **Decision:** (b).
  - Each output format produced by controlproof (run record, evidence manifest, diff, and so on;
    the exact set is fixed in M1) carries a top-level `schema_version` (SemVer). Its schema is at
    `schemas/<format>.schema.json`, with `$id` ending in `/<format>/<schema_version>`.
  - MAJOR: a field is removed or renamed, or a meaning or allowed value changes. MINOR: an
    optional field is added. PATCH: descriptions or docs only. A MAJOR or MINOR bump is a
    public-interface change and needs an ADR and owner approval.
  - Schemas are generated from the pydantic models and committed. A test fails when the committed
    schema differs from the generated one.
  - Example outputs are at `examples/<format>/*.json`. `scripts/validate_outputs.py` (CI job
    `schemas`) validates each one against `schemas/<format>.schema.json` and, where a standard
    schema exists, against `schemas/official/<format>.schema.json`.
  - OSCAL output is versioned by OSCAL itself: `metadata.oscal-version` is the pinned version
    (ADR-0002), and the official NIST schema is the only schema for it. Changing the pin needs an
    ADR.
  - Schema versions are independent of the package version. The first schemas ship in M1 at
    `1.0.0`.
- **Consequence:** A consumer can tell from `schema_version` whether it can read a file. Drift
  between models and schemas fails CI. Bumps are rare and deliberate.
- **Amendment (2026-09-29, M1):** schemas live in the package, at
  `src/controlproof/schemas/<format>.schema.json` and
  `src/controlproof/schemas/official/<format>.schema.json`, so the installed tool can validate
  its own output. A format needs at least one of the two; the OSCAL formats have only the
  official one. The official files are byte-identical to the NIST release assets, and a test
  pins their SHA-256.

## ADR-0004: Commit rules and how they are enforced

- **Date:** 2026-09-29. **Status:** Accepted (owner approved 2026-09-29).
- **Context:** Commits are authored by the owner alone, and their subjects should show which
  milestone each change serves. The rules must hold locally and in CI.
- **Decision:**
  - Subject: Conventional Commits with a milestone scope, `type(scope): summary`. Types feat, fix,
    test, docs, refactor, perf, build, ci, chore. Scope `M<n>` or `infra`. The summary starts
    with a non-space and is at most 71 characters.
  - Rejected anywhere in the message: any `Co-authored-by:` trailer (the owner is the only
    author), any line that starts with "Generated with" or "Generated by" (tool footers), and the
    robot emoji.
  - The rules live once, in `scripts/commit_rules.py`. The commit-msg hook (activated by `make
    setup`) and the CI job `commit-hygiene` (`scripts/check_commits.py`) both import them, so they
    cannot drift. The message is cut at git's scissors line (`# ---...--- >8 ---...---`), because
    `git commit --verbose` appends the diff below it.
  - `check_commits.py` checks `base..head`. When base is missing or all zeros (a push that
    created a branch), it checks the commits on head that are not on `origin/main`, or every
    commit when `origin/main` does not exist. A base git cannot resolve is exit 2, never a pass.
  - Merge commits get the same subject rule. Prefer squash or rebase merges on GitHub.
- **Consequence:** A local bypass (`--no-verify`) is still caught in CI. GitHub's default merge
  commit message ("Merge pull request #...") would fail `commit-hygiene` on `main`. A commit body
  line that starts with "Generated with" (for example about generated models) must be reworded.

## ADR-0005: How results map into OSCAL assessment-results

- **Date:** 2026-09-29. **Status:** Accepted (owner decided OQ-1 to OQ-4 and OQ-6 on 2026-09-29).
- **Context:** OSCAL 1.2.3 constrains how results can be expressed (SPEC_NOTES §1, §6). This
  defines the OSCAL output, a public interface.
- **Decision:**
  1. **Status mapping (OQ-1).** `pass` becomes finding `status.state: satisfied` with reason
     `pass`. `fail` becomes `not-satisfied` with reason `fail`. `error` and `not_tested` become
     `not-satisfied` with reason `other`, plus a controlproof-namespaced prop carrying the exact
     status. The prop's name and namespace URI are fixed in M1. Basis: SP 800-53A §3.3, where
     "other than satisfied" also covers "unable to obtain sufficient information". A control that
     could not run can therefore never read as satisfied.
  2. **Assessment plan (OQ-2).** Each run also writes a minimal OSCAL assessment-plan (the
     profile's controls and methods), and `import-ap` points to it. The `run` command needs no
     extra input. The generated plan must validate against the official 1.2.3 assessment-plan
     schema.
  3. **Method mapping (OQ-3).** `inspect` is reported as `EXAMINE`, `simulate` as `EXAMINE`,
     and `exercise` as `TEST` (SPEC_NOTES §3).
  4. **Finding target (OQ-4).** `target.type: objective-id`, `target-id: <control>_obj` (for
     example `sc-28_obj`), using part ids from the NIST SP 800-53 Rev 5.2.0 OSCAL catalog.
  5. **SSP link (OQ-6, decided 2026-09-29).** The generated plan's `import-ssp.href` points to a
     resource in the plan's own `back-matter` (`#<resource-uuid>`). That resource states that no
     system security plan was supplied and names the assessed account.
- **Consequence:** An assessor can tell a real failure from a test that did not run by the
  reason and the prop, and neither is counted as satisfied. The assessment-plan schema is
  vendored next to the assessment-results schema (facts in SPEC_NOTES §1).

## ADR-0006: Runtime dependencies `regex` and `PyYAML`

- **Date:** 2026-09-29. **Status:** Accepted (owner approved 2026-09-29).
- **Context:** The planned stack has no YAML parser, but profiles and `controlproof.allowlist.yaml`
  are YAML. Validating against the official OSCAL schema with jsonschema crashes on the schema's
  `\p{L}` pattern (SPEC_NOTES §1).
- **Options:** PyYAML or ruamel.yaml for YAML. For patterns: `regex`, rewriting the official
  patterns (rejected: the output would no longer be checked against the official schema), or
  another validator.
- **Decision:** add `regex` (a jsonschema `pattern` keyword backed by `regex.search`) and PyYAML
  (`yaml.safe_load` only, never `yaml.load`) as runtime dependencies from M1.
- **Consequence:** Two more packages in the SBOM and in the pip-audit scope. The OSCAL schemas
  stay byte-for-byte official.

## ADR-0007: The 25 controls

- **Date:** 2026-09-29. **Status:** Accepted (owner approved 2026-09-29).
- **Context:** The MVP runs 25 controls from SP 800-53 Rev 5. `diff.py` keys results by control
  id, so each id appears once. Ids are the lowercase OSCAL form (`ia-2.1` is IA-2(1)). All 25
  exist and none is withdrawn in the Rev 5.2.0 catalog (SPEC_NOTES §2).
- **Mapping basis:** "pack" means AWS's "Operational Best Practices for NIST 800-53 rev 5"
  conformance pack maps that AWS Config rule to that control (SPEC_NOTES §5.6). "Statement" means
  no AWS rule exists for it, so the check follows the control's own statement text. That is the
  tool's interpretation.
- **Proposal:** 15 `inspect` (the first 10 in M2, the other 5 in M3), 5 `simulate` and 5
  `exercise` (M3).

  | # | Control | Method | Passes when | AWS calls | Basis | moto |
  |---|---|---|---|---|---|---|
  | 1 | ac-2 Account Management | inspect | no IAM user's console password or active access key has gone unused longer than `max_unused_days` (default 90) | iam ListUsers, ListAccessKeys, GetAccessKeyLastUsed | pack: iam-user-unused-credentials-check | yes |
  | 2 | ac-6.2 Non-privileged Access for Nonsecurity Functions | inspect | the root user has no access keys | iam GetAccountSummary | pack: iam-root-access-key-check | yes |
  | 3 | ia-2.1 MFA to Privileged Accounts | inspect | the root user has MFA | iam GetAccountSummary | pack: root-account-mfa-enabled | yes |
  | 4 | ia-2.2 MFA to Non-privileged Accounts | inspect | every IAM user with a console password has an MFA device | iam ListUsers, GetLoginProfile, ListMFADevices | pack: mfa-enabled-for-iam-console-access | yes |
  | 5 | ia-5.1 Password-based Authentication | inspect | the account password policy meets the profile's parameters | iam GetAccountPasswordPolicy | pack: iam-password-policy | yes |
  | 6 | sc-28 Protection of Information at Rest | inspect | EBS encryption by default is on in every profiled Region | ec2 GetEbsEncryptionByDefault | pack: ec2-ebs-encryption-by-default | yes |
  | 7 | sc-28.1 Cryptographic Protection | inspect | every bucket's default encryption is SSE-KMS or DSSE-KMS | s3 ListBuckets, GetBucketEncryption | pack: s3-default-encryption-kms | yes |
  | 8 | au-2 Event Logging | inspect | at least one multi-Region trail is logging read and write management events | cloudtrail DescribeTrails, GetTrailStatus, GetEventSelectors | pack: multi-region-cloudtrail-enabled | yes |
  | 9 | si-7.1 Integrity Checks | inspect | every trail has log file validation on | cloudtrail DescribeTrails | pack: cloud-trail-log-file-validation-enabled | yes |
  | 10 | sc-7 Boundary Protection | inspect | no security group allows 0.0.0.0/0 or ::/0 ingress on the profile's admin ports (default 22, 3389) | ec2 DescribeSecurityGroups | pack: restricted-ssh, restricted-common-ports | yes |
  | 11 | ac-21 Information Sharing | inspect | all four account-level S3 Block Public Access settings are on | s3control GetPublicAccessBlock | pack: s3-account-level-public-access-blocks-periodic | yes |
  | 12 | sc-12 Cryptographic Key Establishment and Management | inspect | every enabled symmetric customer managed KMS key rotates automatically | kms ListKeys, DescribeKey, GetKeyRotationStatus | pack: cmk-backing-key-rotation-enabled | yes |
  | 13 | sc-8 Transmission Confidentiality and Integrity | inspect | every bucket policy denies requests where `aws:SecureTransport` is false | s3 ListBuckets, GetBucketPolicy | pack: s3-bucket-ssl-requests-only | yes |
  | 14 | ac-17.2 Protection of Confidentiality and Integrity Using Encryption | inspect | every load balancer listener is HTTPS or TLS, or HTTP that only redirects to HTTPS | elbv2 DescribeLoadBalancers, DescribeListeners | pack: elb-tls-https-listeners-only, alb-http-to-https-redirection-check | yes |
  | 15 | si-4 System Monitoring | inspect | a GuardDuty detector is enabled in every profiled Region | guardduty ListDetectors, GetDetector | pack: guardduty-enabled-centralized | yes |
  | 16 | ac-6 Least Privilege | simulate | profile-listed workload principals are denied privilege-escalation actions (for example iam:CreateUser, iam:CreateAccessKey, iam:AttachRolePolicy, iam:PutRolePolicy) | iam SimulatePrincipalPolicy | statement | no: Stubber |
  | 17 | ac-5 Separation of Duties | simulate | principals allowed to use a key (kms:Decrypt) are denied administering it (kms:ScheduleKeyDeletion, kms:PutKeyPolicy, kms:DisableKey) | iam SimulatePrincipalPolicy | statement (pack maps KMS-action rules to AC-5) | no: Stubber |
  | 18 | ac-6.1 Authorize Access to Security Functions | simulate | only profile-listed security principals may disable security services (guardduty:DeleteDetector, config:StopConfigurationRecorder); the other listed principals are denied | iam SimulatePrincipalPolicy | statement | no: Stubber |
  | 19 | au-9.4 Access by Subset of Privileged Users | simulate | only profile-listed audit admins may call cloudtrail:StopLogging, DeleteTrail, UpdateTrail, PutEventSelectors | iam SimulatePrincipalPolicy | statement | no: Stubber |
  | 20 | cm-5 Access Restrictions for Change | simulate | non-designated principals are denied ec2:AuthorizeSecurityGroupIngress, s3:PutBucketPolicy, s3:PutBucketPublicAccessBlock | iam SimulatePrincipalPolicy | statement | no: Stubber |
  | 21 | ac-3 Access Enforcement | exercise | attaching a public-read policy to a tool-created bucket is refused (account-level Block Public Access at work) | s3 CreateBucket, PutBucketTagging, PutBucketPolicy, DeleteBucket | pack: s3-account-level-public-access-blocks-periodic | enforcement UNVERIFIED |
  | 22 | sc-13 Cryptographic Protection | exercise | writing an SSE-S3 (not KMS) object to a tool-created bucket is refused by an organisation guardrail | s3 CreateBucket, PutObject, DeleteObject, DeleteBucket | pack: s3-default-encryption-kms | no SCP evaluation |
  | 23 | au-9 Protection of Audit Information | exercise | StopLogging on a tool-created trail is refused by a guardrail that protects all trails | cloudtrail CreateTrail, StopLogging, DeleteTrail (plus a tool-created delivery bucket) | pack: cloudtrail-enabled | yes, no SCP evaluation |
  | 24 | au-12 Audit Record Generation | exercise | the tool's own CreateBucket call appears in CloudTrail within `max_wait_minutes` | cloudtrail LookupEvents | pack: cloudtrail-enabled | no: Stubber |
  | 25 | sc-8.1 Cryptographic Protection | exercise | a tool-created HTTPS listener ends up with, or is only allowed, a policy without TLS 1.0 or 1.1 | elbv2, acm, ec2 create and delete | pack: elb-tls-https-listeners-only | yes |

- **Left out of the originally listed examples:** `cm-6`, because AWS's mapping lists no rule for it (a
  specific check can be assigned later), and `si-2`, which needs SSM patch compliance that moto
  does not implement. IA-2, IA-5 and SC-8 are covered through `ia-2.1`, `ia-2.2`, `ia-5.1`, `sc-8`
  and `sc-8.1`.
- **Exercise safety:** every exercise creates only its own resources, tags them
  `controlproof:run=<run-id>`, deletes them in `finally`, and never targets a pre-existing
  resource. No exercise creates a KMS key, because a key cannot be deleted immediately (the
  shortest deletion window is 7 days).
- **Verification owed before each control is built** (SPEC_NOTES items, blocking M2 or M3): each
  AWS response shape; whether moto enforces Block Public Access on PutBucketPolicy; the TLS
  policy condition key an organisation guardrail would use (row 25); CloudTrail delivery delay
  (row 24); how row 25 gets a certificate without a new dependency.
- **Consequence:** M2 builds rows 1 to 10. M3 builds rows 11 to 25 and adds a recorded-response
  test double for the rows moto cannot fake (SPEC_NOTES §5.7). Swapping a row later needs an ADR update.

## ADR-0008: M1 data contracts and output layout

- **Date:** 2026-09-29. **Status:** Accepted (owner approved 2026-09-29; public interfaces:
  profile format and output files).
- **Profile** (YAML, loaded with `yaml.safe_load`, `schema_version` 1.0.0):

  ```yaml
  schema_version: "1.0.0"
  id: aws-baseline
  title: AWS baseline
  provider: aws
  controls:
    - id: sc-28.1
      params: {}
  ```

  Unknown keys, duplicate control ids and unknown control ids are load errors, never skipped.
  Each control validates its own `params` with its own pydantic model.
- **Data model** (pydantic v2, frozen): `Status` (pass, fail, error, not_tested), `Method`
  (inspect, simulate, exercise), and `ControlResult` with exactly the planned fields
  (control_id, method, status, observations, evidence_refs, started_at, ended_at,
  tool_version). `Observation` has summary, subjects and evidence_refs. `RunRecord` has
  schema_version, run_id, profile id, started_at, ended_at, tool_version and results.
- **Run output**, one directory per run:
  `run.json` (RunRecord), `assessment-results.json` and `assessment-plan.json` (OSCAL 1.2.3),
  `manifest.json` (SHA-256 of every file in the run), and `evidence/` from M2 on.
- **Determinism:** the clock is injected. `run_id` is the UTC start time
  (`YYYYMMDDTHHMMSSZ`). Every OSCAL UUID is a version-5 UUID built from a fixed project
  namespace UUID and `<run_id>/<kind>/<key>`. JSON keys and lists are sorted. The same inputs
  give byte-identical files.
- **OSCAL details for ADR-0005:** the exact-status prop is `name: controlproof-status`,
  `ns: https://github.com/Govardhan527/controlproof/ns/oscal`, value `error` or `not_tested`.
  Observed resources become `local-definitions.inventory-items` and are referenced from
  `observations[].subjects`. The account is named in the plan's back-matter resource
  (ADR-0005 item 5).
- **Self-check:** `controlproof` validates each OSCAL file against the vendored official schema
  before writing it, and refuses to write a file that fails.
- **Not in M1:** the CLI (typer arrives with `run` in M2), the evidence bundle and redaction (M2),
  the HTML report and diff (M4).
- **Dev dependencies this needs:** `datamodel-code-generator` (ADR-0002a) and the typeshed stubs
  `types-PyYAML` and `types-regex`, for `mypy --strict`.

## ADR-0009: M2 design (runner, AWS provider, first 10 controls)

- **Date:** 2026-09-29. **Status:** Accepted (owner approved 2026-09-29, including the stricter
  done rule in §1). The unit tier is built first; the owner has no AWS account yet, so the real
  tier waits for one.
- **Scope:** ADR-0007 rows 1 to 10, all `inspect`: ac-2, ac-6.2, ia-2.1, ia-2.2, ia-5.1, sc-28,
  sc-28.1, au-2, si-7.1, sc-7. Done-criteria: each control has pass and fail fixtures; permissions
  documented. Nothing in M2 creates, changes or deletes an AWS resource.

### 1. Real data, real environment
- The shipped tool only ever calls real AWS APIs through boto3, with the caller's own
  credentials. Nothing in the package fakes or stubs a response. The M1 stub controls live in
  `tests/`, are never packaged, and stop being the source of the golden files in M2.
- Tests run in two tiers:
  - **Unit tier** (every push, no credentials, no cost): moto, the fake AWS that the plan
    requires for unit tests and for the CI run of the success test. It proves the control logic
    against known pass and fail states. It is not proof that real AWS behaves the same, because
    moto is a re-implementation.
  - **Real tier** (`integration`, on `main` and manual dispatch): the same controls against a
    dedicated AWS sandbox account. This tier proves real behaviour.
- **Proposed strengthening:** a control counts as done only after it has passed both tiers,
  meaning it returns a pass or fail with evidence, never an error, against the real sandbox. The
  original M2 done-criteria ask only for the moto fixtures.
- The owner provides the real tier: a dedicated sandbox account (never production), local
  credentials through the normal AWS profile or SSO, and for CI a GitHub OIDC role in the sandbox
  that trusts only this repository's `main` branch and carries `docs/iam-readonly.json`. No
  long-lived keys are stored anywhere. The account id lives in a repository variable, not in git.
- The sandbox's expected result per control is kept in `tests/integration/sandbox-expected.yaml`
  (control id to status only, no account data). The real tier checks results against it.

### 2. New dependencies
- Runtime: `boto3` (1.43.104, Apache-2.0) and `typer` (0.27.2, MIT, the planned CLI library).
- Dev: `moto` (5.2.3, Apache-2.0) and `types-boto3` (1.43.104, MIT, typed clients for
  `mypy --strict`).

### 3. CLI (public interface)
```
controlproof run --profile NAME|PATH --account ACCOUNT_ID [--region REGION]... [--out DIR] [--json]
controlproof permissions [--profile NAME|PATH] [--json]
controlproof --version
```
- `--profile` takes a built-in profile name (`aws-baseline`, shipped as package data, rows 1 to 10
  in M2 and all 25 by M3) or a path.
- `--account` must equal the account of the credentials (`sts:GetCallerIdentity`). Otherwise the
  run stops before any control runs.
- `--out` defaults to `./controlproof-runs`. `--json` prints a summary (run id, run directory,
  count per status, status per control) instead of text.
- Exit codes: 0 every control passed; 1 at least one fail and no error; 2 at least one error or
  not tested; 3 the run could not start (bad profile, account mismatch, no credentials).
- `--allow-exercise` is added in M3, not before.

### 4. Profile and run record changes (schema 1.1.0, MINOR under ADR-0003)
- Profile gains an optional `regions` list. `--region` overrides it. With neither, the run uses the
  SDK's configured default region.
- The run record gains `account` and `regions`, so each run states exactly where it looked.

### 5. AWS provider (`providers/aws.py`, the only module that imports boto3)
- The session comes from the standard credential chain. No key ever passes through a CLI flag.
- Retries use botocore's standard mode. A throttle that outlasts the retries, an AccessDenied or
  any other AWS error becomes a typed `ProviderError` naming the call and the error code.
- Every response is recorded as evidence before a control sees it. Paginated calls read every
  page.

### 6. Evidence and redaction (public interface: evidence file format)
- Each API response becomes `evidence/<sha256>.json`: service, operation, region, redacted request
  parameters, redacted response, collected time. The hash covers the redacted bytes. The manifest
  lists every evidence file, and OSCAL `relevant-evidence` gains `href: evidence/<sha256>.json`.
  The format `evidence-record` (1.0.0) gets its own JSON Schema.
- Redaction runs before hashing:
  - values of exact secret field names (`SecretAccessKey`, `SessionToken`, `Password`,
    `PrivateKey`, `CertificateBody`, `CertificateChain`) become `[REDACTED]`;
  - access key ids (`AKIA...`, `ASIA...`) keep only their last 4 characters (`[KEY:...ABCD]`), so
    two keys can still be told apart;
  - 12-digit account ids, standalone or inside ARNs, become `[ACCOUNT]`. The account is named once,
    in the run record and the plan.
  - Field names such as `PasswordLastUsed` or `MinimumPasswordLength` are kept, because the
    controls need them. Matching is by exact name and value pattern, never by substring.
- A test feeds synthetic responses containing each secret type through the pipeline and asserts
  that none survives.

### 7. Runner (`runner.py`)
- Load the profile, validate each control's params, check the account, run the controls in id
  order with the injected clock, then write the run (M1 writer).
- Any `ProviderError`, and any other exception from a control, becomes `error`, never `pass`. The
  runner is the only place allowed to catch a broad exception, and it records the exception type.
- If one Region fails, the whole control is `error`. Partial data never produces a pass.
- **No resources to check:** a control is `pass` only with an observation saying what was checked
  and that nothing was found (for example "no S3 buckets in us-east-1"). The empty response is the
  evidence. A control whose rule needs something to exist (au-2: at least one trail) fails when
  it is absent.

### 8. Permissions
- `docs/iam-readonly.json` is generated from the permissions each control declares, plus
  `sts:GetCallerIdentity`, with a drift test.
- A unit test records every AWS call each control makes under moto and fails if any call's IAM
  action is not in that control's declared permissions.

### 9. Verification owed before each control is written (SPEC_NOTES)
- The response shape and error codes of every call used, including the "not set" cases:
  GetAccountPasswordPolicy and GetLoginProfile return NoSuchEntity; GetBucketEncryption on a
  bucket with only the base SSE-S3 behaviour.
- The IAM action name for every call (AWS Service Authorization Reference).
- Whether moto can seed its random resource ids, which golden files from moto runs need.
  Otherwise the golden test normalises generated ids.

### 10. Implementation notes (2026-09-29, unit tier built)
- **Golden run by record and replay.** moto invents ids and uses the wall clock, so a golden run
  from live moto changes every time. `tests/fixtures/recordings/aws-baseline.json` holds the
  redacted request and response of every call the shipped controls make against a fixed moto
  scenario. The golden test replays it through the same control code into
  `examples/runs/aws-baseline/`, and another test checks that a live moto run still gives the same
  statuses. A recording from the real sandbox can replace the moto one without code changes. The M1
  stub golden files are retired; the stubs stay as tests of the `error` and `not_tested` mappings.
- **Controls receive plain JSON** (timestamps as ISO strings), both live and replayed.
- **Every OSCAL observation links its evidence file** (`relevant-evidence.href`), the manifest
  hashes every file including evidence, and a run citing evidence it did not store is not
  written.
- **Evidence error messages are redacted too.** AWS error text can include account ids.
- **Tests cannot reach a real account:** an autouse fixture sets fake credentials, points the AWS
  config and credential files at an empty path, and disables instance metadata.
- **Formats:** `run-record` and `profile` are at 1.1.0 (ADR-0003 MINOR), and `evidence-record`
  1.0.0 is new. A 1.0.0 profile still loads.
- **8 of the 10 M2 controls are built.** ac-6.2 and ia-2.1 wait on OQ-7 (SPEC_NOTES §6).
