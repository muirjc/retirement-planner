# Implementation Plan: Retirement Account Mechanics

**Branch**: `003-retirement-account-mechanics` | **Date**: 2026-08-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-retirement-account-mechanics/spec.md`

## Summary

A pure, offline account-mechanics library: given a plan year's RMD-eligible age/balance inputs, computes the Required Minimum Distribution (IRS Uniform Lifetime Table, or the Joint Life and Last Survivor Table when a sole-beneficiary spouse is more than 10 years younger); given a spending need and starting account balances, computes a withdrawal plan under a configured, swappable sequencing strategy (default: RMD, then taxable, then traditional, then Roth); and, within a configured conversion window, executes a Roth conversion under a configured, swappable strategy (fill-to-bracket-ceiling or fixed-dollar-amount). Bracket-ceiling conversions call `002-tax-calculation-engine`'s Social Security taxability logic rather than reimplementing it. Like `001` and `002`, this is a downstream-consumer library: no CLI, no multi-year simulation loop, no strategy comparison across configurations (that's the future §3.4 "Strategy/Optimization Layer" feature), and no HSA modeling (explicitly deferred to a future Phase 5 feature per spec.md's Assumptions).

## Technical Context

**Language/Version**: Python 3.11+ — same project, same interpreter floor as `001` and `002` (`pyproject.toml` already pins `>=3.11`).

**Primary Dependencies**: Standard library only (`dataclasses`, `typing`), plus this feature's own in-repo dependencies on `retirement_planner.scenario` (for `RothConversionPlan`'s shape, per FR-016) and `retirement_planner.tax` (for `compute_taxable_social_security` and the `SourcedFigure`/`FigureUsage` types, per FR-015/FR-019). No new third-party runtime dependency — like `002`, this is arithmetic over Python-native data structures, not file parsing or numeric-library territory.

**Storage**: None. RMD divisor tables and the RMD-required starting age are Python module-level constants (`SourcedFigure` instances, continuing `002`'s pattern), loaded once at import time — not files read at call time, not a database.

**Testing**: pytest — continuing `001`/`002`'s convention.

**Target Platform**: Same as `001`/`002`: local developer/user machine, offline, invoked as a library.

**Project Type**: Single Python library project (`src/` layout) — continuing `001`/`002`'s structure, adding a sibling `mechanics` subpackage alongside `scenario` and `tax`.

**Performance Goals**: A single plan-year's RMD + withdrawal-plan + conversion computation should complete in well under 10ms — this is arithmetic over a handful of account balances and one bracket-ceiling lookup, not I/O. As with `002`, this matters beyond this feature alone: the future simulation engine (§3.5, not yet spec'd) will call these mechanics once per simulated year per path (potentially 5,000 paths × ~35 years), so rule tables must be loaded once at import time, not reloaded per call.

**Constraints**: No network access at any point (FR-017); RMD table figures carry citation/date/verification-status inline via `SourcedFigure`, reusing `002`'s convention rather than inventing a second one (FR-019); every mechanic (RMD, withdrawal sequencing, Roth conversion) is independently swappable/extensible without touching the others (FR-014); every computation is reproducible — identical inputs always produce identical outputs (FR-018).

**Scale/Scope**: This feature's own direct scope is one plan year, one household, per call. Designed so the future simulation engine can call it at high volume (thousands of paths × decades) without this feature's design becoming the bottleneck — same posture `002` took for the tax engine.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against all six principles plus the Technology/Architecture Constraints and Development Workflow gates, following the same evaluation `002` did (this is the first feature planned after `002`, so the constitution is fully active, same as it was for `002`):

- **I. Accuracy Over Cleverness** — ✅ PASS. RMD divisor tables and the RMD-required starting age ship as illustrative placeholders (`verified=False`) exactly like `002`'s tax figures, documented in spec.md's Assumptions (FR-019) rather than presented as settled. The withdrawal-sequencing and Roth-conversion simplifications this feature makes (household-level account balances rather than per-owner sub-accounts; ordinary income scoped to RMD + traditional withdrawals, matching `002`'s existing income-scope Assumption) are recorded in data-model.md, not silently absorbed.
- **II. Reproducibility** — ✅ PASS (trivially). No randomness is involved; identical balances, ages, strategy configuration, and plan year always produce identical outputs (FR-018).
- **III. Auditability** — ✅ PASS for the figures this feature owns (RMD tables, RMD-required starting age): each is a `SourcedFigure` with citation, last-verified date, and verification status (FR-019), traceable the same way `002`'s tax figures are. Withdrawal-sequencing and Roth-conversion *strategies* are not externally-sourced legal figures — they're mechanics choices — so Principle III does not require citations for them; where a conversion strategy needs a tax-law figure (Social Security taxability), it obtains it from `002`'s already-audited `SourcedFigure`s rather than re-deriving it, per FR-015.
- **IV. Extensibility Through Module Interfaces** — ✅ PASS. FR-005/FR-014/SC-006 require withdrawal-sequencing and Roth-conversion strategies to be added without touching RMD logic or another strategy's implementation — see the Structure Decision below for how each mechanic's registry pattern satisfies this, mirroring `002`'s `STATE_MODULES` precedent.
- **V. Offline-First, No Runtime Network Dependency** — ✅ PASS. FR-017 states this directly; RMD tables are in-process constants, same as `002`'s tax rule tables.
- **VI. Performance Budget** — ✅ PASS (not directly exercised yet). This feature's own computations are trivial; see Performance Goals above for why the design still guards the future high-volume simulation use case, same posture as `002`.

**Technology & Architecture Constraints — two interpretations worth recording explicitly:**

- *"Config as data, not code"* — RMD divisor tables and the RMD-required starting age are legal facts, not scenario inputs, exactly the same category `002`'s tax rate tables fell into. This plan keeps them as version-controlled Python module constants (`SourcedFigure` instances) for the same reason `002` did: Principle III requires citation/review discipline that user-editable YAML would undermine. No violation — this is `002`'s precedent applied consistently, not a new interpretation.
- *Extensibility (Principle IV) applied differently across this feature's two strategy points* — Roth-conversion strategies (fill-to-bracket-ceiling vs. fixed-dollar-amount) differ in actual computation logic, so they're modeled as independent callables in a registry, directly mirroring `002`'s `STATE_MODULES: dict[str, Callable[...]]` pattern. Withdrawal-sequencing strategies, by contrast, differ *only* in which account type is drawn from in which order — the draw-down arithmetic (respect available balance, roll unmet remainder to the next account type, report shortfall) is identical regardless of order. Modeling each sequencing strategy as a full callable would duplicate that shared arithmetic per strategy, risking the exact kind of per-implementation drift Principle IV exists to prevent. This plan instead registers sequencing strategies as **named account-type orderings** (`dict[str, tuple[AccountType, ...]]`) consumed by one shared, reviewed draw-down function — adding a new sequencing strategy is still "one new registry entry, zero other files change" (satisfying FR-005/FR-006/SC-006), just via a data entry instead of a new function. See data-model.md § WithdrawalSequencingStrategy for the full rationale.
- *Paired-draw comparison is the standard pattern* — N/A. This feature has no Monte Carlo or comparative-run logic; like `002`, it's a deterministic calculator the future simulation engine (§3.5) and strategy-comparison engine (§3.4) will call repeatedly.
- *Scope boundary with the working document* — N/A, not implicated by this feature.

**Development Workflow & Quality Gates:**

- *Regression baseline* — N/A in the "preserve existing output" sense: the prototype's RMD logic only ever implemented the Uniform Lifetime Table path with a single hardcoded conversion rule and a fixed withdrawal order; the Joint Life Table branch, swappable sequencing, and swappable conversion strategy are new capabilities, not behavior this plan must reproduce unchanged.
- *Verified-figure gate* — Every RMD table figure shipped with this feature (RMD-required starting age, Uniform Lifetime Table, Joint Life and Last Survivor Table) starts `verified=False` unless actually cross-checked against IRS Pub. 590-B during implementation — same discipline `002` applied to its tax figures.
- *Unit test coverage for numeric primitives* — Required: RMD divisor-table lookups against published IRS Pub. 590-B reference values for both tables (spec.md SC-001/SC-002), plus withdrawal-plan and conversion-amount arithmetic against hand-calculated examples (SC-003–SC-005).

**Post-Phase 1 re-check**: Confirmed after generating research.md, data-model.md, contracts/mechanics-api.md, and quickstart.md — no new violations. `SourcedFigure` reuse (data-model.md) keeps RMD-table citation/verification mandatory (Principle III) without inventing a second auditability mechanism; `WITHDRAWAL_STRATEGIES` and `CONVERSION_STRATEGIES` (contracts/mechanics-api.md) keep both strategy points independently extensible (Principle IV); quickstart.md labels every illustrative RMD-table figure as an unverified placeholder rather than presenting it as settled (Principle I).

## Project Structure

### Documentation (this feature)

```text
specs/003-retirement-account-mechanics/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md          # Phase 1 output (/speckit-plan command)
├── contracts/               # Phase 1 output (/speckit-plan command)
│   └── mechanics-api.md
└── tasks.md                   # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── retirement_planner/
    ├── __init__.py
    ├── scenario/                     # 001-scenario-config-management (unchanged)
    │   └── ...
    ├── tax/                         # 002-tax-calculation-engine (unchanged)
    │   └── ...
    └── mechanics/
        ├── __init__.py
        ├── models.py                 # AccountBalances, WithdrawalLineItem, WithdrawalPlan,
        │                             # RmdResult, ConversionResult, PlanYearMechanicsResult
        ├── rmd.py                     # compute_rmd(...); RMD_START_AGE, UNIFORM_LIFETIME_TABLE,
        │                             # JOINT_LIFE_TABLE as SourcedFigure (FR-001–FR-003, FR-019)
        ├── withdrawal_sequencing.py    # WITHDRAWAL_STRATEGIES registry (name -> account-type
        │                             # ordering) + compute_withdrawal_plan() dispatcher and
        │                             # shared draw-down arithmetic (FR-004–FR-007)
        ├── roth_conversion.py           # CONVERSION_STRATEGIES registry (name -> callable) +
        │                             # compute_roth_conversion() dispatcher; fill_to_bracket_ceiling
        │                             # and fixed_dollar_amount implementations (FR-008–FR-013)
        └── plan_year.py                  # compute_plan_year_mechanics(...) orchestrator: RMD ->
                                          # withdrawal plan -> Roth conversion for one plan year
                                          # (ties the three mechanics together per Edge Cases)

tests/
├── unit/
│   └── mechanics/
│       ├── test_rmd.py                    # Uniform Lifetime + Joint Life table lookups (US1)
│       ├── test_withdrawal_sequencing.py    # default + swapped sequences, shortfall (US2)
│       ├── test_roth_conversion.py           # both conversion strategies, window boundaries (US3)
│       └── test_plan_year.py                  # RMD-not-convertible interaction (Edge Cases)
└── integration/
    └── test_mechanics_lifecycle.py              # full plan-year walkthrough, quickstart.md scenarios
```

**Structure Decision**: Continues `001`/`002`'s single Python library, `src/` layout — `mechanics/` is a sibling subpackage to `scenario/` and `tax/` inside `retirement_planner`, and is the first subpackage in this project to depend on another subpackage: it imports `retirement_planner.scenario.RothConversionPlan`'s shape (FR-016) and calls `retirement_planner.tax.social_security.compute_taxable_social_security` plus reuses `retirement_planner.tax.models.SourcedFigure`/`FigureUsage` (FR-015, FR-019). `scenario/` and `tax/` remain independent of each other and of `mechanics/`, so the dependency graph stays a strict layer order (`scenario`, `tax` → `mechanics`) with no cycles. RMD table figures live inside `mechanics/rmd.py` as module-level `SourcedFigure` constants, not under top-level `config/`, for the same reason `002` kept tax rule tables in-package rather than in `config/` (see that plan's Constitution Check note) — they are code-reviewed reference data, not user-editable scenario input.

## Complexity Tracking

*No constitution violations were found (see Constitution Check above) — this section is not needed.*
