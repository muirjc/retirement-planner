# Implementation Plan: FICA Payroll Tax on Earned-Income Streams

**Branch**: `022-fica-payroll-tax` | **Date**: 2026-09-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/022-fica-payroll-tax/spec.md`

## Summary

Adds `tax/fica.py` — a new tax-liability module (mirrors `tax/early_withdrawal_penalty.py`'s "flat-rate surtax on a caller-computed base" shape, not an account-mechanics concept) that computes employee-side FICA (6.2% OASDI capped at the wage base, 1.45% Medicare uncapped, both per member; 0.9% Additional Medicare Tax on the household's *combined* earned income above a filing-status threshold) from each member's own `earned_income`-type stream total for the year. Wired into `comparison/projection.py`'s existing `tax_owed` sum (the same variable that already funds federal/state/IRMAA/NIIT/early-withdrawal-penalty from account balances each year) so it genuinely reduces cash flow, not just reports alongside it. Surfaced at the same "cumulative_X_paid" / "median_lifetime_X_paid" level IRMAA/NIIT/the early-withdrawal penalty already are, through `PlanOutcome` → `reporting.aggregation.SummaryStatistics` → Streamlit's `narration.py`.

## Technical Context

**Language/Version**: Python 3.11+ (existing project standard)

**Primary Dependencies**: none new

**Storage**: N/A — no new scenario-configuration input; FICA is entirely derived from `021-pension-annuity-income`'s already-configured `earned_income` streams

**Testing**: `pytest tests/` (core), `pytest apps/streamlit_ui/tests/` (narration display) — existing suites, extended

**Target Platform**: Linux/macOS dev laptop, offline (constitution Principle V)

**Performance Goals**: No material change — O(members) per plan year, negligible

**Constraints**: Must reproduce every existing scenario's output exactly when no `earned_income` streams are configured (the case for every scenario predating `021`); must not alter any existing `compute_plan_year_mechanics()`/`run_plan_projection()` parameter's meaning

**Scale/Scope**: Core library only (`tax`, `comparison`, `reporting`) + Streamlit narration display. No BFF schema change needed (no new scenario input; the new report fields serialize generically the same way `median_lifetime_niit_paid` etc. already do) and no Streamlit *editing* change (nothing new to configure — `earned_income` streams are already configurable per `021`, this feature only changes what their tax consequence is).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Accuracy Over Cleverness**: PASS. The W-2-only (not SECA) scope is an explicit, documented simplification (spec.md Assumptions, to be restated in docs/BRD.md), not silently absorbed.
- **II. Reproducibility**: PASS. No randomness; a pure function of (member earned-income totals, filing status, tax year).
- **III. Auditability**: PASS. Every new figure (OASDI rate, wage base, Medicare rate, Additional Medicare Tax rate + thresholds) is a cited `SourcedFigure`; `FigureUsage` entries flow into the existing `figures_used` union exactly like every other tax module's do.
- **IV. Extensibility Through Module Interfaces**: PASS. One new module, one new function (`compute_fica_tax()`), consumed at exactly one call site in `comparison/projection.py` — mirrors `compute_early_withdrawal_penalty()`'s own integration shape precisely.
- **V. Offline-First**: PASS. Hardcoded `SourcedFigure` schedules, no runtime lookup.
- **VI. Performance Budget**: PASS. Negligible.

No violations — Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/022-fica-payroll-tax/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (addenda to tax-api.md, comparison-api.md, reporting-api.md)
└── tasks.md             # Phase 2 output (/speckit-tasks — not created by this command)
```

### Source Code (repository root)

```text
src/retirement_planner/
├── tax/
│   ├── fica.py            # NEW: OASDI_RATE, OASDI_WAGE_BASE, MEDICARE_RATE,
│   │                       #      ADDITIONAL_MEDICARE_TAX_RATE, ADDITIONAL_MEDICARE_TAX_THRESHOLDS
│   │                       #      SourcedFigures + compute_fica_tax()
│   ├── models.py           # + FicaTaxResult
│   └── __init__.py         # + exports
├── comparison/
│   ├── projection.py       # + _member_earned_income_amounts() helper, compute_fica_tax() call,
│   │                       #   fica_tax.total_fica_tax folded into tax_owed, fica_tax field on
│   │                       #   PlanYearProjection, cumulative_fica_tax_paid in _derive_outcome()
│   └── models.py            # + PlanYearProjection.fica_tax, PlanOutcome.cumulative_fica_tax_paid
└── reporting/
    ├── models.py             # + SummaryStatistics.median_lifetime_fica_tax_paid
    └── aggregation.py        # + median_lifetime_fica_tax_paid derivation (both summarize_run() and
                               #   the deterministic path)

apps/streamlit_ui/src/rp_ui/
└── narration.py            # + "Lifetime FICA payroll tax paid" entry, mirroring the early-withdrawal-
                             #   penalty entry immediately above it

tests/                       # tax/comparison/reporting unit tests; narration UI test
docs/BRD.md                  # new subsection + figure-verification table rows (OASDI rate/wage base,
                              # Medicare rate, Additional Medicare Tax rate/thresholds) + not-modeled
                              # note update (rp-elp's gap closes; SECA/self-employment becomes the new
                              # explicitly-named gap)
```

**Structure Decision**: Extends the existing core-library layer only (no BFF or Streamlit *editing* change needed — see Technical Context). Mirrors `020-early-withdrawal-penalty`'s own integration shape almost exactly, since that is the closest existing precedent (a new flat-ish surtax, funded the same way, reported at the same "cumulative_X"/"median_lifetime_X" level).
