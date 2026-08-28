"""Polish: confirms the Constitution Check's containment-boundary claim
empirically, not just by convention -- the core retirement_planner
package's own pyproject.toml must gain zero new dependencies from this
feature (plan.md Constitution Check, Complexity Tracking)."""

import tomllib
from pathlib import Path


def test_core_pyproject_toml_has_no_new_dependencies():
    repo_root = Path(__file__).resolve().parents[4]
    core_pyproject = repo_root / "pyproject.toml"
    data = tomllib.loads(core_pyproject.read_text())

    assert data["project"]["dependencies"] == ["pyyaml>=6.0"]
