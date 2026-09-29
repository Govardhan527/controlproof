# Spec notes

Every standards-derived fact the code relies on, with the primary source, section and retrieval
date. Tags:
- **VERIFIED**: read in the primary source on the retrieval date.
- **UNVERIFIED**: not yet read in a primary source. It blocks the milestone named next to it.
- **OPEN**: the source is clear, but applying it needs an owner decision (see §6).

All retrievals are dated 2026-09-29 unless noted otherwise.

## 1. NIST OSCAL: assessment-results model and JSON Schema

- **Pinned version:** OSCAL **1.2.3** (ADR-0002). VERIFIED.
  - Source: https://github.com/usnistgov/OSCAL/releases/tag/v1.2.3 (published 2026-08-07, patch
    release). Earlier releases: v1.2.2 2026-04-30, v1.2.1 2026-03-06, v1.2.0 2025-12-12,
    v1.1.3 2024-11-26.
  - Schema: release asset `oscal_assessment-results_schema.json`, SHA-256
    `4034e2032332dbf597e59e0646ec16c2c31df992962490371e91f47b219ff42c`, JSON Schema
    `draft-07`, `$id` `http://csrc.nist.gov/ns/oscal/1.2.3/oscal-ar-schema.json`.
  - 1.2.2 release notes: "fixing the PositiveInteger and NonNegativeInteger datatypes in JSON".
    1.2.3 release notes list only build, dependency and documentation changes.
  - Diff of the assessment-results schema, 1.2.1 to 1.2.3, with version strings normalised: the
    only change is that `system-component.type` gains the suggested values `region`, `zone` and
    `resource-container`.
- **Structure the code must emit** (read from the 1.2.3 schema; VERIFIED):
  - Root: required `assessment-results`. It requires `uuid`, `metadata`, `import-ap` and
    `results`. `import-ap` points to an assessment plan (see OQ-2).
  - `result` requires `uuid`, `title`, `description`, `start` and `reviewed-controls`. Optional
    fields include `end`, `observations`, `findings`, `risks`, `assessment-log`,
    `local-definitions` and `attestations`.
  - `observation` requires `uuid`, `description`, `methods` and `collected`. Suggested `methods`
    values: `EXAMINE`, `INTERVIEW`, `TEST`, `UNKNOWN` (any string is allowed). Suggested `types`
    values: `ssp-statement-issue`, `control-objective`, `mitigation`, `finding`, `discovery`,
    `historic`.
  - `finding` requires `uuid`, `title`, `description` and `target`. `finding-target` requires
    `type` (enum `statement-id` or `objective-id`), `target-id` and `status`. `status` requires
    `state`, enum **`satisfied` or `not-satisfied` only**. Optional `status.reason` suggests
    `pass`, `fail` or `other`. There is no native "not assessed" or "error" state (see OQ-1).
- **Format checking:** the schema uses JSON Schema `format` keywords. With `jsonschema`, formats
  such as `date-time` are only enforced when the optional format dependencies are installed.
  UNVERIFIED which formats the OSCAL schema uses and which ones jsonschema checks; this blocks M1.

## 2. NIST SP 800-53 Rev 5: control identifiers

- **Source:** the NIST OSCAL catalog, https://github.com/usnistgov/oscal-content, file
  `nist.gov/SP800-53/rev5/json/NIST_SP-800-53_rev5_catalog.json` (last commit touching the file
  `78650f02ad9321bb7b817846f8fbd4f2bcd620de`, 2026-05-13). SHA-256
  `01f37cf90ea99d92242c936cbfbdebcc338eef1f71454e2acac36cc56e9bc062`. VERIFIED.
  - `metadata.title`: "Electronic (OSCAL) Version of NIST SP 800-53 Rev 5.2.0 Controls and SP
    800-53A Rev 5.2.0 Assessment Procedures". `version` 5.2.0, `oscal-version` 1.2.2,
    `last-modified` 2026-05-11. It holds 1196 controls plus enhancements.
- **Id format:** lowercase with enhancements dotted (`ac-2`, `ac-2.5`). Each control has part ids
  `<id>_smt` (statement), `<id>_gdn` (guidance), `<id>_obj` (assessment objective) and
  `<id>_asm-examine`, `<id>_asm-interview`, `<id>_asm-test` (assessment methods). VERIFIED.
- **Candidate controls named in the plan:** all exist and none is withdrawn in 5.2.0. VERIFIED:
  `ac-2` Account Management; `ac-6` Least Privilege; `ia-2` Identification and Authentication
  (Organizational Users); `ia-5` Authenticator Management; `sc-8` Transmission Confidentiality
  and Integrity; `sc-12` Cryptographic Key Establishment and Management; `sc-13` Cryptographic
  Protection; `sc-28` Protection of Information at Rest; `au-2` Event Logging; `au-9` Protection
  of Audit Information; `cm-6` Configuration Settings; `si-2` Flaw Remediation.
- **The chosen 25 controls:** UNVERIFIED until the list is fixed in M1 (an ADR). Each one is
  then checked against this catalog.

## 3. NIST SP 800-53A Rev 5: assessment methods

- **Source:** NIST SP 800-53A Revision 5, January 2022,
  https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53Ar5.pdf. VERIFIED.
  - §2.4.1 Assessment objects: specifications, mechanisms, activities, individuals.
  - §2.4.2 Assessment methods (p. 11):
    - Examine: "the process of reviewing, inspecting, observing, studying, or analyzing one or
      more assessment objects (i.e., specifications, mechanisms, or activities)".
    - Interview: "the process of holding discussions with individuals or groups of individuals".
    - Test: "the process of exercising one or more assessment objects (i.e., activities or
      mechanisms) under specified conditions to compare the actual state of the object to the
      desired state or expected behavior of the object".
    - Depth and coverage attributes, each with the values basic, focused and comprehensive.
  - §3.3: each determination statement produces "satisfied (S)" or "other than satisfied (O)".
    "O" "may also indicate that the assessor was unable to obtain sufficient information to make
    the determination".
  - Appendix C: method descriptions, including sampling under coverage (see §7).
- The OSCAL catalog in §2 carries the updated 5.2.0 procedures. Methods are encoded as parts named
  `assessment-method` with prop `method` (namespace `http://csrc.nist.gov/ns/rmf`) set to
  `EXAMINE`, `INTERVIEW` or `TEST`. VERIFIED.
- **Proposed mapping of controlproof methods.** This is the tool's interpretation, not a NIST
  statement. OPEN (OQ-3):

  | controlproof | 800-53A / OSCAL | Basis |
  |---|---|---|
  | `inspect` (read config) | EXAMINE | "reviewing, inspecting ... mechanisms" |
  | `exercise` (act on a tool-created resource) | TEST | "exercising ... mechanisms under specified conditions" |
  | `simulate` (IAM policy simulation) | proposed EXAMINE | AWS says the simulator "does not perform the API operations" and results "can differ from your live AWS environment" (§5.2), so the mechanism is not exercised |

## 4. FedRAMP 20x Key Security Indicators (for the V2 mapping)

- **Primary source:** https://github.com/FedRAMP/rules, file `fedramp-consolidated-rules.json`
  (commit `58487bda77d76d9ce334304ec2e779ece7cc7d54`, 2026-09-13). SHA-256
  `64915d88e72353c95f321ea4a9014516ac9441972cbd7f3d1abef7d1514c8fc8`. `info.title`: "FedRAMP
  Consolidated Rules for 2026", `info.version` 2026.09.13.02. VERIFIED.
- **Why it counts as official:** https://www.fedramp.gov/2026/rules/ states: "The FedRAMP Rules
  repository on GitHub (https://github.com/FedRAMP/rules) is the machine-readable source of
  truth for these rules." The website itself is "only intended as a human-readable reference".
  VERIFIED.
- **Content:** top-level keys `info`, `FRD`, `FRR`, `KSI`, `CTL`. There are 10 KSI themes (CED,
  CMT, CNA, IAM, INR, MLA, PIY, RPL, SCR, SVC) with 46 indicators, ids like `KSI-IAM-ELP`. Each
  indicator has `name`, `statement` (some have `varies_by_class` instead), `controls` (800-53 ids
  in the §2 format) and `updated`. Examples: `KSI-IAM-ELP` "Ensuring Least Privilege" lists
  `ac-6`, `ia-2` and others; `KSI-SVC-VRI` "Validating Resource Integrity" lists `sc-13`, `si-7`
  and others. VERIFIED.
- The KSI set is versioned by date and changes over time. A V2 mapping must pin
  `info.version` and the file hash.

## 5. AWS API behaviour

### 5.1 S3 default encryption (SC-28)
- https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-encryption.html. VERIFIED:
  "Amazon S3 now applies server-side encryption with Amazon S3 managed keys (SSE-S3) as the base
  level of encryption for every bucket". "Starting January 5, 2023, all new object uploads to
  Amazon S3 are automatically encrypted". "All Amazon S3 buckets have encryption configured by
  default". The other options are SSE-KMS and DSSE-KMS.
- https://docs.aws.amazon.com/AmazonS3/latest/API/API_DeleteBucketEncryption.html. VERIFIED:
  DeleteBucketEncryption "resets the default encryption for the bucket as server-side encryption
  with Amazon S3 managed keys (SSE-S3)". It needs `s3:PutEncryptionConfiguration`.
- **Consequence:** default bucket encryption cannot be turned off in real AWS (OQ-5).
- GetBucketEncryption response shape, and a bucket policy that denies PutObject without
  encryption headers: UNVERIFIED, blocks M2 (inspect) and M3 (exercise).

### 5.2 IAM SimulatePrincipalPolicy (AC-6, least privilege)
- https://docs.aws.amazon.com/IAM/latest/APIReference/API_SimulatePrincipalPolicy.html. VERIFIED:
  - Required parameters: `ActionNames`, `PolicySourceArn`. Optional parameters include
    `ResourceArns` (default `*`), `ResourcePolicy`, `CallerArn`, `ContextEntries`,
    `PermissionsBoundaryPolicyInputList`, `PolicyInputList` and `PolicyExclusionList`.
  - "The simulation does not perform the API operations; it only checks the authorization".
  - "The IAM policy simulator evaluates statements in identity-based policies, service control
    policies (SCPs) ... and the inputs that you provide". "The policy simulator results can differ
    from your live AWS environment."
  - "Simulation of resource-based policies isn't supported for IAM roles." RCPs are "not supported
    in this release" (PolicyExclusionList).
  - Pagination: `MaxItems` (default 100, range 1 to 1000), `IsTruncated`, `Marker`. "IAM might
    return fewer than the MaxItems number of results even when there are more results available."
  - Errors: `InvalidInput`, `NoSuchEntity`, `PolicyEvaluation`.
  - The page's examples show `EvalDecision` values `allowed` and `implicitDeny`.
- The full `EvalDecision` enum (the `EvaluationResult` type), the IAM action name for the
  permission, and moto support for this call: UNVERIFIED, blocks M3.

### 5.3 KMS GetKeyRotationStatus (SC-12)
- https://docs.aws.amazon.com/kms/latest/APIReference/API_GetKeyRotationStatus.html. VERIFIED:
  - "Automatic key rotation is supported only on symmetric encryption KMS keys". It is not
    supported for asymmetric keys, HMAC keys, keys with imported key material, or keys in a custom
    key store.
  - AWS managed keys: rotation "is not configurable", key material rotates every year, and "The
    key rotation status for AWS managed KMS keys is always `true`".
  - Response: `KeyId`, `KeyRotationEnabled`, `NextRotationDate`, `OnDemandRotationStartDate`,
    `RotationPeriodInDays` (default 365, range 90 to 2560).
  - While a key is pending deletion its rotation status is `false`. Disabling a key does not
    change its rotation status.
  - Permission `kms:GetKeyRotationStatus` (key policy). Errors: `DependencyTimeoutException`,
    `InvalidArnException`, `KMSInternalException`, `KMSInvalidStateException`,
    `NotFoundException`, `UnsupportedOperationException`.

### 5.4 ELBv2 security policies (SC-8, SC-13)
- https://docs.aws.amazon.com/elasticloadbalancing/latest/application/describe-ssl-policies.html.
  VERIFIED:
  - An HTTPS listener created without a policy gets the default. Console default:
    `ELBSecurityPolicy-TLS13-1-2-Res-PQ-2025-09`. Other methods (CLI, CloudFormation, CDK):
    `ELBSecurityPolicy-2016-08`.
  - `ELBSecurityPolicy-2016-08` supports TLS 1.2, 1.1 and 1.0, not 1.3.
    `ELBSecurityPolicy-TLS13-1-2-2021-06` and `ELBSecurityPolicy-TLS13-1-2-Res-PQ-2025-09`
    support TLS 1.3 and 1.2 only.
  - FIPS policies are named with `FIPS` (for example `ELBSecurityPolicy-TLS13-1-2-FIPS-2023-04`).
    AWS recommends `ELBSecurityPolicy-TLS13-1-2-Res-PQ-2025-09` or
    `ELBSecurityPolicy-TLS13-1-2-Res-FIPS-PQ-2025-09`.
- DescribeSSLPolicies and DescribeListeners API shapes, and the cost and ACM certificate needed
  for a tool-created HTTPS listener: UNVERIFIED, blocks M3.

### 5.5 CloudTrail (AU-2, AU-9)
- https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_GetTrailStatus.html. VERIFIED:
  - It returns `IsLogging` and delivery fields (`LatestDeliveryError`, `LatestDeliveryTime`,
    `LatestDigestDeliveryError`, `StartLoggingTime`, `StopLoggingTime`, and others). Some fields
    are marked "no longer in use".
  - "This operation returns trail status from a single Region." A shadow trail needs its ARN. A
    member account of an organization trail must pass the full ARN.
  - Errors: `CloudTrailARNInvalidException`, `InvalidTrailNameException`,
    `OperationNotPermittedException`, `TrailNotFoundException`, `UnsupportedOperationException`.
- DescribeTrails (multi-Region flag, `LogFileValidationEnabled`) and GetEventSelectors:
  UNVERIFIED, blocks M2.

## 6. Open questions

- **OQ-1 (blocks M1): how to express `error` and `not_tested` in OSCAL.** A finding's
  `status.state` can only be `satisfied` or `not-satisfied`. 800-53A §3.3 allows "other than
  satisfied" when the assessor could not obtain enough information. Proposal: `pass` becomes
  `satisfied`/`pass`, `fail` becomes `not-satisfied`/`fail`, and `error` and `not_tested` become
  `not-satisfied` with reason `other` plus a controlproof-namespaced prop giving the exact
  status. The alternative is an observation without a finding.
- **OQ-2 (blocks M1): `import-ap` is required.** Options: emit a minimal OSCAL assessment-plan
  per run and point `import-ap` at it, or point at an assessment plan the user supplies.
- **OQ-3 (blocks M1): the `simulate` method mapping.** See the table in §3: EXAMINE (proposed)
  or TEST.
- **OQ-4 (blocks M1): finding target.** Proposal: `type: objective-id`, `target-id: <control>_obj`
  (for example `sc-28_obj`), using the part ids in §2.
- **OQ-5 (blocks M4): the deliberate change for the M4 run-over-run demo.** The planned example
  (turning off default bucket encryption) cannot be done in real AWS (§5.1). It was only an
  example, so the goal stands; only the concrete change needs choosing, for example a bucket
  moved from SSE-KMS to SSE-S3 when the control requires KMS, or KMS rotation disabled on a
  tool-created key.

## 7. Plain-word explainers

**How assessors sample, and what evidence they accept.** 800-53A describes each method by
*depth* (how rigorous) and *coverage* (how much). For testing, "basic" and "focused" coverage use
"a representative sample of assessment objects (by type and number within type)". "Comprehensive"
uses "a sufficiently large sample". The organization and the assessor agree the numbers when they
plan (Appendix C, and footnote 57: the organization "confers with assessors"). What counts as
enough evidence is written into the assessment plan (§3.2); nothing is accepted by default. For
controlproof this means every observation should say which resources were checked and how many
of that type exist, so an assessor can see the coverage instead of guessing. How §3.2.3.5
("reuse of assessment evidence") applies to automated evidence: UNVERIFIED, not yet read.

**The OSCAL assessment-results model.** It is a JSON document for "what we tested and what we
found". It points to the plan it followed (`import-ap`), then holds one or more `results`, one
per assessment run. Each result lists the controls in scope (`reviewed-controls`), the raw facts
collected (`observations`: what was looked at, by which method, and when), and the conclusions
(`findings`: for one control objective, satisfied or not-satisfied, citing the observations that
support it). Risks and a log are optional. Observations are evidence; findings are the verdicts
built on them.

**FedRAMP 20x Key Security Indicators.** A KSI states an outcome a cloud service must show it
achieves, for example "Ensuring Least Privilege", instead of a list of control statements. Each
KSI names the 800-53 controls behind it. FedRAMP publishes them as JSON, and that JSON is the
official version (§4). FedRAMP wants providers to show them persistently with automation, which
is the kind of evidence controlproof produces. Mapping to KSIs is V2.

**How 800-53A test procedures are written.** Every control has an *assessment objective* phrased
as determination statements ("Determine if ..."). For SC-28 it is "the {confidentiality;
integrity} of {information at rest} is/are protected", where the braces are values the
organization fills in. There are also *methods* (examine, interview, test), each with a list of
*objects*. For SC-28 the test object is "Mechanisms supporting and/or implementing confidentiality
and integrity protections for information at rest". The assessor applies the methods to the
objects and marks each determination statement satisfied or other than satisfied. A controlproof
control automates one method against one object type for one objective.
