# Implementation Plan: Survivor Scenario Projection Wiring

**Branch**: `018-survivor-scenario-projection` | **Date**: 2026-08-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/018-survivor-scenario-projection/spec.md`

## Summary

Fixes rp-g8y: `HouseholdMember.predicted_death_age` (added by `017` specifically for this feature)
and `compute_survivor_benefit()` (`017`) currently have no caller inside a running projection —
`run_plan_projection()`'s per-year loop treats every plan year as if both spouses are alive and
`married_filing_jointly`, no matter what's configured. This feature computes, once per
`run_plan_projection()` call, the household's **death tax year** (the tax year the dying member's
translated age first reaches `predicted_death_age`, via the engine's existing
`member_age_in_tax_year()` formula) for an MFJ household where exactly one member has
`predicted_death_age` set (the earlier of the two, if both do — Edge Cases). For every plan year
*after* that year, the loop now uses `single` filing status (federal/state tax, IRMAA, NIIT),
`compute_survivor_benefit()`'s result (the higher of the two members' own already-computed benefit
amounts that year, replacing their sum) as the household's Social Security income, and
`annual_spending_need * (1 - household.survivor_spending_reduction_pct)` (a new optional `Household`
field, default `0.0`, i.e. no-op) as spending need. The death year itself and every year before it are
completely unaffected. `PlanYearProjection` gains `filing_status` and `effective_spending_need`
fields so a downstream reporting/UI consumer can see exactly which years switched. Monte Carlo (`simulation/monte_carlo.py`)
is untouched (FR-007) — every path already calls `run_plan_projection()` internally, so nothing
further is needed for the death-driven switch to propagate through every Monte Carlo path's own
run, but `survival_curves`-based scoring remains a separate, disconnected post-hoc metric, as today.

## Technical Context

**Language/Version**: Python 3.11+ (matches this project's existing constraint; no new dependency).

**Primary Dependencies**: None new — reuses `retirement_planner.mechanics.compute_survivor_benefit()`
(`017`, already implemented and unit-tested but never called), stdlib only.

**Storage**: N/A — in-memory dataclasses and YAML scenario files, same as every existing feature.

**Testing**: `pytest` (`tests/unit/comparison/test_projection.py` for the core wiring;
`tests/unit/comparison/test_compare.py` for User Story 2's propagation into comparisons;
`tests/unit/scenario/test_loader.py`/`test_validation.py` for the new `Household` field;
`tests/unit/simulation/test_monte_carlo.py` re-run unmodified as a regression check for FR-007/SC-005).
`services/bff/tests/` and `apps/streamlit_ui/tests/` get the mechanical field-mirror coverage 016's
research.md Decision 6 already established a precedent for.

**Target Platform**: Same as the rest of this project — a single-user, offline-first CLI/library plus
its BFF/Streamlit UI (constitution Principle V).

**Project Type**: Library feature (core `retirement_planner` package) with mechanical, additive
ripple into the BFF and Streamlit UI packages — not a new deployable unit.

**Performance Goals**: No material change — the new per-year work is one O(1) tax-year comparison, at
most one `compute_survivor_benefit()` call (closed-form arithmetic), and one float multiply, replacing
work already done in every plan year. Constitution Principle VI's Monte Carlo budget is unaffected
(Monte Carlo's own loop is untouched, FR-007).

**Constraints**: Must preserve reproducibility (Principle II) — same scenario + seed still yields
identical output. Must not change any output for a household with no `predicted_death_age` configured
on any member (FR-005, SC-002) — this is the overwhelming majority of existing scenarios and every
existing test fixture. Must not change Monte Carlo output at all (FR-007, SC-005).

**Scale/Scope**: One modified function (`comparison/projection.py::run_plan_projection()`, plus one
new private helper to compute the household's death tax year), one modified dataclass
(`PlanYearProjection` gains `filing_status` and `effective_spending_need`), one new `Household` field
(`survivor_spending_reduction_pct`), one new validation warning rule, mechanical field mirrors in
`services/bff` and `apps/streamlit_ui`, and `docs/BRD.md` updates. `comparison/compare.py`'s three
`compare_*()` functions need **no** code change (User Story 2) — they already forward `household`
unchanged into each candidate's own `run_plan_projection()` call.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design below.*

| Principle | Check | Status |
|---|---|---|
| I. Accuracy Over Cleverness | This feature removes a silent gap (a configured hypothetical death has zero effect on any output) rather than introducing a new one. Its own simplifications — no Qualifying Surviving Spouse / MFJ-in-year-of-death status, no remarriage, a single flat spending-reduction percentage instead of a re-planned budget, no Monte Carlo per-path wiring — are each documented in spec.md Assumptions/Edge Cases and carried into `docs/BRD.md` (FR-008), not silently absorbed. | PASS |
| II. Reproducibility | The death-tax-year computation and `compute_survivor_benefit()` are both pure/deterministic (no randomness, no I/O); identical scenario + seed still yields identical output. | PASS |
| III. Auditability | `compute_survivor_benefit()`'s existing `SS_SURVIVOR_BENEFIT_RULE` citation/`last_verified` date (`017`) now actually reaches `PlanYearProjection.figures_used` for the first time, once this feature calls it — no new figure is introduced by this plan; the existing one becomes live. | PASS |
| IV. Extensibility Through Module Interfaces | All new logic lives inside `run_plan_projection()`'s existing per-year loop and one new private helper in the same module — no new module, no change to `mechanics/social_security_benefit.py`'s already-locked signatures (`017`'s contract). | PASS |
| V. Offline-First | No network dependency introduced. | PASS |
| VI. Performance Budget | O(1) additional work per plan year; Monte Carlo's own loop and budget are untouched (FR-007). | PASS |
| Paired-draw comparison standard | No comparison axis is added or restructured — `compare_*()` functions are unchanged; only a candidate's own post-death years, when `predicted_death_age` is configured, differ from its pre-death years, exactly as a plain projection's would. | PASS |
| Config as data, not code | `survivor_spending_reduction_pct` is a scenario YAML field, not a hardcoded value. | PASS |

No violations — Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/018-survivor-scenario-projection/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── scenario-api.md      # addendum to 001/010/016/017
│   └── comparison-api.md    # addendum to 004/010/011/012
└── tasks.md             # Phase 2 output (/speckit-tasks — not created by this command)
```

### Source Code (repository root)

```text
src/retirement_planner/
├── scenario/
│   ├── models.py              # Household gains survivor_spending_reduction_pct
│   ├── loader.py               # _build_household() parses the new optional field
│   └── validation.py           # _validate_household() (or a new _validate_survivor_spending())
│                                # gains a plausibility-warning rule (0.0-1.0 range)
└── comparison/
    ├── models.py                # PlanYearProjection gains filing_status
    └── projection.py            # run_plan_projection() gains the death-tax-year switch;
                                  # one new private helper (_household_death_tax_year() or similar)

services/bff/src/rp_bff/
└── schemas.py                  # HouseholdRequest gains survivor_spending_reduction_pct

apps/streamlit_ui/pages/
└── 1_Scenarios.py              # household-level spending-reduction input, mirroring existing
                                  # optional-field inputs (e.g. hsa_contribution)

docs/
└── BRD.md                      # Social Security / projection-engine section updated (data-model.md)

tests/
├── unit/comparison/test_projection.py   # + death-year switch cases (filing status, SS income,
│                                          #   spending, per-year filing_status field, no-op cases)
├── unit/comparison/test_compare.py      # + at least one comparison-propagation case (US2)
├── unit/scenario/test_loader.py         # survivor_spending_reduction_pct parsing cases
├── unit/scenario/test_validation.py     # plausibility-warning cases
└── unit/simulation/test_monte_carlo.py  # re-run unmodified — regression guard for FR-007/SC-005

services/bff/tests/  and  apps/streamlit_ui/tests/
    # mechanical field-mirror coverage where each package's existing pattern already tests an
    # optional Household-level field the same way (016 research.md Decision 6 precedent)
```

**Structure Decision**: Follows the existing package layout exactly — no new top-level package, no
new deployable unit, no new module. The death-tax-year switch lives inside
`comparison/projection.py::run_plan_projection()` itself (the single per-year loop every plain
projection and every comparison candidate already shares — FR-006/User Story 2), not a new sibling
module, since it has no independent reusable shape of its own (unlike `017`'s two new pure
calculation functions) — it's orchestration over already-existing calculations
(`compute_survivor_benefit()`, `compute_federal_tax()`, `compute_plan_year_mechanics()`).

## Complexity Tracking

*No Constitution Check violations — this section is intentionally empty.*
