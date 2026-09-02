# Contract: `retirement_planner.tax` public API (addendum to `002`, `010`, `020`)

## New data type (`models`)

```python
@dataclass
class FicaTaxResult:
    member_oasdi_tax: dict[str, float]
    member_medicare_tax: dict[str, float]
    additional_medicare_tax: float
    total_fica_tax: float
    figures_used: list[FigureUsage]
```

## New operation (`fica`)

```python
OASDI_RATE: SourcedFigure[float]                                  # 0.062
OASDI_WAGE_BASE: SourcedFigure[float]                              # 184_500.0 (2026, held flat)
MEDICARE_RATE: SourcedFigure[float]                                # 0.0145
ADDITIONAL_MEDICARE_TAX_RATE: SourcedFigure[float]                 # 0.009
ADDITIONAL_MEDICARE_TAX_THRESHOLDS: dict[FilingStatus, SourcedFigure[float]]  # {"single": 200_000.0, "married_filing_jointly": 250_000.0}

def compute_fica_tax(
    member_earned_income: dict[str, float],
    filing_status: FilingStatus,
    tax_year: int,
) -> FicaTaxResult: ...
```

For each `person_name` in `member_earned_income`: `member_oasdi_tax[person_name] = min(member_earned_income[person_name], OASDI_WAGE_BASE.value_for_year(tax_year)) * OASDI_RATE.value_for_year(tax_year)`; `member_medicare_tax[person_name] = member_earned_income[person_name] * MEDICARE_RATE.value_for_year(tax_year)` (uncapped). `additional_medicare_tax = max(0.0, sum(member_earned_income.values()) - ADDITIONAL_MEDICARE_TAX_THRESHOLDS[filing_status].value_for_year(tax_year)) * ADDITIONAL_MEDICARE_TAX_RATE.value_for_year(tax_year)` — computed once against the household's combined total, never per member (data-model.md § Relationships, research.md §3). `total_fica_tax` sums all three components. `figures_used` always contains all five figures' usages for `tax_year`, even when every amount is `0.0` (mirrors `compute_niit()`/`compute_early_withdrawal_penalty()`'s "always cited" precedent). Raises `UnsupportedTaxYearError` if any figure has no schedule entry for `tax_year`.

`member_earned_income` is caller-computed and opaque to this function — it does not itself determine which income counts as "earned" (mirrors `compute_early_withdrawal_penalty()`'s own "caller determines the base" precedent).

## Consumption expectations for downstream features

- `comparison.projection.run_plan_projection()` is the only caller — see `contracts/comparison-api.md` addendum for exactly how `member_earned_income` is derived and how the result is consumed.
- No existing `tax` module or type changes shape — this is a purely additive new module and data type.
