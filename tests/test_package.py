from importlib.metadata import version

import controlproof


def test_version_comes_from_distribution_metadata() -> None:
    assert controlproof.__version__ == version("controlproof")
