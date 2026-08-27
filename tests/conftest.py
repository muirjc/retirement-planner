"""Shared pytest fixtures.

Every test that touches scenario storage MUST use `scenario_store_dir` (or a
fixture that depends on it) instead of the real `config/scenarios/` directory,
so tests never read or write repository files.
"""

import pytest


@pytest.fixture
def scenario_store_dir(tmp_path):
    """A temporary directory standing in for config/scenarios/ during a test.

    Pass this to store.py functions via their `scenarios_dir` keyword
    argument, e.g. `save_scenario(scenario, scenarios_dir=scenario_store_dir)`.
    """
    directory = tmp_path / "scenarios"
    directory.mkdir()
    return directory
