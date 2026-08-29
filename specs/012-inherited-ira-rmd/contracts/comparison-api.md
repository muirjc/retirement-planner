# Contract: `retirement_planner.comparison` public API (addendum to `004`, `011`)

Extends `specs/004-strategy-comparison-layer/contracts/comparison-api.md` (further extended by `011`'s own addendum) with one new parameter threaded through `run_plan_projection()` and every function in `compare.py` (`compare_roth_conversion_strategies`, `compare_withdrawal_sequencing_strategies`, `compare_claiming_age_grid`), plus a new step in `run_plan_projection()`'s per-year sequence, alongside `011`'s already-modified step 3. `PlanProjection`, `ComparisonResult`, and every other existing type are unchanged in shape; `deemed_rmd_owner()`, `member_age_in_tax_year()`, and `011`'s `traditional_ownership_shares` handling are all unchanged in behavior.

**Scope note**: `retirement_planner.simulation` (`005` — `run_simulation()` and `simulation/compare.py`'s four functions) is **not** touched by this feature. Threading `inherited_accounts` through the Monte Carlo path requires giving every path its own independent, freshly-copied `list[InheritedAccountBalance]` across a multiprocessing worker boundary (`_init_worker`/`_run_one_path_shared`'s existing `initargs` mechanism) — a materially different problem from this feature's in-process `compare.py` threading below, and is named explicit follow-on work (research.md §10). `services/bff` (this feature) rejects, rather than silently runs, a Monte Carlo simulation or simulated comparison request against a scenario with any inherited account — see [bff-api.md](./bff-api.md).

## Modified operations (`projection`)

```python
def run_plan_projection(
    household: Household,
    accounts: AccountBalances,
    traditional_ownership_shares: dict[str, float],
    inherited_accounts: list[InheritedAccountBalance] = [],   # NEW — see data-model.md § Derived
    annual_spending_need: float,
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    strategy: StrategyConfiguration,
    return_assumption: ReturnSchedule,
) -> PlanProjection:
```

> **Note on parameter ordering**: shown here immediately after `traditional_ownership_shares` for readability; the actual implementation should place a defaulted (`= []`) parameter after every non-defaulted one in Python's actual call signature (after `return_assumption`), and this should be called with keyword arguments at every call site, consistent with how this function is already invoked throughout `004`/`services/bff`.

Every function in `comparison/compare.py` gains the identical parameter, in the identical relative position (immediately after `traditional_ownership_shares`), forwarded unchanged to each of its own `run_plan_projection()` calls — **except** that each candidate's call must receive its own fresh, independently-copied `list[InheritedAccountBalance]` (e.g. `[replace(a) for a in inherited_accounts]` or equivalent), never the same list/instances reused across candidates, since `run_plan_projection()` mutates each instance's `balance` in place and candidates must not corrupt each other's state (data-model.md § Consumption):

- `compare_roth_conversion_strategies(household, accounts, traditional_ownership_shares, inherited_accounts, annual_spending_need, ...)`
- `compare_withdrawal_sequencing_strategies(household, accounts, traditional_ownership_shares, inherited_accounts, annual_spending_need, ...)`
- `compare_claiming_age_grid(household, accounts, traditional_ownership_shares, inherited_accounts, annual_spending_need, ...)`

## Modified behavior (`run_plan_projection`)

`011`'s already-modified step 3 (per-member `compute_rmd()` calls, replacing `004`'s original deemed-sole-owner call) is unchanged by this feature. A new step is inserted immediately after it:

> **3a.** For each `InheritedAccountBalance` in `inherited_accounts` with `balance > 0` and `tax_year <= depletion_deadline_year`: if `tax_year == depletion_deadline_year`, that account's distribution for this year is its entire remaining `balance` (forced full depletion); otherwise its distribution is `min(compute_inherited_rmd(inherited_balance=balance, tax_year=tax_year, death_year=death_year, decedent_age_at_death=decedent_age_at_death, decedent_was_taking_rmds=True, beneficiary_classification="non_eligible_designated_beneficiary").required_amount, balance)`. The account's `balance` is reduced by its distribution amount immediately (data-model.md § Consumption); the year's total inherited distribution is the sum across every such account, and `inherited_rmd_figures_used` is the union of every `compute_inherited_rmd()` call's `figures_used`. `inherited_accounts=[]` (the default) makes this step a strict no-op.

Step 4 (`004`'s original numbering — the `compute_plan_year_mechanics()` call) now also passes `inherited_distribution_amount=<step 3a's total>` and `inherited_rmd_figures_used=<step 3a's figures union>` as two additional arguments (`mechanics-api.md`, this feature) — every other argument to that call is unchanged.

Step 7 (`004`'s original numbering — applying `return_assumption` to produce next year's starting balances) now also applies the identical `growth_factor` to every `InheritedAccountBalance` in `inherited_accounts` whose `tax_year < depletion_deadline_year` (research.md §10) — mutating each instance's `balance` in place, the same way this step already mutates `AccountBalances`' fields via the household's pooled arithmetic. A deadline-year account's `balance` is already `0.0` after step 3a and growing it is a no-op either way.

`deemed_rmd_owner()`'s use as this function's own loop-termination condition, and every other step (1, 2, 5, 6), are unchanged.

## Consumption expectations for downstream features

- `inherited_accounts` is fixed in *composition* (which accounts are present, and their static `death_year`/`decedent_age_at_death`/`depletion_deadline_year`) across every candidate inside one `compare_*()` invocation, exactly like `accounts`/`traditional_ownership_shares` already are — but, as noted above, each candidate's own `run_plan_projection()` call receives its own independently-copied `list[InheritedAccountBalance]` (fresh `balance` values), never shared instances, since balances mutate in place year-by-year.
- `run_simulation()` and every `simulation.compare_*()` (`005`) would need the identical "fresh copy per Monte Carlo path" treatment, plus safe handling across the `_init_worker`/`_run_one_path_shared` multiprocessing boundary, if/when this parameter is threaded there — explicitly out of scope for this feature (see the Scope note above and `bff-api.md`'s rejection behavior), named as follow-on work.
- `services/bff`'s `resolution.py` (`007`, extended by this feature) is the only place `InheritedAccountBalance` instances are built from a `Scenario`; every caller inside `retirement_planner` itself receives them as opaque, pre-resolved arguments — mirrors how `traditional_ownership_shares` is already treated (`011`'s own contract).
