"""Control profiles: which controls a run executes, with their parameters (ADR-0008).

Unknown keys, duplicate keys, duplicate control ids and unknown control ids are load errors;
nothing in a profile is ever silently skipped.
"""

from collections.abc import Collection, Hashable
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import Field, JsonValue, ValidationError, model_validator

from controlproof.model import Contract, ControlId, Token


class ProfileError(Exception):
    """A profile file cannot be used as written."""


class ProfileControl(Contract):
    id: ControlId
    params: dict[str, JsonValue] = Field(default_factory=dict)


class Profile(Contract):
    schema_version: Literal["1.0.0"]
    id: Token
    title: str = Field(min_length=1)
    provider: Literal["aws"]
    controls: tuple[ProfileControl, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_controls(self) -> Self:
        ids = [control.id for control in self.controls]
        if duplicates := sorted({cid for cid in ids if ids.count(cid) > 1}):
            raise ValueError(f"controls listed more than once: {duplicates}")
        return self

    @property
    def control_ids(self) -> tuple[str, ...]:
        return tuple(sorted(control.id for control in self.controls))


class _StrictLoader(yaml.SafeLoader):
    """`yaml.SafeLoader` that rejects duplicate mapping keys instead of keeping the last one."""


def _construct_mapping(loader: _StrictLoader, node: yaml.MappingNode) -> dict[Hashable, Any]:
    seen: set[Hashable] = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r}", key_node.start_mark
            )
        seen.add(key)
    return loader.construct_mapping(node)


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def load_profile(path: Path, known_controls: Collection[str]) -> Profile:
    """Load and check a profile. Raises `ProfileError` with every problem found."""
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=_StrictLoader)  # noqa: S506
    except OSError as exc:
        raise ProfileError(f"{path}: cannot read profile: {exc.strerror}") from exc
    except yaml.YAMLError as exc:
        raise ProfileError(f"{path}: not valid YAML: {exc}") from exc
    try:
        profile = Profile.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(map(str, error['loc'])) or '<root>'}: {error['msg']}"
            for error in exc.errors()
        )
        raise ProfileError(f"{path}: {problems}") from exc
    if unknown := sorted(set(profile.control_ids) - set(known_controls)):
        raise ProfileError(f"{path}: unknown control ids: {unknown}")
    return profile
