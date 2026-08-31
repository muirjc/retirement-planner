# Contract: `retirement_planner.mechanics` public API (addendum to `003`, `010`, `016`)

Extends `specs/016-ss-claiming-age-actuarial-adjustment/contracts/mechanics-api.md` (itself extending
`003`/`010`) with two new operations in the existing `social_security_benefit` module. Everything
else — `compute_rmd()`, `compute_roth_conversion()`, `compute_withdrawal_plan()`,
`compute_plan_year_mechanics()`, `compute_hsa_eligibility()`, `compute_hsa_contribution()`,
`compute_social_security_benefit()` — keeps its exact locked shape, unchanged.

## New data types (`models`)

```python
@dataclass
class SpousalBenefitResult:
    spousal_amount: float
    adjustment_factor: float   # spousal_amount / (0.5 * other_member_pia); never > 1.0
    figures_used: list[FigureUsage]

@dataclass
class SurvivorBenefitResult:
    survivor_benefit: float    # max(member_a_benefit, member_b_benefit)
    figures_used: list[FigureUsage]
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## New operations (`social_security_benefit`)

```python
# retirement_planner.mechanics.social_security_benefit:

def compute_spousal_benefit_floor(
    other_member_pia: float,
    full_retirement_age: float,
    claiming_age: int,
    tax_year: int,
) -> SpousalBenefitResult:
    """Derives the spousal-derived amount available to a member claiming
    at claiming_age relative to their OWN full_retirement_age, based on
    the OTHER member's raw PIA (017-ss-spousal-survivor-benefits FR-001,
    FR-003). Returns spousal_amount == 0.5 * other_member_pia,
    adjustment_factor == 1.0 for claiming_age >= full_retirement_age --
    no delayed-retirement credit applies to a spousal amount, ever.
    Applies the tiered spousal early-reduction formula (distinct from
    compute_social_security_benefit()'s own worker-benefit rate) when
    claiming_age < full_retirement_age. Raises UnsupportedTaxYearError
    if the adjustment-rate figure has no schedule entry for tax_year.
    Does not itself validate claiming_age's 62-70 range, consistent with
    compute_social_security_benefit()."""


def compute_survivor_benefit(
    member_a_benefit: float,
    member_b_benefit: float,
    tax_year: int,
) -> SurvivorBenefitResult:
    """Returns the higher of the two currently-claimed benefit amounts
    as the survivor's ongoing benefit (FR-005) -- the caller attributes
    this amount to whichever member is actually still living; the result
    does not depend on which one that is. Raises UnsupportedTaxYearError
    if SS_SURVIVOR_BENEFIT_RULE has no schedule entry for tax_year."""
```

`retirement_planner.mechanics.__init__` re-exports both functions and both new result types alongside
the module's existing exports.

## Consumption expectations for downstream features

- `retirement_planner.comparison.run_plan_projection()`'s `_member_gross_social_security_benefits()`
  calls `compute_spousal_benefit_floor()` once per member per plan year, for a
  `"married_filing_jointly"` household once both members have reached their own claiming age, passing
  the *other* member's `ss_annual_benefit` as `other_member_pia` and this member's own resolved
  `full_retirement_age`/claiming age. That member's benefit becomes `max(own_benefit,
  spousal_amount)`; the result's `figures_used` flows into that plan year's existing `figures_used`
  list only when the spousal amount was actually computed (data-model.md).
- `retirement_planner.simulation` requires no direct change: every simulation path already calls
  `comparison.run_plan_projection()` internally (016 research.md Decision 4, unchanged by this
  feature), so it consumes the spousal-floor fix transitively.
- `compute_survivor_benefit()` has **no** caller anywhere in this codebase as of this feature
  (FR-007) — it is implemented, unit-tested, and cited, for a future feature (`rp-g8y`) to call once
  mortality is wired into `run_plan_projection()`'s per-year loop. A downstream feature calling it
  should not expect it to already be invoked as part of any existing projection path.
