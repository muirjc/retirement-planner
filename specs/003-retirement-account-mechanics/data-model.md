# Data Model: Retirement Account Mechanics

Source: [spec.md](./spec.md) Key Entities section. Types are described conceptually (Python `dataclasses`, per [research.md](./research.md)) — field names are illustrative, not a locked contract; the locked contract for downstream features is [contracts/mechanics-api.md](./contracts/mechanics-api.md).

This feature is a **pure calculator over explicit inputs**, like `002-tax-calculation-engine`: it does not read a `Scenario` object directly, load config files, or validate that inputs are individually sensible (that's `001`'s job for the values it owns). It composes with `001` (its `RothConversionPlan` shape) and `002` (its Social Security taxability logic and `SourcedFigure`/`FigureUsage` types) at the field/function level, not by importing and orchestrating those features' own public entry points.

## AccountType

An enum: `traditional`, `roth`, or `taxable` — the same three account types `001`'s `Account.account_type` uses.

## AccountBalances

| Field | Type | Notes |
|---|---|---|
| `traditional` | number | Maps directly onto `001`'s household-level `Account(account_type="traditional")` balance — no per-owner split (see research.md §4). |
| `roth` | number | Maps directly onto `001`'s `Account(account_type="roth")` balance. |
| `taxable` | number | Maps directly onto `001`'s `Account(account_type="taxable")` balance. |

Used as both the starting-balance input and the ending-balance output of a `WithdrawalPlan`, and as the traditional/Roth balances a `ConversionResult` updates.

## RmdResult

| Field | Type | Notes |
|---|---|---|
| `required_amount` | number | The computed RMD in dollars. `0` if the member is below the RMD-required starting age for that tax year, or has no traditional balance (FR-003). |
| `table_used` | `"uniform_lifetime"` \| `"joint_life"` \| `null` | Which divisor table produced `required_amount`; `null` when `required_amount` is `0` and no table lookup was needed. |
| `divisor` | number \| `null` | The divisor actually used; `null` alongside `table_used=null`. |
| `figures_used` | list[FigureUsage] | The RMD-required-starting-age figure, plus whichever divisor-table figure was consulted (empty only when no lookup occurred). |

**No sign/range validation is performed on `traditional_balance` or `member_age` here** — a negative or implausible value is passed through as given (consistent with `002`'s "pure calculator" stance); catching that is `001`'s validation responsibility for whatever feature ultimately sources these numbers from a `Scenario`.

## WithdrawalLineItem

| Field | Type | Notes |
|---|---|---|
| `account_type` | AccountType | Which account this draw came from. |
| `amount` | number | Dollar amount drawn from that account for this plan year. Always `≥ 0` and never exceeds that account's balance at the time of the draw (FR-006). |

## WithdrawalPlan

| Field | Type | Notes |
|---|---|---|
| `rmd_drawn` | number | The mandatory RMD amount drawn from the traditional account — always the first draw, before the configured sequencing strategy's non-RMD legs run (FR-004, Edge Cases). |
| `sequence_withdrawals` | list[WithdrawalLineItem] | The non-RMD draws, in the order the configured strategy applied them. Empty if RMD alone met the year's spending need (Acceptance Scenario US2.2). |
| `ending_balances` | AccountBalances | Balances after `rmd_drawn` and every `sequence_withdrawals` entry has been subtracted. |
| `shortfall` | number | `0` unless total available balance across all account types was insufficient to meet the year's spending need — then the unmet dollar amount (FR-007, Acceptance Scenario US2.4). Never expressed as a negative account balance. |

## WithdrawalSequencingStrategy

Not a class — a **named ordering**: `WITHDRAWAL_STRATEGIES: dict[str, tuple[AccountType, ...]]` where each tuple lists the non-RMD account types in draw order (e.g., the shipped default `"rmd_taxable_traditional_roth"` → `(taxable, traditional, roth)`). One shared draw-down function consumes whichever ordering is selected, so a new strategy is a new dict entry, not a new function (see research.md §5 and plan.md's Constitution Check for why this differs from `002`'s callable-per-module pattern). RMD itself is never listed in the tuple — it's always the unconditional first draw (FR-004).

## RothConversionStrategy

A named **callable**, mirroring `002`'s `STATE_MODULES` pattern exactly, since fill-to-bracket-ceiling and fixed-dollar-amount genuinely compute different things: `CONVERSION_STRATEGIES: dict[str, RothConversionFunction]`. Every registered function shares the identical signature `(ordinary_income_established, social_security_gross_benefit, filing_status, tax_year, traditional_balance, roth_balance, bracket_ceiling_or_amount) -> ConversionResult` — the same "amount" field slot (`bracket_ceiling_or_amount`, matching `001`'s `RothConversionPlan.bracket_ceiling_or_amount` field name exactly) is interpreted as a ceiling by one strategy and a fixed dollar amount by the other. `roth_balance` was added during implementation (not in the original draft) because `ConversionResult.ending_roth_balance`, below, cannot be computed without it — see contracts/mechanics-api.md's implementation note.

## ConversionResult

| Field | Type | Notes |
|---|---|---|
| `amount_converted` | number | Dollars moved from traditional to Roth this plan year. `0` when the plan year is outside the conversion window, or when established ordinary income already meets/exceeds a bracket ceiling (FR-009, Acceptance Scenario US3.5). Never exceeds the traditional balance passed in (FR-011). |
| `ordinary_income_added` | number | Equal to `amount_converted` (FR-012) — kept as a separate field so callers building up a year's total ordinary income don't need to know conversion internals to know what to add. |
| `ending_traditional_balance` | number | Traditional balance after the conversion. |
| `ending_roth_balance` | number | Roth balance after the conversion (starting Roth balance + `amount_converted`). |
| `figures_used` | list[FigureUsage] | Populated only by `fill_to_bracket_ceiling` (the Social Security taxability figures obtained from `002`, per FR-015/research.md §3); always empty for `fixed_dollar_amount`, which needs no external figure. |

## PlanYearMechanicsResult

| Field | Type | Notes |
|---|---|---|
| `plan_year` | int | Which plan year this result is for. |
| `withdrawal_plan` | WithdrawalPlan | This year's RMD + sequenced withdrawals. |
| `conversion` | ConversionResult | This year's Roth conversion (zeroed fields if outside the window or no conversion plan configured). |
| `ending_balances` | AccountBalances | `withdrawal_plan.ending_balances` further adjusted by `conversion`'s traditional/Roth movement — the single final balance snapshot for the year. |
| `ordinary_income` | number | `withdrawal_plan.rmd_drawn` + any traditional draws in `withdrawal_plan.sequence_withdrawals` + `conversion.ordinary_income_added` — the figure a future tax-computation call for this year would use as `IncomeComponents.ordinary_income` (taxable-account and Roth draws are excluded, consistent with `002`'s existing income-scope Assumption). |
| `figures_used` | list[FigureUsage] | Union of the RMD figures used and `conversion.figures_used` — the single place a downstream reporting feature (§3.6) looks for this year's verification status, mirroring `002`'s `figures_used` convention. |

## Relationships

- `WithdrawalPlan` and `ConversionResult` are computed in a fixed order for a given plan year — `WithdrawalPlan` first (it establishes `rmd_drawn` and the post-withdrawal traditional balance), then `ConversionResult` (which consumes that post-withdrawal balance) — never independently or in the reverse order, per research.md §6 and the RMD-non-convertible Edge Case.
- `RmdResult.required_amount` values (summed across however many household members the caller is tracking) are the caller-supplied `rmd_drawn` input to `compute_withdrawal_plan()` — `compute_rmd()` itself has no knowledge of withdrawal sequencing or conversions.
- `ConversionResult.figures_used` values originate from `retirement_planner.tax`'s `SourcedFigure`s (via `compute_taxable_social_security`), not from any `SourcedFigure` this feature defines itself — this feature's own `SourcedFigure`s (RMD tables, RMD starting age) never appear in `ConversionResult.figures_used`, only in `RmdResult.figures_used`.
- State tax modules (`002`) and withdrawal/conversion strategies (`003`) do not share registries or figures with each other — each feature owns its own extension points (FR-014).

## State transitions

None — every computation is stateless, same as `002`. A `RmdResult`, `WithdrawalPlan`, `ConversionResult`, or `PlanYearMechanicsResult` is produced fresh from its inputs each call; nothing is persisted. A caller iterating multiple plan years (the future simulation engine, §3.5) is responsible for feeding one year's `ending_balances` in as the next year's starting balances — this feature does not maintain that state itself.
