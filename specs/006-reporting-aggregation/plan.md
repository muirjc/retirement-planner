# Implementation Plan: Reporting & Aggregation

**Branch**: `006-reporting-aggregation` | **Date**: 2026-08-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-reporting-aggregation/spec.md`

## Summary

A pure, offline computation layer — `retirement_planner.reporting` — that turns `005`'s `SimulationRun`/`SimulationComparisonResult` and `004`'s `ComparisonResult` into decision-ready `SummaryStatistics` (success rate, ending balance, percentile bands, median depletion age, median lifetime tax paid, and every unverified figure name behind those numbers) and into spreadsheet-ready CSV text. No HTTP, no chart rendering, no new dependency — this is the last pure-library feature before `007`'s BFF wraps everything built so far in an HTTP boundary. Like `004`/`005`, this is a downstream-consumer library: it computes nothing `002`–`005` don't already compute, it only aggregates and shapes their existing output.

## Technical Context

**Language/Version**: Python 3.11+ — same project, same interpreter floor as `001`–`005`.

**Primary Dependencies**: Standard library only (`dataclasses`, `statistics`, `csv`, `io`), plus this feature's own in-repo dependencies on `retirement_planner.scenario` (`Household`), `retirement_planner.tax` (`FigureUsage`), `retirement_planner.comparison` (`ComparisonResult`, `PlanProjection`, `PlanOutcome`, and two small renamed-to-public helpers — see research.md §1), and `retirement_planner.simulation` (`SimulationRun`, `SimulationComparisonResult`, `PercentileBand`). No new third-party runtime dependency — continuing `001`–`005`'s precedent, and consistent with `docs/frontend_architecture.md`'s own framing that the web/UI dependency departure belongs entirely to the future `007`/`008` features, never to this one.

**Storage**: None. This feature holds no figures of its own and persists nothing — it reads already-computed result objects and returns new, equally ephemeral ones.

**Testing**: pytest — continuing `001`–`005`'s convention.

**Target Platform**: Same as `001`–`005`: local developer/user machine, offline, invoked as a library.

**Project Type**: Single Python library project (`src/` layout) — continuing `001`–`005`'s structure, adding a sibling `reporting` subpackage alongside `scenario`, `tax`, `mechanics`, `comparison`, `simulation`, plus one small additive rename inside `004`'s already-shipped `comparison/projection.py` (research.md §1).

**Performance Goals**: Every operation this feature performs is a single O(paths) or O(candidates) pass over already-computed data (an existing `SimulationRun` may hold up to ~5,000 pre-computed `PlanProjection`s; summarizing it means iterating that list once for depletion ages, once for cumulative tax, and a constant-time read of already-deduplicated `figures_used`/already-computed `percentile_bands`) — no new simulation, tax, or mechanics computation is performed. Expect low-single-digit milliseconds even at the 5,000-path reference scale; comfortably inside SC-005's "no perceptible added delay" bar and Constitution Principle VI's budget without requiring any of `005`'s parallelism machinery.

**Constraints**: No network access at any point (Principle V); identical input produces identical summary/export output on every call (Principle II, FR-013); no unverified figure already present in an input's `figures_used` is ever dropped, altered, or left unrepresented (Principle III, FR-011); this feature performs no tax/mechanics/comparison/simulation computation of its own (FR-014).

**Scale/Scope**: One `SimulationRun` (up to ~5,000 paths) or one comparison result (up to the largest candidate set `004`/`005` support, e.g. the 81-cell claiming-age grid) summarized or exported per call — the same scale `004`/`005` already operate at, since this feature adds no new fan-out of its own.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against all six principles plus the Technology/Architecture Constraints and Development Workflow gates, following the same evaluation `002`–`005` did:

- **I. Accuracy Over Cleverness** — ✅ PASS. One real simplification is made and documented rather than silently absorbed: a Monte Carlo run's per-plan-year "was an unverified figure involved" CSV column uses `path_results[0]`'s per-year `figures_used` as representative for that plan year across every path in the run, rather than inspecting all thousands of paths — justified because every path within one run shares an identical tax-year-per-plan-year schedule (only dollar amounts differ across paths, never which `SourcedFigure`s a given tax year consults), recorded in research.md §6 rather than assumed. No other simplification exists — every numeric aggregate (median, success rate, percentile bands) is read or derived directly from `004`/`005`'s own already-correct output.
- **II. Reproducibility** — ✅ PASS. No randomness anywhere in this feature; `summarize_run()`/`summarize_*_comparison()`/the CSV exporters are pure functions of their inputs — identical `SimulationRun`/`ComparisonResult` plus identical `household`/`reference_tax_year` arguments always produce identical output (FR-013, quickstart.md's repeat-call assertion).
- **III. Auditability** — ✅ PASS. This feature introduces no new externally-sourced figure of its own — it only reads `verified`/`FigureUsage` data `002`/`003` already attached and `005` already deduplicated. `SummaryStatistics.unverified_figure_names` and every CSV export's per-row verification indicator are populated from that existing data and are always present (even when empty, FR-004/FR-010), never omitted or collapsed away — this feature is a pass-through *amplifier* for auditability (making it impossible to miss), not a new source of it.
- **IV. Extensibility Through Module Interfaces** — ✅ PASS. `summarize_simulation_comparison()` and `summarize_deterministic_comparison()` are thin loops over `summarize_run()`/an internal per-candidate helper — adding a new comparison axis to `005` or a new candidate shape to `004` requires no change here, since this feature consumes `SimulationRun`/`PlanProjection` shapes generically, never branching on which axis or strategy produced them. The one change this feature makes outside its own subpackage — renaming two private helpers in `004`'s `comparison/projection.py` to public and exporting them (research.md §1) — is additive and mechanical: their behavior is unchanged, only their visibility, mirroring the precedent `005` set widening `004`'s `DeterministicReturnAssumption`.
- **V. Offline-First, No Runtime Network Dependency** — ✅ PASS. Pure computation over caller-supplied, already-offline `004`/`005` output; no I/O of any kind.
- **VI. Performance Budget** — ✅ PASS, and unlike `005` this is not a flagged risk: every operation is a single linear pass over data `004`/`005` already computed, with no new simulation/mechanics/tax work and no new fan-out (Performance Goals above). No mitigation or benchmark gate is needed the way `005`'s parallel-dispatch decision required one.

**Technology & Architecture Constraints — three interpretations worth recording explicitly:**

- *"Config as data, not code"* — N/A; this feature accepts already-constructed result objects and a household/reference-tax-year pair as plain arguments, hardcoding no scenario data of its own.
- *Paired-draw comparison is the standard pattern* — N/A directly (this feature doesn't run comparisons, it summarizes their already-computed output), but `summarize_simulation_comparison()`'s per-candidate loop preserves the pairing `005` already established (same input order, same candidate count) rather than re-deriving or re-ordering it.
- *Scope boundary with the working document* — Directly relevant: this feature is what makes the source document's "feeding results into the existing markdown working document workflow (pipe-table conventions)" ask concrete — its CSV export exists specifically for that hand-off, without this feature or its output ever modeling any of the qualitative, non-financial factors that document tracks.

**Development Workflow & Quality Gates:**

- *Regression baseline* — N/A in the "reproduce prototype output" sense, same posture `004`/`005` recorded: the prototype scripts had no separable reporting/aggregation layer to diff against (their charting and CSV logic was inline, ad hoc, and out of this refactor's scope per the source document's own phased plan).
- *Verified-figure gate* — N/A for new figures (this feature introduces none, per Principle III above); it must, however, never let an existing unverified figure appear indistinguishable from a verified one in its own output — enforced by FR-004/FR-010/FR-011 and this feature's own test suite.
- *Unit test coverage for numeric primitives* — Required: `statistics.median()`-based aggregation (lifetime tax, depletion age) against hand-computed reference cases; the "not applicable" branch for a 100%-success run (no depletion age) and for a deterministic `ComparisonResult` (no success rate/percentile bands); the unverified-figure deduplication-by-name logic; and the CSV row-shaping functions against small, hand-checked example outputs — each per spec.md's Acceptance Scenarios.

**Post-Phase 1 re-check**: Confirmed after generating research.md, data-model.md, contracts/reporting-api.md, and quickstart.md — no new violations. `SummaryStatistics.unverified_figure_names` being a mandatory, always-populated field (never `Optional`) keeps Principle III's "present even when empty" requirement mechanically enforced by the type itself, not merely by convention; research.md's explicit documentation of the per-plan-year figure-representativeness simplification (§6) keeps Principle I satisfied without discovering it late; the `004` rename-and-export (§1) stays additive and behavior-preserving, confirmed by `004`'s own existing test suite continuing to pass unmodified once its imports are updated.

## Project Structure

### Documentation (this feature)

```text
specs/006-reporting-aggregation/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── reporting-api.md
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
    │   ├── models.py                    # unchanged
    │   ├── projection.py                # _member_age_in_tax_year -> member_age_in_tax_year,
    │   │                                 # _deemed_rmd_owner -> deemed_rmd_owner (research.md §1)
    │   │                                 # -- rename only, behavior unchanged
    │   └── __init__.py                  # +export member_age_in_tax_year, deemed_rmd_owner
    ├── simulation/                      # 005-simulation-engine (unchanged)
    │   └── ...
    └── reporting/
        ├── __init__.py
        ├── models.py                    # SummaryStatistics
        ├── aggregation.py               # summarize_run(), summarize_simulation_comparison(),
        │                                # summarize_deterministic_comparison() (FR-001-FR-007)
        └── export.py                    # run_to_csv_text(), simulation_comparison_to_csv_text(),
                                          # deterministic_comparison_to_csv_text() (FR-008-FR-010)

tests/
├── unit/
│   ├── comparison/
│   │   └── test_projection.py          # +cases confirming the renamed helpers' behavior is
│   │                                    # unchanged (unchanged file, extended per research.md §1)
│   └── reporting/
│       ├── test_aggregation.py         # median/percentile/not-applicable logic (US1, US2)
│       └── test_export.py              # CSV row shaping, verification-status column (US3, US4)
└── integration/
    └── test_reporting_lifecycle.py     # full quickstart.md walkthrough, US1-US4
```

**Structure Decision**: Continues `001`–`005`'s single Python library, `src/` layout — `reporting/` is a sibling subpackage to `scenario`, `tax`, `mechanics`, `comparison`, and `simulation` inside `retirement_planner`, and is the first subpackage to depend on both `comparison` and `simulation` simultaneously as *consumers* of their output types rather than as an orchestrator of new computation (contrast with `005`, which called `004`'s functions to produce new results; `006` only reads results `004`/`005` already produced). The dependency graph stays a strict layer order (`scenario`, `tax` → `mechanics` → `comparison` → `simulation` → `reporting`) with no cycles. The one change this feature makes outside its own subpackage — renaming two private helpers to public in `004`'s `comparison/projection.py` and exporting them from `comparison/__init__.py` — is additive and behavior-preserving, mirroring the precedent `005` set widening `004`'s `DeterministicReturnAssumption` (research.md §1).

## Complexity Tracking

*No constitution violations were found (see Constitution Check above) — this section is not needed.*
