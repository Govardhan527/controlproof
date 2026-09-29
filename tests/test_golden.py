"""Golden run: the committed examples/runs/aws-baseline/ is exactly what the controls produce.

The run replays tests/fixtures/recordings/aws-baseline.json, a redacted recording of the shipped
controls against a known moto scenario. Regenerate both after an intended change with:
    CONTROLPROOF_UPDATE_GOLDEN=1 make test
"""

import hashlib
import json
import os
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

import aws_scenarios as scenario
from conftest import REGION
from controlproof.controls.registry import REGISTRY
from controlproof.evidence import EvidenceStore
from controlproof.model import RunRecord
from controlproof.output import MANIFEST, RunExistsError, render_run, write_run
from controlproof.profile import load_profile
from controlproof.providers.aws import AwsProvider
from controlproof.runner import prepare, run_controls
from replay import RecordingAws, ReplayAws
from stub_controls import START, render_stub, ticking_clock

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "examples" / "runs" / "aws-baseline"
RECORDING = Path(__file__).parent / "fixtures" / "recordings" / "aws-baseline.json"
PROFILE = ROOT / "src" / "controlproof" / "profiles" / "aws-baseline.yaml"
ACCOUNT = "123456789012"
UPDATE = os.environ.get("CONTROLPROOF_UPDATE_GOLDEN") == "1"


def baseline_scenario() -> None:
    """Passes and failures on purpose, so the golden run shows both."""
    scenario.console_user("alice", mfa=True)
    scenario.console_user("bob", mfa=False)
    scenario.api_user("svc-deploy")
    scenario.password_policy(MinimumPasswordLength=8)
    scenario.ebs_default_encryption()
    scenario.bucket("cp-demo-kms", "aws:kms")
    scenario.bucket("cp-demo-sse-s3", "AES256")
    scenario.trail("cp-demo-trail", multi_region=True, logging=True, validation=True)
    boto3.client("cloudtrail", region_name=REGION).put_event_selectors(
        TrailName="cp-demo-trail",
        EventSelectors=[{"ReadWriteType": "All", "IncludeManagementEvents": True}],
    )
    scenario.open_security_group("cp-demo-open-ssh", port=22)


def run_baseline(aws_factory: object) -> tuple[RunRecord, EvidenceStore]:
    profile = load_profile(PROFILE, REGISTRY)
    ticks = ticking_clock(START["stub-run-a"])
    clock = lambda: next(ticks)  # noqa: E731
    evidence = EvidenceStore()
    aws = aws_factory(evidence, clock)  # type: ignore[operator]
    record = run_controls(
        prepare(profile, REGISTRY),
        profile_id=profile.id,
        account=ACCOUNT,
        regions=(REGION,),
        aws=aws,
        evidence=evidence,
        clock=clock,
        tool_version="0.0.0",
    )
    return record, evidence


def render_replay() -> dict[str, bytes]:
    record, evidence = run_baseline(lambda ev, clock: ReplayAws(RECORDING, ev, clock, REGION))
    profile = load_profile(PROFILE, REGISTRY)
    titles = {cid: c.title for cid, c in REGISTRY.items()}
    methods = {cid: c.method for cid, c in REGISTRY.items()}
    return render_run(record, profile, titles, methods, evidence.files())


def live_statuses() -> dict[str, str]:
    with mock_aws():
        baseline_scenario()
        recorder: list[RecordingAws] = []

        def factory(evidence: EvidenceStore, clock: object) -> RecordingAws:
            live = AwsProvider(boto3.Session(), evidence, clock, REGION, max_attempts=1)  # type: ignore[arg-type]
            recorder.append(RecordingAws(live))
            return recorder[0]

        record, _ = run_baseline(factory)
        if UPDATE:
            recorder[0].save(RECORDING)
    return {r.control_id: r.status.value for r in record.results}


def test_recording_matches_a_live_moto_run() -> None:
    live = live_statuses()
    replayed = json.loads(render_replay()["run.json"])
    assert {r["control_id"]: r["status"] for r in replayed["results"]} == live
    assert set(live.values()) == {"pass", "fail"}, "the golden run should show passes and failures"


def test_outputs_match_the_golden_run() -> None:
    files = render_replay()
    if UPDATE:
        for name, data in files.items():
            target = GOLDEN / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    committed = {str(p.relative_to(GOLDEN)): p.read_bytes() for p in GOLDEN.rglob("*.json")}
    assert sorted(committed) == sorted(files)
    for name, data in files.items():
        assert committed[name] == data, f"{name} differs from the golden run"


def test_rendering_is_deterministic() -> None:
    assert render_replay() == render_replay()


def test_manifest_hashes_every_other_file() -> None:
    files = render_replay()
    manifest = json.loads(files[MANIFEST])
    assert manifest["files"] == {
        name: hashlib.sha256(data).hexdigest() for name, data in files.items() if name != MANIFEST
    }


def test_every_cited_evidence_file_is_in_the_run() -> None:
    files = render_replay()
    record = json.loads(files["run.json"])
    for result in record["results"]:
        for ref in result["evidence_refs"]:
            assert f"evidence/{ref}.json" in files


def test_write_run_writes_every_file_and_never_overwrites(tmp_path: Path) -> None:
    files = render_stub("stub-run-a")
    run_dir = write_run(tmp_path, files, "20260929T120000Z")
    written = {
        str(p.relative_to(run_dir)): p.read_bytes() for p in run_dir.rglob("*") if p.is_file()
    }
    assert written == files
    with pytest.raises(RunExistsError):
        write_run(tmp_path, files, "20260929T120000Z")
