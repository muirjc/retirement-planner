# Contract: `retirement_planner.simulation` public API (addendum to `005`)

Extends `specs/005-simulation-engine/contracts/simulation-api.md` with the same new required parameter `comparison-api.md` (this feature) adds to `004`, threaded through unchanged in meaning. `SimulationRun`, `SimulationComparisonResult`, and every other existing type are unchanged in shape.

## Modified operations (`monte_carlo`, `compare`)

Every function below gains `traditional_ownership_shares: dict[str, float]` (see `comparison-api.md` and `data-model.md § Derived`), inserted immediately after `accounts`, forwarded unchanged to every `run_plan_projection()` call each function makes (directly, or transitively via `run_simulation()`):

- `run_simulation(household, accounts, traditional_ownership_shares, annual_spending_need, state, ...)`
- `compare_states(household, accounts, traditional_ownership_shares, annual_spending_need, states, ...)`
- `compare_roth_conversion_strategies(household, accounts, traditional_ownership_shares, annual_spending_need, ...)`
- `compare_withdrawal_sequencing_strategies(household, accounts, traditional_ownership_shares, annual_spending_need, ...)`
- `compare_claiming_age_grid(household, accounts, traditional_ownership_shares, annual_spending_need, ...)`

Every other parameter, in every one of these functions, is unchanged in name, type, and position relative to each other.

## Modified behavior (`monte_carlo`)

`run_simulation()`'s parallel-dispatch path (`_init_worker`/`_worker_shared_args`/`ProcessPoolExecutor(initargs=...)`) carries `traditional_ownership_shares` through the same shared-per-worker tuple `household`/`accounts`/`strategy` already travel in — sent once per worker process, not once per path, consistent with `005`'s existing research.md §7 rationale for why those arguments are shared rather than re-pickled per task. This is an internal dispatch detail, not a public-contract change beyond the new parameter itself.

Every other documented behavior of `run_simulation()` (path aggregation, `success_rate`, `percentile_bands`, `survival_adjusted_success_rate`, the `ValueError`/`KeyError` cases already documented) is unchanged; `run_simulation()` additionally raises `KeyError` under the same eager, before-any-path-is-scored condition `run_plan_projection()` now does (`comparison-api.md`) if `traditional_ownership_shares` omits a household member's `person_name` — this is on top of, not a replacement for, `run_simulation()`'s existing `KeyError` case for `survival_curves`.

## Consumption expectations for downstream features

- `examples/reference_scenario.py` (the project's own runnable example, README's "Getting started") is a direct library caller and must construct `traditional_ownership_shares` explicitly, like it already constructs `AccountBalances` directly — there is no scenario/`Account` object in that example to derive it from automatically.
- Every existing `005` test fixture that calls `run_simulation()`/`compare_*()` directly needs the same mechanical update — this is expected call-site churn from a required-parameter addition to a locked contract, not a design gap (Complexity Tracking, plan.md).
