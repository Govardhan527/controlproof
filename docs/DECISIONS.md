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
  7. **pip-audit audits `uv export` output** (hashed requirements, `--disable-pip
     --require-hashes --strict`), so it audits exactly what `uv.lock` pins.
  8. **mypy covers `scripts/` as well as `src/`.**
  9. **The SBOM comes from `uv export --format cyclonedx1.5`** in `make release-dry` (uv 0.12.9
     supports it), so no extra SBOM tool is needed.
  10. **uv is pinned** to `>=0.12.9,<0.13` (`[tool.uv] required-version`, and `version` in CI).
- **Input for ADR-0002a (to be written in M1):** compliance-trestle v5.1.0 (2026-09-02) declares
  `OSCAL_VERSION = '1.2.1'` and `OSCAL_VERSION_REGEX = r'^1\.2\.[0-1]$'`
  (`trestle/oscal/__init__.py` at tag v5.1.0). It therefore does not cover the 1.2.3 pin as-is.
  If 1.2.3 stands, the M1 default is `datamodel-code-generator` against the official schema.
- **Consequence:** The toolchain is reproducible from `uv.lock`, and CI and local runs use the same
  make targets. A change to any (A) item needs owner approval and an ADR update.

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
