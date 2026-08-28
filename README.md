# Retirement Planner

A single-user retirement planning tool that answers three linked questions, meant to be rerun as account balances, tax law, and personal timelines change:

1. **Longevity** — given a spending need, account mix, and market uncertainty, how confident should I be that the money lasts to a target age?
2. **Tax optimization** — given a specific state and income profile, what's the tax-efficient sequence of withdrawals and Roth conversions?
3. **Location comparison** — holding market risk constant, how much does state of residence move the outcome?

It is not a one-off analysis script — it's infrastructure: a deterministic tax/withdrawal engine, a Monte Carlo simulation core, an HTTP API, and a Streamlit UI, each independently testable and independently deployable.

**Non-goals**: multi-user/SaaS support, investment advice or trade execution, tax filing, real-time account aggregation. This is a single-household tool with manual, config-driven data entry.

## Architecture

Four layers, built incrementally as four independent features (`specs/001`–`008`), each with its own dependency boundary:

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

Each package's test suite runs independently (they share test-directory names, so a single combined `pytest` invocation across packages isn't supported):

```bash
pytest tests/                        # core library      -- 191 tests
pytest services/bff/tests/           # BFF API service    --  41 tests
pytest apps/streamlit_ui/tests/      # Streamlit UI       --  49 tests
```

## Project layout

```
src/retirement_planner/    Core library (scenario, tax, mechanics, comparison, simulation, reporting)
services/bff/               FastAPI HTTP/JSON API wrapping the core library
apps/streamlit_ui/          Streamlit UI, talking to the BFF over HTTP
examples/                   Runnable example (no CLI exists yet)
config/scenarios/           Saved scenario YAML files (gitignored contents; directory tracked)
docs/                       Requirements source, architecture notes, gap analysis
specs/                      Full spec -> plan -> tasks -> implementation record for every feature
tests/                      Core library tests (unit + integration)
```

## Development process

This project was built with a spec-driven workflow: every feature (`specs/NNN-*/`) has a `spec.md` (requirements, user-facing), `plan.md` (architecture, Constitution Check), `research.md`, `data-model.md`, `contracts/`, `quickstart.md`, and `tasks.md` (TDD-ordered, one checkbox per task) before any implementation code was written. `.specify/memory/constitution.md` records the project's governing principles (accuracy over cleverness, reproducibility, auditability, offline-first, performance budget) that every plan is checked against.

## License

[MIT](LICENSE)
