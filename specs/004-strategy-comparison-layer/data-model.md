# Data Model: Strategy Comparison Layer

Source: [spec.md](./spec.md) Key Entities section, resolved against research.md's design decisions. Types are described conceptually (Python `dataclasses`, per research.md and following `001`/`002`/`003`'s convention) — field names are illustrative, not a locked contract; the locked contract for downstream features is [contracts/comparison-api.md](./contracts/comparison-api.md).

This feature is an **orchestrator**, not another pure calculator like `002`/`003`: it is the first feature to call another feature's public API repeatedly across years and candidate configurations rather than compute a single self-contained result. It composes `001`'s `Household`/`Account`/`MarketAssumptions` shapes, `002`'s `compute_federal_tax()`/`compute_state_tax()`/`IncomeComponents`, and `003`'s `compute_rmd()`/`compute_plan_year_mechanics()`/`AccountBalances` — it does not re-derive any of their logic.

## DeterministicReturnAssumption

| Field | Type | Notes |
|---|---|---|
| `annual_real_return` | number | The single blended real return applied to every account type in every plan year of one comparison (research.md §1, §6). |

Produced by `derive_deterministic_return(market_assumptions)` from `001`'s `MarketAssumptions.equity_allocation`/`equity_return_mean_real`/`bond_allocation`/`bond_return_mean_real`. Held constant across every candidate configuration within one `ComparisonResult`, per FR-009.

## StrategyConfiguration

| Field | Type | Notes |
|---|---|---|
| `label` | string | Identifies this candidate in a `ComparisonResult` (e.g., `"fill_to_10_pct_bracket"`, `"no_conversion"`, `"rmd_traditional_taxable_roth"`). Not interpreted — purely a display/lookup key. |
| `withdrawal_strategy` | string | Registry key into `003`'s `mechanics.WITHDRAWAL_STRATEGIES` (research.md §8). |
| `conversion_strategy` | string \| `null` | Registry key into `003`'s `mechanics.CONVERSION_STRATEGIES`. `null` = no conversion plan configured for this candidate, matching `003`'s "zeroed `ConversionResult`" behavior. |
| `conversion_bracket_ceiling_or_amount` | number \| `null` | Passed through to `003`'s `compute_roth_conversion()` unchanged; `null` iff `conversion_strategy` is `null`. |
| `conversion_window` | tuple[int, int] \| `null` | Passed through to `003`'s `compute_roth_conversion()` unchanged; `null` iff `conversion_strategy` is `null`. |
| `claiming_ages` | dict[str, int] | Maps each `001` `HouseholdMember.person_name` to the claiming age used for this candidate — overrides, not mutates, the scenario's originally configured `ss_claim_age` (spec.md Assumptions). |

One `StrategyConfiguration` fully determines one candidate's behavior for an entire `PlanProjection` — nothing about it varies year to year within a single projection.

## PlanYearProjection

| Field | Type | Notes |
|---|---|---|
| `plan_year` | int | Sequential plan year, starting at the projection's `start_plan_year`. |
| `tax_year` | int | The calendar tax year this plan year corresponds to (advances 1:1 with `plan_year`, research.md §2). |
| `mechanics` | `PlanYearMechanicsResult` | `003`'s unmodified result for this year — RMD, spending-need withdrawals, and conversion (Requirements FR-001). |
| `federal_tax` | `FederalTaxResult` | `002`'s unmodified result for this year's `mechanics.ordinary_income` + household Social Security benefit. |
| `state_tax` | `StateTaxResult` | `002`'s unmodified result for the same year's income. |
| `tax_funding_withdrawal` | `WithdrawalPlan` | The second `003` withdrawal-plan call that draws `federal_tax.federal_tax_owed + state_tax.state_tax_owed` from `mechanics.ending_balances` (research.md §5). |
| `starting_balances` | `AccountBalances` | This year's balances before any mechanics ran — the prior year's `ending_balances` (or the scenario's original balances, for `plan_year == start_plan_year`). |
| `ending_balances` | `AccountBalances` | `tax_funding_withdrawal.ending_balances`, after the deterministic return (research.md §6) has been applied — this is what becomes next year's `starting_balances`. |
| `shortfall` | number | `mechanics.withdrawal_plan.shortfall + tax_funding_withdrawal.shortfall` — this year's total unmet dollar amount, spending and tax combined (research.md §7). |
| `figures_used` | list[FigureUsage] | Union of `mechanics.figures_used`, `federal_tax.figures_used`, and `state_tax.figures_used` — FR-013's verification-flag pass-through, unmodified. |

## PlanOutcome

| Field | Type | Notes |
|---|---|---|
| `ending_balance` | number | The last plan year's `ending_balances`, summed across all three account types, in real terms. |
| `first_shortfall_plan_year` | int \| `null` | The lowest `plan_year` with `shortfall > 0`; `null` if no year in the horizon had a shortfall. |
| `cumulative_tax_paid` | number | Sum of `federal_tax.federal_tax_owed + state_tax.state_tax_owed` across every plan year in the horizon (research.md §5 — tax *owed*, independent of whether it was fully funded that year). |

Derived entirely from a `PlanProjection`'s `years` list — never computed independently of it.

## PlanProjection

| Field | Type | Notes |
|---|---|---|
| `strategy` | StrategyConfiguration | The single candidate configuration this projection ran under. |
| `return_assumption` | DeterministicReturnAssumption | The deterministic return applied throughout — carried alongside the projection so a `ComparisonResult`'s candidates can be confirmed to share it (FR-009). |
| `years` | list[PlanYearProjection] | One entry per plan year, `start_plan_year` through the horizon's last year, in order. |
| `outcome` | PlanOutcome | Summary metrics derived from `years`. |

The User Story 1 deliverable in isolation: one `PlanProjection` is a complete, standalone full-horizon result for one strategy configuration.

## ComparisonResult

| Field | Type | Notes |
|---|---|---|
| `dimension` | enum: `roth_conversion_strategy`, `withdrawal_sequencing`, `claiming_age_grid` | Which axis this comparison varied — informational, so a downstream reporting feature (§3.6) knows how to label the result without inspecting every candidate's `StrategyConfiguration`. |
| `return_assumption` | DeterministicReturnAssumption | The single return assumption shared by every `projections` entry (FR-009) — a downstream consumer can assert every entry's `PlanProjection.return_assumption` equals this without re-deriving it. |
| `projections` | list[PlanProjection] | One per candidate configuration, in the order requested. May contain a single entry (Edge Cases: a "comparison" of one candidate is still valid, per FR-011). |

## Relationships

- A `ComparisonResult` is produced by running `run_plan_projection()` once per candidate `StrategyConfiguration` in a list, holding `return_assumption` (and every scenario input other than the varied dimension) fixed across every call — the comparison functions (contracts/comparison-api.md) are thin loops over `run_plan_projection()`, not a separate computation path.
- Within one `PlanProjection`, each `PlanYearProjection`'s `starting_balances` is exactly the previous `PlanYearProjection`'s `ending_balances` — there is no independent state store; the list itself is the full history (mirrors `003`'s "no state transitions, caller feeds balances forward" posture, data-model.md § State transitions, now actually exercised across years for the first time).
- `PlanYearProjection.mechanics` is produced by `003`'s `compute_plan_year_mechanics()`, called with `rmd_amount` from this feature's own `compute_rmd()` call against the deemed RMD owner (research.md §3–4) — this feature does not call `003`'s `compute_rmd()` for both household members, only the deemed owner.
- `PlanYearProjection.federal_tax`/`state_tax` are produced by `002`'s functions called with `IncomeComponents(ordinary_income=mechanics.ordinary_income, social_security_gross_benefit=<household total for this year's claiming ages>)` — this feature computes the household Social Security total itself (summing each member's `ss_annual_benefit` where that year's translated age has reached their `claiming_ages` entry) since neither `002` nor `003` does that translation.
- `StrategyConfiguration.withdrawal_strategy` and `.conversion_strategy` are registry keys owned by `003`, not by this feature — this feature's own registry addition (research.md §8) lives inside `003`'s package, not a new one here.

## State transitions

None new beyond what `002`/`003` already establish — every `PlanProjection`/`ComparisonResult` is produced fresh from its inputs each call, with no persistence. This feature is the first to iterate that stateless per-year computation into a multi-year sequence, but the sequencing itself is a plain loop over already-stateless calls, not a new state machine.
