"""The command line, end to end against moto (ADR-0009 §3)."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from controlproof import __version__
from controlproof.cli import app
from controlproof.validation import oscal_errors
from test_golden import baseline_scenario

RUNNER = CliRunner()
ACCOUNT = "123456789012"


def invoke(*args: str) -> tuple[int, str, str]:
    result = RUNNER.invoke(app, list(args))
    return result.exit_code, result.stdout, result.stderr


@pytest.mark.usefixtures("moto")
def test_run_writes_a_complete_valid_run_and_exits_1_on_failures(tmp_path: Path) -> None:
    baseline_scenario()
    code, out, _ = invoke(
        "run", "--profile", "aws-baseline", "--account", ACCOUNT, "--out", str(tmp_path), "--json"
    )
    assert code == 1  # some controls fail, none errored
    summary = json.loads(out)
    run_dir = Path(summary["run_dir"])
    assert summary["counts"]["error"] == 0
    assert summary["counts"]["fail"] > 0
    assert summary["account"] == ACCOUNT
    assert summary["regions"] == ["us-east-1"]
    for name, model in (
        ("assessment-results.json", "assessment-results"),
        ("assessment-plan.json", "assessment-plan"),
    ):
        assert oscal_errors(json.loads((run_dir / name).read_text()), model) == []  # type: ignore[arg-type]
    manifest = json.loads((run_dir / "manifest.json").read_text())
    on_disk = {str(p.relative_to(run_dir)) for p in run_dir.rglob("*") if p.is_file()} - {
        "manifest.json"
    }
    assert set(manifest["files"]) == on_disk
    assert any(name.startswith("evidence/") for name in on_disk)


@pytest.mark.usefixtures("moto")
def test_text_output_never_claims_compliance(tmp_path: Path) -> None:
    code, out, _ = invoke(
        "run", "--profile", "aws-baseline", "--account", ACCOUNT, "--out", str(tmp_path)
    )
    assert code in (1, 2)
    assert "not a compliance statement" in out
    assert "compliant" not in out.lower()


@pytest.mark.usefixtures("moto")
def test_a_wrong_account_stops_the_run_before_any_control(tmp_path: Path) -> None:
    code, _, err = invoke(
        "run", "--profile", "aws-baseline", "--account", "111111111111", "--out", str(tmp_path)
    )
    assert code == 3
    assert "not 111111111111; nothing was run" in err
    assert not any(tmp_path.iterdir())


def test_a_bad_profile_cannot_start(tmp_path: Path) -> None:
    code, out, _ = invoke(
        "run", "--profile", str(tmp_path / "missing.yaml"), "--account", ACCOUNT, "--json"
    )
    assert code == 3
    assert "cannot read profile" in json.loads(out)["error"]


def test_no_region_cannot_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AWS_DEFAULT_REGION")
    code, _, err = invoke("run", "--profile", "aws-baseline", "--account", ACCOUNT)
    assert code == 3
    assert "no AWS Region configured" in err


def test_permissions_prints_the_read_only_policy() -> None:
    code, out, _ = invoke("permissions", "--json")
    assert code == 0
    policy = json.loads(out)
    actions = policy["Statement"][0]["Action"]
    assert policy["Version"] == "2012-10-17"
    assert "sts:GetCallerIdentity" in actions
    assert "s3:GetEncryptionConfiguration" in actions


def test_permissions_for_one_profile() -> None:
    code, out, _ = invoke("permissions", "--profile", "aws-baseline", "--json")
    assert code == 0
    assert json.loads(out)["Statement"][0]["Effect"] == "Allow"


def test_version_and_help() -> None:
    assert invoke("--version")[1].strip() == __version__
    for command in ([], ["run"], ["permissions"]):
        code, out, _ = invoke(*command, "--help")
        assert code == 0
        assert "--help" in out
    assert "--json" in invoke("run", "--help")[1]


def test_missing_credentials_cannot_start(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(name)
    code, _, err = invoke("run", "--profile", "aws-baseline", "--account", ACCOUNT)
    assert code == 3
    assert "cannot identify the AWS account" in err


def test_permissions_with_a_bad_profile_cannot_start(tmp_path: Path) -> None:
    code, _, err = invoke("permissions", "--profile", str(tmp_path / "missing.yaml"))
    assert code == 3
    assert "cannot read profile" in err
