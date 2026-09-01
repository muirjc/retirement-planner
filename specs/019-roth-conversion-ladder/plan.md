# Implementation Plan: Roth Conversion Ladder (Five-Year Rule) Tracking

**Branch**: `019-roth-conversion-ladder` | **Date**: 2026-09-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/019-roth-conversion-ladder/spec.md`

## Summary

Fixes rp-886: `mechanics/roth_conversion.py`'s `compute_roth_conversion()` executes a conversion
each plan year and folds the converted amount straight into the household's single pooled
`AccountBalances.roth` float — nothing distinguishes a converted dollar that has satisfied its own
individual 5-year seasoning clock (26 U.S.C. §408A(d)(3)(F)) from one that hasn't, and
`withdrawal_sequencing.py`'s Roth draw is blind to this entirely. This feature adds a new sibling
module, `mechanics/roth_conversion_ladder.py`, with one new pure function
(`compute_roth_ladder_consumption()`) that attributes a plan year's Roth withdrawal across an
assumed-already-seasoned "non-lot" portion first, then across tracked conversion lots
oldest-conversion-year-first, flagging (never penalizing in dollars) the portion sourced from a
lot that hasn't yet cleared 5 tax years while at least one household member's translated age is 59
or younger. `comparison/projection.py::run_plan_projection()` maintains the lot list as **purely
local, per-call state** (`roth_conversion_lots: list[RothConversionLot] = []`, initialized fresh
inside the function, exactly like its existing local `years: list[PlanYearProjection] = []`) —
never a caller-supplied parameter, since there is no scenario input representing a pre-existing
lot (FR-002's "pre-existing balance is always already-seasoned" assumption stands in for that).
This is the key scope-narrowing insight versus `012`'s inherited-accounts precedent: because the
list never crosses a `run_plan_projection()` call boundary, **no** threading through
`comparison/compare.py`, `simulation/monte_carlo.py`, `services/bff`, or `apps/streamlit_ui` is
needed — every one of those already calls `run_plan_projection()` once per candidate/path and gets
this feature's behavior automatically, with zero shared-mutable-state risk (unlike inherited
accounts, which *are* caller-supplied and *do* need the "fresh copy per call" discipline).

## Technical Context

**Language/Version**: Python 3.11+ (matches this project's existing constraint; no new dependency).

**Primary Dependencies**: None new — reuses `retirement_planner.tax.SourcedFigure`/`FigureUsage`
(already imported by every other mechanics module carrying a cited figure), stdlib `dataclasses`
only.

**Storage**: N/A — in-memory dataclasses, same as every existing feature. No new scenario YAML
field (see Summary) — this feature has no data-model input surface at all, only new output.

**Testing**: `pytest` (`tests/unit/mechanics/test_roth_conversion_ladder.py` (new),
`tests/unit/comparison/test_projection.py`), mirroring `012`'s own suite layout for a new sibling
mechanics module plus its comparison-layer integration tests. No `services/bff/tests/` or
`apps/streamlit_ui/tests/` changes needed (no new field to mirror there — see Summary).

**Target Platform**: Same as the rest of this project — a single-user, offline-first CLI/library
plus its BFF/Streamlit UI (constitution Principle V).

**Project Type**: Library feature (core `retirement_planner` package) only — no ripple into the BFF
or Streamlit UI packages at all (Summary), unlike every prior feature that added a scenario field.

**Performance Goals**: No material change — `compute_roth_ladder_consumption()` is O(number of
open lots) per plan year, and a Roth conversion ladder scenario has at most a handful of lots open
at once (one per conversion-window year, each closing after 5 years); Constitution Principle VI's
Monte Carlo budget is unaffected (each path's own local lot list is exactly as cheap as the
existing local `years` list already is).

**Constraints**: Must preserve reproducibility (Principle II) — the new logic is pure/deterministic
(no randomness, no I/O). Must not change any numeric output (spending, tax, shortfall, ending
balances) for any household, with or without a Roth conversion configured (FR-007, SC-005) — this
feature adds an informational field, never alters an existing computed value. Must not change
output at all for a household with no Roth conversion configured (FR-008, SC-004).

**Scale/Scope**: One new module (`mechanics/roth_conversion_ladder.py`, one public function, one
new cited figure), one new dataclass (`RothConversionLot`) plus a small result type
(`RothLadderConsumptionResult`) in `mechanics/models.py`, one modified function
(`comparison/projection.py::run_plan_projection()`, purely additive local state), one new
`PlanYearProjection` field (`unseasoned_roth_withdrawal`), and `docs/BRD.md` updates. No changes to
`mechanics/roth_conversion.py`'s or `mechanics/withdrawal_sequencing.py`'s own locked signatures —
this feature reads their already-computed results (`ConversionResult.amount_converted`,
`WithdrawalPlan.sequence_withdrawals`) rather than modifying either function.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design below.*

| Principle | Check | Status |
|---|---|---|
| I. Accuracy Over Cleverness | This feature *removes* a silent gap (a Roth conversion ladder's own seasoning is entirely untracked today) rather than introducing a new one. Its own simplifications — pre-existing balance always assumed seasoned, household-level (not per-owner) age check, whole-plan-year age precision, flag-only (no penalty dollars) — are each documented in spec.md Assumptions/Edge Cases and carried into `docs/BRD.md` (FR-010), not silently absorbed. | PASS |
| II. Reproducibility | `compute_roth_ladder_consumption()` is pure/deterministic (no randomness, no I/O); identical scenario + seed still yields identical output. | PASS |
| III. Auditability | The new 5-year seasoning figure carries a citation and `last_verified` date via `SourcedFigure`/`FigureUsage`, flowing into `PlanYearProjection.figures_used` whenever a plan year's draw actually reaches into a tracked lot — `verified=True` only set after the citation is cross-checked at implementation time, per the constitution's verified-figure gate. | PASS |
| IV. Extensibility Through Module Interfaces | New logic lives entirely behind one new function in one new sibling module, called from exactly one place in the simulation core (`run_plan_projection()`'s per-year loop) — mirrors `012`'s own "new sibling module for a conceptually distinct computation" precedent (research.md Decision 1). | PASS |
| V. Offline-First | No network dependency introduced. | PASS |
| VI. Performance Budget | O(number of open lots) per plan year, materially cheaper than a Monte Carlo path's own return-draw cost; no regression to the Monte Carlo budget (Technical Context). | PASS |
| Paired-draw comparison standard | No comparison axis is added or restructured — every existing `compare_*()` function is unchanged (Summary: the lot list never crosses a call boundary, so nothing needs threading). | PASS |
| Config as data, not code | N/A — this feature adds no new scenario-configurable value (Summary); the 5-year rule itself is a fixed statutory constant, cited like every other such constant (`RMD_START_AGE`, `SS_CLAIMING_AGE_ADJUSTMENT`), not something a household configures. | PASS |

No violations — Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/019-roth-conversion-ladder/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── mechanics-api.md     # addendum to 003/010 (new operation), plus a comparison-api.md
│                             # addendum (addendum to 004/010/011/012/018) for the new
│                             # PlanYearProjection field
└── tasks.md             # Phase 2 output (/speckit-tasks — not created by this command)
```

### Source Code (repository root)

```text
src/retirement_planner/
├── mechanics/
│   ├── models.py                    # + RothConversionLot, RothLadderConsumptionResult
│   ├── roth_conversion_ladder.py    # NEW: compute_roth_ladder_consumption(),
│   │                                 #      ROTH_CONVERSION_SEASONING_YEARS SourcedFigure
│   └── __init__.py                  # re-exports the two new symbols + the new function
└── comparison/
    ├── models.py                # PlanYearProjection gains unseasoned_roth_withdrawal
    └── projection.py            # run_plan_projection() gains local roth_conversion_lots
                                  # state + the per-year attribution call

docs/
└── BRD.md                      # Roth conversion section + §7 known limitations updated

tests/
├── unit/mechanics/test_roth_conversion_ladder.py   # NEW: seasoning/attribution/ordering cases
└── unit/comparison/test_projection.py               # + ladder-flag-in-a-real-projection cases
```

**Structure Decision**: Follows the existing package layout exactly — no new top-level package, no
new deployable unit, and (uniquely among this project's recent features) no ripple into
`services/bff` or `apps/streamlit_ui` at all, since this feature introduces no new
scenario-configurable input (Summary). The new consumption function joins a new sibling module
(`roth_conversion_ladder.py`) rather than `roth_conversion.py` itself, mirroring `012`'s own
"conceptually distinct computation gets a sibling module, not a branch inside an existing locked
function" precedent (`inherited_rmd.py` alongside `rmd.py`) — `compute_roth_conversion()`'s locked
signature (`003`/`010` contracts) is unmodified.

## Complexity Tracking

*No Constitution Check violations — this section is intentionally empty.*
