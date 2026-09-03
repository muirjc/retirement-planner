# Implementation Plan: Year-by-Year Results Walkthrough

**Branch**: `028-results-walkthrough` | **Date**: 2026-09-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/028-results-walkthrough/spec.md`

## Summary

Add a deterministic, plain-language "story" per plan year for one representative simulated
path from a completed Run Simulation result, and a new Streamlit step-through page that lets a
user read it three plan years at a time. A new pure `reporting/narrative.py` module selects the
representative path (closest final `ending_balance` to the run's median) and detects a fixed v1
set of notable year-over-year drivers (RMD start, SS claiming, Roth conversion, withdrawal-source
change, ≥15% tax change, IRMAA start/lookback-switch, survivor death, shortfall) entirely from
figures the engine already computes — no new tax, mechanics, or simulation logic. The BFF adds
one field (`narrative`) to POST /simulations's existing response; the UI reads it from the same
`run_last_result` session-state object `2_Run_Simulation.py` already populates, so opening the new
page costs no extra network round trip.

## Technical Context

**Language/Version**: Python 3.11+ (matches the rest of the repo; no version-specific feature
needed).

**Primary Dependencies**: None new. Reuses the existing stack: dataclasses (core library),
FastAPI/Pydantic (BFF), Streamlit (UI). No new package is added to any of the three
`pyproject.toml`/`requirements` files.

**Storage**: N/A — the narrative is derived in-memory from an already-computed `SimulationRun`
and discarded per request/session; nothing is persisted.

**Testing**: pytest, mirroring the project's four existing suites:
`tests/unit/reporting/test_narrative.py` (new, core), `services/bff/tests/` (route addition),
`apps/streamlit_ui/tests/` (new page), and no e2e change required beyond what the existing
Playwright smoke coverage already exercises for page navigation (extending it is optional
polish, not required by this feature's acceptance criteria).

**Target Platform**: Same as the rest of the tool — a local machine running the BFF (FastAPI/
uvicorn) and Streamlit UI, offline-capable, no server deployment target.

**Project Type**: Web application over a core library (existing three-package layout: core
library → BFF → Streamlit UI). This feature adds to all three, following that existing chain.

**Performance Goals**: Negligible added cost — narrative construction is O(plan years) pure
string/dataclass composition over data the simulation already computed (typically 20-40 plan
years), reused only for the one selected path, computed once per request. No measurable addition
to the constitution's reference-scale Monte Carlo budget (Principle VI), since it runs after the
simulation completes, not as part of it.

**Constraints**: Offline-first (Principle V) — no new runtime dependency, no additional network
round trip; the UI reads `narrative` from the same response object the Run Simulation page
already fetches and stores in `st.session_state["run_last_result"]`. Fully reproducible given
the same scenario + seed (Principle II) — pure functions over deterministic already-computed
data, no new randomness.

**Scale/Scope**: One new core module (`narrative.py`, ~3 functions + 3 dataclasses), one BFF
response field, one new Streamlit page, three new/extended test files. No change to any existing
computation's output (FR-014).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Accuracy Over Cleverness | v1's explicit deferred-driver list (HSA, FICA, earnings-test withholding, inherited-account detail, state exclusions, NIIT — FR-007) keeps the narrative from silently implying completeness it doesn't have; that detail stays visible as raw numbers, never narrated as settled. | PASS |
| II. Reproducibility | FR-006/SC-002: identical scenario+seed → identical selected path index and byte-identical narrative text. Pure functions over already-computed deterministic data; no new randomness introduced. | PASS |
| III. Auditability | FR-011/SC-003: any figure already flagged unverified elsewhere stays flagged on the walkthrough page, via the existing `render_verification_indicator()` (no parallel flagging mechanism invented). | PASS |
| IV. Extensibility Through Module Interfaces | New driver-detection logic lives entirely in one new module (`narrative.py`) with a documented, closed v1 driver list — touches no simulation-core, tax-module, or withdrawal-strategy interface. Not itself a new *extension point* (this is a reporting consumer, not a plug-in surface), so N/A beyond "does not regress existing extension points" — confirmed true. | PASS |
| V. Offline-First | FR-008: entirely offline, zero new dependency, zero new round trip (narrative computed server-side alongside the existing simulation response). | PASS |
| VI. Performance Budget | O(plan years) pure composition, run once per already-completed simulation request — no regression to the Monte Carlo budget itself. | PASS |

No violations. Complexity Tracking table below is not needed.

**Post-Phase 1 re-check**: data-model.md and contracts/reporting-narrative-api.md confirm the
design stayed within the plan above — no new dependency, no simulation-core/`PlanYearProjection`
schema change, no new network round trip, and every driver traced to a field the engine already
computes (research.md §3). All six gates above still PASS unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/028-results-walkthrough/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── reporting-narrative-api.md   # Phase 1 output (/speckit-plan command)
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/retirement_planner/reporting/
├── models.py             # EXTEND: add NarrativeEntry, YearStory, RunNarrative dataclasses
│                          #   (mirrors how SummaryStatistics already lives here, imported by
│                          #   aggregation.py, account_attribution.py, export.py)
├── aggregation.py         # RENAME: _unverified_figure_names -> unverified_figure_names
│                          #   (private -> public, research.md §4 — narrative.py reuses it
│                          #   per plan year; no behavior change)
├── narrative.py           # NEW: select_representative_path(run) -> int
│                          #   build_year_stories(projection, household, reference_tax_year)
│                          #     -> list[YearStory]
│                          #   build_narrative_for_run(run, household, reference_tax_year)
│                          #     -> RunNarrative
│                          #   (mirrors aggregation.py's pure/testable style; imports
│                          #    member_age_in_tax_year, deemed_rmd_owner, WITHDRAWAL_STRATEGIES
│                          #    from existing 004/comparison and mechanics modules -- no new
│                          #    tax/mechanics/simulation computation, FR-004/FR-014)
└── __init__.py            # EXTEND: export the three new dataclasses + build_narrative_for_run

tests/unit/reporting/
└── test_narrative.py      # NEW: mirrors test_aggregation.py's fixture style -- synthetic
                            #   PlanProjection/PlanYearProjection built via run_plan_projection(),
                            #   assembled into a SimulationRun; asserts each driver fires exactly
                            #   on its transition year, path selection, and repeated-call
                            #   byte-identity (FR-006/SC-002)

services/bff/src/rp_bff/routes/
└── simulations.py         # EXTEND: run_simulation_route() calls build_narrative_for_run() once
                            #   (selected-path-only, per FR-008) and adds "narrative":
                            #   to_jsonable(narrative) to the existing response dict

services/bff/tests/integration/
└── test_bff_lifecycle.py  # EXTEND: asserts the new "narrative" response field's
                            #   presence/shape (mirrors test_run_simulation_response_includes_
                            #   account_detail_shaped_per_account's style) and that every other
                            #   field is unchanged (FR-014)

apps/streamlit_ui/pages/
└── 4_Walkthrough.py       # NEW: reads st.session_state["run_last_result"]["narrative"] (same
                            #   key 2_Run_Simulation.py already populates -- no new HTTP call);
                            #   batches of 3 plan years with Next/Previous (FR-009/FR-010);
                            #   reuses render_verification_indicator() scoped per shown year
                            #   (FR-011); guides the user to run a simulation first when
                            #   run_last_result is absent (FR-013)

apps/streamlit_ui/tests/unit/
└── test_walkthrough.py    # NEW: mirrors test_account_table.py/test_verification.py's style
                            #   for the new page's pure-rendering helpers

README.md                  # UPDATE: new page + response field, per living-documentation rule
docs/SOLUTION_ARCHITECTURE.md  # UPDATE: new module/response field/page in the relevant C4 views
docs/BRD.md                 # NO CHANGE: no new regulated figure, tax rule, or math (Assumptions)
```

**Structure Decision**: Extends the existing three-package chain (core library →
`src/retirement_planner/reporting/` → BFF `services/bff/src/rp_bff/routes/simulations.py` →
Streamlit `apps/streamlit_ui/pages/`) exactly the way every prior reporting-surfacing feature
(006-reporting-aggregation, 015-per-account-projection-detail) already does — no new package,
no new top-level directory, no new project type.

## Complexity Tracking

*No Constitution Check violations — this table is intentionally empty.*
