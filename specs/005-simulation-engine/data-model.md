# Data Model: Simulation Engine

Source: [spec.md](./spec.md) Key Entities section, resolved against research.md's design decisions. Types are described conceptually (Python `dataclasses`, per research.md and following `001`–`004`'s convention) — field names are illustrative, not a locked contract; the locked contract for downstream features is [contracts/simulation-api.md](./contracts/simulation-api.md).

Like `004`, this feature is an **orchestrator**: it composes `001`'s `MarketAssumptions`/`SimulationSettings`, `002`'s `SourcedFigure`/`FigureUsage`/`STATE_MODULES`, `003`'s `AccountBalances`, and — most directly — `004`'s `StrategyConfiguration`/`PlanProjection`/`run_plan_projection()`, calling the latter once per path per candidate rather than re-deriving any of its per-year logic.

## ReturnSchedule (protocol, `comparison.models`)

| Member | Type | Notes |
|---|---|---|
| `return_for_plan_year(plan_year)` | `(int) -> float` | The one method `run_plan_projection()` now calls for its growth-factor line (research.md §1). Implemented by both `DeterministicReturnAssumption` (`004`, ignores `plan_year`) and `ReturnPath` (this feature, indexes by `plan_year`). |

Not a new runtime type — a structural typing seam. Recorded here because it's the one piece of this feature's data model that lives outside `simulation/`.

## ReturnPath

| Field | Type | Notes |
|---|---|---|
| `start_plan_year` | int | The plan year `annual_returns[0]` corresponds to — makes `return_for_plan_year()` self-contained (research.md §1). |
| `annual_returns` | list[float] | One blended real return per plan year, `start_plan_year` through `start_plan_year + len(annual_returns) - 1` (research.md §3). Index `i` is plan year `start_plan_year + i`. |
| `generation_mode` | enum: `parametric`, `historical_bootstrap` | Which generator produced this path (research.md §3–4) — every path in one `Paired-Draw Set` shares the same mode (FR-011). |
| `figures_used` | list[FigureUsage] | Empty for `parametric` mode (a blend of user-supplied market opinion, not a citable fact — mirrors `004`'s Decision 1). For `historical_bootstrap` mode, the `HISTORICAL_RETURNS.usage_for_year()` snapshots for every historical year actually drawn into this path (research.md §4). |

`return_for_plan_year(plan_year)` returns `annual_returns[plan_year - start_plan_year]`; a `plan_year` outside the covered range is a caller error (the horizon requested from `generate_return_paths()`/`generate_historical_bootstrap_paths()` must cover at least as many plan years as the projection will iterate — contracts/simulation-api.md documents this as a precondition).

## Paired-Draw Set

Not a distinct dataclass — the entity name for **the same `list[ReturnPath]` object**, generated once by `generate_return_paths()` or `generate_historical_bootstrap_paths()`, passed unmodified into `run_simulation()`/every `compare_*()` call. Its identity (not merely its values) is what makes the paired-draw guarantee structural rather than conventional (research.md §2).

## StressScenario

| Field | Type | Notes |
|---|---|---|
| `magnitude` | float | The forced blended real return applied to every plan year within the shock window (e.g., `-0.30`) — replaces, not adjusts, the path's originally generated return for those years. |
| `duration_years` | int | How many consecutive plan years the shock covers. |
| `start_plan_year` | int | The first plan year the shock applies to; the window is `[start_plan_year, start_plan_year + duration_years)`. |

`apply_stress_scenario(paths, stress, horizon_last_plan_year)` returns a new `list[ReturnPath]` (via `dataclasses.replace`, not mutation) with every path's `annual_returns` overridden within the window and every other year untouched; `generation_mode` and `figures_used` are carried through unchanged. Raises `ValueError` if `start_plan_year + duration_years - 1 > horizon_last_plan_year` (FR-015).

## SurvivalCurve

| Field | Type | Notes |
|---|---|---|
| `person_name` | string | Matches a `001` `HouseholdMember.person_name` this curve applies to. |
| `probabilities_by_age` | dict[int, float] | Age → probability of surviving to (at least) that age, from a starting reference age. Not interpolated — an age missing from this dict is a caller/config error (research.md §5, mirrors `SourcedFigure`'s no-fallback discipline). |
| `citation` | string | Source of the underlying life table. |
| `last_verified` | date | Per Principle III. |
| `verified` | bool | `False` until cross-checked (research.md §5). |

`survival_probability(age) -> float` looks up `probabilities_by_age[age]`, raising if absent. `.usage() -> FigureUsage` snapshots the citation fields, mirroring `SourcedFigure.usage_for_year()`'s shape (research.md §5).

## SimulationRun

| Field | Type | Notes |
|---|---|---|
| `candidate_label` | string | Identifies this run within a `SimulationComparisonResult` — a state code (`"GA"`) or a `StrategyConfiguration.label`, depending on the comparison axis (or the sole run's own label, for a non-comparison single-configuration call). |
| `strategy` | StrategyConfiguration | The configuration held fixed for every path in this run (`004`'s type, unmodified). |
| `state` | string | The state this run's tax calculations used — always present, even outside a state comparison, so a downstream consumer never has to look inside `strategy` or a candidate list to know which state a run reflects. |
| `path_results` | list[PlanProjection] | One per `ReturnPath` in the Paired-Draw Set this run was given, in path order (`004`'s type, unmodified — each `PlanProjection.return_assumption` here is the specific `ReturnPath` that produced it, satisfying `ReturnSchedule`). Retains every path's `first_shortfall_plan_year` individually (FR-004). |
| `success_rate` | float | Share of `path_results` whose `outcome.first_shortfall_plan_year is None` (FR-003). |
| `percentile_bands` | list[PercentileBand] | One entry per plan year, summarizing `path_results`' ending balances at that year across every path (FR-003). |
| `survival_adjusted_success_rate` | float \| null | Present only when survival-adjusted scoring was requested (FR-017); `null` otherwise — never silently computed. |
| `figures_used` | list[FigureUsage] | Union of every path's `PlanProjection` years' `figures_used`, plus every path's own `ReturnPath.figures_used`, plus (when survival-adjusted scoring was requested) every consulted `SurvivalCurve.usage()` — deduplicated by `(name, last_verified)` so a figure consulted by thousands of paths appears once (FR-019). |

## PercentileBand

| Field | Type | Notes |
|---|---|---|
| `plan_year` | int | Which plan year this band summarizes. |
| `percentiles` | dict[float, float] | Percentile level (e.g., `0.10`, `0.50`, `0.90`) → total ending account balance at that percentile, across every path's `path_results[i].years[...].ending_balances` for this `plan_year` (research.md, `statistics.quantiles`). |

## SimulationComparisonResult

| Field | Type | Notes |
|---|---|---|
| `axis` | enum: `state`, `roth_conversion_strategy`, `withdrawal_sequencing`, `claiming_age_grid` | Which dimension this comparison varied — mirrors `004`'s `ComparisonDimension`, with `state` added as this feature's own axis (research.md §2). |
| `return_paths` | list[ReturnPath] | The single Paired-Draw Set shared by every `runs` entry (FR-007, FR-009) — a downstream consumer can confirm every entry's `path_results[i]` came from `return_paths[i]` without re-deriving it. |
| `runs` | list[SimulationRun] | One per candidate, in the order requested. May contain a single entry (FR-010, mirroring `004`'s FR-011). |

## Relationships

- A `SimulationRun` is produced by `run_simulation()` calling `run_plan_projection()` once per entry in a shared `return_paths` list, holding `strategy`/`state`/every other scenario input fixed across all of them within that run — the same "thin loop over an existing per-unit function" shape `004`'s `compare_*()` functions established, one level up (once per path, not once per candidate).
- A `SimulationComparisonResult` is produced by one of the four `compare_*()` functions calling `run_simulation()` once per candidate, holding `return_paths` (and every input other than the varied axis) fixed across all of them.
- `PercentileBand`s are derived entirely from a `SimulationRun`'s own `path_results` — never computed independently of it, mirroring `004`'s "`PlanOutcome` derived entirely from `PlanProjection.years`" relationship.
- `StressScenario` application happens once, before `run_simulation()`/`compare_*()` are called — it transforms a Paired-Draw Set into another Paired-Draw Set (research.md § StressScenario); it is not a field any `SimulationRun` carries, since by the time a run executes, the stress override is already baked into the `ReturnPath`s it received (a downstream consumer wanting to know a run was stress-tested inspects the `ReturnPath`s it was given, not the run itself).
- `SurvivalCurve` lookups happen inside `run_simulation()`'s per-path aggregation step, after each path's `PlanProjection` is already computed (research.md §5) — survival-adjusted scoring never changes a `PlanProjection`'s own contents, only what `SimulationRun.survival_adjusted_success_rate` derives from it, satisfying US5 Acceptance Scenario 2's non-interference requirement.

## State transitions

None new beyond what `002`–`004` already establish — every `ReturnPath`, `SimulationRun`, and `SimulationComparisonResult` is produced fresh from its inputs each call, with no persistence. This feature is the first to fan a single stateless per-year computation out across thousands of independent paths (optionally across worker processes, research.md §7), but each path's own computation remains the same stateless call chain `004` already established — parallelism changes *where* a call runs, never *what* it computes or *what order it's assembled back in* (path index order is preserved regardless of completion order, Principle II).
