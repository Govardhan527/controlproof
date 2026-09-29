"""JSON Schema validation, including against the official OSCAL schemas.

The OSCAL `TokenDatatype` pattern uses `\\p{L}` and `\\p{N}`, which Python's `re` module rejects,
so the `pattern` keyword is backed by the `regex` package here (ADR-0006, SPEC_NOTES §1). The
schemas themselves stay byte-for-byte the NIST release files.
"""

import json
from collections.abc import Iterator, Mapping
from functools import cache
from importlib.resources import files
from typing import Any, Literal, cast

import regex
from jsonschema import FormatChecker, ValidationError
from jsonschema.exceptions import SchemaError, best_match
from jsonschema.protocols import Validator
from jsonschema.validators import extend, validator_for

OSCAL_VERSION = "1.2.3"

OscalModel = Literal["assessment-results", "assessment-plan"]


class OscalValidationError(Exception):
    """An OSCAL document does not validate against the official schema."""

    def __init__(self, model: OscalModel, errors: list[str]) -> None:
        self.model = model
        self.errors = errors
        super().__init__(
            f"OSCAL {model} document fails the official {OSCAL_VERSION} schema:\n  "
            + "\n  ".join(errors)
        )


def _pattern(
    validator: Validator, pattern: str, instance: object, schema: Mapping[str, Any]
) -> Iterator[ValidationError]:
    if isinstance(instance, str) and not regex.search(pattern, instance):
        yield ValidationError(f"{instance!r} does not match {pattern!r}")


def _compiles(instance: object) -> bool:
    if isinstance(instance, str):
        regex.compile(instance)
    return True


def _regex_aware(checker: FormatChecker) -> FormatChecker:
    """A copy of `checker` whose "regex" format is checked with `regex`, not `re`."""
    aware = FormatChecker(name for name in checker.checkers if name != "regex")
    aware.checks("regex", raises=regex.error)(_compiles)
    return aware


def build_validator(schema: dict[str, Any]) -> Validator:
    """Return a validator for `schema` whose `pattern` keyword understands `\\p{...}` classes.

    Raises `SchemaError` if `schema` is not a valid schema for its draft. The metaschema's
    "regex" format is checked with `regex` too, or the official OSCAL schema itself would fail.
    """
    base = validator_for(schema)
    formats = _regex_aware(base.FORMAT_CHECKER)
    meta_schema = base.META_SCHEMA
    problem = best_match(
        validator_for(meta_schema)(meta_schema, format_checker=formats).iter_errors(schema)
    )
    if problem is not None:
        raise SchemaError.create_from(problem)
    # types-jsonschema leaves `extend` untyped; it returns a validator class like `base`.
    validator_cls = cast(
        "type[Validator]",
        extend(base, {"pattern": _pattern}),  # type: ignore[no-untyped-call]
    )
    return validator_cls(schema, format_checker=formats)


def schema_errors(validator: Validator, instance: Any) -> list[str]:
    """Every validation error as `path: message`, in a stable order."""
    errors = sorted(validator.iter_errors(instance), key=lambda e: [str(p) for p in e.path])
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in errors]


@cache
def _official_validator(model: OscalModel) -> Validator:
    path = files("controlproof") / "schemas" / "official" / f"oscal-{model}.schema.json"
    return build_validator(json.loads(path.read_text(encoding="utf-8")))


def oscal_errors(document: Mapping[str, Any], model: OscalModel) -> list[str]:
    """Validate `document` against the official OSCAL schema for `model`."""
    return schema_errors(_official_validator(model), document)


def check_oscal(document: Mapping[str, Any], model: OscalModel) -> None:
    """Raise `OscalValidationError` unless `document` is valid OSCAL."""
    errors = oscal_errors(document, model)
    if errors:
        raise OscalValidationError(model, errors)
