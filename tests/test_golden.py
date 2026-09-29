"""Golden files: the committed examples/ outputs are exactly what the stub runs render.

Regenerate after an intended change with: CONTROLPROOF_UPDATE_GOLDEN=1 make test
"""

import hashlib
import json
import os
from pathlib import Path

import pytest

from controlproof.output import MANIFEST, RunExistsError, write_run
from stub_controls import render_stub

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
FORMAT = {
    "run.json": "run-record",
    "assessment-plan.json": "oscal-assessment-plan",
    "assessment-results.json": "oscal-assessment-results",
    "manifest.json": "manifest",
}
RUNS = ("stub-run-a", "stub-run-b")


@pytest.mark.parametrize("name", RUNS)
def test_outputs_match_golden_files(name: str) -> None:
    files = render_stub(name)
    assert set(files) == set(FORMAT)
    for filename, content in files.items():
        golden = EXAMPLES / FORMAT[filename] / f"{name}.json"
        if os.environ.get("CONTROLPROOF_UPDATE_GOLDEN") == "1":
            golden.parent.mkdir(parents=True, exist_ok=True)
            golden.write_bytes(content)
        assert golden.read_bytes() == content, f"{golden} differs from the rendered {filename}"


@pytest.mark.parametrize("name", RUNS)
def test_rendering_is_deterministic(name: str) -> None:
    assert render_stub(name) == render_stub(name)


def test_manifest_hashes_every_other_file() -> None:
    files = render_stub("stub-run-a")
    manifest = json.loads(files[MANIFEST])
    assert manifest["files"] == {
        name: hashlib.sha256(content).hexdigest()
        for name, content in files.items()
        if name != MANIFEST
    }


def test_write_run_writes_every_file_and_never_overwrites(tmp_path: Path) -> None:
    files = render_stub("stub-run-a")
    run_dir = write_run(tmp_path, files, "20260929T120000Z")
    assert {p.name: p.read_bytes() for p in run_dir.iterdir()} == files
    with pytest.raises(RunExistsError):
        write_run(tmp_path, files, "20260929T120000Z")
