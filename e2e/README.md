# End-to-end tests

Full-stack, browser-driven tests: a real `services/bff` (uvicorn) instance
and a real `apps/streamlit_ui` (`streamlit run`) instance, each launched
as a subprocess pointed at an isolated temp `config/scenarios/` directory
(never the real one), driven through a real headless Chromium browser via
[Playwright](https://playwright.dev/python/). This is the fourth,
outermost layer of this project's test pyramid — `tests/`,
`services/bff/tests/`, and `apps/streamlit_ui/tests/` each already cover
their own layer in isolation (pure engine logic, HTTP contract,
Streamlit-script-level UI logic respectively); this suite instead
confirms the real, wired-together stack actually works end to end,
through the same browser interactions a user would make.

## One-time setup

This project's main `.venv` (`../​.venv`) was created with Python 3.12
but also has a parallel Python 3.14 site-packages tree with `pip`
unavailable there — so Playwright (and this suite's other dependencies)
are installed against `../.venv/bin/python3.12` specifically, not
`../.venv/bin/python`. The BFF/Streamlit subprocesses this suite launches
always use `../.venv/bin/python` (3.14, the interpreter with
`retirement_planner`/`rp_bff`/`rp_ui` actually installed) regardless of
which interpreter runs pytest itself — see `conftest.py`'s own
`APP_PYTHON` constant.

```bash
cd e2e
../.venv/bin/python3.12 -m pip install -e ".[dev]"
../.venv/bin/python3.12 -m playwright install chromium
```

(`playwright install --with-deps` additionally installs the OS-level
libraries Chromium needs via `apt` — skip `--with-deps` and use plain
`playwright install chromium` in a sandboxed environment without root/
`sudo` access; the browser binary alone is enough as long as the host
already has the needed shared libraries, which most desktop/CI Linux
images do.)

## Running

```bash
cd e2e
../.venv/bin/python3.12 -m pytest -q
```

Each test module's own fixtures create whatever scenario(s) they need
(via a direct HTTP call to the isolated BFF instance, or by driving the
Scenarios page's own form for `test_scenarios_page.py`, which is
specifically testing that form) — no fixed startup dataset, and nothing
here ever touches the real `config/scenarios/` directory.

`conftest.py`'s `e2e_stack` fixture is session-scoped: one BFF+Streamlit
pair for the whole run, torn down at the end. Pass `-x` to stop at the
first failure while iterating, since a whole session's worth of tests
share that one running stack.

Slower than the other three suites (a real browser, a real Streamlit
rerun cycle per interaction) — expect low tens of seconds, not
sub-second, for the full run.
