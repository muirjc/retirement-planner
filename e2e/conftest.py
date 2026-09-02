"""End-to-end test infrastructure. See README.md.

Session-scoped fixtures launch a real services/bff (uvicorn) instance and
a real apps/streamlit_ui (streamlit run) instance as subprocesses, each
pointed at an isolated temp scenarios directory -- never the real
config/scenarios/. Tests drive the Streamlit UI through a real browser
(Playwright, via pytest-playwright's own `page` fixture) exactly the way
a user would; nothing in this suite imports retirement_planner/rp_bff/
rp_ui directly -- this whole suite exercises the real HTTP+browser stack,
not Python internals (unit/integration coverage for those already lives
in tests/, services/bff/tests/, apps/streamlit_ui/tests/).
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
_LOCAL_APP_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
APP_PYTHON = _LOCAL_APP_PYTHON if _LOCAL_APP_PYTHON.exists() else Path(sys.executable)
"""The interpreter with retirement_planner/rp_bff/rp_ui installed.

Prefers .venv/bin/python over sys.executable when it exists, because
this suite's own pytest process may be running under a *different*
interpreter than the one those packages are installed into (this
repo's own local dev sandbox has exactly that split -- see README.md).
CI (.github/workflows/ci.yml) never creates a .venv at all -- it
installs every package directly into whichever single interpreter runs
pytest itself -- so there, sys.executable is correct and .venv/bin/python
would raise FileNotFoundError (rp-7x2: e2e-tests never actually ran in
CI until this session's own quality-gates fix let it start, which is
when this was first caught)."""
STREAMLIT_APP = REPO_ROOT / "apps" / "streamlit_ui" / "app.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_until_up(url: str, timeout: float = 30.0) -> None:
    """Polls url until it returns any non-5xx response, or raises once
    timeout elapses -- a starting Streamlit/uvicorn process refuses the
    connection outright for the first moment, not a slow response, so a
    plain retry loop is enough (no need to distinguish "not listening
    yet" from "listening but not ready")."""
    deadline = time.monotonic() + timeout
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=2.0)
            if response.status_code < 500:
                return
        except httpx.HTTPError as exc:
            last_exc = exc
        time.sleep(0.5)
    raise RuntimeError(f"{url} did not come up within {timeout}s") from last_exc


def _terminate(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


@dataclass(frozen=True)
class Stack:
    """The two base URLs a test needs -- ui_base_url to navigate
    Playwright's `page` to, bff_base_url for a test's own direct HTTP
    setup calls (e.g. seeding a scenario faster than driving the
    Scenarios page's form, for a test that isn't itself about that
    form)."""

    ui_base_url: str
    bff_base_url: str


@pytest.fixture(scope="session")
def e2e_stack():
    """Launches an isolated BFF + Streamlit UI pair for the whole test
    session, torn down at the end. Scenarios persist across tests within
    one session (a real user's own session works the same way) -- each
    test module uses its own distinctly-named scenario(s) to stay
    independent of the others, never relying on save/delete ordering
    across modules."""
    scenarios_dir = Path(tempfile.mkdtemp(prefix="rp_e2e_"))
    (scenarios_dir / "config" / "scenarios").mkdir(parents=True)

    bff_port = _free_port()
    ui_port = _free_port()
    bff_base_url = f"http://127.0.0.1:{bff_port}/api/v1"
    ui_base_url = f"http://127.0.0.1:{ui_port}"

    bff_process = subprocess.Popen(
        [str(APP_PYTHON), "-m", "uvicorn", "rp_bff.main:app", "--host", "127.0.0.1", "--port", str(bff_port)],
        cwd=scenarios_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    ui_process: subprocess.Popen | None = None
    try:
        _wait_until_up(f"{bff_base_url}/reference/states")

        ui_process = subprocess.Popen(
            [
                str(APP_PYTHON), "-m", "streamlit", "run", str(STREAMLIT_APP),
                "--server.port", str(ui_port), "--server.headless", "true", "--server.address", "127.0.0.1",
            ],
            cwd=scenarios_dir,
            env={**os.environ, "RP_BFF_BASE_URL": bff_base_url},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _wait_until_up(ui_base_url)

        yield Stack(ui_base_url=ui_base_url, bff_base_url=bff_base_url)
    finally:
        if ui_process is not None:
            _terminate(ui_process)
        _terminate(bff_process)
        shutil.rmtree(scenarios_dir, ignore_errors=True)
