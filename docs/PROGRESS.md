# Progress

Tick an item only when its done-criteria pass and the evidence is stored or linked.

## M0: bootstrap

- [x] Repo layout, `pyproject.toml`, `uv.lock`, Makefile, CI workflow, commit-msg hook and PR
      template exist.
- [x] Project docs exist: PROGRESS.md (full milestone list), DECISIONS.md, SPEC_NOTES.md,
      PARKED.md.
- [x] ADR-0001 (licence), ADR-0002 (stack), ADR-0003 (output schema versioning) exist. Owner
      approval is still pending on the items listed in ADR-0002, ADR-0003 and ADR-0004.
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
- [ ] CI green on GitHub. Needs the M0 commits pushed (owner's call).

## M1 (week 2)

Data model, profile format, OSCAL output from 3 stub controls, validated against the official
schema in CI.
- [ ] Done: schema validation green; golden files committed.
- [ ] Open questions OQ-1 to OQ-4 in `docs/SPEC_NOTES.md` answered by the owner (they block M1).
- [ ] ADR-0002a (OSCAL models: compliance-trestle or datamodel-code-generator).
- [ ] ADR recording the exact 25 controls.

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
- **Changed:** M0 skeleton: pyproject, uv.lock, Makefile, CI workflow (actions pinned by SHA),
  commit-msg hook + `scripts/check_commits.py` + shared `scripts/commit_rules.py`,
  `scripts/validate_outputs.py`, PR template, project docs, ADR-0001 to ADR-0004, SPEC_NOTES from
  primary sources.
- **Tests:** `make check` green, `src/` coverage 100%. `pip-audit` and `gitleaks` clean when run
  locally. `make integration` collects 0 tests (expected until M2).
- **Commits:** `17df0ed` skeleton, `9612a9f` commit rules, `7ca1db4` output validator, `195467c`
  Makefile, `c26d26d` CI, `c957670` docs, then this status update. Not pushed.
- **Not done:** CI has not run on GitHub (needs a push, the owner's call). ADR-0002 (A) items,
  ADR-0003 and ADR-0004 await owner approval.
- **Next step:** the owner pushes `main` and checks that CI is green, approves or amends the ADRs,
  and answers OQ-1 to OQ-4 in `docs/SPEC_NOTES.md`. Then M1 starts.
