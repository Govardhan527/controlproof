"""Write one run's output directory (ADR-0008, ADR-0009 §6).

    <out>/<run-id>/run.json                  RunRecord
    <out>/<run-id>/assessment-plan.json      OSCAL 1.2.3
    <out>/<run-id>/assessment-results.json   OSCAL 1.2.3
    <out>/<run-id>/evidence/<sha256>.json    redacted API responses
    <out>/<run-id>/manifest.json             SHA-256 of every other file

Every file is rendered and validated in memory first; nothing is written unless all pass.
"""

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from controlproof.canonical import to_json
from controlproof.evidence import EVIDENCE_DIR
from controlproof.model import Contract, Method, RunId, RunRecord, Sha256
from controlproof.oscal.mapping import build_assessment_plan, build_assessment_results
from controlproof.profile import Profile

MANIFEST_VERSION: Literal["1.0.0"] = "1.0.0"
RUN_RECORD = "run.json"
PLAN = "assessment-plan.json"
RESULTS = "assessment-results.json"
MANIFEST = "manifest.json"


class RunExistsError(Exception):
    """The run directory already exists; runs are never overwritten."""


class MissingEvidenceError(Exception):
    """A result cites evidence that was not collected; the run is not written."""


class Manifest(Contract):
    schema_version: Literal["1.0.0"] = MANIFEST_VERSION
    run_id: RunId
    algorithm: Literal["sha256"] = "sha256"
    files: dict[str, Sha256]


def render_run(
    run: RunRecord,
    profile: Profile,
    titles: Mapping[str, str],
    methods: Mapping[str, Method],
    evidence: Mapping[str, bytes],
) -> dict[str, bytes]:
    """Every file of the run, by relative path.

    Raises if cited evidence is missing or an OSCAL document fails the official schema.
    """
    cited = {ref for result in run.results for ref in result.evidence_refs}
    if missing := sorted(ref for ref in cited if f"{EVIDENCE_DIR}/{ref}.json" not in evidence):
        raise MissingEvidenceError(f"results cite evidence that was not stored: {missing}")
    files = {
        RUN_RECORD: to_json(run.model_dump(mode="json")),
        PLAN: to_json(build_assessment_plan(run, profile, titles, methods)),
        RESULTS: to_json(build_assessment_results(run, profile, titles)),
        **evidence,
    }
    manifest = Manifest(
        run_id=run.run_id,
        files={name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
    )
    files[MANIFEST] = to_json(manifest.model_dump(mode="json"))
    return files


def write_run(out_dir: Path, files: Mapping[str, bytes], run_id: str) -> Path:
    """Write rendered files to `out_dir/<run_id>/`, refusing to overwrite an earlier run."""
    run_dir = out_dir / run_id
    try:
        run_dir.mkdir(parents=True)
    except FileExistsError as exc:
        raise RunExistsError(f"{run_dir} already exists; runs are never overwritten") from exc
    for name, data in sorted(files.items()):
        target = run_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return run_dir
