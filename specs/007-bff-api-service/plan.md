# Implementation Plan: BFF API Service

**Branch**: `007-bff-api-service` | **Date**: 2026-08-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-bff-api-service/spec.md`

## Summary

A new, independently deployable HTTP/JSON service — `services/bff/` — that wraps `001`'s scenario storage/validation, `002`/`003`'s tax/mechanics registries, `004`'s deterministic comparisons, `005`'s Monte Carlo simulation/comparisons, and `006`'s summarization/export functions behind request/response endpoints, decoupled from any specific UI per the project's multi-UI goal. This is the first feature in the project to introduce a third-party runtime dependency (FastAPI/uvicorn) — deliberately confined to this new, separate package so the core `retirement_planner` library's own dependency footprint (`pyyaml` only) is untouched. It computes nothing itself: every response is `001`–`006`'s existing, already-tested output, reshaped for HTTP.

## Technical Context

**Language/Version**: Python 3.11+ — same interpreter floor as `001`–`006`; the new `services/bff/` package pins the same floor.

**Primary Dependencies**: `fastapi` (routing, request validation, OpenAPI generation), `uvicorn[standard]` (ASGI server), `pydantic` (transitive via FastAPI, request-body validation) — all confined to `services/bff/pyproject.toml`. `httpx` as a test-only dependency (FastAPI's `TestClient` requires it). This feature's own in-repo dependencies: `retirement_planner.scenario`, `retirement_planner.tax`, `retirement_planner.mechanics`, `retirement_planner.comparison`, `retirement_planner.simulation`, `retirement_planner.reporting` (an editable path dependency on the core package, plus one small additive prerequisite change to `001` — see research.md §1). Core's own `pyproject.toml` gains zero new dependencies from this feature.

**Storage**: `001`'s existing `config/scenarios/` YAML storage only — no database, no cache, no persisted run/comparison/export result (FR-019, research.md §2).

**Testing**: pytest + FastAPI's `TestClient` (in-process ASGI testing, no real socket/port needed) — continuing `001`–`006`'s pytest convention while adopting FastAPI's own standard testing pattern for the new HTTP layer.

**Target Platform**: Local developer/user machine, offline — `uvicorn` binds `127.0.0.1` by default (research.md §1); no LAN/internet exposure without an explicit, separate opt-in outside this feature's scope.

**Project Type**: A new, independently deployable Python package (`services/bff/`), sibling to the core `src/retirement_planner/` package — not a subpackage of it. Confirmed with the user during `docs/frontend_architecture.md`'s planning: separate `pyproject.toml` per component, not an optional extra on core's own package metadata.

**Performance Goals**: Every response is `001`–`006`'s existing computation reshaped, not new computation — the same reference-scale budget `005`/`006` already established (a 5,000-path run completing in low single-digit seconds) applies unchanged through this HTTP layer. FR-018 additionally requires estimating a request's cost *before* running it and rejecting anything projected to exceed the constitution's "well under a minute" budget (research.md §5) — this is the one genuinely new performance-relevant behavior this feature adds.

**Constraints**: No network I/O beyond serving local requests (Principle V, FR-021); no authentication/session/multi-user mechanism, ever (Principle-adjacent non-goal, FR-020); no persisted computed result (FR-019); identical requests (including seed) always produce identical responses (Principle II, FR-010); every unverified figure `001`–`006` already flag remains visible through both JSON and CSV responses (Principle III, FR-017); this feature performs no tax/mechanics/comparison/simulation/aggregation computation of its own (FR-022).

**Scale/Scope**: One scenario, one run or one comparison (up to the largest candidate set `004`/`005` already support) per request — the same scale `004`/`005`/`006` already operate at; this feature adds no new fan-out, only an HTTP boundary and a pre-flight cost check around it.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against all six principles plus the Technology/Architecture Constraints and Development Workflow gates, following the same evaluation `002`–`006` did — with one principle-adjacent departure this feature must justify explicitly, the same way `005` justified its Performance Budget risk.

- **I. Accuracy Over Cleverness** — ✅ PASS. This feature introduces no new simplification of its own; every figure it returns is `001`–`006`'s already-accurate, already-flagged output, reshaped. *Requirement to enforce*: the JSON serializer (research.md §3) and every response schema must carry `FigureUsage`/unverified-figure data through unmodified — never dropped in translation to JSON or CSV.
- **II. Reproducibility** — ✅ PASS, contingent on two explicit requirements this feature adds on top of `001`–`006`'s existing guarantee: (1) when a request omits `seed`/`n_paths`, the service MUST default them from the named scenario's own `SimulationSettings` (FR-011) — never from a clock or unseeded generator; (2) `reference_tax_year`/`start_plan_year`/`start_tax_year` have **no default at all** and MUST be required request fields (research.md §4) — `004`'s own research.md already rejected deriving these from the system clock as a Principle II violation, and nothing in `001`'s `Scenario` schema carries an "as-of" reference year to derive them from instead, so this feature must not invent one.
- **III. Auditability** — ✅ PASS, contingent on the same figures-through-unmodified requirement as Principle I. `006`'s `unverified_figure_names`/`has_unverified_figure` fields are what this feature's responses surface — it does not re-derive or summarize them differently.
- **IV. Extensibility Through Module Interfaces** — ✅ PASS, concretely demonstrated: the reference-data endpoints (User Story 2) read `002`'s `STATE_MODULES`, `003`'s `WITHDRAWAL_STRATEGIES`/`CONVERSION_STRATEGIES`, and `005`'s `ComparisonAxis` live, so a new state or strategy registered in a future feature becomes visible through this service with zero code change here (Acceptance Scenario US2.2).
- **V. Offline-First, No Runtime Network Dependency** — ✅ PASS. A locally-bound HTTP server serving a locally-running client is not an external/internet dependency — Principle V's own rationale ("a hidden network dependency would make runs non-reproducible... and fragile") is about *external* services this feature never calls; `uvicorn` defaults to `127.0.0.1` specifically to keep this true in practice, not just in principle (research.md §1).
- **VI. Performance Budget** — ✅ PASS, with FR-018's cost-estimation-and-rejection as the concrete mechanism (research.md §5) — this feature is the first to sit in front of a client that could request an arbitrarily large `n_paths`/candidate combination, so unlike `005`/`006` (whose own callers are trusted, already-scoped test/example code), this feature must actively defend the budget rather than merely operate within it.
- **"No new third-party dependency" precedent — the one deliberate, explicit exception this feature needs.** Every one of `002`–`006`'s `research.md` invoked this precedent; `docs/frontend_architecture.md` already worked through the justification this plan inherits: serving an HTTP boundary is new capability the core library itself never needs (the "would this dependency solve the actual problem" test `005`'s numpy-rejection established — here it passes, unlike numpy). **Containment boundary**: `fastapi`/`uvicorn`/`pydantic`/`httpx` are declared *only* in `services/bff/pyproject.toml`; the repository root `pyproject.toml` (the core `retirement_planner` package's own manifest) is untouched by this feature and gains no new dependency, confirmed by Phase 1's Project Structure below.

**Technology & Architecture Constraints — three interpretations worth recording explicitly:**

- *"Config as data, not code"* — Every request body is plain data a client constructs; this service hardcodes no scenario, strategy, or comparison data of its own. Saving a scenario round-trips through `001`'s own `parse_scenario()` (JSON → YAML text → `parse_scenario()`) rather than hand-building a `Scenario` object field-by-field, keeping exactly one parse/construct code path in existence (research.md §3, mirroring `006`'s own precedent of reusing rather than re-implementing).
- *Paired-draw comparison is the standard pattern* — `/comparisons/simulated` dispatches directly to `005`'s existing `compare_*()` functions (which already enforce the paired-draw guarantee internally); this service never re-derives or bypasses that guarantee.
- *Scope boundary with the working document* — N/A, not implicated by this feature (same posture `005`/`006` recorded for features with no qualitative/non-financial modeling of their own).

**Development Workflow & Quality Gates:**

- *Regression baseline* — N/A in the "reproduce prototype output" sense, same posture `004`–`006` recorded: no HTTP layer existed in the prototype to diff against.
- *Verified-figure gate* — N/A for new figures (this feature introduces none); it must, however, never let the JSON/CSV serialization step silently drop an existing unverified-figure indicator — enforced by this feature's own contract tests.
- *Unit test coverage for numeric primitives* — Required: the cost-estimation heuristic (FR-018) against hand-computed reference cases (a request just under vs. just over the rejection threshold); the seed/`n_paths`/`plan_to_age` defaulting logic (FR-011); the `to_jsonable()` serializer's `date`/non-string-keyed-dict/tuple handling (research.md §3) — each against constructed reference cases, per spec.md's Acceptance Scenarios.

**Post-Phase 1 re-check**: Confirmed after generating research.md, data-model.md, contracts/bff-api.md, and quickstart.md — no new violations. The `delete_scenario()` prerequisite (research.md §1) stays additive to `001`, mirroring the precedent `004`/`005`/`006` each already set adding one small, explicit capability to an earlier feature; `reference_tax_year`/`start_plan_year`/`start_tax_year` remaining required (never defaulted) fields keeps Principle II's guarantee intact through the HTTP boundary exactly as it already holds inside the library; the dependency containment boundary (fastapi/uvicorn/pydantic/httpx confined to `services/bff/`) is verified by Phase 1's Project Structure showing zero changes to core's `pyproject.toml`.

## Project Structure

### Documentation (this feature)

```text
specs/007-bff-api-service/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── bff-api.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pyproject.toml                        # core retirement_planner package -- UNCHANGED by this feature
src/
└── retirement_planner/
    ├── scenario/                     # 001-scenario-config-management
    │   ├── store.py                  # +delete_scenario() (research.md §1) -- additive only
    │   └── __init__.py               # +export delete_scenario
    ├── tax/                          # 002 (unchanged)
    ├── mechanics/                    # 003 (unchanged)
    ├── comparison/                   # 004 (unchanged)
    ├── simulation/                   # 005 (unchanged)
    └── reporting/                    # 006 (unchanged)

services/
└── bff/                              # NEW -- independently deployable package (multi-package monorepo)
    ├── pyproject.toml                # deps: retirement_planner (editable path dep), fastapi,
    │                                 # uvicorn[standard], pydantic (transitive); dev: httpx, pytest
    └── src/
        └── rp_bff/
            ├── __init__.py
            ├── main.py                # FastAPI app construction, route registration
            ├── serialization.py       # to_jsonable() (research.md §3)
            ├── cost_estimation.py     # estimate_cost_seconds() / reject-if-over-budget (research.md §5)
            ├── schemas.py             # Pydantic request models (scenario payload, run/comparison bodies)
            └── routes/
                ├── scenarios.py       # GET/PUT /scenarios, GET /scenarios/{name}, DELETE /scenarios/{name},
                │                      # POST /scenarios/{name}/validate
                ├── reference.py       # GET /reference/states, /withdrawal-strategies,
                │                      # /conversion-strategies, /comparison-axes
                ├── simulations.py     # POST /simulations
                ├── comparisons.py     # POST /comparisons/deterministic, POST /comparisons/simulated
                └── reports.py         # POST /reports/simulations.csv, POST /reports/comparisons.csv

tests/
├── unit/
│   └── scenario/
│       └── test_store.py             # +cases for delete_scenario() (unchanged file, extended
│                                      # per research.md §1)
services/bff/tests/
├── unit/
│   ├── test_serialization.py         # to_jsonable() date/dict/tuple handling
│   ├── test_cost_estimation.py       # under/over-budget reference cases
│   └── test_schemas.py               # request-body validation edge cases
└── integration/
    └── test_bff_lifecycle.py         # full quickstart.md walkthrough, US1-US5, via FastAPI TestClient
```

**Structure Decision**: A new, independently deployable package (`services/bff/`), sibling to the core `src/retirement_planner/` package — not a subpackage of it, and not sharing its `pyproject.toml`. This is the multi-package monorepo layout confirmed with the user during `docs/frontend_architecture.md`'s planning (over the alternative of an optional-dependency extra on core's own package), specifically so the core library's dependency footprint stays exactly `pyyaml`-only and so a future second UI package (`008`, and any later third UI) has the identical, single, already-proven HTTP contract to build against rather than a choice between "import the library" and "call the API." `services/bff/` depends on `retirement_planner` via an editable path dependency; nothing in `src/retirement_planner/` depends on `services/bff/` — the dependency arrow points one way, matching the strict layer order every prior feature in this project has maintained. The one change this feature makes inside `src/retirement_planner/` — `delete_scenario()` — is additive to `001`'s already-established storage module, mirroring the precedent `004`/`005`/`006` each already set.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| New third-party runtime dependency (`fastapi`, `uvicorn`, `pydantic`) — the first in this project's history | An HTTP/JSON boundary is genuinely new capability `001`–`006` never needed, and a hand-rolled `http.server`/`wsgiref` implementation would reinvent request validation, routing, and OpenAPI schema generation for no benefit over an actively-maintained, widely-adopted framework | Building the HTTP layer on the standard library alone (rejected in `docs/frontend_architecture.md` §2): unlike `005`'s numpy rejection, this dependency *does* solve this feature's actual problem (serving HTTP), and confining it to a new, separate package (`services/bff/`) means the core library's own "no third-party dependency" precedent stays intact rather than being compromised — this is the smallest-footprint way to add a capability the project genuinely now needs |