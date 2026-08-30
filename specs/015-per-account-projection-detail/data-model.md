# Phase 1 Data Model: Per-Account Year-by-Year Projection Detail

## `PlanYearProjection` extension (`004`'s locked shape, extended)

Four new fields, all `field(default_factory=dict)` — every existing
construction call site is unaffected (no positional argument shifts, no
required-field breakage):

| Field | Type | Notes |
|---|---|---|
| `member_rmd_amounts` | `dict[str, float]` | person_name → that member's own exact `RmdResult.required_amount` this year, pre-cap. Empty dict for a year/household with no traditional RMDs due. |
| `member_social_security_benefits` | `dict[str, float]` | person_name → gross (not taxable-portion) Social Security benefit received this year. `0.0` for a member who hasn't started claiming yet — never omitted (mirrors `006`'s "present even when zero" convention, spec.md Edge Cases). |
| `inherited_account_balances` | `dict[str, float]` | account_id → that inherited account's own ending balance this year, snapshotted from the already-independently-tracked `InheritedAccountBalance.balance`. |
| `inherited_account_distributions` | `dict[str, float]` | account_id → that inherited account's own distribution amount this year. |

No other `PlanYearProjection` field changes shape or value.

## `reporting/account_attribution.py` (new module)

### `AccountShare`

| Field | Type | Notes |
|---|---|---|
| `account_id` | str | Matches `scenario.models.Account.account_id`. |
| `account_type` | `Literal["traditional", "roth", "taxable"]` | Inherited accounts are never represented here — they're exact by construction (see `PlanYearAccountDetail` below), not part of share math. |
| `owner` | str | person_name. |
| `fixed_share` | float | `account.balance / sum(balances of every non-inherited account of the same type in the household)` at scenario-entry time, `0.0` when that type's household total is `<= 0` (research.md §2's zero-guard, mirroring `resolution._traditional_ownership_shares()`). Computed once; held fixed for the life of a run. |

### `AccountYearDetail`

| Field | Type | Notes |
|---|---|---|
| `account_id` | str | |
| `account_type` | `Literal["traditional", "roth", "taxable"]` | |
| `owner` | str | |
| `starting_balance` | float | `fixed_share × PlanYearProjection.starting_balances.<type>` (ordinary) or the prior year's `inherited_account_balances[account_id]` / scenario-entry balance for year 1 (inherited). |
| `ending_balance` | float | `fixed_share × PlanYearProjection.ending_balances.<type>` (ordinary) or `inherited_account_balances[account_id]` (inherited), this year. |
| `rmd_amount` | float | For a traditional account: the owning member's exact `member_rmd_amounts[owner]` when that member owns exactly one traditional account; otherwise that member's total sub-allocated by within-member starting-balance share (research.md §2). `0.0` for Roth/taxable accounts (no lifetime RMD modeled) and for a member below RMD-required age. For an inherited account: `inherited_account_distributions[account_id]` when that account's own rules require an annual distribution, else `0.0` (mechanics/inherited_rmd.py's existing rules — unchanged by this feature). |
| `withdrawal_amount` | float | `fixed_share ×` the pooled type's total withdrawal this year (`mechanics.withdrawal_plan.rmd_drawn` when type is traditional, plus the matching `sequence_withdrawals`/`tax_funding_withdrawal.sequence_withdrawals` entries for the account's type) — ordinary accounts. `inherited_account_distributions[account_id]` — inherited accounts (same value as `rmd_amount` there, since an inherited account's whole distribution *is* its withdrawal). |
| `attribution` | `Literal["independently_tracked", "fixed_share_of_pooled_total"]` | `"independently_tracked"` for every inherited-account row, and for an ordinary account's `rmd_amount` when it's the sole holder of its owner's traditional RMD. `"fixed_share_of_pooled_total"` for every other value on an ordinary-account row. |

### `PlanYearAccountDetail`

| Field | Type | Notes |
|---|---|---|
| `plan_year` | int | |
| `tax_year` | int | |
| `accounts` | `list[AccountYearDetail]` | One row per account the household holds that year (ordinary accounts present throughout; an inherited account only for years it exists/hasn't fully depleted). |
| `member_social_security_benefits` | `dict[str, float]` | Passthrough of `PlanYearProjection.member_social_security_benefits` — kept alongside the account rows since it's not itself an account figure, but belongs in the same per-year view (spec.md FR-002). |

### Functions

- `compute_account_shares(accounts: list[Account]) -> list[AccountShare]` —
  pure function of the scenario's accounts list; called once per
  request (BFF layer), not once per candidate/path.
- `attribute_plan_projection(projection: PlanProjection, shares: list[AccountShare]) -> list[PlanYearAccountDetail]` —
  one `PlanYearAccountDetail` per `projection.years` entry.

## BFF response shape addenda

- `POST /simulations` response gains `"account_detail":
  list[PlanYearAccountDetail]` (via `to_jsonable()`), computed for
  `run.path_results[detail_path_index or 0]`.
- `POST /comparisons/deterministic` and `POST /comparisons/simulated`
  responses gain `"account_detail": list[list[PlanYearAccountDetail]]`
  — one list per candidate, in the same order as `"summaries"`.
- `SimulationRequest`/`ComparisonRequest` gain `detail_path_index: int |
  None = None`. Out-of-range (`>= len(path_results)` or `< 0`) raises
  HTTP 422 with `{"error": "path_index_out_of_range", "requested":
  ..., "path_count": ...}`, mirroring `unsupported_tax_year_error()`'s
  existing shape.

## Relationship to existing entities

`AccountShare`/`AccountYearDetail`/`PlanYearAccountDetail` are pure
*derivations* — they don't replace, wrap, or get stored inside
`PlanProjection`/`SimulationRun`/`ComparisonResult`. They're computed
fresh, on demand, from an already-completed result plus the scenario's
own `accounts` list, entirely inside `reporting/` and the BFF's response-
assembly layer — never inside `comparison/`'s or `simulation/`'s own
locked result types.
