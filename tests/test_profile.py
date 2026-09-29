from pathlib import Path

import pytest

from controlproof.profile import ProfileError, load_profile
from stub_controls import FIXTURES, STUBS

GOOD = """\
schema_version: "1.0.0"
id: demo
title: Demo
provider: aws
controls:
  - id: sc-13
  - id: ac-2
    params: {outcome: pass}
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "profile.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_valid_profile_loads(tmp_path: Path) -> None:
    profile = load_profile(write(tmp_path, GOOD), STUBS)
    assert profile.control_ids == ("ac-2", "sc-13")
    assert profile.controls[1].params == {"outcome": "pass"}


def test_fixture_profiles_load() -> None:
    for path in sorted(FIXTURES.glob("*.yaml")):
        assert load_profile(path, STUBS).controls


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (GOOD + "extra: 1\n", "extra"),
        (GOOD.replace("title: Demo\n", "title: Demo\ntitle: Again\n"), "duplicate key 'title'"),
        (GOOD + "  - id: ac-2\n", "more than once"),
        (GOOD.replace("sc-13", "sc-28"), "unknown control ids: ['sc-28']"),
        (GOOD.replace("sc-13", "SC-13"), "controls.0.id"),
        (GOOD.replace('"1.0.0"', '"2.0.0"'), "schema_version"),
        (GOOD.replace("provider: aws", "provider: gcp"), "provider"),
        ("- just\n- a list\n", "<root>"),
        ("id: [unclosed\n", "not valid YAML"),
        (
            GOOD.replace(
                "controls:\n  - id: sc-13\n  - id: ac-2\n    params: {outcome: pass}\n",
                "controls: []\n",
            ),
            "controls",
        ),
    ],
)
def test_bad_profiles_are_rejected(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(ProfileError, match=None) as caught:
        load_profile(write(tmp_path, text), STUBS)
    assert message in str(caught.value)


def test_a_missing_profile_is_a_profile_error(tmp_path: Path) -> None:
    with pytest.raises(ProfileError, match="cannot read profile"):
        load_profile(tmp_path / "absent.yaml", STUBS)
