# Implementation Plan: Streamlit UI

**Branch**: `008-streamlit-ui` | **Date**: 2026-08-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-streamlit-ui/spec.md`

## Summary

A new, independently deployable package — `apps/streamlit_ui/` — the first UI a person actually uses: a multi-page Streamlit app for scenario management, running simulations, comparing candidates, and downloading reports, talking to `007`'s HTTP API exclusively (never importing `retirement_planner` or `rp_bff` directly). It computes nothing itself — every chart, table, and figure it renders is `007`'s response data reshaped for display. This is the third and final feature in `docs/frontend_architecture.md`'s front-end program.

## Technical Context

**Language/Version**: Python 3.11+ — same interpreter floor as `001`–`007`.

**Primary Dependencies**: `streamlit` (the UI framework — confirmed during `docs/frontend_architecture.md`'s planning), `httpx` (the HTTP client talking to `007`), `plotly` (charting — `docs/frontend_architecture.md` §7's named choice). All confined to `apps/streamlit_ui/pyproject.toml`; neither `retirement_planner` nor `rp_bff` (`007`'s package) is a dependency of this package at all (research.md §1) — a structural, not just conventional, enforcement of "talks over HTTP only."

**Storage**: None of its own. `007`'s scenario storage (itself wrapping `001`'s `config/scenarios/`) is the only persisted state anywhere in this program; this feature's own state is either ephemeral in-browser form state or a live HTTP response.

**Testing**: `streamlit.testing.v1.AppTest` (Streamlit's own official headless app-testing API, available since Streamlit 1.28 — confirmed present in the resolved `streamlit==1.62.0`) driving each page script directly, asserting on rendered widgets/text without a browser; `pytest` as the runner, continuing `001`–`007`'s convention. `httpx`'s `MockTransport` (or an equivalent request-stubbing fixture) isolates these tests from needing a real running `007` instance.

**Target Platform**: Local developer/user machine, offline except for HTTP calls to `007` running on the same machine (`127.0.0.1`) — no other network access (FR-018).

**Project Type**: A new, independently deployable Python package (`apps/streamlit_ui/`), sibling to `src/retirement_planner/` and `services/bff/` — the multi-package monorepo layout `docs/frontend_architecture.md` established and `007` already followed.

**Performance Goals**: This feature adds no computation of its own — its own overhead is negligible (HTTP round trip + chart rendering). The user-perceived wait for a run/comparison is entirely `007`'s existing budget (well under a minute at reference scale, per `007`'s own Performance Goals); this feature's job is to make that wait visible (FR-008), not to shorten it.

**Constraints**: No import of `retirement_planner`/`rp_bff` (FR-016, research.md §1); no authentication (FR-017); no network call other than to `007` (FR-018); every displayed figure traceable to a specific `007` response field, never fabricated or locally derived (FR-016).

**Scale/Scope**: One scenario, one run or comparison in view at a time (per spec.md's Assumptions — no multi-scenario dashboard); the same candidate-count/path-count scale `007` already supports, since this feature only requests what `007` can already serve.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against all six principles plus the Technology/Architecture Constraints and Development Workflow gates, following the same evaluation `002`–`007` did.

- **I. Accuracy Over Cleverness** — ✅ PASS. This feature introduces no new simplification, computation, or approximation of its own — every number and chart is `007`'s response data, displayed. *Requirement to enforce*: chart/table rendering must never round, aggregate, or omit a field in a way that changes its meaning (e.g., truncating `unverified_figure_names` would silently weaken Principle III downstream — FR-013 forbids this explicitly).
- **II. Reproducibility** — ✅ PASS (inherited, not re-implemented). This feature always forwards the user's actual entered `reference_tax_year`/`start_plan_year`/`start_tax_year`/seed values to `007` verbatim (spec.md Assumptions) — it never substitutes a client-side default that could make an identical scenario produce different requests on different days.
- **III. Auditability** — ✅ PASS. `007`'s `unverified_figure_names`/`has_unverified_figure` data is what FR-013's Verification Indicator renders — always present (positive or negative), on every run/comparison view, per Acceptance Scenarios US4.1–US4.2 (mirroring `006`'s own "present even when empty" discipline one layer further downstream).
- **IV. Extensibility Through Module Interfaces** — ✅ PASS, concretely demonstrated the same way `007`'s reference-data endpoints demonstrated it one layer down: this feature's state/withdrawal-strategy/conversion-strategy/axis selection widgets are populated from `007`'s live reference-data responses (FR-003), never a hardcoded list — a new state module two layers down becomes selectable here with zero code change in this feature.
- **V. Offline-First, No Runtime Network Dependency** — ✅ PASS. The only network call this feature ever makes is to `007` on `127.0.0.1` (FR-018) — the same "local client, local server, no internet" reasoning `007`'s own Constitution Check already established, one layer further out.
- **VI. Performance Budget** — ✅ PASS. This feature adds no new computation subject to the budget; it inherits `007`'s own budget and cost-rejection gate unchanged, surfacing a rejection as a specific message (FR-007) rather than working around it.
- **"No new third-party dependency" precedent** — **A second deliberate, explicit exception**, following `007`'s own precedent for adding the first. `streamlit`/`httpx`/`plotly` are declared *only* in `apps/streamlit_ui/pyproject.toml` — confined the same way `007`'s dependencies were confined to `services/bff/pyproject.toml`; neither the core package nor `007`'s own package gains anything. Streamlit's own transitive dependencies (`pandas`, `numpy`, `pyarrow`, etc., per the dependency resolution during planning) are likewise fully contained to this one new package — notable only because this project has otherwise avoided `numpy` specifically (`005`'s own research.md), but this is Streamlit's dependency choice, not this feature's, and it never touches the simulation engine.

**Technology & Architecture Constraints — three interpretations worth recording explicitly:**

- *"Config as data, not code"* — N/A directly (this feature holds no scenario/tax data of its own); the one configuration value this feature does own — the BFF's base URL — is externalized as an environment variable (research.md §2), never hardcoded.
- *Paired-draw comparison is the standard pattern* — N/A directly; this feature never runs a comparison itself, only requests one from `007` and displays the result, so the pairing guarantee `005`'s functions already enforce is inherited, not re-implemented or re-checked here.
- *Scope boundary with the working document* — Directly relevant, same as `006`: this feature's CSV download (User Story 5) is what makes the source document's "feeding results into the working document" workflow actually reachable by a person, without this feature modeling any of that document's own qualitative content.

**Development Workflow & Quality Gates:**

- *Regression baseline* — N/A, same posture `004`–`007` recorded: no prototype UI exists to diff against.
- *Verified-figure gate* — N/A for new figures (this feature introduces none); it must never let a chart/table's rendering step silently drop the unverified-figure indicator `007` already provides — enforced by this feature's own `AppTest`-based tests.
- *Unit test coverage for numeric primitives* — N/A in the traditional sense (no bracket math or divisor tables here); the analogous requirement for this feature is test coverage for its own non-trivial logic: the error-shape-to-message mapping (research.md §4) and the engine-dependent chart-shape logic (research.md §3), each against constructed reference `007` response fixtures.

**Post-Phase 1 re-check**: Confirmed after generating research.md, data-model.md, contracts/ui-pages.md, and quickstart.md — no new violations. The dependency containment boundary is verified the same way `007` verified its own (a test confirming neither `pyproject.toml` nor `services/bff/pyproject.toml` changed); the engine-dependent overlay-chart design (research.md §3) keeps Principle I intact by never fabricating a time series `007`'s deterministic comparisons don't actually provide.

## Project Structure

### Documentation (this feature)

```text
specs/008-streamlit-ui/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── ui-pages.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pyproject.toml                        # core retirement_planner package -- UNCHANGED
services/bff/pyproject.toml           # 007's package -- UNCHANGED

apps/
└── streamlit_ui/                     # NEW -- independently deployable package
    ├── pyproject.toml                # deps: streamlit, httpx, plotly; dev: pytest
    ├── app.py                        # Streamlit entry point -- Home page (backend status, navigation)
    ├── pages/                        # Streamlit's own multi-page convention: files here become
    │   │                             # sidebar-navigable pages automatically (research.md §5) --
    │   │                             # this directory MUST sit next to app.py, not under src/
    │   ├── 1_Scenarios.py            # US1: list/create/edit/delete
    │   ├── 2_Run_Simulation.py       # US2: run + fan chart
    │   └── 3_Compare.py              # US3: comparison + overlay/bar chart
    └── src/
        └── rp_ui/
            ├── __init__.py
            ├── api_client.py         # thin httpx wrapper for every 007 endpoint (research.md §2)
            ├── errors.py             # maps 007's 4 documented error shapes + network failures
            │                         # to human messages (FR-007, FR-015, research.md §4)
            ├── charts.py             # fan chart (percentile_bands) + engine-dependent comparison
            │                         # chart (line overlay for simulated, bar for deterministic,
            │                         # research.md §3)
            └── verification.py       # the Verification Indicator widget (FR-013)

apps/streamlit_ui/tests/
├── unit/
│   ├── test_api_client.py            # request shaping + response parsing, httpx.MockTransport
│   ├── test_errors.py                # each of 007's 4 error shapes + a network failure -> message
│   └── test_charts.py                # fan chart / engine-dependent comparison chart construction
│                                      # against constructed SummaryStatistics-shaped fixtures
└── integration/
    └── test_app_pages.py             # AppTest-driven walkthrough of all three pages, US1-US5
```

**Structure Decision**: A third independently deployable package, `apps/streamlit_ui/`, sibling to `src/retirement_planner/` and `services/bff/` — continuing the multi-package monorepo layout `docs/frontend_architecture.md` established and `007` already followed. Streamlit's own multi-page convention requires `pages/` to sit directly next to the entry-point script (`app.py`), not nested under `src/` the way `001`–`007`'s code lives — this is a structural requirement of the UI framework itself, not a deviation from this project's own convention by choice (research.md §5); the *reusable* logic each page script imports (`api_client`, `errors`, `charts`, `verification`) still lives in an importable `src/rp_ui/` package, keeping that part consistent with every prior feature's layout. `apps/streamlit_ui/` depends on nothing in this repository except its own three third-party packages — no editable path dependency on `retirement_planner` or `rp_bff`, enforced structurally (not just by convention) by this package's own `pyproject.toml` never listing either.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| A second new third-party runtime dependency set (`streamlit`, `httpx`, `plotly`, plus Streamlit's own transitive dependencies) — following `007`'s precedent of adding the first | A UI a person actually uses is genuinely new capability nothing in `001`–`007` provides; `docs/frontend_architecture.md`'s planning already evaluated and confirmed Streamlit as the fastest path to a working, professional-enough local UI, over a hand-rolled or framework-free alternative | Building the UI as raw HTML/JS served by `007` itself, or a framework-free Python templating approach — rejected during `docs/frontend_architecture.md`'s own planning (not re-litigated here) as materially more engineering effort for a single-developer tool where the goal is a working UI quickly, not a bespoke frontend; confining the dependency to this one new package (never touching core or `007`) is the same smallest-footprint containment strategy `007` already established for its own dependency |