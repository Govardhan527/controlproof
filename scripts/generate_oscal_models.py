"""Generate the OSCAL pydantic models from the vendored official schemas (ADR-0002a).

    generate_oscal_models.py           rewrite src/controlproof/oscal/models/*.py
    generate_oscal_models.py --check   exit 1 if the committed models differ from a fresh run

The `--type-mappings` keep date-time, email, uri and uri-reference values as strings. Without
them the generator attaches OSCAL's regex patterns to datetime fields and every document fails
with a TypeError (ADR-0002a). The official schema check remains the authoritative validation.
"""

import argparse
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "src" / "controlproof" / "schemas" / "official"
OUTPUT = ROOT / "src" / "controlproof" / "oscal" / "models"
MODELS = {"assessment-results": "assessment_results.py", "assessment-plan": "assessment_plan.py"}
FLAGS = (
    "--input-file-type=jsonschema",
    "--output-model-type=pydantic_v2.BaseModel",
    "--target-python-version=3.12",
    "--use-standard-collections",
    "--use-union-operator",
    "--field-constraints",
    "--allow-population-by-field-name",
    "--disable-timestamp",
    "--formatters=builtin",
    "--type-mappings",
    "date-time=string",
    "email=string",
    "uri=string",
    "uri-reference=string",
)
HEADER = (
    "# Generated from the official OSCAL {model} schema by scripts/generate_oscal_models.py.\n"
    "# Do not edit by hand; regenerate instead.\n"
)


def run(*command: str) -> None:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f"{' '.join(command[:4])} ... failed:\n{result.stderr}")


def generate(out_dir: Path) -> list[Path]:
    """Write every model module into `out_dir` and return their paths."""
    written = []
    for model, filename in MODELS.items():
        target = out_dir / filename
        schema = SCHEMAS / f"oscal-{model}.schema.json"
        run(
            sys.executable,
            "-m",
            "datamodel_code_generator",
            f"--input={schema}",
            f"--output={target}",
            *FLAGS,
        )
        target.write_text(HEADER.format(model=model) + target.read_text(encoding="utf-8"))
        written.append(target)
    config = str(ROOT / "pyproject.toml")
    run(sys.executable, "-m", "ruff", "format", "--quiet", "--config", config, *map(str, written))
    return written


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate OSCAL models from official schemas.")
    parser.add_argument("--check", action="store_true", help="fail if committed models differ")
    args = parser.parse_args(argv)

    # Always generate outside the repo: the generator's own formatter reads the nearest
    # pyproject.toml, so output written in place would differ from a --check run.
    with tempfile.TemporaryDirectory() as tmp:
        fresh = {path.name: path.read_bytes() for path in generate(Path(tmp))}
    stale = [
        name
        for name, content in fresh.items()
        if not (OUTPUT / name).is_file() or (OUTPUT / name).read_bytes() != content
    ]
    if args.check:
        for name in stale:
            print(f"{OUTPUT.relative_to(ROOT) / name} is out of date; run {Path(__file__).name}")
        return 1 if stale else 0
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in stale:
        (OUTPUT / name).write_bytes(fresh[name])
        print(f"wrote {(OUTPUT / name).relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
