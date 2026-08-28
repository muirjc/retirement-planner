"""FastAPI dependencies shared across route modules.

get_scenarios_dir() is the seam that lets tests isolate scenario storage
(via app.dependency_overrides, see tests/conftest.py) without touching
production's default config/scenarios/ directory -- a small addition
discovered during implementation, not called out by name in plan.md's
Project Structure, but a direct consequence of route handlers needing to
pass a scenarios_dir through to 001's storage functions testably.
"""

from __future__ import annotations

from pathlib import Path


def get_scenarios_dir() -> Path | None:
    """Returns the scenarios_dir to pass through to 001's storage
    functions. None (the production default) means "use 001's own
    default" (config/scenarios/, relative to the current working
    directory) -- tests override this dependency to point at an isolated
    tmp_path instead."""
    return None
