# Contract: `retirement_planner.mechanics` public API (addendum to `003`, `010`)

Extends `specs/003-retirement-account-mechanics/contracts/mechanics-api.md` (as already extended by
`specs/010-advanced-tax-benefits/contracts/mechanics-api.md`) with the new `social_security_benefit`
module. Everything else in that contract — `compute_rmd()`, `compute_roth_conversion()`,
`compute_withdrawal_plan()`, `compute_plan_year_mechanics()`, `compute_hsa_eligibility()`,
`compute_hsa_contribution()` — keeps its exact locked shape, unchanged.

## New data types (`models`)

```python
@dataclass
class SocialSecurityBenefitResult:
    annual_benefit: float
    adjustment_factor: float   # annual_benefit / primary_insurance_amount
    figures_used: list[FigureUsage]
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## New operations (`social_security_benefit`)

```python
# retirement_planner.mechanics.social_security_benefit:

def compute_social_security_benefit(
    primary_insurance_amount: float,
    full_retirement_age: float,
    claiming_age: int,
    tax_year: int,
) -> SocialSecurityBenefitResult:
    """Derives the annual Social Security benefit actually paid at
    claiming_age, given a member's PIA and FRA (FR-002-FR-005 of
    016-ss-claiming-age-actuarial-adjustment). Returns
    annual_benefit == primary_insurance_amount, adjustment_factor == 1.0
    when claiming_age == full_retirement_age. Applies the tiered early-
    reduction formula (5/9 of 1% per month for the first 36 months
    claimed early, 5/12 of 1% per month beyond that) when
    claiming_age < full_retirement_age, and the delayed retirement
    credit (2/3 of 1% per month, capped at age 70) when
    claiming_age > full_retirement_age. Raises UnsupportedTaxYearError
    if the adjustment-rate figure has no schedule entry for tax_year.
    Does not itself validate claiming_age's 62-70 range -- callers rely
    on scenario.validation.validate() for that, as compute_rmd() and
    compute_taxable_social_security() already do for their own inputs.
    """
```

`retirement_planner.mechanics.__init__` re-exports `compute_social_security_benefit` and
`SocialSecurityBenefitResult` alongside the module's existing exports.

## Consumption expectations for downstream features

- `retirement_planner.comparison.run_plan_projection()`'s `_member_gross_social_security_benefits()`
  calls this once per household member per plan year (once that member's age has reached their
  claiming age), passing the member's `ss_annual_benefit` as `primary_insurance_amount`, the member's
  resolved `full_retirement_age`, and this comparison's `claiming_ages[member.person_name]` as
  `claiming_age`. Its `figures_used` flow into that plan year's existing `figures_used` list
  (data-model.md).
- `retirement_planner.simulation` requires no direct change: every simulation path already calls
  `comparison.run_plan_projection()` internally (research.md Decision 4), so it consumes this new
  operation transitively.
