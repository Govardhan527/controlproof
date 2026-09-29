"""Write one run's output directory (ADR-0008).

    <out>/<run-id>/run.json                  RunRecord
    <out>/<run-id>/assessment-plan.json      OSCAL 1.2.3
    <out>/<run-id>/assessment-results.json   OSCAL 1.2.3
    <out>/<run-id>/manifest.json             SHA-256 of every other file

Every file is rendered and validated in memory first; nothing is written unless all pass.
"""

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from controlproof.model import SCHEMA_VERSION, Contract, Method, RunId, RunRecord, Sha256
from controlproof.oscal.mapping import build_assessment_plan, build_assessment_results
from controlproof.profile import Profile

RUN_RECORD = "run.json"
PLAN = "assessment-plan.json"
RESULTS = "assessment-results.json"
MANIFEST = "manifest.json"


class RunExistsError(Exception):
    """The run directory already exists; runs are never overwritten."""


class Manifest(Contract):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    run_id: RunId
    algorithm: Literal["sha256"] = "sha256"
    files: dict[str, Sha256]


def to_json(data: Any) -> bytes:
    """Canonical JSON: sorted keys, two-space indent, UTF-8, trailing newline."""
    return (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def render_run(
    run: RunRecord,
    profile: Profile,
    titles: Mapping[str, str],
    methods: Mapping[str, Method],
    account: str,
) -> dict[str, bytes]:
    """Every file of the run, by name. Raises if any OSCAL document fails the official schema."""
    files = {
        RUN_RECORD: to_json(run.model_dump(mode="json")),
        PLAN: to_json(build_assessment_plan(run, profile, titles, methods, account)),
        RESULTS: to_json(build_assessment_results(run, profile, titles)),
    }
    manifest = Manifest(
        run_id=run.run_id,
        files={
            name: hashlib.sha256(content).hexdigest() for name, content in sorted(files.items())
        },
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
    for name, content in sorted(files.items()):
        (run_dir / name).write_bytes(content)
    return run_dir
