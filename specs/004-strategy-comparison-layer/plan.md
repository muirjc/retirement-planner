# Implementation Plan: Strategy Comparison Layer

**Branch**: `004-strategy-comparison-layer` | **Date**: 2026-08-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-strategy-comparison-layer/spec.md`

## Summary

An offline orchestration library that chains `003`'s per-plan-year account mechanics and `002`'s federal/state tax calculation into a full multi-year retirement-horizon projection for one strategy configuration, then runs that same projection repeatedly — holding one shared deterministic market-return assumption fixed — across candidate Roth conversion strategies, withdrawal sequencing orders, or Social Security claiming-age pairs, returning a single structured comparison result per dimension. Like `001`–`003`, this is a downstream-consumer library: no CLI, no genuine multi-path Monte Carlo simulation (deferred to the future §3.5 Simulation Engine feature, which this feature's per-year loop is designed to slot randomly-drawn returns into without restructuring), and no chart/table/report rendering (§3.6, also future).

## Technical Context

**Language/Version**: Python 3.11+ — same project, same interpreter floor as `001`–`003` (`pyproject.toml` already pins `>=3.11`).

**Primary Dependencies**: Standard library only (`dataclasses`, `typing`, `itertools` for a caller building a claiming-age grid), plus this feature's own in-repo dependencies on `retirement_planner.scenario` (`Household`, `HouseholdMember`, `MarketAssumptions`), `retirement_planner.tax` (`compute_federal_tax`, `compute_state_tax`, `IncomeComponents`, `FigureUsage`), and `retirement_planner.mechanics` (`compute_rmd`, `compute_plan_year_mechanics`, `compute_withdrawal_plan`, `AccountBalances`, `WithdrawalPlan`, `PlanYearMechanicsResult`). No new third-party runtime dependency — like `002`/`003`, this is orchestration and arithmetic over Python-native data structures, not file parsing or numeric-library territory.

**Storage**: None. This feature holds no figures of its own (research.md §1) — everything it reads is either a caller-supplied argument or a `SourcedFigure` already owned by `002`/`003`.

**Testing**: pytest — continuing `001`–`003`'s convention.

**Target Platform**: Same as `001`–`003`: local developer/user machine, offline, invoked as a library.

**Project Type**: Single Python library project (`src/` layout) — continuing `001`–`003`'s structure, adding a sibling `comparison` subpackage alongside `scenario`, `tax`, and `mechanics`, and adding one registry entry to `mechanics.withdrawal_sequencing` (research.md §8).

**Performance Goals**: A single plan year's mechanics + tax + tax-funding-withdrawal computation is a handful of calls into already-sub-10ms functions (`003`'s own budget) — well under 50ms. A full 35-year single projection therefore completes in well under 2 seconds; the largest comparison this feature defines (the full claiming-age grid, 9×9 = 81 candidates × 35 years ≈ 2,835 year-computations) stays comfortably under a few seconds on a laptop, consistent with Constitution Principle VI and leaving headroom for the future simulation engine's much larger path counts.

**Constraints**: No network access at any point (Principle V); every comparison holds `return_assumption` identical across all its candidates (FR-009); every projection and comparison is reproducible — identical inputs always produce identical outputs (FR-012); every `FigureUsage` `002`/`003` attach to a year's figures is retained, not dropped (FR-013).

**Scale/Scope**: This feature's own direct scope is one household, one full retirement horizon (≈30-40 plan years), across up to roughly 100 candidate configurations per comparison call (the claiming-age grid being the largest). Designed so the future Simulation Engine feature can call `run_plan_projection()` at Monte-Carlo path volumes (thousands of paths × decades) without this feature's per-year step sequence changing shape (contracts/comparison-api.md § Consumption expectations).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against all six principles plus the Technology/Architecture Constraints and Development Workflow gates, following the same evaluation `002` and `003` did:

- **I. Accuracy Over Cleverness** — ✅ PASS. Three real simplifications are made here, and all three are explicitly documented rather than silently absorbed: (1) full-horizon comparisons run under one fixed, deterministic return rather than genuine Monte Carlo (research.md §1, spec.md Assumptions); (2) RMD determination in this feature's projections always uses the Uniform Lifetime Table, never the Joint Life Table, because `001`'s schema has no sole-beneficiary field to determine eligibility correctly (research.md §3); (3) a plan year's tax bill is funded from account balances without an iterative gross-up solve (research.md §5). Each is recorded in research.md with its rationale and rejected alternative, and surfaces in data-model.md/contracts so it's visible to any downstream consumer, not just buried in code comments.
- **II. Reproducibility** — ✅ PASS. No randomness is introduced anywhere in this feature (the deterministic return is a fixed formula over caller-supplied means, research.md §1); identical scenario, strategy configuration, and return assumption always produce identical outputs (FR-012, quickstart.md §1's repeat-run assertion).
- **III. Auditability** — ✅ PASS. This feature introduces no new externally-sourced legal figure of its own (the blended return is user-supplied market opinion from `001`'s existing schema, not a citable fact) — nothing here needs a `SourcedFigure`. Every `FigureUsage` `002`/`003` already attach to a year's tax/RMD figures is carried through `PlanYearProjection.figures_used` untouched and unioned, never dropped (FR-013) — this feature is a pass-through for auditability, not a source of it.
- **IV. Extensibility Through Module Interfaces** — ✅ PASS. Adding a new Roth conversion strategy, withdrawal sequencing order, or claiming-age combination to compare requires only adding an entry to the `candidates`/`claiming_age_grid` list a caller passes in — none of `run_plan_projection()`, `compare_roth_conversion_strategies()`, `compare_withdrawal_sequencing_strategies()`, or `compare_claiming_age_grid()` branches on which concrete strategies exist (contracts/comparison-api.md). The one registry change this feature makes (a second withdrawal order, research.md §8) is a single data entry in `003`'s already-designed extension point, not new branching logic.
- **V. Offline-First, No Runtime Network Dependency** — ✅ PASS. Pure computation over caller-supplied arguments and `002`/`003`'s already-offline functions; no I/O of any kind.
- **VI. Performance Budget** — ✅ PASS. See Performance Goals above — this feature's own multi-year, multi-candidate loops stay comfortably within budget by composing already-cheap per-year functions; the largest defined comparison (81-cell claiming-age grid) is still on the order of a few thousand cheap calls, not a scaling risk.

**Technology & Architecture Constraints — three interpretations worth recording explicitly:**

- *"Config as data, not code"* — Every `StrategyConfiguration` and the claiming-age grid are plain data a caller constructs and passes in; this package hardcodes no list of "the strategies that exist" beyond the two registries `003` already owns. A future feature reading these lists from a scenario file or CLI arguments changes only the caller, not this package.
- *Paired-draw comparison is the standard pattern* — This is the first feature to actually implement the discipline the constitution names (previously prototype-only): FR-009 requires every candidate within one `ComparisonResult` to share the identical `return_assumption`, and `data-model.md`'s `ComparisonResult.return_assumption` field makes that sharing checkable, not just asserted. The genuine "paired random draw across scenarios" the constitution ultimately describes still needs the future Simulation Engine's stochastic return generation — this feature establishes the comparison *structure* (hold everything but one dimension fixed, compare outcomes) that random draws will plug into unchanged (contracts/comparison-api.md § Consumption expectations), rather than deferring the whole pattern.
- *Extensibility applied to two genuinely different "candidate list" shapes* — Roth-conversion and withdrawal-sequencing comparisons vary one `StrategyConfiguration` field across an explicit candidate list (a small, caller-curated set); the claiming-age comparison varies two independent integers across a combinatorial grid a caller typically builds with `itertools.product` (up to 81 cells for the full 62-70 range). Both are handled by the same `run_plan_projection()` call repeated per candidate — the grid's size difference is a caller construction detail (contracts/comparison-api.md's consumption note explicitly says this module doesn't enumerate the grid itself), not a reason to special-case claiming-age comparison's internals.
- *Scope boundary with the working document* — N/A, not implicated by this feature.

**Development Workflow & Quality Gates:**

- *Regression baseline* — N/A in the "preserve existing prototype output exactly" sense: the prototype scripts ran a single fixed strategy through a full Monte Carlo simulation, not a deterministic multi-strategy comparison — this feature's comparison mechanism is new relative to the prototype (per spec.md's Input), so there is nothing bit-for-bit to reproduce yet; that reconciliation is explicitly the source document's Validation Plan item, deferred until the future Simulation Engine feature exists to make a fair comparison possible.
- *Verified-figure gate* — N/A for new figures (this feature introduces none, per Principle III above); the existing gate on `002`'s and `003`'s figures is unaffected — this feature never marks anything "verified" itself.
- *Unit test coverage for numeric primitives* — Required: `derive_deterministic_return()`'s blend formula against hand-calculated examples; the age-translation formula (research.md §2); the tax-funding second-withdrawal arithmetic (research.md §5); the claiming-age-to-Social-Security-income translation; and the deemed-RMD-owner selection (research.md §4) — each against constructed reference cases, per spec.md's Acceptance Scenarios.

**Post-Phase 1 re-check**: Confirmed after generating research.md, data-model.md, contracts/comparison-api.md, and quickstart.md — no new violations. `DeterministicReturnAssumption` reuse across every `ComparisonResult.projections` entry keeps the paired-comparison discipline (Principle IV / the constitution's paired-draw standard) mechanically checkable rather than merely asserted; `PlanYearProjection.figures_used`'s union-not-derivation contract keeps Principle III's pass-through intact; research.md's explicit documentation of the Uniform-Lifetime-Table-only, deterministic-return, and non-gross-up simplifications keeps Principle I satisfied without discovering any of them late.

## Project Structure

### Documentation (this feature)

```text
specs/004-strategy-comparison-layer/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── comparison-api.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── retirement_planner/
    ├── __init__.py
    ├── scenario/                        # 001-scenario-config-management (unchanged)
    │   └── ...
    ├── tax/                             # 002-tax-calculation-engine (unchanged)
    │   └── ...
    ├── mechanics/                       # 003-retirement-account-mechanics
    │   ├── ...                          # (unchanged)
    │   └── withdrawal_sequencing.py     # +1 registry entry: "rmd_traditional_taxable_roth"
    │                                    # -> (traditional, taxable, roth) (research.md §8, FR-007)
    └── comparison/
        ├── __init__.py
        ├── models.py                    # DeterministicReturnAssumption, StrategyConfiguration,
        │                                # PlanYearProjection, PlanOutcome, PlanProjection,
        │                                # ComparisonResult
        ├── returns.py                   # derive_deterministic_return() (FR-003)
        ├── projection.py                # run_plan_projection(): the per-plan-year orchestration
        │                                # loop (RMD -> mechanics -> tax -> tax-funding withdrawal
        │                                # -> growth) (FR-001, FR-002, FR-004)
        └── compare.py                   # compare_roth_conversion_strategies(),
                                          # compare_withdrawal_sequencing_strategies(),
                                          # compare_claiming_age_grid() (FR-005–FR-011): thin loops
                                          # over run_plan_projection()

tests/
├── unit/
│   ├── mechanics/
│   │   └── test_withdrawal_sequencing.py   # +cases for the new registry entry (unchanged file,
│   │                                        # extended per research.md §8)
│   └── comparison/
│       ├── test_returns.py                 # blend formula (research.md §1)
│       ├── test_projection.py              # age translation, deemed-RMD-owner selection,
│       │                                   # tax-funding withdrawal, growth, shortfall
│       │                                   # continuation (research.md §2, §4–§7; US1)
│       ├── test_compare_roth_conversion.py     # US2
│       ├── test_compare_withdrawal_sequencing.py  # US3
│       └── test_compare_claiming_age_grid.py      # US4, bounds rejection (FR-010)
└── integration/
    └── test_comparison_lifecycle.py            # full quickstart.md walkthrough, all four sections
```

**Structure Decision**: Continues `001`–`003`'s single Python library, `src/` layout — `comparison/` is a sibling subpackage to `scenario/`, `tax/`, and `mechanics/` inside `retirement_planner`, and is the first subpackage to depend on all three of the others simultaneously (`scenario` for `Household`/`MarketAssumptions`, `tax` for federal/state calculation, `mechanics` for per-year account mechanics). The dependency graph stays a strict layer order (`scenario`, `tax` → `mechanics` → `comparison`) with no cycles — `comparison` is a pure consumer of the other three, and none of them import from it. The one change this feature makes outside its own subpackage — a second entry in `mechanics.withdrawal_sequencing.WITHDRAWAL_STRATEGIES` — is additive to an existing registry `003` designed for exactly this (data-model.md § Relationships), not a modification of `003`'s shared draw-down logic.

## Complexity Tracking

*No constitution violations were found (see Constitution Check above) — this section is not needed.*
