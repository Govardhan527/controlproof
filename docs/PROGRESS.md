# Progress

Tick an item only when its done-criteria pass and the evidence is stored or linked.

## M0: bootstrap

- [x] Repo layout, `pyproject.toml`, `uv.lock`, Makefile, CI workflow, commit-msg hook and PR
      template exist.
- [x] Project docs exist: PROGRESS.md (full milestone list), DECISIONS.md, SPEC_NOTES.md,
      PARKED.md.
- [x] ADR-0001 (licence), ADR-0002 (stack), ADR-0003 (output schema versioning) exist. All of
      ADR-0001 to ADR-0004 are Accepted (owner approved 2026-09-29).
- [x] SPEC_NOTES.md lists every spec source (OSCAL, SP 800-53, SP 800-53A, FedRAMP 20x KSIs, AWS
      APIs), with the primary URL and retrieval date, or `UNVERIFIED`.
- [x] `make check` is green on the empty skeleton (2026-09-29: all unit tests pass, coverage 100%
      of `src/`, 0 example files).
- [x] A test commit with a forbidden trailer is rejected by the hook, and
      `scripts/check_commits.py` fails on a crafted bad range in a unit test.
      - [x] Unit test: `tests/test_check_commits.py::test_crafted_bad_range_fails` passes.
      - [x] Hook rejection shown in a scratch repo and in
            `tests/test_commit_msg_hook.py::test_hook_rejects_a_real_commit`.
      - [x] Hook rejection shown in this repo (2026-09-29): a `Co-authored-by:` trailer and
            the subject "Initial setup" were both rejected with "commit rejected:" and exit 1,
            and no commit was created.
- [x] M0 committed (2026-09-29): `17df0ed`..this commit on `main`. A clean clone passes
      `make check`, and `scripts/check_commits.py` passes on `origin/main..HEAD`.
- [x] CI green on GitHub (2026-09-29): run 36592992569 on `7f04fb4`, all six jobs passed
      (commit-hygiene checked 7 commits, 42 tests, no leaks, no known vulnerabilities).

## M1 (week 2)

Data model, profile format, OSCAL output from 3 stub controls, validated against the official
schema in CI.
- [x] Done: schema validation green; golden files committed.
      - [x] Locally (2026-09-29): `make check` green, 116 tests, 99% core coverage; the `schemas`
            step validates 8 example files against the official OSCAL 1.2.3 schemas and the
            project schemas. Each M1 commit also passed `make check` in a clean worktree.
      - [x] Golden files committed: `examples/<format>/stub-run-a.json` and `stub-run-b.json`
            (`2f53039`).
      - [x] Green in CI on GitHub (2026-09-29): run 36598001727 on `bca8d92`, all six jobs
            passed; the `schemas` job validated the 8 examples against the official schemas.
- [x] Open questions OQ-1 to OQ-4 and OQ-6 answered by the owner (2026-09-29, ADR-0005).
- [x] ADR-0002a (OSCAL models): generated models, accepted 2026-09-29.
- [x] ADR-0006 (runtime dependencies `regex`, `PyYAML`): accepted 2026-09-29.
- [x] ADR-0007 (the 25 controls): accepted 2026-09-29.
- [x] ADR-0008 (profile format, data model, output layout): accepted 2026-09-29.
- Build plan, tests first:
  - [x] Vendored the official 1.2.3 schemas with a SHA-256 test (`18cdcf9`).
  - [x] Official-schema validator with a `regex`-backed `pattern` keyword and metaschema check,
        tested with valid documents and five rejected variants (`18cdcf9`).
  - [x] Generation script, generated OSCAL models and a drift test (`fb497b7`).
  - [x] Data model, profile loader and control base (`fbd9219`); JSON Schemas generated into
        `src/controlproof/schemas/` with a drift test (`1b43b40`).
  - [x] OSCAL mapper for assessment-results and assessment-plan, and the run writer with its
        manifest and self-check (`1b43b40`).
  - [x] 3 stub controls (`tests/stub_controls.py`) covering pass, fail, error and not tested.
  - [x] Golden files in `examples/`, byte-stable, validated by the `schemas` step (`2f53039`).
- Carried to M2: evidence files under `evidence/` with redaction, and `href`s from
  `relevant-evidence` to them (M1 cites evidence by SHA-256 in the description only).

## M2 (weeks 3-4)

Runner, AWS provider, 10 `inspect` controls with moto tests.
- [ ] Done: each control has pass and fail fixtures; permissions documented.
      - [x] 8 of 10 controls have moto pass and fail fixtures (`tests/test_controls.py`), and each
            test also checks that the control's AWS calls are within its declared permissions.
      - [x] Permissions documented: `docs/iam-readonly.json`, generated and drift-tested;
            `controlproof permissions` prints it.
      - [ ] ac-6.2 and ia-2.1: blocked on OQ-7 (owner decision on the root-user data source).
      - [ ] Real tier (ADR-0009 §1): no control has run against a real AWS account yet.
- [x] ADR-0009 (M2 design) approved by the owner (2026-09-29).
- [ ] Sandbox account and CI OIDC role provided by the owner (for the real tier). The owner has
      no AWS account yet (2026-09-29); controls are unit-tier verified only until then.
- Build plan, tests first (unit tier first):
  - [x] Dependencies: boto3, typer; dev: moto, types-boto3.
  - [x] SPEC_NOTES for each call's response shape, errors and IAM action (SPEC_NOTES §5.8).
  - [x] Evidence recording and redaction, with the redaction test; `evidence-record` schema.
  - [x] AWS provider: session, account check, retries, typed errors, pagination.
  - [x] Runner: error isolation, partial-Region handling, empty-inventory observations.
  - [x] Profile and run record 1.1.0 (`regions`, `account`); built-in `aws-baseline` profile.
  - [ ] Controls 1 to 10: 8 built with moto pass and fail fixtures; ac-6.2 and ia-2.1 wait on OQ-7.
  - [x] `docs/iam-readonly.json` generated, with a drift test.
  - [x] CLI: `run`, `permissions`, `--version`, `--json`, exit codes.
  - [x] Golden run `examples/runs/aws-baseline/`, replayed from a recording (ADR-0009 §10).
  - [ ] Real tier: `tests/integration/` against the sandbox; CI job wired to the OIDC role.
  - [ ] Remove the "no integration tests yet" exit-5 allowance from `make integration`.

## M3 (weeks 5-6)

`simulate` and `exercise` controls up to 25 total.
- [ ] Done: allowlist and cleanup tested, including cleanup after a crash.

## M4 (week 7)

Run-over-run diff, `not_tested` detection, HTML report.
- [ ] Done: a second run after one deliberate change reports exactly that control as changed, and
      a control whose test was removed is reported as "not tested this run", never as pass.
- [ ] Owner picks the deliberate change (OQ-5: S3 default encryption cannot be turned off in real
      AWS).

## M5 (weeks 8-9)

GitHub Action, packaging, docs, `make demo`.
- [ ] Done: the end-to-end demo passes against the sandbox account.

## M6 (week 10)

Hardening buffer: fix defects, tighten docs, no new features.
- [ ] Done: defects fixed, docs tightened.
- [ ] Add the CI `release` job (tag `v*`: build, SBOM, PyPI trusted publishing), only after M6.

## Last session (resume here)

- **Date:** 2026-09-30. **Current milestone:** M2, unit tier built; 2 of 10 controls and the real
  tier are still open.
- **State of `main`:** pushed and even with `origin/main` at the end of the session. Last code
  change CI-checked: `de9f454`, run 36625863577 green (195 tests, 97.93% coverage, 29 example
  files valid, no leaks, no known vulnerabilities); later commits changed only this file. `make check` green
  locally with 196 tests (one more test runs only locally).
- **Built in M2 so far:** evidence recording and redaction, AWS provider (the only boto3 import;
  refuses undeclared calls), runner (errors never become passes), 8 inspect controls (ac-2,
  ia-2.2, ia-5.1, sc-28, sc-28.1, au-2, si-7.1, sc-7), CLI (`run`, `permissions`, `--version`,
  `--json`, exit codes 0 to 3), `docs/iam-readonly.json`, run record and profile 1.1.0,
  `evidence-record` 1.0.0, golden run replayed from a recording (ADR-0009 §10).
- **Incident, fixed (2026-09-29):** the first M2 push failed CI. gitleaks flagged three synthetic
  key-shaped strings in the redaction test, and a CLI test broke on colour codes. The strings are
  now built at runtime, and `.gitleaksignore` lists only those three published findings by
  fingerprint (ADR-0002 item 6 amendment).
- **Waiting on the owner:**
  1. **OQ-7** (SPEC_NOTES §6): the data source for ac-6.2 (root access keys) and ia-2.1 (root
     MFA). (a) `GetAccountSummary` keys: one call, and moto supports it, but AWS does not document
     their meaning. (b) The IAM credential report: documented columns including the root user;
     data up to 4 hours old; generating it replaces the stored report; moto has no root row, so
     tests would use recorded responses. Recommended: (b), generating only when no current report
     exists, and stating the report's generation time in the evidence.
  2. **A sandbox AWS account** for the real tier (ADR-0009 §1). The owner has none yet. Until
     then no control is described as validated in a real environment.
- **Next steps, in order:**
  1. On the OQ-7 answer: record it (SPEC_NOTES §5.8 and §6, ADR-0009 §10), verify the calls it
     needs (`GetCredentialReport` and `GenerateCredentialReport` errors and report format, or the
     summary keys), add them to `OPERATION_ACTIONS`, build ac-6.2 and ia-2.1 with tests, add them
     to `REGISTRY`, the `aws-baseline` profile, the golden recording and `docs/iam-readonly.json`
     (`CONTROLPROOF_UPDATE_GOLDEN=1 make test`).
  2. When a sandbox exists: `tests/integration/` against it, the CI `integration` job wired to a
     GitHub OIDC role (no stored keys), then remove the exit-5 allowance in `make integration`
     and replace the moto recording behind the golden run with a real one.
  3. Then close M2 and plan M3 (simulate and exercise controls, ADR-0007 rows 11 to 25).
- **Check the state on resume:** `git status -sb` (expect clean and even with `origin/main`),
  `make check`, and `gh run list --limit 1`.
