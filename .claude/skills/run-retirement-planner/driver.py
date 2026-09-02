#!/usr/bin/env python3
"""Driver for run-retirement-planner (see SKILL.md).

Launches an isolated BFF (uvicorn) + Streamlit UI pair exactly the way
e2e/conftest.py's own tested `e2e_stack` fixture does -- this module
imports that fixture's own helpers (APP_PYTHON, _free_port,
_wait_until_up, _terminate) directly rather than re-deriving them, so
the driver never drifts from what the e2e suite already verifies works.

Two subcommands:

    start   Launches BFF+UI on fixed ports (8000/8501 by default),
            prints their URLs, and blocks until Ctrl-C -- tears down
            cleanly on exit. Use this to leave the stack up for manual
            poking, curl, or a browser you open yourself.

    smoke   Launches BFF+UI on free (auto-chosen) ports, drives the
            home page and the Scenarios page with Playwright,
            screenshots both to ./screenshots/, checks for browser
            console errors, tears down. Exits non-zero (and prints
            why) if anything failed -- this is the "prove it still
            works" entry point.

Must run under an interpreter with `playwright`'s Python bindings and
a Chromium binary already installed for `smoke` -- see SKILL.md
Prerequisites (../.venv/bin/python3.12, this repo's e2e/ setup).
`start` has no such requirement (it only launches subprocesses under
APP_PYTHON, never imports playwright itself).
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "e2e"))
import conftest as e2e_conftest  # noqa: E402 -- see sys.path.insert above

SCREENSHOTS_DIR = Path(__file__).resolve().parent / "screenshots"


def _launch_stack(bff_port: int, ui_port: int) -> tuple[subprocess.Popen, subprocess.Popen, Path]:
    """Mirrors e2e/conftest.py's e2e_stack fixture body exactly (same
    isolated scenarios dir, same launch commands, same readiness
    polling), just as a plain function instead of a pytest fixture so
    it can be driven from a standalone script."""
    scenarios_dir = Path(tempfile.mkdtemp(prefix="rp_driver_"))
    (scenarios_dir / "config" / "scenarios").mkdir(parents=True)

    bff_base_url = f"http://127.0.0.1:{bff_port}/api/v1"
    ui_base_url = f"http://127.0.0.1:{ui_port}"

    bff_process = subprocess.Popen(
        [str(e2e_conftest.APP_PYTHON), "-m", "uvicorn", "rp_bff.main:app",
         "--host", "127.0.0.1", "--port", str(bff_port)],
        cwd=scenarios_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    e2e_conftest._wait_until_up(f"{bff_base_url}/reference/states")

    ui_process = subprocess.Popen(
        [str(e2e_conftest.APP_PYTHON), "-m", "streamlit", "run", str(e2e_conftest.STREAMLIT_APP),
         "--server.port", str(ui_port), "--server.headless", "true", "--server.address", "127.0.0.1"],
        cwd=scenarios_dir, env={**os.environ, "RP_BFF_BASE_URL": bff_base_url},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    e2e_conftest._wait_until_up(ui_base_url)

    return bff_process, ui_process, scenarios_dir


def cmd_start(args: argparse.Namespace) -> int:
    bff_process, ui_process, scenarios_dir = _launch_stack(args.bff_port, args.ui_port)
    print(f"BFF:       http://127.0.0.1:{args.bff_port}  (docs at /docs)")
    print(f"Streamlit: http://127.0.0.1:{args.ui_port}")
    print(f"Scenarios dir (isolated, not the real config/scenarios/): {scenarios_dir}")
    print("Ctrl-C to stop.")

    # Python's default SIGTERM disposition kills the process immediately,
    # WITHOUT running the try/finally below -- `except KeyboardInterrupt`
    # only ever catches SIGINT. A caller stopping this script via `timeout`,
    # `kill` (no -9), or a supervisor's default stop signal sends SIGTERM,
    # not SIGINT -- without this handler that leaks the uvicorn/streamlit
    # subprocesses (confirmed: `timeout 8 ... start ...` leaked a Streamlit
    # process before this handler was added). Translating SIGTERM into the
    # same KeyboardInterrupt path below makes every stop signal clean up.
    def _on_sigterm(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _on_sigterm)

    try:
        while True:
            time.sleep(1)
            if bff_process.poll() is not None:
                print("BFF process exited unexpectedly", file=sys.stderr)
                return 1
            if ui_process.poll() is not None:
                print("Streamlit process exited unexpectedly", file=sys.stderr)
                return 1
    except KeyboardInterrupt:
        pass
    finally:
        e2e_conftest._terminate(ui_process)
        e2e_conftest._terminate(bff_process)
        shutil.rmtree(scenarios_dir, ignore_errors=True)
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    from playwright.sync_api import sync_playwright

    bff_port = e2e_conftest._free_port()
    ui_port = e2e_conftest._free_port()
    bff_process, ui_process, scenarios_dir = _launch_stack(bff_port, ui_port)
    ui_base_url = f"http://127.0.0.1:{ui_port}"

    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    console_errors: list[str] = []
    ok = True
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

            page.goto(ui_base_url, wait_until="networkidle", timeout=30_000)
            page.wait_for_selector("text=Retirement Planner", timeout=15_000)
            page.wait_for_selector("text=Connected to the backend", timeout=15_000)
            page.screenshot(path=str(SCREENSHOTS_DIR / "01_home.png"))
            print(f"[ok] home page loaded, backend connected -> {SCREENSHOTS_DIR / '01_home.png'}")

            page.click("text=Scenarios")
            page.wait_for_selector("text=Load an existing scenario", timeout=15_000)
            page.screenshot(path=str(SCREENSHOTS_DIR / "02_scenarios.png"))
            print(f"[ok] Scenarios page loaded -> {SCREENSHOTS_DIR / '02_scenarios.png'}")

            browser.close()
    except Exception as exc:  # noqa: BLE001 -- smoke script: report and fail, don't traceback-crash
        print(f"[FAIL] {exc}", file=sys.stderr)
        ok = False
    finally:
        e2e_conftest._terminate(ui_process)
        e2e_conftest._terminate(bff_process)
        shutil.rmtree(scenarios_dir, ignore_errors=True)

    if console_errors:
        print(f"[FAIL] browser console errors: {console_errors}", file=sys.stderr)
        ok = False
    else:
        print("[ok] no browser console errors")

    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Launch BFF+UI and block until Ctrl-C")
    start_parser.add_argument("--bff-port", type=int, default=8000)
    start_parser.add_argument("--ui-port", type=int, default=8501)
    start_parser.set_defaults(func=cmd_start)

    smoke_parser = subparsers.add_parser("smoke", help="Launch, drive with Playwright, screenshot, tear down")
    smoke_parser.set_defaults(func=cmd_smoke)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
