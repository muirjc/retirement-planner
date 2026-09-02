# Contract: `retirement_planner.mechanics` public API (addendum to `003`, `010`, `012`)

## New operations (`income_streams`)

```python
INFLATION_RATE: SourcedFigure[float]  # 0.024 -- 2025 OASDI Trustees Report intermediate
                                        # assumption (research.md §1), keyed by tax year like
                                        # every other SourcedFigure schedule.

def compute_income_stream_amount(
    annual_amount: float,
    inflation_adjustment: Literal["cola_adjusted", "fixed_nominal"],
    start_age: int,
    end_age: int | None,
    member_age_this_year: int,
    tax_year: int,
    reference_tax_year: int,
) -> IncomeStreamAmountResult:
    ...
```

Takes an `IncomeStream`'s fields as plain values, not an `IncomeStream` instance — this package is a pure calculator over explicit inputs (`003`'s own data-model.md: "does not read a Scenario object directly"), the same convention `compute_social_security_benefit()` already follows (a raw PIA/FRA/claiming_age, never a `HouseholdMember`).

Returns `amount=0.0, figures_used=[]` when `member_age_this_year` falls outside `[start_age, end_age or +inf]`. Otherwise: `amount=annual_amount, figures_used=[]` when `inflation_adjustment == "cola_adjusted"`; `amount=annual_amount / (1 + INFLATION_RATE.value_for_year(tax_year)) ** (tax_year - reference_tax_year), figures_used=[INFLATION_RATE.usage_for_year(tax_year)]` when `"fixed_nominal"` (data-model.md § IncomeStreamAmountResult, research.md §1). Pure function — no dependency on any other stream, member, or account state (mirrors `compute_social_security_benefit()`'s own independence).

`IncomeStreamAmountResult` (new, `mechanics.models`): `amount: float`, `figures_used: list[FigureUsage]`.

## Modified operation (`plan_year`)

```python
def compute_plan_year_mechanics(
    plan_year: int,
    tax_year: int,
    spending_need: float,
    starting_balances: AccountBalances,
    rmd_amount: float,
    social_security_gross_benefit: float,
    filing_status: FilingStatus,
    conversion_window: tuple[int, int] | None,
    conversion_strategy: str | None,
    conversion_bracket_ceiling_or_amount: float | None,
    withdrawal_strategy: str = "rmd_taxable_traditional_roth",
    rmd_figures_used: list[FigureUsage] | None = None,
    hsa_contribution: HsaContributionResult | None = None,
    inherited_distribution_amount: float = 0.0,
    inherited_rmd_figures_used: list[FigureUsage] | None = None,
    income_stream_total: float = 0.0,                              # NEW
    income_stream_figures_used: list[FigureUsage] | None = None,    # NEW
) -> PlanYearMechanicsResult:
```

Unchanged behavior for every existing parameter. `income_stream_total`/`income_stream_figures_used` (research.md §3): `ordinary_income_established` becomes `withdrawal_plan.rmd_drawn + traditional_draws + withdrawal_plan.inherited_distribution_drawn + income_stream_total` (was: the first three terms only) — computed **before** `compute_roth_conversion()` runs, so a configured income stream correctly reduces that year's remaining bracket-fill headroom, exactly like a traditional withdrawal already does. `figures_used` gains `(income_stream_figures_used or [])` as a fifth unioned source. Both new parameters default such that omitting them reproduces this function's exact prior behavior unchanged (FR-001/SC-003).

`PlanYearMechanicsResult` itself gains no new field — `income_stream_total` is folded into the existing `ordinary_income` output, the same way `hsa_contribution` already reduces it in place rather than surfacing as its own result field.

## Consumption expectations for downstream features

- `comparison.projection.run_plan_projection()` computes each member's own income-stream total via a new private `_member_income_stream_amounts()` (mirrors `_member_gross_social_security_benefits()`), sums it into `income_stream_total`, and passes both new parameters through to `compute_plan_year_mechanics()` — see `contracts/comparison-api.md` addendum.
- No existing caller of `compute_plan_year_mechanics()` needs to change — omitting the two new parameters reproduces exactly the output that caller already got.
