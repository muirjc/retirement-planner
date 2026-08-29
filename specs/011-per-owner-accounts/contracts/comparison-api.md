# Contract: `retirement_planner.comparison` public API (addendum to `004`)

Extends `specs/004-strategy-comparison-layer/contracts/comparison-api.md` with one new required parameter, threaded through every function that (directly or transitively) computes an RMD. `PlanProjection`, `ComparisonResult`, and every other existing type are unchanged in shape; `deemed_rmd_owner()` and `member_age_in_tax_year()` (public since `006`) are unchanged in behavior (research.md §4).

## Modified operations (`projection`, `compare`)

Every function below gains one new required, keyword-capable parameter, inserted immediately after `accounts`:

```python
traditional_ownership_shares: dict[str, float]   # NEW — see data-model.md § Derived
```

- `run_plan_projection(household, accounts, traditional_ownership_shares, annual_spending_need, state, ...)`
- `compare_roth_conversion_strategies(household, accounts, traditional_ownership_shares, annual_spending_need, ...)`
- `compare_withdrawal_sequencing_strategies(household, accounts, traditional_ownership_shares, annual_spending_need, ...)`
- `compare_claiming_age_grid(household, accounts, traditional_ownership_shares, annual_spending_need, ...)`

Every other parameter, in every one of these functions, is unchanged in name, type, and position relative to each other.

## Modified behavior (`run_plan_projection`)

Step 3 of `run_plan_projection()`'s documented per-year sequence (`004`'s contract, "Calls `compute_rmd()` once, against the older member's translated age... the deemed sole owner for RMD purposes") is replaced by:

> 3. For each household member whose `traditional_ownership_shares[member.person_name] > 0`, calls `retirement_planner.mechanics.compute_rmd()` once, against that member's own translated age and `traditional_ownership_shares[member.person_name] * current_balances.traditional`, with `spouse_age`/`spouse_is_sole_beneficiary=False` passed exactly as `004` already does (unchanged, separate simplification — data-model.md § Consumption). This year's `rmd_amount` (step 4's input) is the sum of every member's `required_amount`; `figures_used` is the union across every member's call. Raises `KeyError` immediately, before processing any plan year, if `traditional_ownership_shares` omits any of `household.members[*].person_name` (mirrors `005`'s existing `survival_curves` precedent).

Every other step (2, 4–7) of `run_plan_projection()`'s documented sequence is unchanged.

## Consumption expectations for downstream features

- `traditional_ownership_shares` is fixed for the life of one `run_plan_projection()` call (and therefore for every candidate's call inside one `compare_*()` invocation, since all four functions above hold `household`/`accounts`/`traditional_ownership_shares` fixed while varying only their named comparison dimension, exactly like every other shared argument already documented in `004`'s contract) — a caller comparing candidates never needs to (and must not) vary ownership shares across candidates within one comparison call.
- `run_simulation()` and every `simulation.compare_*()` (`005`, extended by this feature) accept and forward this same parameter unchanged in meaning — see [simulation-api.md](./simulation-api.md).
- `services/bff`'s `resolution.py` (`007`, extended by this feature) is the only place this parameter is computed from a `Scenario`; every caller inside `retirement_planner` itself receives it as an opaque, pre-resolved argument (data-model.md § Derived) — mirrors how `accounts: AccountBalances` is already treated.
