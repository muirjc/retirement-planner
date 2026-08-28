# Front-End Architecture: BFF + Reporting + First UI

**Status**: Requirements/architecture recommendation — no code implements this yet.

**Purpose**: `retirement_planner` (specs `001`–`005`) is a complete, tested, offline retirement-planning engine with **no way for a human to use it** — `docs/remaining_scope.md` already identified this precisely: §3.6 "Reporting/Output" from `docs/initial_requirement.md` has zero spec coverage, and the source document's own `cli.py`/notebook entry point was never built. This document answers "what is required to put a professional-looking front end on this library, for data entry, visualization, and reporting" and lays out a recommended architecture and phased delivery plan for the three future features that would build it — `006 Reporting & Aggregation`, `007 BFF API Service`, `008 Streamlit UI` — in the same style each of `001`–`005`'s specs used for their own scope notes.

**Direction constraint (set explicitly, not derived)**: build a BFF (backend-for-frontend) layer first, decoupling the core library from any specific UI technology, because the long-term goal is multiple front-end UIs, not just one. The API boundary must be UI-agnostic; a UI choice must be swappable later without reworking the boundary.

---

## 1. Layering

Four components, not three — the JSON serialization concern is pulled out into its own named seam rather than folded into an undifferentiated "BFF":

| # | Component | Lives in | I/O | New dependencies |
|---|---|---|---|---|
| a | `retirement_planner.reporting` | inside the core library, sibling to `simulation/` | none — pure functions | none |
| b | wire-format serializer (`to_jsonable`) | inside the BFF package | none (pure transform) | none (stdlib `dataclasses`/`json`) |
| c | BFF route/handler layer | new BFF package | HTTP, calls into (a)/(b) plus `scenario`/`tax`/`mechanics` registries | `fastapi`, `uvicorn` |
| d | first UI client | new UI package | HTTP only, to (c) | `streamlit`, `httpx`, `plotly` |

`reporting` becomes the sixth subpackage in the existing dependency chain — `scenario`, `tax` → `mechanics` → `comparison` → `simulation` → **`reporting`** — continuing the project's exact layering discipline (each of `001`–`005` is a strictly acyclic, dependency-ordered subpackage). It is the first subpackage to depend on all five others, mirroring how `005`'s own plan.md described itself as "the first subpackage to depend on all four" of its predecessors.

`reporting`'s scope closes the specific §3.6 requirements `docs/remaining_scope.md` names as unaddressed:

- **`aggregation.py`**: a `SummaryStatistics` dataclass (success rate, median/percentile ending balance, median depletion age, and **`median_lifetime_tax_paid`** — computed as `statistics.median(p.outcome.cumulative_tax_paid for p in run.path_results)`, which exists nowhere in the codebase today despite the source document explicitly asking for it) plus `unverified_figure_names: list[str]` — first-class surfacing of Principle III's "needs verification" flag, so a UI never has to dig it out of nested `figures_used` lists itself.
- **`export.py`**: CSV row-shaping functions (`simulation_run_to_csv_rows()`, `comparison_result_to_csv_rows()`) plus a stdlib-`csv`-based `rows_to_csv_text()`. CSV generation stays "pure" in the same sense `scenario/store.py`'s `yaml.safe_dump()` call is — deterministic, offline, no third-party dependency.

Explicitly **not** in `reporting`:
- **Chart rendering** — `SimulationRun.percentile_bands` is already fan-chart-shaped data; drawing pixels is squarely the UI layer's job.
- **JSON serialization** — a transport-boundary concern coupled to "what does JSON require," not a domain computation. A future non-HTTP consumer of `reporting` (a script, a notebook) should never need it.

---

## 2. New dependency: where it lives

**Recommendation, confirmed with the user: a fully separate package per component, not an optional extra on the core library's `pyproject.toml`.**

Today's core `pyproject.toml` has exactly `pyyaml` + `pytest[dev]`. Every one of `002`–`005`'s `research.md` invokes "no new third-party runtime dependency" as precedent; `005` specifically rejected `numpy` using a "would this dependency solve the actual problem" test. Applying that same test here: it **passes** for the BFF, because serving an HTTP boundary is new capability the core library itself never needs and never will — `retirement_planner` must stay independently installable (for a notebook, a future CLI, anything) without ever pulling in `fastapi`/`uvicorn` transitively. An `[project.optional-dependencies] api = [...]` extra on the *core* package would still make its own metadata permanently advertise "this library optionally speaks HTTP" — the wrong ownership direction given the multi-UI goal (a service depends on a library, never the reverse).

**Layout** (monorepo, not separate git repos — splitting repos isn't justified for a single-developer project today, but an independent `pyproject.toml` per component keeps that door open later):

```
src/retirement_planner/          # unchanged core, still pyyaml-only, + new reporting/ subpackage
services/bff/
  pyproject.toml                 # deps: retirement_planner (editable path dep), fastapi, uvicorn[standard]
  src/rp_bff/
    main.py                      # FastAPI app + route registration
    routes/                      # scenarios.py, reference.py, simulations.py, comparisons.py, reports.py
    serialization.py             # to_jsonable()
    schemas.py                   # Pydantic request models
apps/streamlit_ui/
  pyproject.toml                 # deps: streamlit, httpx, plotly — explicitly NOT retirement_planner
  app.py
```

**Framework: FastAPI.** Automatic OpenAPI schema generation is what makes "multi-UI" concrete rather than aspirational — a future JS SPA can generate a typed client straight from `/openapi.json` with zero hand-written contract duplication, and the built-in Swagger UI (`/docs`) is itself a usable manual-testing surface that exists before any real UI is built (useful for validating `007` independently, before `008` exists).

**Exact packages, and where they're added:**

| Package | Purpose | Lives in |
|---|---|---|
| `fastapi` | routing, request validation, OpenAPI generation | `services/bff/pyproject.toml` |
| `uvicorn[standard]` | ASGI server; `standard` extra pulls in perf (`uvloop`/`httptools`) and dev-reload (`watchfiles`) — still a local process, no internet dependency | `services/bff/pyproject.toml` |
| `pydantic` | transitive via FastAPI, not separately pinned | `services/bff/pyproject.toml` |
| `python-multipart` | likely needed if a "paste/upload a YAML scenario file" endpoint uses multipart form data — flagged now, not discovered late | `services/bff/pyproject.toml` |
| `httpx` | HTTP client for the UI to talk to the BFF | `apps/streamlit_ui/pyproject.toml` |
| `streamlit` | the UI framework itself | `apps/streamlit_ui/pyproject.toml` |
| `plotly` (or `altair`) | fan-chart/overlay-chart rendering | `apps/streamlit_ui/pyproject.toml` |

Core's `pyproject.toml` gains **zero** new dependencies from this entire program.

---

## 3. The JSON serialization gap

**No JSON serialization exists anywhere in the codebase today** — confirmed by direct inspection: every result type (`SimulationRun`, `ComparisonResult`, `FigureUsage`, `PlanProjection`, etc.) is a plain `@dataclass`, and no `to_dict()`/`asdict()`/JSON-encoder helper exists anywhere except a private, scenario-only, YAML-specific helper (`scenario/store.py::_scenario_to_dict()`) that isn't exported and isn't JSON.

Lives in `services/bff/serialization.py` (not `reporting` — it's a transport concern, per §1). A single recursive `to_jsonable(obj) -> Any` function, not bare `dataclasses.asdict()` (which recurses uniformly and can't special-case the problem below):

- **`date` fields** (`FigureUsage.last_verified`, `SurvivalCurve.last_verified`) → `obj.isoformat()`.
- **`PercentileBand.percentiles: dict[float, float]`** — a non-string-keyed dict, **not valid JSON as-is** → `[{"percentile": k, "value": v} for k, v in sorted(d.items())]`. Deliberately array-of-objects, not stringified-float-keys: lossless (no float→string→float round-trip ambiguity), self-describing, and it's exactly the shape a chart library (Plotly or otherwise) wants natively for a fan chart — the serializer shapes data for its consumer's actual use, not just technical JSON legality.
- **`tuple` fields** (`StrategyConfiguration.conversion_window`, `BracketTable`) → JSON array, recursively converted.
- **dataclass instances** → recurse field-by-field via `dataclasses.fields()`.
- **list / nested dataclass / plain scalar** → recurse / pass through.

**Response-model trade-off, stated explicitly rather than silently accepted:**
- **Request** bodies (scenario payloads, run parameters) get real Pydantic models in `schemas.py` — validation quality directly matters here for a professional UI (clear 422 errors on a malformed scenario).
- **Response** bodies for simulation/comparison results are plain `to_jsonable()` output, not hand-mirrored Pydantic models. Hand-authoring a full nested response schema (`PlanProjection` → `PlanYearProjection` → `PlanYearMechanicsResult` → …) would need re-syncing every time `002`–`005` add a field, for read-only computed output where that maintenance cost isn't yet justified. OpenAPI docs for these routes will show a generic/`Any` schema for v1 — an explicit, acceptable gap, not an oversight. Full response typing is reasonable future work once the API shape stabilizes.

---

## 4. BFF API surface sketch (`/api/v1`)

Endpoint groups, not full code — enough specificity to be actionable in `007`'s future spec.

**Scenario CRUD + validation** (wraps `retirement_planner.scenario`):
- `GET /scenarios` — wraps `list_scenarios()`
- `GET /scenarios/{name}` — wraps `load_scenario()`; 404 on `ScenarioParseError`; response includes `validation_flags`/`is_usable`
- `PUT /scenarios/{name}` — idempotent upsert (mirrors `save_scenario()`'s documented "overwrite on same name" contract); the handler converts the received JSON to YAML text and calls **`parse_scenario()` directly**, rather than hand-building a `Scenario` dataclass field-by-field — keeps exactly one parse/construct code path in existence, not a second one that could drift
- `POST /scenarios/{name}/validate` — re-runs `validate()` without saving, for live-validation UX (e.g. re-checking on every form field change)

**Flagged gap**: `001` has no `delete_scenario()`. The BFF must not reach into `config/scenarios/` and delete a file directly — that bypasses the storage abstraction, a real layering violation. A small, explicit, additive amendment to `001` (one function, same precedent as `004` adding a registry entry to `003`) is a prerequisite sub-task of `007`, not a BFF-side workaround.

**Reference-data lookups** — read live from the library's own registries, never hardcoded, so extensibility (Principle IV) is demonstrated at the HTTP layer, not just promised by the tax module:
- `GET /reference/states` → `sorted(STATE_MODULES.keys())` — currently `SC`/`DE`/`FL` only; a 4th/5th/6th state module becomes visible with zero BFF code change
- `GET /reference/withdrawal-strategies` → `sorted(WITHDRAWAL_STRATEGIES.keys())`
- `GET /reference/conversion-strategies` → `sorted(CONVERSION_STRATEGIES.keys())`
- `GET /reference/comparison-axes` → `typing.get_args(ComparisonAxis)` — read from the type alias itself, not a second hand-copied list

**Simulation run**:
- `POST /simulations` — body: `{scenario_name, strategy, state?, n_paths?, seed?, generation_mode?, plan_to_age?, stress_scenario?}` (overrides layered on top of the scenario's own `SimulationSettings`, for quick-preview UX at lower path counts). Rejects with 422 + the blocking flags if `scenario.is_usable` is false — never runs an invalid scenario silently. Response: `{"run": to_jsonable(SimulationRun), "summary": to_jsonable(SummaryStatistics)}` — `reporting`'s aggregation is embedded in the same response, since it's cheap relative to the simulation itself (see §5).

**Paired-draw comparison** — two endpoints, since `004`'s deterministic `ComparisonResult` and `005`'s Monte Carlo `SimulationComparisonResult` are genuinely different response shapes:
- `POST /comparisons/deterministic` — dispatches to `004`'s `compare_roth_conversion_strategies`/`compare_withdrawal_sequencing_strategies`/`compare_claiming_age_grid` by `dimension`
- `POST /comparisons/simulated` — dispatches to `005`'s `compare_states`/`compare_roth_conversion_strategies`/etc. by `axis`

Both must call these functions **verbatim**, never reimplement pairing logic at the BFF layer — "paired-draw comparison is the standard pattern" is a constitutional constraint, not a suggestion.

**Reporting/export**:
- `POST /reports/export.csv` (and a comparison-axis sibling) — takes the *same* request shape as the trigger endpoints and regenerates on demand rather than referencing a stored run id (see §5). Responds `text/csv` with `Content-Disposition: attachment`.

---

## 5. No results database — regenerate on demand

Principle II guarantees `(scenario, seed, params) → identical output`, so persisting computed results is never a correctness requirement — at the measured 3.77s reference-scale cost, it isn't currently a performance necessity either.

There's a sharper reason to actively avoid a results store, not just decline it for lack of need: a disk-cached result's true identity is really `(scenario, seed, params, code_version)`. If a tax module is later corrected (e.g. a state module moves from `verified=False` to a corrected, verified figure), a cache keyed only on `(scenario, seed, params)` would silently disagree with what current code actually produces — precisely the "can't tell if a changed result reflects a changed assumption or a silent bug" ambiguity Principle II's own rationale warns against.

**Implication for CSV export**: export endpoints take the full run/comparison parameter set, not a stored-result reference — they regenerate the run and shape it to CSV in one request. Strictly simpler than a "run once, export later" model, with zero reproducibility risk. If performance ever demands caching, it must key on library version as well as `(scenario, seed, params)` — an explicit future concern, not a v1 one.

Only `001`'s existing scenario YAML storage (`config/scenarios/`) persists anything, ever.

---

## 6. Performance/UX: synchronous v1, with a stated async trigger

**v1: synchronous request + client-side spinner.** The measured 3.77s (5,000 paths × 3 states, this environment) is well inside any reasonable HTTP client/browser timeout and well inside Principle VI's "well under a minute" budget. Streamlit's default blocking-with-spinner behavior fits with zero extra plumbing.

**Concrete trigger for switching to async job/polling**: once a request's *estimated* cost (extrapolated from measured per-path-per-state cost against the requested `path_count × candidate_count`) exceeds roughly 10 seconds. Two realistic paths there: (1) the full 9-state comparison lands (`docs/remaining_scope.md`'s backlog item — GA/NC/TN/MS/PA/NH still unimplemented) — naive 3× scaling of the 3-state benchmark lands around ~11s, right at the boundary; (2) a `claiming_age_grid` comparison (9 candidate ages × 9 = 81 cells) at reference-scale path counts — plausibly 30s+ on its own, and combined with more states could push toward or past the one-minute budget. Recommend the BFF **estimate and reject** (a 4xx-style response) any request whose projected cost exceeds the Constitution's budget, rather than let an HTTP request hang past it.

The async pattern, when needed, should slot in *without changing the synchronous endpoints' request/response shapes* — same body, wrapped in a job envelope (`POST` → `202 {job_id}`, `GET /jobs/{id}` → status/result). No new dependency required — FastAPI's `BackgroundTasks` plus an in-process dict keyed by job id is sufficient at single-user volume; no Celery/Redis. Not built for v1; explicitly deferred until the trigger above is actually hit, per Principle VI's own "flagged and justified... before merged" language — not asserted away preemptively.

---

## 7. First UI: Streamlit, and what a second/third UI needs

**Recommendation: Streamlit**, in `apps/streamlit_ui/`, talking to the BFF exclusively over HTTP via `httpx` — **never** `import retirement_planner` directly. This is deliberate: it's the cheapest way to actually exercise the decoupled architecture on day one. If the first UI imported the core library directly, the BFF's contract would go untested by its only client, and the "swap the UI later" claim would itself be untested. Two separate local processes/ports (Streamlit's own server + the FastAPI/uvicorn server), both on `localhost` — a local client + local server, no internet call, does not violate Principle V (Offline-First is about external/internet-service dependency, not about whether HTTP is used as a local transport).

**Scope**: a scenario builder/editor form (against `007`'s scenario endpoints), a run view rendering the fan chart from `percentile_bands`, an overlay chart from comparison runs, the summary-statistics table (including median lifetime tax), verification-flag badges surfaced prominently from `figures_used`/`unverified_figure_names` (per Principle III — "must not be indistinguishable from a verified figure in what the user sees"), and a CSV download button.

**What a second UI needs from the same BFF**, to make the multi-UI claim real rather than aspirational:
- A **JS SPA** needs the free `/openapi.json` (to generate a typed client, e.g. via `openapi-typescript`) and CORS configured on the BFF (`fastapi.middleware.cors.CORSMiddleware`, allowing the SPA's dev-server origin) — a real, concrete BFF addition, named now so it isn't discovered late.
- A **desktop wrapper** (pywebview/Tauri around the same JS SPA, or a thin native client) needs *nothing further* from the BFF — same JSON/HTTP contract, proving a third UI genuinely requires zero BFF changes, only a new client package.
- **Neither needs auth** — §1.1 Non-goals in `docs/initial_requirement.md` explicitly rules out multi-user/SaaS support; no auth/session layer belongs in the BFF, ever, for this project.

---

## 8. Phased delivery: three future features

Sequenced strictly `006 → 007 → 008`; each independently valuable and testable on its own before the next begins, matching the phased-delivery discipline `001`–`005` already established.

### `006` — Reporting & Aggregation
Pure library, no HTTP, no new dependency. Scope: the `retirement_planner.reporting` subpackage — `SummaryStatistics` and `summary_statistics()`/`compute_median_lifetime_tax()` operating on `SimulationRun`/`SimulationComparisonResult`/`ComparisonResult`; CSV-row shaping plus stdlib-`csv`-based text generation. Explicitly out of scope: any HTTP/JSON serialization (`007`'s job), any chart rendering (the UI's job), any new third-party dependency, any change to `001`–`005`'s existing types. Depends on `002`–`005` as a pure consumer of their output types; adds nothing to them. Independently valuable: usable from `examples/reference_scenario.py` or a notebook with zero UI or HTTP layer in existence.

### `007` — BFF API Service
New deployable package, `services/bff/`, own `pyproject.toml`. Scope: the HTTP/JSON boundary over `scenario`+`tax`+`mechanics`+`comparison`+`simulation`+`reporting`; `to_jsonable()`; scenario CRUD+validate endpoints (including the small, additive `delete_scenario()` amendment to `001`, tracked as an explicit prerequisite sub-task); reference-data endpoints reading live from `STATE_MODULES`/`WITHDRAWAL_STRATEGIES`/`CONVERSION_STRATEGIES`/`typing.get_args(ComparisonAxis)`; synchronous run/comparison endpoints embedding `reporting.summary_statistics()` in the response; a CSV export endpoint that regenerates rather than references a stored id. Explicitly out of scope: auth (non-goal), a results database (§5), async job/polling (deferred per §6's trigger), any specific frontend beyond exercising itself via FastAPI's built-in `/docs`. Depends on `001`–`006` — the first feature to depend on all six subpackages. Independently valuable/testable: a working, `pytest`-`TestClient`-testable HTTP API exists and is manually exercisable via Swagger UI before any UI package exists at all.

### `008` — Streamlit UI
New deployable package, `apps/streamlit_ui/`, own `pyproject.toml`. Scope: scenario builder form, run/comparison trigger views, fan chart + overlay chart + summary table + verification-flag surfacing + CSV download, all against `007`'s HTTP contract only. Explicitly out of scope: any second UI technology, any co-evolution of the BFF's contract — if `008` discovers a genuine API gap, that's a small, explicit, additive amendment to `007` (same precedent as `004`'s registry addition to `003`), not a scope blend between the two specs. Depends on `007` only — not on `001`–`006` directly, which is the entire point of the BFF.

---

## 9. Constitution Check

Mirroring every prior spec's plan.md practice of evaluating a new feature against the project's own governing rules before it's built.

| Principle | Status | Requirement to hold it true |
|---|---|---|
| I. Accuracy Over Cleverness | PASS | `to_jsonable()` must never drop `figures_used`/`verified=False` data; `summary_statistics()` must carry `unverified_figure_names` explicitly — otherwise this principle degrades from real to aspirational across the HTTP boundary |
| II. Reproducibility | PASS (given §5) | The BFF must default `seed` deterministically (e.g. from `scenario.simulation_settings.seed`) when a client omits it — never `random.SystemRandom()` at the BFF layer, or identical requests stop being byte-identical end-to-end |
| III. Auditability | PASS | Same requirement as I |
| IV. Extensibility Through Module Interfaces | PASS | Concretely demonstrated, not just promised, by reference-data endpoints reading live from registries — a new state module becomes usable with zero BFF code change |
| V. Offline-First, No Runtime Network Dependency | PASS | Local client + local server, no internet call — `uvicorn` binds `127.0.0.1` by default; LAN exposure is an explicit opt-in, never the default |
| VI. Performance Budget | PASS for v1 | The async-trigger condition (§6) is carried forward as an explicit **watch item**, not asserted away — mirrors `005`'s own Constitution Check treatment of its performance risk |
| "No new third-party dependency" precedent | **Deliberate, justified exception** | The one exception this program needs. `007`'s own future plan.md must state it the way `005` stated its Performance Budget risk: name the violation (`fastapi`+`uvicorn`), justify it against the "solves the actual problem" test (§2), state the containment boundary (confined to `services/bff/`'s own `pyproject.toml`, never touching core) |
| "Config as data, not code" | PASS | The BFF round-trips scenario JSON through `001`'s own `parse_scenario()` (JSON→YAML text bridge), never hand-builds `Scenario` objects — one parse/construct path, not two that could drift |
| "Paired-draw comparison is the standard pattern" | PASS | `/comparisons/simulated` dispatches directly to `005`'s existing `compare_*` functions, never reimplements pairing at the BFF layer |
| Development Workflow gates | Applies | `reporting`'s median/aggregate functions need unit tests against hand-computed reference cases before use, mirroring the "numeric primitives" gate `002`/`003` applied to RMD/bracket math. "Regression baseline" is N/A for `006`–`008`, the same way it was N/A for `004`/`005` — no prototype analog exists for an HTTP/UI layer |

---

## 10. Next steps

This document is a requirements/architecture recommendation only — no code implements it. The natural next step is running `/speckit-specify` for `006` (Reporting & Aggregation), continuing this project's established spec → plan → tasks → implement workflow, using this document as grounding the same way `docs/remaining_scope.md` grounded `005`'s planning. `007` and `008` follow in sequence once `006` is built — see §8 for why that order is load-bearing (`008` should depend on `007` only, and `007` needs `006`'s aggregation output already tested and stable before wrapping it in an HTTP contract).
