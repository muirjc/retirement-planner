# Implementation Plan: Social Security Claiming-Age Actuarial Adjustment

**Branch**: `016-ss-claiming-age-actuarial-adjustment` | **Date**: 2026-08-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/016-ss-claiming-age-actuarial-adjustment/spec.md`

## Summary

Fixes rp-n44: the Social Security claiming-age comparison grid currently varies only *when* a
member's flat benefit starts, never the *amount*, so it mechanically favors claiming as early as
possible. This feature adds an optional per-member `full_retirement_age` (defaulting to the
member's own claiming age, so every existing scenario's output is unchanged unless it opts in),
reinterprets the existing `ss_annual_benefit` field as the member's Primary Insurance Amount, and
adds a new cited `retirement_planner.mechanics.compute_social_security_benefit()` operation that
derives the actually-paid annual benefit via the standard SSA early-reduction / delayed-retirement-
credit formulas. One call site — `comparison/projection.py`'s
`_member_gross_social_security_benefits()` — is updated to use it; every other engine path
(single-run, every other comparison axis, Monte Carlo simulation) inherits the fix automatically
because they all already funnel through `run_plan_projection()` (research.md Decision 4).

## Technical Context

**Language/Version**: Python 3.11+ (matches this project's existing constraint; no new dependency).

**Primary Dependencies**: None new — reuses `retirement_planner.tax.SourcedFigure`/`FigureUsage`
(already imported outside the `tax` package by `mechanics/rmd.py`, confirming the precedent), stdlib
`dataclasses`/`datetime` only.

**Storage**: N/A — in-memory dataclasses and YAML scenario files, same as every existing feature.

**Testing**: `pytest` (`tests/unit/mechanics/`, `tests/unit/scenario/`, `tests/unit/comparison/`),
mirroring the existing suite layout; `services/bff/tests/`, `apps/streamlit_ui/tests/`, and
`e2e/` get the mechanical field-addition updates research.md Decision 6 describes.

**Target Platform**: Same as the rest of this project — a single-user, offline-first CLI/library
plus its BFF/Streamlit UI (constitution Principle V).

**Project Type**: Library feature (core `retirement_planner` package) with mechanical, additive
ripple into the BFF and Streamlit UI packages — not a new deployable unit.

**Performance Goals**: No material change — `compute_social_security_benefit()` is closed-form
arithmetic (no loop, no table scan beyond a single dict lookup), called once per household member
per plan year, replacing a call that was already O(1) (`member.ss_annual_benefit if ... else 0.0`).
Constitution Principle VI's Monte Carlo budget is unaffected.

**Constraints**: Must preserve reproducibility (Principle II) — same scenario + seed still yields
identical output; must not change any existing scenario's output unless it explicitly sets a
`full_retirement_age` different from its `ss_claim_age` (research.md Decision 3).

**Scale/Scope**: One new module (`mechanics/social_security_benefit.py`), one modified function
(`comparison/projection.py::_member_gross_social_security_benefits()`), one new dataclass field
(`HouseholdMember.full_retirement_age`), one new validation rule, mechanical field mirrors in
`services/bff` and `apps/streamlit_ui`, and `docs/BRD.md` updates. No fixture-breaking migration
(research.md Decision 3) — the ~34 files referencing `ss_annual_benefit` found by grep need no
changes for correctness; only tests that specifically exercise claiming-age sensitivity gain new
cases.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design below.*

| Principle | Check | Status |
|---|---|---|
| I. Accuracy Over Cleverness | The early-reduction/delayed-credit approximation this feature *removes* (flat benefit regardless of claiming age) is replaced with the real SSA formula, not a new simplification. The one real simplification introduced — fractional months computed as a continuous linear function of claiming age rather than SSA's whole-month processing — is documented in spec.md Edge Cases and data-model.md, not silently absorbed. | PASS |
| II. Reproducibility | `compute_social_security_benefit()` is pure/deterministic (no randomness, no I/O); identical scenario + seed still yields identical output. | PASS |
| III. Auditability | New figure (`SS_CLAIMING_AGE_ADJUSTMENT`) carries a citation and `last_verified` date via `SourcedFigure`/`FigureUsage`, flows into `PlanYearProjection.figures_used` like every other figure (research.md Decision 2). `verified=True` only set after the citation is actually cross-checked at implementation time, per the constitution's verified-figure gate. | PASS |
| IV. Extensibility Through Module Interfaces | New logic lives behind one new function with a locked signature (`compute_social_security_benefit()`), called from exactly one place in the simulation core (`_member_gross_social_security_benefits()`) — adding it does not require the core loop (`run_plan_projection()`'s overall structure) to change shape, only one internal helper's body. | PASS |
| V. Offline-First | No network dependency introduced. | PASS |
| VI. Performance Budget | O(1) per member per plan year; no regression to the Monte Carlo budget (see Technical Context). | PASS |
| Paired-draw comparison standard | `compare_claiming_age_grid()` (both `comparison/` and `simulation/`) is unchanged in structure — it still reuses identical random draws across every claiming-age candidate; only the benefit *amount* each candidate now uses differs, which is the dimension actually under test. | PASS |
| Config as data, not code | `full_retirement_age` is a scenario YAML field, not a hardcoded value. | PASS |

No violations — Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/016-ss-claiming-age-actuarial-adjustment/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── scenario-api.md      # addendum to 001/010
│   └── mechanics-api.md     # addendum to 003/010
└── tasks.md             # Phase 2 output (/speckit-tasks — not created by this command)
```

### Source Code (repository root)

```text
src/retirement_planner/
├── scenario/
│   ├── models.py              # HouseholdMember gains full_retirement_age
│   ├── loader.py               # _build_household_member() resolves the default
│   └── validation.py           # _validate_household() gains the FRA-range warning
├── mechanics/
│   ├── social_security_benefit.py   # NEW: compute_social_security_benefit()
│   ├── models.py                    # SocialSecurityBenefitResult
│   └── __init__.py                  # re-exports the new symbols
├── comparison/
│   └── projection.py           # _member_gross_social_security_benefits() calls the new function
└── (simulation/ — no change; reuses comparison.run_plan_projection(), research.md Decision 4)

services/bff/src/rp_bff/
└── schemas.py                  # HouseholdMemberRequest gains full_retirement_age

apps/streamlit_ui/pages/
└── 1_Scenarios.py              # per-member FRA input, mirroring existing SS fields

docs/
└── BRD.md                      # §2.1, §6.2 updated (data-model.md)

tests/
├── unit/mechanics/test_social_security_benefit.py   # NEW
├── unit/scenario/test_loader.py                      # FRA default-resolution cases
├── unit/scenario/test_validation.py                  # FRA plausibility-warning cases
└── unit/comparison/test_compare_claiming_age_grid.py # amount-varies-by-age cases

services/bff/tests/  and  apps/streamlit_ui/tests/  and  e2e/
    # mechanical field-mirror coverage where each package's existing pattern already tests
    # other per-member fields the same way (research.md Decision 6)
```

**Structure Decision**: Follows the existing package layout exactly — no new top-level package,
no new deployable unit. The new calculation lives in `mechanics/` alongside `rmd.py` (the closest
existing analog: a cited, age-keyed, table-driven dollar-amount derivation), not in `tax/` (which
only taxes an already-known income figure, per research.md Decision 1).

## Complexity Tracking

*No Constitution Check violations — this section is intentionally empty.*
