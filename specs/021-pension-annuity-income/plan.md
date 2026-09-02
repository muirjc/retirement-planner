# Implementation Plan: Pension, Annuity & Phased-Retirement Income Streams

**Branch**: `021-pension-annuity-income` | **Date**: 2026-09-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/021-pension-annuity-income/spec.md`

## Summary

Add a generic, per-household-member `IncomeStream` (pension, annuity, or phased-retirement earned income) with a start age, optional end age, annual amount, and an inflation-adjustment mode. Each stream is computed per plan year exactly the way `ss_annual_benefit` already is — a new `mechanics.income_streams` module derives the year's gross amount — and is summed into the same `ordinary_income_established` total a traditional withdrawal already contributes, so it correctly funds Roth-conversion bracket-fill headroom, federal/state tax, IRMAA/NIIT MAGI, and the early-withdrawal-penalty base without any of those already-correct computations needing to know a new income type exists. `cola_adjusted` streams stay flat in this engine's real-dollar convention (identical treatment to `ss_annual_benefit`); `fixed_nominal` streams erode against a new, explicitly cited planning inflation-rate figure (the SSA Trustees Report's own intermediate CPI assumption) — this engine's first inflation-rate figure, since nothing before this needed one.

## Technical Context

**Language/Version**: Python 3.11+ (existing project standard)

**Primary Dependencies**: none new — reuses `dataclasses`, `pyyaml` (scenario), `pydantic` (BFF), already-vendored deps only

**Storage**: YAML scenario files under `config/scenarios/` (existing `scenario.store` mechanism) — no new storage

**Testing**: `pytest tests/` (core), `pytest services/bff/tests/` (BFF), `pytest apps/streamlit_ui/tests/` (UI) — existing suites, extended

**Target Platform**: Linux/macOS dev laptop, offline (constitution Principle V)

**Project Type**: Library-first (core `src/retirement_planner`) + thin BFF (FastAPI) + Streamlit UI, per existing repo structure

**Performance Goals**: No material change — one new O(1) computation per member per plan year, negligible against the existing Monte Carlo performance budget (constitution Principle VI)

**Constraints**: Must reproduce every existing scenario's output exactly when no income streams are configured (empty-list default); must not alter `compute_plan_year_mechanics()`'s existing parameters' meaning, only add new optional ones

**Scale/Scope**: Core library (scenario model/validation/loader/store, mechanics, comparison, reporting) + BFF schema pass-through + a minimal, non-lossy Streamlit round-trip fix (no new editing widgets — see Scope Boundaries below) + `docs/BRD.md`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Accuracy Over Cleverness**: PASS. The `fixed_nominal` erosion assumption is new and inherently a planning estimate, not a settled figure — it is added as a `SourcedFigure` with `verified` reflecting genuine primary-source confirmation (see research.md §1), and both spec.md and docs/BRD.md state plainly that it's a planning assumption, not government-published law, the same way the Joint Life RMD table's `verified=False` is already handled.
- **II. Reproducibility**: PASS. No randomness introduced; a stream's amount is a pure function of (stream config, member age, tax year, reference tax year).
- **III. Auditability**: PASS. The new inflation-rate figure carries a citation, `last_verified` date, and `verified` flag, and its `FigureUsage` is unioned into `PlanYearMechanicsResult.figures_used`/`PlanYearProjection.figures_used` like every other engine figure — a `fixed_nominal` stream's provenance is visible in existing figures-used reporting, no new reporting mechanism needed.
- **IV. Extensibility Through Module Interfaces**: PASS. New income-stream computation lives in its own `mechanics/income_streams.py` module behind one function (`compute_income_stream_amount()`); `compute_plan_year_mechanics()` only gains two new optional, additively-defaulted parameters (`income_stream_total`, `income_stream_figures_used`) — the simulation core's own control flow is unchanged.
- **V. Offline-First**: PASS. The new inflation-rate figure is a hardcoded `SourcedFigure` schedule, like every other figure in this codebase — no runtime lookup.
- **VI. Performance Budget**: PASS. O(members × streams) per plan year, negligible.

No violations — Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/021-pension-annuity-income/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (addenda to scenario-api.md, mechanics-api.md, comparison-api.md, reporting-api.md)
└── tasks.md             # Phase 2 output (/speckit-tasks — not created by this command)
```

### Source Code (repository root)

Existing single-project layout (library-first core + BFF + Streamlit UI), extended in place — no new top-level directory:

```text
src/retirement_planner/
├── scenario/
│   ├── models.py         # + IncomeStream dataclass; HouseholdMember.income_streams
│   ├── loader.py          # + _build_income_stream(), wired into _build_household_member()
│   ├── store.py            # + _income_stream_to_dict(), wired into _scenario_to_dict()
│   └── validation.py       # + income-stream validation rules in _validate_household()
├── mechanics/
│   ├── income_streams.py  # NEW: INFLATION_RATE SourcedFigure + compute_income_stream_amount()
│   ├── plan_year.py       # + income_stream_total / income_stream_figures_used params
│   └── __init__.py         # + new exports
├── comparison/
│   ├── projection.py       # + _member_income_stream_amounts(), threaded into run_plan_projection()
│   └── models.py            # + PlanYearProjection.member_income_stream_amounts
└── reporting/
    └── account_attribution.py  # + PlanYearAccountDetail.member_income_stream_amounts

services/bff/src/rp_bff/
└── schemas.py              # + IncomeStreamRequest; HouseholdMemberRequest.income_streams (pass-through, model_dump()-based YAML round-trip needs no resolution.py change)

apps/streamlit_ui/pages/
└── 1_Scenarios.py          # Minimal non-lossy pass-through only (see Scope Boundaries) — no new editing widgets this iteration

tests/                       # scenario/mechanics/comparison/reporting unit + integration tests, mirroring existing test layout
services/bff/tests/          # schema round-trip test
docs/BRD.md                  # new §6.x "Pension, annuity & phased-retirement income streams" + figure-verification table row
```

**Structure Decision**: Extends the existing four-package layout (core library → BFF → Streamlit UI, plus e2e) in place; no new package or route.

### Scope Boundaries (explicit, not deferred silently)

- **Payroll/self-employment tax (FICA/SECA)** on `earned_income` streams: out of scope (spec.md Assumptions) — a follow-on issue, not silently dropped.
- **Streamlit UI editing widgets** for income streams: out of scope this iteration. The existing 1_Scenarios.py form is explicitly fixed-shape/no-free-form-list by its own module docstring (accounts, inherited-IRA) — designing a new repeating-list editing pattern is a real UI decision deserving its own scoped feature, not a rider on this one. What IS in scope: a **non-lossy round-trip pass-through** (load → keep in session_state → resave unchanged) so a household that configured income streams via YAML or the API does not have them silently deleted the next time they save via the UI — the same "don't silently destroy data the form doesn't expose" bar already applied elsewhere in this form. A follow-on issue will be filed for full editing widgets.
