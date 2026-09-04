# Retirement Planner

A single-user retirement planning tool that answers three linked questions, meant to be rerun as account balances, tax law, and personal timelines change:

1. **Longevity** — given a spending need, account mix, and market uncertainty, how confident should I be that the money lasts to a target age?
2. **Tax optimization** — given a specific state and income profile, what's the tax-efficient sequence of withdrawals and Roth conversions?
3. **Location comparison** — holding market risk constant, how much does state of residence move the outcome?

It is not a one-off analysis script — it's infrastructure: a deterministic tax/withdrawal engine, a Monte Carlo simulation core, an HTTP API, and a Streamlit UI, each independently testable and independently deployable.

**Non-goals**: multi-user/SaaS support, investment advice or trade execution, tax filing, real-time account aggregation. This is a single-household tool with manual, config-driven data entry.

For what this tool actually models — which regulations it implements, what math each engine uses, and what's still an illustrative placeholder — see [`docs/BRD.md`](docs/BRD.md). For a deeper architectural walkthrough with C4 diagrams, see [`docs/SOLUTION_ARCHITECTURE.md`](docs/SOLUTION_ARCHITECTURE.md). For day-to-day operating procedure — starting/stopping the stack, health checks, backups, and troubleshooting — see [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

## Architecture

Three layers, built incrementally as 28 spec-driven features (`specs/001`–`028`, one `spec.md` → `plan.md` → `tasks.md` per feature), each with its own dependency boundary:

```
┌─────────────────────────┐
│  apps/streamlit_ui       │  Streamlit UI -- scenario entry, run/compare,
│  (rp-ui)                 │  fan charts, CSV export. Talks to the BFF over
│                           │  HTTP only -- no import of the core library.
└────────────┬──────────────┘
             │ HTTP/JSON
┌────────────▼──────────────┐
│  services/bff             │  FastAPI BFF (backend-for-frontend) --
│  (rp-bff)                 │  the one HTTP/JSON contract any future UI
│                           │  (a JS SPA, a desktop wrapper) builds against.
└────────────┬──────────────┘
             │ import
┌────────────▼──────────────┐
│  src/retirement_planner   │  The core library -- pure Python, no HTTP,
│                           │  no UI framework. Usable standalone from a
│                           │  script or notebook (see examples/).
└────────────────────────────┘
```

Each of the three packages has its own `pyproject.toml` and its own dependency set — the core library only ever depends on `pyyaml`; `fastapi`/`uvicorn` are confined to `services/bff`; `streamlit`/`httpx`/`plotly` are confined to `apps/streamlit_ui`. Every dependency boundary is enforced by a test, not just convention (`test_dependency_containment.py` in each of the two outer packages).

### Core library subpackages

`src/retirement_planner/` is six subpackages, each depending only on the ones before it:

| Subpackage | Responsibility |
|---|---|
| `scenario` | Household/account/scenario config -- YAML parse, validate, save/load |
| `tax` | Federal + state tax calculation (currently `SC`, `DE`, `FL`), Social Security taxability |
| `mechanics` | RMDs, Roth conversions, withdrawal sequencing -- one plan-year at a time |
| `comparison` | Deterministic paired-draw comparison across states/strategies/claiming ages |
| `simulation` | Monte Carlo engine -- parametric and historical-bootstrap return paths, stress scenarios, survival-adjusted scoring |
| `reporting` | Summary statistics and CSV export, shared by the BFF's JSON and CSV responses |

## Getting started

Requires Python 3.11+.

```bash
# Core library
pip install -e ".[dev]"
pytest tests/

# Run the reference scenario end-to-end (no CLI exists yet -- this is
# the runnable example)
python examples/reference_scenario.py
```

### Running the full stack (API + UI)

The BFF and UI are separate packages; install and run each in the same environment as the core library (an editable install of the core library must already be present):

```bash
pip install -e "services/bff[dev]"
pip install -e "apps/streamlit_ui[dev]"

# Terminal 1 -- the API, on 127.0.0.1 only (never bound to a public interface)
uvicorn rp_bff.main:app --app-dir services/bff/src --host 127.0.0.1 --port 8000

# Terminal 2 -- the UI, pointed at that API
RP_BFF_BASE_URL=http://127.0.0.1:8000/api/v1 streamlit run apps/streamlit_ui/app.py
```

Open the URL Streamlit prints (default `http://localhost:8501`) to create a scenario, run a Monte Carlo or deterministic simulation, compare candidates, and download results as CSV. The API's interactive docs are at `http://127.0.0.1:8000/docs`.

## Testing

Four independent suites, one per layer of the test pyramid (each package's own suite runs independently — they share test-directory names, so a single combined `pytest` invocation across packages isn't supported):

```bash
pytest tests/                        # core library       -- 622 tests
pytest services/bff/tests/           # BFF API service     -- 102 tests
pytest apps/streamlit_ui/tests/      # Streamlit UI         -- 152 tests
cd e2e && ../.venv/bin/python3.12 -m pytest -q   # browser-driven e2e -- 16 tests
```

`e2e/` is the outermost layer: it launches a real BFF + real Streamlit UI as subprocesses and drives them through a real headless Chromium browser via Playwright, against an isolated scratch `config/scenarios/` directory — see [`e2e/README.md`](e2e/README.md) for one-time setup (it needs its own `pip install` and `playwright install chromium`, and runs under a specific interpreter — the README explains why).

### Quality gates

Each of the three packages also has its own lint (`ruff`), type-check (`mypy`), Python security scan (`bandit`), and dependency CVE scan (`pip-audit`) — install via each package's own `dev` extra (already included in the `pip install -e ".[dev]"` commands above):

```bash
ruff check src/ tests/                          # lint -- core
ruff check services/bff/                        # lint -- BFF
ruff check apps/streamlit_ui/                    # lint -- Streamlit UI
mypy --config-file pyproject.toml src/retirement_planner                                   # type check -- core
mypy --config-file services/bff/pyproject.toml services/bff/src/rp_bff                      # type check -- BFF
mypy --config-file apps/streamlit_ui/pyproject.toml apps/streamlit_ui/src/rp_ui             # type check -- Streamlit UI
bandit -r src/retirement_planner -ll             # security scan -- core
bandit -r services/bff/src/rp_bff -ll            # security scan -- BFF
bandit -r apps/streamlit_ui/src/rp_ui -ll        # security scan -- Streamlit UI
pip-audit --skip-editable                        # dependency CVE scan, all three packages' dependencies
```

### CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every push and every PR to `main`: the quality gates above plus all four test suites, then (needing that job to pass first) the e2e suite and an [OWASP ZAP](https://www.zaproxy.org/) API security scan (a DAST pen test, not just static analysis) against a live BFF instance, driven by its own OpenAPI spec and thresholded by [`.zap/rules.tsv`](.zap/rules.tsv) — its report is uploaded as a build artifact regardless of pass/fail. The ZAP job runs report-only (`continue-on-error`) pending its first few real-runner calibration passes (its own comment in `ci.yml` explains why — it could not be executed end-to-end in the environment this pipeline was authored in); every other check, including mypy (rp-cgj triaged and fixed its initial 28-finding baseline), is blocking.

## Project layout

```
src/retirement_planner/    Core library (scenario, tax, mechanics, comparison, simulation, reporting)
services/bff/               FastAPI HTTP/JSON API wrapping the core library
apps/streamlit_ui/          Streamlit UI, talking to the BFF over HTTP
e2e/                         Browser-driven Playwright suite over the real BFF + UI, together
examples/                   Runnable example (no CLI exists yet)
config/scenarios/           Saved scenario YAML files (gitignored contents; directory tracked)
docs/                       Requirements source, BRD, solution architecture, gap analysis
specs/                      Full spec -> plan -> tasks -> implementation record for every feature
tests/                      Core library tests (unit + integration)
```

## Development process

This project was built with a spec-driven workflow: every feature (`specs/NNN-*/`) has a `spec.md` (requirements, user-facing), `plan.md` (architecture, Constitution Check), `research.md`, `data-model.md`, `contracts/` (where the feature changes a public interface), `quickstart.md`, and `tasks.md` (dependency-ordered, one checkbox per task) before any implementation code was written. `.specify/memory/constitution.md` records the project's governing principles (accuracy over cleverness, reproducibility, auditability, offline-first, performance budget) that every plan is checked against.

**Keeping this README, `docs/BRD.md`, `docs/SOLUTION_ARCHITECTURE.md`, and `docs/RUNBOOK.md` current is part of finishing a feature**, not a separate cleanup pass — see the "Keeping this document current" note at the top of each of those docs, and `CLAUDE.md`'s Architecture Overview section.

## License

[MIT](LICENSE)
