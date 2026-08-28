"""Polish (T037): confirms the Constitution Check's containment-boundary
claim empirically, not just by convention -- mirroring 007's own
test_dependency_containment.py one layer further out. This package must
declare neither `retirement_planner` nor `rp_bff` as a dependency
(research.md §1, structural not conventional enforcement), and neither
the core package's nor 007's own pyproject.toml may have gained anything
from this feature.
"""

import ast
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_streamlit_ui_pyproject_declares_no_core_or_bff_dependency():
    data = tomllib.loads((REPO_ROOT / "apps" / "streamlit_ui" / "pyproject.toml").read_text())
    dependencies = data["project"]["dependencies"]
    assert not any(dep.startswith("retirement_planner") or dep.startswith("retirement-planner") for dep in dependencies)
    assert not any(dep.startswith("rp_bff") or dep.startswith("rp-bff") for dep in dependencies)


def test_core_pyproject_toml_has_no_new_dependencies():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    assert data["project"]["dependencies"] == ["pyyaml>=6.0"]


def test_bff_pyproject_toml_is_unchanged_by_this_feature():
    data = tomllib.loads((REPO_ROOT / "services" / "bff" / "pyproject.toml").read_text())
    assert data["project"]["dependencies"] == ["retirement_planner", "fastapi>=0.110", "uvicorn[standard]>=0.29"]


def test_instructions_page_imports_nothing_from_api_client_or_core_or_bff():
    """009's own Constitution Check: this is the one page in the package
    that makes zero HTTP calls -- enforced here at the source level
    (an import, not just an unused-at-runtime capability), not only by
    the AppTest-level "renders with no mock transport installed" test."""
    forbidden_prefixes = ("rp_ui.api_client", "retirement_planner", "rp_bff")
    for relative_path in (
        "apps/streamlit_ui/src/rp_ui/instructions_content.py",
        "apps/streamlit_ui/pages/0_Instructions.py",
    ):
        source = (REPO_ROOT / relative_path).read_text()
        tree = ast.parse(source, filename=relative_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module] if node.module else []
            else:
                continue
            for name in names:
                assert not any(name.startswith(prefix) for prefix in forbidden_prefixes), (
                    f"{relative_path} imports {name!r} -- forbidden for this feature"
                )
