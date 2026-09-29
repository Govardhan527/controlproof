"""The `controlproof` command line (ADR-0009 §3).

Exit codes: 0 every control passed; 1 at least one failed and none errored; 2 at least one error
or not tested; 3 the run could not start.
"""

import json
from collections import Counter
from datetime import UTC, datetime
from importlib.resources import as_file, files
from pathlib import Path
from typing import Annotated, Any

import typer

from controlproof import __version__
from controlproof.controls.registry import REGISTRY
from controlproof.evidence import EvidenceStore
from controlproof.model import RunRecord, Status
from controlproof.output import MissingEvidenceError, RunExistsError, render_run, write_run
from controlproof.permissions import readonly_policy
from controlproof.profile import Profile, ProfileError, load_profile
from controlproof.providers import ProviderError
from controlproof.providers.aws import AwsProvider, default_region
from controlproof.runner import prepare, run_controls
from controlproof.validation import OscalValidationError

CANNOT_START = 3
app = typer.Typer(
    help="Test security controls against a live AWS account and write the evidence as OSCAL.",
    no_args_is_help=True,
    add_completion=False,
)


def _version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version, is_eager=True, help="Print the version and exit."
        ),
    ] = False,
) -> None:
    """controlproof: control test results, never compliance claims."""


def resolve_profile(name_or_path: str) -> Profile:
    """A built-in profile name (for example `aws-baseline`) or a path to a profile file."""
    looks_like_name = "/" not in name_or_path and not name_or_path.endswith((".yaml", ".yml"))
    built_in = files("controlproof") / "profiles" / f"{name_or_path}.yaml"
    if looks_like_name and built_in.is_file():
        with as_file(built_in) as path:
            return load_profile(path, REGISTRY)
    return load_profile(Path(name_or_path), REGISTRY)


def exit_code(run: RunRecord) -> int:
    statuses = {result.status for result in run.results}
    if statuses & {Status.ERROR, Status.NOT_TESTED}:
        return 2
    return 1 if Status.FAIL in statuses else 0


def _fail_to_start(message: str, as_json: bool) -> typer.Exit:
    if as_json:
        typer.echo(json.dumps({"error": message}, sort_keys=True))
    else:
        typer.echo(f"controlproof: {message}", err=True)
    return typer.Exit(CANNOT_START)


def _summary(run: RunRecord, run_dir: Path) -> dict[str, Any]:
    counts = Counter(result.status.value for result in run.results)
    return {
        "run_id": run.run_id,
        "run_dir": str(run_dir),
        "account": run.account,
        "regions": list(run.regions),
        "counts": {status.value: counts.get(status.value, 0) for status in Status},
        "results": [{"control_id": r.control_id, "status": r.status.value} for r in run.results],
    }


@app.command()
def run(
    profile: Annotated[
        str, typer.Option(help="Built-in profile name (aws-baseline) or a profile file path.")
    ],
    account: Annotated[
        str, typer.Option(help="12-digit AWS account id; the credentials must belong to it.")
    ],
    region: Annotated[
        list[str] | None,
        typer.Option(
            help="Region to test; repeat for several. Default: the profile's, else the SDK's."
        ),
    ] = None,
    out: Annotated[
        Path, typer.Option(help="Directory that receives one sub-directory per run.")
    ] = Path("controlproof-runs"),
    as_json: Annotated[
        bool, typer.Option("--json", help="Print a JSON summary instead of text.")
    ] = False,
) -> None:
    """Run a profile's controls against the AWS account the credentials belong to."""
    try:
        loaded = resolve_profile(profile)
        planned = prepare(loaded, REGISTRY)
    except ProfileError as exc:
        raise _fail_to_start(str(exc), as_json) from exc
    regions = tuple(region or ()) or loaded.regions or tuple(filter(None, [default_region()]))
    if not regions:
        raise _fail_to_start(
            "no AWS Region configured: pass --region or set regions in the profile", as_json
        )

    evidence = EvidenceStore()
    clock = lambda: datetime.now(UTC).replace(microsecond=0)  # noqa: E731
    provider = AwsProvider.from_environment(evidence, clock, regions[0])
    try:
        actual = provider.account_id()
    except ProviderError as exc:
        raise _fail_to_start(f"cannot identify the AWS account: {exc}", as_json) from exc
    if actual != account:
        raise _fail_to_start(
            f"the credentials belong to account {actual}, not {account}; nothing was run", as_json
        )

    record = run_controls(
        planned,
        profile_id=loaded.id,
        account=account,
        regions=regions,
        aws=provider,
        evidence=evidence,
        clock=clock,
        tool_version=__version__,
    )
    titles = {item.control.id: item.control.title for item in planned}
    methods = {item.control.id: item.control.method for item in planned}
    try:
        rendered = render_run(record, loaded, titles, methods, evidence.files())
        run_dir = write_run(out, rendered, record.run_id)
    except (MissingEvidenceError, OscalValidationError, RunExistsError) as exc:
        raise _fail_to_start(f"the run was not written: {exc}", as_json) from exc

    if as_json:
        typer.echo(json.dumps(_summary(record, run_dir), indent=2, sort_keys=True))
    else:
        for result in record.results:
            typer.echo(
                f"{result.control_id:8} {result.status.value:10} {titles[result.control_id]}"
            )
        typer.echo(
            f"Wrote {run_dir}. Control test results only; this is not a compliance statement."
        )
    raise typer.Exit(exit_code(record))


@app.command()
def permissions(
    profile: Annotated[
        str | None, typer.Option(help="Only the controls of this profile. Default: every control.")
    ] = None,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print only the IAM policy JSON.")
    ] = False,
) -> None:
    """Print the read-only IAM policy a run needs."""
    try:
        controls = (
            [REGISTRY[e.id] for e in resolve_profile(profile).controls]
            if profile
            else list(REGISTRY.values())
        )
    except ProfileError as exc:
        raise _fail_to_start(str(exc), as_json) from exc
    policy = json.dumps(readonly_policy(controls), indent=2, sort_keys=True)
    if not as_json:
        typer.echo("Attach this read-only policy to the identity that runs controlproof:", err=True)
    typer.echo(policy)
