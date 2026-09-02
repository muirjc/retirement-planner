---
name: run-retirement-planner
description: Build, run, and drive the retirement-planner app (BFF + Streamlit UI). Use when asked to start the app, run the full stack, take a screenshot of the Streamlit UI, smoke-test the app end-to-end, or interact with the running app.
---

This is a two-process web app: a FastAPI BFF (`services/bff`) and a Streamlit UI (`apps/streamlit_ui`), both importing the core `retirement_planner` library in-process (no separate core service). Drive it via `.claude/skills/run-retirement-planner/driver.py`, which reuses `e2e/conftest.py`'s own tested launch/readiness helpers so it never drifts from what the project's real e2e suite already verifies works. All paths below are relative to the repo root.

## Prerequisites

The three project packages (needed by both `start` and `smoke`) — this exact command is idempotent, verified by re-running it in this container:

```bash
python3 -m pip install --break-system-packages -q -e ".[dev]" -e "services/bff[dev]" -e "apps/streamlit_ui[dev]"
```

`smoke` additionally needs Playwright's Python bindings + a Chromium binary under `.venv/bin/python3.12` specifically (this repo's `.venv/bin/python` is a symlink to the system `python3` that has the three packages above; `.venv/bin/python3.12` is a *separate* interpreter — see Gotchas). Install via `e2e/`'s own one-time setup (rp-xwm: this used to fail with a setuptools flat-layout package-discovery error — fixed and re-verified from a clean-uninstall state in this session, including a full 16-test e2e run afterward):

```bash
cd e2e && ../.venv/bin/python3.12 -m pip install -e ".[dev]" && ../.venv/bin/python3.12 -m playwright install chromium && cd ..
```

## Run (agent path)

**Smoke test** — launches BFF+UI on free ports, drives the home page and Scenarios page with Playwright, screenshots both, checks for browser console errors, tears down, exits non-zero on failure:

```bash
.venv/bin/python3.12 .claude/skills/run-retirement-planner/driver.py smoke
```

Screenshots land in `.claude/skills/run-retirement-planner/screenshots/` (`01_home.png`, `02_scenarios.png`, overwritten each run — gitignored).

**Leave it running** — launches BFF (port 8000) + UI (port 8501) and blocks until Ctrl-C (or any stop signal — SIGINT and SIGTERM both trigger clean teardown), for manual poking, `curl`, or opening the UI in a real browser:

```bash
.venv/bin/python3.12 .claude/skills/run-retirement-planner/driver.py start
# BFF:       http://127.0.0.1:8000  (docs at /docs)
# Streamlit: http://127.0.0.1:8501
```

Both subcommands use an isolated temp scenarios directory (never the real `config/scenarios/`) and free/fixed ports as noted — safe to run alongside a manually-started instance on different ports (`--bff-port`/`--ui-port` on `start`).

| command | what it does |
|---|---|
| `driver.py smoke` | launch, drive, screenshot, teardown, exit code reflects success |
| `driver.py start [--bff-port N] [--ui-port N]` | launch and block until stopped |

## Run (human path)

Same two-terminal setup `README.md` documents, using the interpreter that actually has the packages installed (`.venv/bin/python`, **not** bare `uvicorn`/`streamlit` — see Gotchas):

```bash
# Terminal 1
.venv/bin/python -m uvicorn rp_bff.main:app --app-dir services/bff/src --host 127.0.0.1 --port 8000
# Terminal 2
RP_BFF_BASE_URL=http://127.0.0.1:8000/api/v1 .venv/bin/python -m streamlit run apps/streamlit_ui/app.py
```

Open `http://localhost:8501`. Ctrl-C each terminal to stop.

## Test

```bash
pytest tests/                                   # core library
pytest services/bff/tests/                       # BFF API service
pytest apps/streamlit_ui/tests/                  # Streamlit UI
cd e2e && ../.venv/bin/python3.12 -m pytest -q   # browser-driven e2e
```

---

## Gotchas

- **`uvicorn`/`streamlit`'s installed entry-point scripts have a hardcoded `#!/usr/bin/python3.12` shebang, but the three project packages are installed under the *other* `python3` (3.14) in this container.** Running bare `uvicorn ...` or `streamlit run ...` fails with `ModuleNotFoundError: No module named 'retirement_planner'` — the script runs under python3.12, which never had the packages installed into it. Fix: invoke via `.venv/bin/python -m uvicorn ...` / `.venv/bin/python -m streamlit ...` (`.venv/bin/python` is a symlink to the system `python3` that *does* have them) instead of the bare scripts. `e2e/conftest.py`'s own `APP_PYTHON` constant already encodes this fix — this skill's driver imports and reuses it rather than re-deriving it.
- **Two different interpreters are both called "the venv" and neither is what it sounds like.** `.venv/bin/python3.12` has Playwright + Chromium (used to *drive* the browser); `.venv/bin/python` (3.14) has `retirement_planner`/`rp_bff`/`rp_ui` (used to *run* the app subprocesses). `driver.py smoke` must itself run under `.venv/bin/python3.12` (it imports `playwright.sync_api`) while internally launching the app subprocesses under `.venv/bin/python` (via the imported `e2e_conftest.APP_PYTHON`) — mixing these up in either direction breaks.
- **A stop signal other than SIGINT leaks the subprocesses.** Python's default `SIGTERM` disposition kills the process immediately without running `try/finally` — confirmed by running `driver.py start` under `timeout 8 ...`, which sends `SIGTERM` and left an orphaned Streamlit process behind before this was fixed. `driver.py` now installs a `SIGTERM` handler that raises `KeyboardInterrupt` so the same cleanup path runs for both signals — if you fork this driver for another project, don't drop that handler.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'retirement_planner'` on launch**: you ran the bare `uvicorn`/`streamlit` script. Use `.venv/bin/python -m uvicorn`/`.venv/bin/python -m streamlit` instead (see Gotchas).
- **`driver.py smoke` fails with `ModuleNotFoundError: No module named 'playwright'`**: you ran it under the wrong interpreter. Use `.venv/bin/python3.12 .claude/skills/run-retirement-planner/driver.py smoke`, not `.venv/bin/python` or bare `python3`.
- **A leftover `uvicorn`/`streamlit` process from a previous run holds the port**: `ps aux | grep -E "uvicorn|streamlit"` and `kill` the PIDs — `driver.py start` stopped with anything other than SIGKILL should already avoid this (see Gotchas), but a process started outside the driver (e.g. by hand, or by another agent session) won't self-clean.
