# Implementation Plan: Social Security Earnings Test (Withholding + FRA Recredit)

**Branch**: `025-ss-earnings-test` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/025-ss-earnings-test/spec.md`

## Summary

Extends `mechanics/social_security_benefit.py` (016/017's own module) with a third operation,
`compute_earnings_test_withholding()`, plus two new `SourcedFigure`s (the below-FRA and
FRA-attainment-year annual exempt-earnings thresholds, both pinned to their 2026 SSA-published
values per `tax/fica.py`'s existing "annually-varying-in-reality figure held flat" convention) and
one new dataclass, `_EarningsTestRates`, mirroring `_ClaimingAgeAdjustmentRates`'s shape. Wired into
`comparison/projection.py`'s `_member_gross_social_security_benefits()` — the single existing call
site that already derives each member's claiming-age-adjusted benefit — so a member's benefit for a
plan year is reduced by withholding whenever that member has claimed before FRA and has a nonzero
`earned_income` stream that year. `run_plan_projection()`'s own per-plan-year loop carries one new
piece of local, per-member cross-year state (`cumulative_earnings_test_withheld: dict[str, float]`,
mirroring `roth_conversion_lots`'s existing "purely local, never a function parameter" precedent) so
that once a member's age reaches their FRA year, the accumulated withheld total permanently raises
that member's benefit from then on — SSA's real recredit rule, not a modeled permanent loss.

## Technical Context

**Language/Version**: Python 3.11+ (existing project standard)

**Primary Dependencies**: none new

**Storage**: N/A — no new scenario-configuration input; the earnings test is entirely derived from
each member's already-configured `ss_claim_age`/`full_retirement_age`/`ss_annual_benefit` (016) and
already-configured `earned_income` streams (021, already read by 022's FICA module via the same
`_member_earned_income_amounts()` helper this feature reuses)

**Testing**: `pytest tests/` (core) — existing suite, extended with unit tests on
`compute_earnings_test_withholding()` against the SSA's own 2026 published exempt amounts/ratios,
plus a `run_plan_projection()`-level integration test proving the full withhold-then-recredit
lifecycle for one member across several plan years

**Target Platform**: Linux/macOS dev laptop, offline (constitution Principle V)

**Performance Goals**: No material change — O(members) additional work per plan year, negligible

**Constraints**: Must reproduce every existing scenario's output exactly when no member both claims
before FRA and has a nonzero `earned_income` stream during any pre-FRA claimed year (the case for
every scenario predating this feature); must not alter `compute_social_security_benefit()`'s own
locked signature (016/017 contract) — this feature only adds new operations alongside it, consistent
with 017's own precedent of extending this module rather than replacing anything in it

**Scale/Scope**: Core library only (`mechanics`, `comparison`). No BFF schema change needed (no new
scenario input) and no Streamlit *editing* change (nothing new to configure — `earned_income`
streams and claiming-age/FRA inputs are already configurable). `docs/BRD.md` §5.3/§6.2a updated per
FR-010.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Accuracy Over Cleverness**: PASS. The whole-plan-year granularity simplifications (FRA-year
  earnings counted for the whole year rather than only months before FRA; withholding applied as a
  smooth dollar reduction rather than whole-month benefit checks; recredit computed from cumulative
  dollars withheld rather than a real-time monthly reconciliation) are each explicitly documented in
  the module docstring and `docs/BRD.md`, mirroring this module's own existing "months early/delayed
  ... not a real calendar-month count" precedent — not silently absorbed.
- **II. Reproducibility**: PASS. No randomness; a pure function per plan year of (that member's
  claiming-age-adjusted benefit, that member's own earned income, ages, FRA, tax year) plus one
  deterministic running total threaded through `run_plan_projection()`'s own already-deterministic
  loop.
- **III. Auditability**: PASS. Both new exempt-earnings thresholds are cited `SourcedFigure`s
  (2026 SSA COLA Fact Sheet, the same source `tax/fica.py`'s `OASDI_WAGE_BASE` already cites);
  `FigureUsage` entries flow into the existing per-plan-year `figures_used` union exactly like every
  other mechanics operation's do.
- **IV. Extensibility Through Module Interfaces**: PASS. One new operation
  (`compute_earnings_test_withholding()`) in the existing module, consumed at the one existing call
  site (`_member_gross_social_security_benefits()`) that already owns per-member benefit derivation
  — mirrors 017's own "extend this module, one new call site" integration shape.
- **V. Offline-First**: PASS. Hardcoded `SourcedFigure` schedules, no runtime lookup.
- **VI. Performance Budget**: PASS. Negligible — O(members) per plan year, same order as the
  claiming-age adjustment it extends.

No violations — Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/025-ss-earnings-test/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (addendum to mechanics-api.md)
└── tasks.md             # Phase 2 output (/speckit-tasks — not created by this command)
```

### Source Code (repository root)

```text
src/retirement_planner/
├── mechanics/
│   ├── social_security_benefit.py
│   │     # + SS_EARNINGS_TEST_EXEMPT_AMOUNT_BELOW_FRA, SS_EARNINGS_TEST_EXEMPT_AMOUNT_FRA_YEAR
│   │     #   SourcedFigures, _EarningsTestRates, compute_earnings_test_withholding(),
│   │     #   compute_earnings_test_recredit()
│   └── models.py
│         # + EarningsTestWithholdingResult, EarningsTestRecreditResult
└── comparison/
    ├── projection.py
    │     # _member_gross_social_security_benefits(): + earned_income parameter, withholding call
    │     #   + cumulative_earnings_test_withheld local state in run_plan_projection(), FRA-year
    │     #   recredit call
    └── models.py
          # + PlanYearProjection.member_ss_earnings_test_withheld: dict[str, float]

tests/unit/mechanics/test_social_security_benefit.py   # + earnings-test/recredit unit tests
tests/unit/comparison/test_projection.py                # + integration test across FRA transition
docs/BRD.md   # §6.2a rewritten to describe what's now modeled; §5.3 gap entry closed/narrowed;
              # new figure-verification table rows for the two exempt-earnings thresholds
```

**Structure Decision**: Extends the existing `mechanics.social_security_benefit` module exactly as
`017-ss-spousal-survivor-benefits` extended `016`'s — new operations alongside the existing ones,
one new call site in `comparison/projection.py`, no BFF/Streamlit editing change (no new
scenario-configuration surface).
