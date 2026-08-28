# Implementation Plan: Simulation Engine

**Branch**: `005-simulation-engine` | **Date**: 2026-08-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-simulation-engine/spec.md`

## Summary

A multi-path Monte Carlo layer built on top of `004-strategy-comparison-layer`'s single-projection loop: generate a shared, seeded set of randomly drawn annual-return sequences (the "Paired-Draw Set," parametric-normal by default, historical-block-bootstrap as an alternative), run `run_plan_projection()` once per path per candidate substituting each path's own per-year returns for `004`'s single fixed value, and aggregate the resulting per-path `PlanProjection`s into a success rate and percentile ending-balance bands. The same pre-generated path set is reused, unmodified, across every candidate in a paired-draw comparison — including a new state-of-residence axis `004` never built — so any outcome difference is attributable only to the compared dimension. A configurable stress-scenario overlay and an optional survival-adjusted success metric are additive layers on top of the same aggregation machinery. Like `001`–`004`, this is an offline library feature with no CLI and no report rendering (§3.6, future).

## Technical Context

**Language/Version**: Python 3.11+ — same project, same interpreter floor as `001`–`004`.

**Primary Dependencies**: Standard library only — `random` (seeded correlated-normal draws and block bootstrap), `statistics` (percentile aggregation), `concurrent.futures.ProcessPoolExecutor` (path-level parallelism, research.md §7), `dataclasses`/`typing` — plus this feature's own in-repo dependencies on `retirement_planner.scenario` (`Household`, `MarketAssumptions`, `SimulationSettings`), `retirement_planner.tax` (`FigureUsage`, `SourcedFigure`, `STATE_MODULES`), `retirement_planner.mechanics` (`AccountBalances`), and `retirement_planner.comparison` (`StrategyConfiguration`, `PlanProjection`, `run_plan_projection` — this feature's primary consumer dependency, with one additive signature widening described in research.md §1). No new third-party runtime dependency, continuing `002`–`004`'s precedent; research.md §6 records why `numpy` was considered and rejected.

**Storage**: Two new package-embedded, read-only static data tables (a historical annual real-return series and an actuarial survival table), following `002`'s existing `SourcedFigure`-per-module convention for externally-sourced, citable figures — no database, no runtime file I/O.

**Testing**: pytest — continuing `001`–`004`'s convention. Includes a dedicated performance benchmark test (research.md §7) asserting the reference-scale budget, not only correctness.

**Target Platform**: Same as `001`–`004`: local developer/user machine, offline, invoked as a library — now optionally spanning multiple CPU cores via stdlib multiprocessing for path-level parallelism.

**Project Type**: Single Python library project (`src/` layout) — continuing `001`–`004`'s structure, adding a sibling `simulation` subpackage alongside `scenario`, `tax`, `mechanics`, and `comparison`, plus one additive signature change inside `comparison/projection.py` and `comparison/models.py` (research.md §1).

**Performance Goals**: Reference-scale simulation — 3,000–5,000 paths, up to 9 candidate states or comparable strategy/order/claiming-age candidate counts — completes in well under a minute on a standard laptop (source document §4, Constitution Principle VI), matching the existing (numpy-based) prototype's established budget using a pure-Python, multiprocessing-parallelized design instead (research.md §7).

**Constraints**: No network access at any point (Principle V); identical scenario/configuration/path-count/seed/mode always produces identical per-path returns and aggregated results regardless of worker count (Principle II, FR-005); every paired-draw comparison reuses the identical pre-generated path set — path-for-path — across every candidate (FR-007, FR-009); every `FigureUsage` `002`/`003`/`004` attach to a plan year, plus this feature's own historical-series/survival-curve figures, is retained (FR-019).

**Scale/Scope**: One household, one full retirement horizon (~30–40 plan years), up to roughly 5,000 return paths per candidate, across up to 9 candidate states or a handful of strategy/order candidates or an 81-cell claiming-age grid (mirroring `004`'s established scope) — the state axis and path-level Monte Carlo aggregation are the two capabilities `004` explicitly left for this feature (`004`'s plan.md Performance Goals; contracts/comparison-api.md § Consumption expectations).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against all six principles plus the Technology/Architecture Constraints and Development Workflow gates, following the same evaluation `002`–`004` did:

- **I. Accuracy Over Cleverness** — ✅ PASS. Real simplifications are made and each is explicitly documented rather than silently absorbed: (1) one blended real return per year (equity/bond blend, same formula `004` established) stands in for separately tracked equity/bond paths, since `004`'s account-growth mechanics only ever apply one rate to all three account types (research.md §2, inherited from `004`'s own Decision 6); (2) the historical-bootstrap series and the actuarial survival table are both shipped as illustrative, `verified=False` `SourcedFigure`/`SurvivalCurve` placeholders pending a primary source (research.md §4–5), exactly mirroring `002`'s state-tax-figure precedent; (3) survival-adjusted scoring uses a fixed probability-≥-0.5 "presumed alive" threshold per member rather than per-path stochastic death sampling, recorded as a deliberate scope choice (research.md §5) matching the spec's own deterministic-threshold framing (spec.md US5 Acceptance Scenario 3).
- **II. Reproducibility** — ✅ PASS. All randomness is drawn from a single `random.Random(seed)` stream consumed in a fixed, documented order before any parallel dispatch begins (research.md §3, §7) — identical scenario, path count, seed, and return-generation mode always produce identical per-path return sequences and aggregated results (FR-005), regardless of whether path-level work is parallelized, since parallel workers only consume pre-generated, order-indexed `ReturnPath` objects and never generate randomness themselves.
- **III. Auditability** — ✅ PASS. The two new externally-sourced figures this feature introduces (the historical return series, the survival table) are `SourcedFigure`/`SurvivalCurve` instances carrying `citation`/`last_verified`/`verified` fields, `verified=False` until confirmed against a primary source (research.md §4–5), and their `FigureUsage` snapshots propagate into `SimulationRun.figures_used` alongside every `002`/`003`/`004` figure a path's years already carry (FR-019) — nothing is dropped or silently resolved.
- **IV. Extensibility Through Module Interfaces** — ✅ PASS. Adding a new comparison axis (this feature's own state axis) required no change to `run_plan_projection()`'s per-year mechanics — only a new thin `compare_states()` loop over the existing per-candidate-call pattern `004` established (research.md §2). Historical-bootstrap and parametric return generation are two interchangeable functions producing the identical `ReturnPath` shape (research.md §3, §4) — `run_simulation()`/`compare_*()` never branch on which mode produced their input. The one change outside this feature's own subpackage — widening `run_plan_projection()`'s `return_assumption` parameter from a single concrete type to a small shared protocol (research.md §1) — is additive: every existing `004` caller and test continues to work unmodified, since `DeterministicReturnAssumption` keeps its existing field and gains a method.
- **V. Offline-First, No Runtime Network Dependency** — ✅ PASS. Pure computation over caller-supplied arguments, `002`–`004`'s already-offline functions, and this feature's own package-embedded static data tables; no I/O of any kind at simulation run time.
- **VI. Performance Budget** — ⚠️ PASS, WITH A DOCUMENTED RISK AND MITIGATION. Unlike `002`–`004` (single-path or small-candidate-count workloads), this feature is the first to run the per-plan-year mechanics/tax loop at genuine Monte-Carlo volume (thousands of paths × decades × up to 9 candidates) — a workload the source document's own prototype meets only by being numpy-vectorized. Research.md §7 records this honestly as a real risk rather than assuming it away, and commits to two mitigations that keep this feature stdlib-only: (a) path-level parallelism via `ProcessPoolExecutor`, since paths are embarrassingly parallel and involve no shared mutable state; (b) a required implementation-phase benchmark test asserting the reference-scale budget before this feature is considered done, not merely a plan-level assertion that it will be fine. This is not a constitution violation being waived — it is Principle VI's own "flagged and justified (or optimized) before being merged" clause being followed for the first feature where the budget is genuinely at risk.

**Technology & Architecture Constraints — three interpretations worth recording explicitly:**

- *"Config as data, not code"* — `ReturnPath`, `StressScenario`, and `SurvivalCurve` are all plain data a caller constructs (or this feature's generator functions produce from `001`'s existing `MarketAssumptions`/`SimulationSettings`); no simulation parameter is hardcoded into the aggregation logic.
- *Paired-draw comparison is the standard pattern* — This is the feature that finally makes the constitution's own named pattern ("identical random draws reused across scenarios") literally true rather than structurally anticipated: `004` established the comparison *shape* under one shared deterministic value; this feature reuses the identical `list[ReturnPath]` object — not merely an equal value — across every candidate in a comparison (research.md §2), so the pairing is enforced by construction, not by convention.
- *Extensibility applied to a genuinely new axis* — The state axis (`compare_states()`) is the first comparison this project builds where the varying input isn't a `StrategyConfiguration` field at all, but a top-level `run_plan_projection()` argument (`state`) that `004`'s `StrategyConfiguration` never included. Handling it as its own `compare_*()` function (research.md §2) rather than stretching `StrategyConfiguration` to carry an optional state field keeps `004`'s existing three comparison functions and their tests completely untouched.
- *Scope boundary with the working document* — N/A, not implicated by this feature.

**Development Workflow & Quality Gates:**

- *Regression baseline* — N/A in the "reproduce prototype output exactly" sense, same posture `004` recorded: the existing prototype's Monte Carlo results were produced by numpy's RNG under a different algorithm than this feature's stdlib `random`-based generator, so bit-for-bit reproduction against the prototype's saved CSVs is not meaningful; the source document's Validation Plan reconciliation item is about directional conclusions (success-rate ordering across states/strategies), which this feature's quickstart.md exercises.
- *Verified-figure gate* — Required: the historical return series and survival table (research.md §4–5) MUST NOT be marked `verified=True` until cross-checked against a primary source, mirroring `002`'s SC/DE gate.
- *Unit test coverage for numeric primitives* — Required: the correlated-normal draw formula (research.md §3) against hand-computed reference draws for a fixed seed; the block-bootstrap resampling logic against a small synthetic historical series; the stress-scenario window-override arithmetic; the survival-adjusted success determination; and the percentile-band aggregation — each against constructed reference cases, per spec.md's Acceptance Scenarios.

**Post-Phase 1 re-check**: Confirmed after generating research.md, data-model.md, contracts/simulation-api.md, and quickstart.md — no new violations. The `ReturnSchedule` protocol keeps `004`'s existing callers mechanically unaffected (Principle IV); pre-generating the full seeded draw sequence before any parallel dispatch keeps Principle II intact under parallelism; `SimulationRun.figures_used`'s union-not-derivation contract keeps Principle III's pass-through discipline consistent with `004`'s own precedent; the Performance Budget risk from the initial Constitution Check remains open until the implementation-phase benchmark test referenced in research.md §7 actually runs — `/speckit-tasks` MUST include that benchmark as a task, not treat this plan's mitigation as self-certifying.

## Project Structure

### Documentation (this feature)

```text
specs/005-simulation-engine/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── simulation-api.md
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
    ├── mechanics/                       # 003-retirement-account-mechanics (unchanged)
    │   └── ...
    ├── comparison/                      # 004-strategy-comparison-layer
    │   ├── models.py                    # +ReturnSchedule protocol; DeterministicReturnAssumption
    │   │                                # gains return_for_plan_year() (research.md §1) — existing
    │   │                                # annual_real_return field untouched
    │   └── projection.py                # run_plan_projection()'s growth_factor line now calls
    │                                     # return_assumption.return_for_plan_year(plan_year)
    │                                     # instead of reading .annual_real_return directly
    │                                     # (research.md §1) — no other line changes
    └── simulation/
        ├── __init__.py
        ├── models.py                    # ReturnPath, StressScenario, SurvivalCurve,
        │                                # SimulationRun, PercentileBand, SimulationComparisonResult
        ├── returns.py                   # generate_return_paths() (parametric, FR-001),
        │                                # generate_historical_bootstrap_paths() (FR-012),
        │                                # apply_stress_scenario() (FR-014)
        ├── historical_data.py           # HISTORICAL_RETURNS: SourcedFigure[tuple[float, float]]
        │                                # (research.md §4) — verified=False pending source
        ├── survival_data.py             # SURVIVAL_TABLE: SurvivalCurve per household-member
        │                                # role (research.md §5) — verified=False pending source
        ├── monte_carlo.py               # run_simulation(): runs run_plan_projection() once per
        │                                # ReturnPath, aggregates into SimulationRun (FR-002–FR-004,
        │                                # FR-006, FR-017–FR-019); parallelized via
        │                                # ProcessPoolExecutor (research.md §7)
        └── compare.py                   # compare_states(), compare_roth_conversion_strategies(),
                                          # compare_withdrawal_sequencing_strategies(),
                                          # compare_claiming_age_grid() (FR-007–FR-011, FR-016):
                                          # thin loops over run_simulation(), reusing one
                                          # return_paths list across every candidate

tests/
├── unit/
│   ├── comparison/
│   │   └── test_projection.py          # +cases: ReturnPath-driven growth (unchanged file,
│   │                                    # extended per research.md §1)
│   └── simulation/
│       ├── test_returns.py             # correlated-normal draw formula, block bootstrap,
│       │                               # stress overlay (research.md §3, §4, §6; US1, US3, US4)
│       ├── test_monte_carlo.py         # success rate, percentile bands, depletion tracking,
│       │                               # reproducibility under parallelism (research.md §7; US1)
│       ├── test_compare.py             # paired-draw path reuse across all four axes,
│       │                               # single-candidate case, mode-mismatch rejection (US2)
│       └── test_survival.py            # survival-adjusted success determination (research.md §5; US5)
└── integration/
    ├── test_simulation_lifecycle.py    # full quickstart.md walkthrough, US1–US4
    └── test_simulation_performance.py  # reference-scale benchmark (research.md §7; SC-003) —
                                         # the Constitution Check's Performance Budget gate
```

**Structure Decision**: Continues `001`–`004`'s single Python library, `src/` layout — `simulation/` is a sibling subpackage to `scenario`, `tax`, `mechanics`, and `comparison` inside `retirement_planner`, and is the first subpackage to depend on all four of the others simultaneously (`scenario` for `MarketAssumptions`/`SimulationSettings`, `tax` for `STATE_MODULES`/`SourcedFigure`, `mechanics` for `AccountBalances`, `comparison` for `run_plan_projection()`/`StrategyConfiguration`/`PlanProjection`). The dependency graph stays a strict layer order (`scenario`, `tax` → `mechanics` → `comparison` → `simulation`) with no cycles. The one change this feature makes outside its own subpackage — widening `comparison.models.DeterministicReturnAssumption` and the type `comparison.projection.run_plan_projection()` accepts for `return_assumption` — is additive (research.md §1), mirroring the precedent `004` set by adding one registry entry to `003`'s `WITHDRAWAL_STRATEGIES` rather than reimplementing withdrawal sequencing itself.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No constitution violations were found (see Constitution Check above) — the Performance Budget item is a flagged risk with a committed mitigation and required benchmark gate, not an unresolved violation, so this section is not needed.*
