# Implementation Plan: Social Security Spousal and Survivor Benefits

**Branch**: `017-ss-spousal-survivor-benefits` | **Date**: 2026-08-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/017-ss-spousal-survivor-benefits/spec.md`

## Summary

Fixes rp-52n: each household member's Social Security benefit is currently derived entirely
independently (`mechanics/social_security_benefit.py`, `016-ss-claiming-age-actuarial-adjustment`),
with no spousal-benefit floor and no survivor-benefit calculation. This feature adds two new cited
operations to that module — `compute_spousal_benefit_floor()` (a lower-earning spouse's benefit is
raised to up to 50% of the other spouse's PIA, reduced for the claiming spouse's own early claiming
via the SSA's spousal-specific reduction rate, with no delayed-retirement credit) and
`compute_survivor_benefit()` (the higher of two benefit amounts, per the "higher continues, lower
stops" rule) — and one new optional `HouseholdMember` field (`predicted_death_age`) for a future
feature (`rp-g8y`) to consume. The spousal floor is wired into `comparison/projection.py`'s
`_member_gross_social_security_benefits()` (the single per-year call site 016 already established as
the one place every engine path funnels through), so it takes effect in every projection immediately.
The survivor-benefit function and the new data-model field are deliberately **not** wired into a
running projection's per-year loop — that mid-horizon behavior change is `rp-g8y`'s scope.

## Technical Context

**Language/Version**: Python 3.11+ (matches this project's existing constraint; no new dependency).

**Primary Dependencies**: None new — reuses `retirement_planner.tax.SourcedFigure`/`FigureUsage`
(already imported by `mechanics/social_security_benefit.py` and `mechanics/rmd.py`), stdlib
`dataclasses`/`datetime` only.

**Storage**: N/A — in-memory dataclasses and YAML scenario files, same as every existing feature.

**Testing**: `pytest` (`tests/unit/mechanics/test_social_security_benefit.py`,
`tests/unit/scenario/test_loader.py`, `tests/unit/scenario/test_validation.py`,
`tests/unit/comparison/test_projection.py`), mirroring 016's own suite layout; `services/bff/tests/`
and `apps/streamlit_ui/tests/` get the mechanical field-addition coverage 016's research.md Decision 6
already established a precedent for.

**Target Platform**: Same as the rest of this project — a single-user, offline-first CLI/library plus
its BFF/Streamlit UI (constitution Principle V).

**Project Type**: Library feature (core `retirement_planner` package) with mechanical, additive
ripple into the BFF and Streamlit UI packages — not a new deployable unit.

**Performance Goals**: No material change — both new functions are closed-form arithmetic (no loop,
no table scan beyond a single dict lookup), and `compute_spousal_benefit_floor()` is called at most
once per member per plan year (only for an MFJ household, only once both members have claimed),
replacing an already-O(1) per-member computation. Constitution Principle VI's Monte Carlo budget is
unaffected.

**Constraints**: Must preserve reproducibility (Principle II) — same scenario + seed still yields
identical output; must not change a `"single"`-filing-status household's output at all (FR-004); must
not change an MFJ household's output unless the spousal floor actually raises a member's benefit
above what their own claiming-age-adjusted benefit already was (SC-002 — no regression to households
this feature shouldn't affect).

**Scale/Scope**: One modified module (`mechanics/social_security_benefit.py`, gaining two new public
functions and one new private cited-rate figure, plus one new figure carrying the survivor rule's
citation), one modified function (`comparison/projection.py::_member_gross_social_security_benefits()`),
one new dataclass field (`HouseholdMember.predicted_death_age`), one new validation rule (plausibility
warning) plus one new blocking rule (an incoherent death age), mechanical field mirrors in
`services/bff` and `apps/streamlit_ui`, and `docs/BRD.md` updates (§5.3, §6.2a). Confirmed via grep
(research.md Decision 5) that **zero existing test fixtures need numeric correction**: every MFJ
household fixture in this repo (`tests/`, `services/bff/tests/`, `apps/streamlit_ui/tests/`, `e2e/`)
uses a PIA pair (~$32k/$24k, or $30k/$20k) where the lower PIA already exceeds 50% of the higher —
comfortably above the spousal floor's threshold — so User Story 1 shipping is purely additive to
existing output; only new tests exercising the fix itself need a fixture with a larger disparity.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design below.*

| Principle | Check | Status |
|---|---|---|
| I. Accuracy Over Cleverness | This feature *removes* a silent gap (spousal/survivor benefits entirely absent, not even documented as a simplification) rather than introducing a new one. The simplifications this feature does introduce — no family maximum benefit, no "deemed filing" mechanics, survivor benefit ignores the widow(er)'s-own early-claiming reduction and the "widow's limit" cap — are each documented in spec.md Assumptions/Edge Cases and carried into `docs/BRD.md` (FR-008, FR-010), not silently absorbed. | PASS |
| II. Reproducibility | Both new functions are pure/deterministic (no randomness, no I/O); identical scenario + seed still yields identical output. | PASS |
| III. Auditability | Both new figures (spousal reduction rate; survivor "higher of two" rule) carry a citation and `last_verified` date via `SourcedFigure`/`FigureUsage`, flowing into `PlanYearProjection.figures_used` exactly like 016's own `SS_CLAIMING_AGE_ADJUSTMENT` already does. `verified=True` only set after the citation is actually cross-checked at implementation time, per the constitution's verified-figure gate. | PASS |
| IV. Extensibility Through Module Interfaces | New logic lives behind two new functions with locked signatures in the existing `mechanics/social_security_benefit.py` module, called from exactly one place in the simulation core (`_member_gross_social_security_benefits()`) for the spousal floor; the survivor function is called from nowhere in the core yet (by design — `rp-g8y`'s job) so it cannot regress anything by construction. | PASS |
| V. Offline-First | No network dependency introduced. | PASS |
| VI. Performance Budget | O(1) per member per plan year; no regression to the Monte Carlo budget (see Technical Context). | PASS |
| Paired-draw comparison standard | No comparison axis is added or restructured by this feature — every existing comparison (`compare_states`, `compare_withdrawal_strategies`, `compare_roth_conversion_strategies`, `compare_claiming_age_grid`) is unaffected in structure; only the benefit *amount* each MFJ candidate uses can change. | PASS |
| Config as data, not code | `predicted_death_age` is a scenario YAML field, not a hardcoded value. | PASS |

No violations — Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/017-ss-spousal-survivor-benefits/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── scenario-api.md      # addendum to 001/010/016
│   └── mechanics-api.md     # addendum to 003/010/016
└── tasks.md             # Phase 2 output (/speckit-tasks — not created by this command)
```

### Source Code (repository root)

```text
src/retirement_planner/
├── scenario/
│   ├── models.py              # HouseholdMember gains predicted_death_age
│   ├── loader.py               # _build_household_member() parses the new optional field
│   └── validation.py           # _validate_household() gains a blocking + a warning rule
├── mechanics/
│   ├── social_security_benefit.py   # + compute_spousal_benefit_floor(), compute_survivor_benefit()
│   ├── models.py                    # + SpousalBenefitResult, SurvivorBenefitResult
│   └── __init__.py                  # re-exports the two new symbols
└── comparison/
    └── projection.py           # _member_gross_social_security_benefits() applies the spousal floor

services/bff/src/rp_bff/
└── schemas.py                  # HouseholdMemberRequest gains predicted_death_age

apps/streamlit_ui/pages/
└── 1_Scenarios.py              # per-member predicted death age input, mirroring full_retirement_age

docs/
└── BRD.md                      # §5.3, §6.2a updated (data-model.md)

tests/
├── unit/mechanics/test_social_security_benefit.py   # + spousal floor / survivor cases
├── unit/scenario/test_loader.py                      # predicted_death_age parsing cases
├── unit/scenario/test_validation.py                  # blocking + plausibility-warning cases
└── unit/comparison/test_projection.py                # spousal-floor-applies-in-projection cases

services/bff/tests/  and  apps/streamlit_ui/tests/
    # mechanical field-mirror coverage where each package's existing pattern already tests
    # full_retirement_age the same way (016 research.md Decision 6 precedent)
```

**Structure Decision**: Follows the existing package layout exactly — no new top-level package, no
new deployable unit, no new module. Both new functions join
`mechanics/social_security_benefit.py` rather than a new sibling module, since they share that
module's exact shape (PIA/FRA/claiming-age-keyed, `SourcedFigure`-cited, no dependency on
`scenario/`) and its existing `_DOCUMENTED_YEARS`/rate-figure pattern (research.md Decision 1).

## Complexity Tracking

*No Constitution Check violations — this section is intentionally empty.*
