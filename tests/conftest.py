import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from moto import mock_aws

GitRunner = Callable[..., str]
REGION = "us-east-1"


@pytest.fixture(autouse=True)
def _no_real_aws(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> None:
    """Every test gets fake credentials and no real AWS config, so nothing can reach an account."""
    empty = tmp_path_factory.mktemp("aws") / "none"
    for name in (
        "AWS_PROFILE",
        "AWS_DEFAULT_PROFILE",
        "AWS_REGION",
        "AWS_ROLE_ARN",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", str(empty))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(empty))
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")


@pytest.fixture
def moto() -> Iterator[None]:
    """The moto fake AWS (ADR-0009 §1, unit tier)."""
    with mock_aws():
        yield


@pytest.fixture
def git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, GitRunner]:
    """An empty repository whose git config ignores the machine's global and system config."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Test Author")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "test@example.invalid")
    repo = tmp_path / "repo"
    repo.mkdir()

    def run(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
        ).stdout.strip()

    run("init", "--quiet", "--initial-branch=main")
    return repo, run


@pytest.fixture
def commit(git_repo: tuple[Path, GitRunner]) -> Callable[[str], str]:
    """Create an empty commit with the given message, bypassing hooks; return its SHA."""
    _, run = git_repo

    def make(message: str) -> str:
        run("commit", "--quiet", "--allow-empty", "--no-verify", "-m", message)
        return run("rev-parse", "HEAD")

    return make
