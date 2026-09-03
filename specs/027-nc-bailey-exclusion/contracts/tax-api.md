# Contract: `retirement_planner.tax` public API (addendum to `002`, `010`, `020`, `022`)

Extends `specs/022-fica-payroll-tax/contracts/tax-api.md`'s chain with one additive field on
`IncomeComponents` and one behavior change in `retirement_planner.tax.state.nc` (itself an
addendum to `024-nc-state-tax/contracts/tax-api.md`). `compute_federal_tax()`,
`compute_state_tax()`, `STATE_MODULES`' locked type, and every other existing operation keep their
existing signatures exactly — this is a data-shape and one-module-behavior addendum only.

## Modified data type (`models`)

```python
@dataclass
class IncomeComponents:
    ordinary_income: float
    social_security_gross_benefit: float
    government_pension_income: float = 0.0   # NEW — this feature
```

`government_pension_income`: the subset of `ordinary_income` sourced from household-attested
Bailey-qualifying income streams (data-model.md). Defaults to `0.0` — every existing caller that
constructs `IncomeComponents` without this keyword (there are none outside
`comparison/projection.py` today; any future direct construction, e.g. in a test, is also
unaffected) gets identical behavior to before this feature.

## Modified operation (`tax.state.nc.compute_tax`)

```python
def compute_tax(
    income: IncomeComponents,
    filer_ages: list[int],
    filing_status: FilingStatus,
    tax_year: int,
) -> StateTaxResult: ...
```

Signature unchanged (`024`'s contract). Behavior: taxable base is now
`max(0.0, income.ordinary_income - income.government_pension_income)`, run through the same
`apply_progressive_brackets()` call as before — previously `income.ordinary_income` directly.
`figures_used` is unchanged (still just `_NC_FLAT_RATE.usage_for_year(tax_year)`) — no new
`SourcedFigure` is introduced for the Bailey exclusion (research.md §4); it is a categorical,
citation-backed structural rule documented in the module docstring, not a scheduled figure.

`income.government_pension_income == 0.0` (the default, and every pre-existing call site's
effective value) reproduces exactly `024-nc-state-tax`'s original behavior — `max(0.0, x - 0.0) ==
x` for any `x >= 0.0`.

## Unmodified operations

- `compute_federal_tax()`, `compute_taxable_social_security()`: read `income.ordinary_income` only,
  as before — `government_pension_income` is a Bailey/NC-specific side-channel, never subtracted
  from `ordinary_income` itself (research.md §5).
- `tax.state.sc.compute_tax()`, `tax.state.de.compute_tax()`, `tax.state.fl.compute_tax()`: none
  reads `government_pension_income` — identical output for identical `ordinary_income`/
  `social_security_gross_benefit`, regardless of what `government_pension_income` is set to.

## Consumption expectations for downstream features

- `comparison.projection.run_plan_projection()` is the sole constructor of `IncomeComponents`
  outside tests; it now passes `government_pension_income=<sum of this year's Bailey-qualifying
  stream amounts>` alongside the existing `ordinary_income`/`social_security_gross_benefit`
  keywords (`comparison-api.md` addendum, this feature).
- `_approximate_magi()`, FICA, IRMAA, NIIT (`010`, `022`): all consume `income.ordinary_income` or
  `mechanics_result.ordinary_income` directly, neither of which changes — unaffected.
