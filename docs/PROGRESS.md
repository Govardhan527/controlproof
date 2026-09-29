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
- [ ] Done: schema validation green; golden files committed.
- [x] Open questions OQ-1 to OQ-4 and OQ-6 answered by the owner (2026-09-29, ADR-0005).
- [x] ADR-0002a (OSCAL models): generated models, accepted 2026-09-29.
- [x] ADR-0006 (runtime dependencies `regex`, `PyYAML`): accepted 2026-09-29.
- [ ] ADR-0007 (the 25 controls): proposed, awaiting owner approval.
- [ ] ADR-0008 (profile format, data model, output layout): proposed, awaiting owner approval.
- Build plan once ADR-0008 is approved, tests first:
  - [ ] Vendor the official 1.2.3 assessment-results and assessment-plan schemas under
        `schemas/official/`, with a test that pins their SHA-256 (SPEC_NOTES §1).
  - [ ] Official-schema validator (jsonschema plus a `regex`-backed `pattern` keyword), tested
        with the valid minimal documents and the five rejected variants from SPEC_NOTES §1.
  - [ ] Generation script and generated OSCAL models (ADR-0002a).
  - [ ] Data model and profile loader (ADR-0008); JSON Schemas generated into `schemas/` with a
        drift test (ADR-0003).
  - [ ] OSCAL mapper for assessment-results and assessment-plan (ADR-0005, ADR-0008).
  - [ ] 3 stub controls covering pass, fail and error, plus a `not_tested` case.
  - [ ] Golden files in `examples/`, byte-stable, validated by the CI `schemas` job.

## M2 (weeks 3-4)

Runner, AWS provider, 10 `inspect` controls with moto tests.
- [ ] Done: each control has pass and fail fixtures; permissions documented.
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

## Last session

- **Date:** 2026-09-29
- **Changed:** M0 finished and pushed (CI green: runs 36592992569 and 36593562138). M1 research:
  assessment-plan schema, jsonschema cannot run OSCAL's `\p{L}` pattern (fixed with `regex` in a
  probe), trestle versus generated models, moto coverage, AWS's 800-53 mapping. Decisions
  recorded: ADR-0002a, ADR-0005 item 5 (OQ-6), ADR-0006. Proposed: ADR-0007 (25 controls) and
  ADR-0008 (M1 contracts).
- **Tests:** `make check` green; no product code changed since M0.
- **Not done:** M1 code. It waits for approval of ADR-0007 and ADR-0008.
- **Next step:** the owner approves or amends ADR-0007 and ADR-0008. Then build M1 in the order of
  the build plan above.
