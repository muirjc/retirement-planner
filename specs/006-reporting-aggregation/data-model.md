# Data Model: Reporting & Aggregation

Source: [spec.md](./spec.md) Key Entities section, resolved against research.md's design decisions. Types are described conceptually (Python `dataclasses`, per research.md and following `001`–`005`'s convention) — field names are illustrative, not a locked contract; the locked contract for downstream features is [contracts/reporting-api.md](./contracts/reporting-api.md).

This feature is a **consumer**, not an orchestrator like `004`/`005` or a pure calculator like `002`/`003`: it is the first feature whose functions take another feature's *already-computed result* as input rather than composing other features' functions to produce a new result. It reads `005`'s `SimulationRun`/`SimulationComparisonResult`/`PercentileBand`, `004`'s `ComparisonResult`/`PlanProjection`/`PlanOutcome`, and `002`'s `FigureUsage` — it does not construct or re-derive any of them.

## SummaryStatistics

| Field | Type | Notes |
|---|---|---|
| `candidate_label` | string \| `null` | The candidate's label within a comparison (`run.candidate_label` for a `005` candidate, `projection.strategy.label` for a `004` candidate); `null` when summarizing a single `SimulationRun` outside any comparison (User Story 1). |
| `success_rate` | number \| `null` | Read directly from `SimulationRun.success_rate` for Monte Carlo input; `null` for a deterministic `004` candidate, which has no probability distribution to report a rate over (research.md §2). |
| `ending_balance` | number | Always populated: the median final-year ending balance (`percentile_bands[-1].percentiles[0.50]`) for Monte Carlo input, or the single `PlanOutcome.ending_balance` for a deterministic candidate (research.md §3). |
| `percentile_bands` | list[PercentileBand] \| `null` | `005`'s own unmodified `percentile_bands` for Monte Carlo input; `null` for a deterministic candidate, which has no percentile spread (research.md §2). |
| `median_depletion_age` | number \| `null` | The median, across every path/candidate that depleted, of the deemed household member's age at the plan year depletion first occurred (research.md §1); `null` when nothing depleted (FR-003, Acceptance Scenario US1.3). |
| `median_lifetime_tax_paid` | number | The median `cumulative_tax_paid` across every path/candidate, successful or not (FR-002). For a deterministic candidate (one path), this is simply that path's own `cumulative_tax_paid`. |
| `unverified_figure_names` | list[string] | The distinct (by name) unverified figure names behind this summary, deduplicated (research.md §5); always present, `[]` when nothing is unverified — never `null` (FR-004, Acceptance Scenario US4.2). |

One `SummaryStatistics` is the complete User Story 1 deliverable for a single `SimulationRun` — every other function in this feature either produces a list of these (comparisons) or renders one/several of these to CSV text.

## Comparison Summary Set

Not a distinct dataclass — the entity name for the return value of `summarize_simulation_comparison()`/`summarize_deterministic_comparison()`: an ordered `list[SummaryStatistics]`, one entry per candidate, in the exact order the input comparison result's own candidates (`runs`/`projections`) appear — never re-sorted or re-grouped by this feature (Acceptance Scenario US2.1).

## Export Report

Not a distinct dataclass either — the entity name for the CSV text `run_to_csv_text()`/`simulation_comparison_to_csv_text()`/`deterministic_comparison_to_csv_text()` return (plain `str`). Row shape:

| Export | One row per | Columns |
|---|---|---|
| `run_to_csv_text(run)` | plan year | `plan_year`, one column per requested percentile (e.g. `p10`, `p25`, `p50`, `p75`, `p90`), `has_unverified_figure` |
| `simulation_comparison_to_csv_text(comparison, household, reference_tax_year)` | candidate | `candidate_label`, `success_rate`, `ending_balance`, `median_depletion_age`, `median_lifetime_tax_paid`, `has_unverified_figure` |
| `deterministic_comparison_to_csv_text(comparison, household, reference_tax_year)` | candidate | same columns as the row above, with `success_rate`/`percentile_bands`-derived columns left blank (the CSV rendering of `null`) for every row, since every candidate in a deterministic comparison is deterministic (research.md §2) |

## Relationships

- `summarize_run(run, household, reference_tax_year)` reads `run.success_rate`, `run.percentile_bands`, and `run.figures_used` unmodified, and derives `ending_balance`, `median_depletion_age`, and `median_lifetime_tax_paid` by iterating `run.path_results` (each a `PlanProjection` from `004`, produced by `005`'s per-path call to `run_plan_projection()`) — it does not call `run_plan_projection()` or `run_simulation()` itself, only reads their already-computed output.
- `summarize_simulation_comparison(comparison, household, reference_tax_year)` is `[summarize_run(run, household, reference_tax_year) for run in comparison.runs]`, with `candidate_label` overwritten from each `run.candidate_label` (research.md §4) — a thin loop, not a separate computation path.
- `summarize_deterministic_comparison(comparison, household, reference_tax_year)` is the equivalent loop over `comparison.projections`, via a private per-candidate helper that reads one `PlanProjection`'s `outcome` (`ending_balance`, `first_shortfall_plan_year`, `cumulative_tax_paid`) and `years[*].figures_used` directly, with `success_rate`/`percentile_bands` left `null` (research.md §2, §4).
- `median_depletion_age` for one summary is derived by, for every path/candidate whose `outcome.first_shortfall_plan_year` is not `null`: finding that plan year's `tax_year` in `years`, calling `deemed_rmd_owner(household)` and `member_age_in_tax_year(deemed_owner, tax_year, reference_tax_year)` (both newly-public, reused from `004`, research.md §1), then taking `statistics.median()` of the resulting ages across all such paths/candidates; `null` when the set is empty.
- `run_to_csv_text(run)` reads `run.percentile_bands` directly for its per-row percentile columns and `run.path_results[0].years[y].figures_used` for its per-row `has_unverified_figure` column (research.md §6) — it does not call `summarize_run()` internally, since a per-plan-year export needs data at a different granularity than the run-level `SummaryStatistics` does.
- `simulation_comparison_to_csv_text()`/`deterministic_comparison_to_csv_text()` each call the corresponding `summarize_*_comparison()` function internally and render its `list[SummaryStatistics]` to rows — these two exporters *do* build directly on this feature's own summarization functions, unlike `run_to_csv_text()`.

## State transitions

None — every function in this feature is a pure, stateless transform of its already-computed input, producing a new, equally stateless output (a `SummaryStatistics`, a `list[SummaryStatistics]`, or a CSV `str`) with no persistence anywhere. This feature introduces no state machine and touches no file, network, or database.
