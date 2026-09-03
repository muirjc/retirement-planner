# Contract: `retirement_planner.mechanics` public API (addendum to `003`, `010`, `016`, `017`)

Extends `specs/017-ss-spousal-survivor-benefits/contracts/mechanics-api.md` (itself extending
`016`/`010`/`003`) with two new operations in the existing `social_security_benefit` module.
Everything else — `compute_social_security_benefit()`, `compute_spousal_benefit_floor()`,
`compute_survivor_benefit()`, and every other existing mechanics operation — keeps its exact locked
shape, unchanged.

## New data types (`models`)

```python
@dataclass
class EarningsTestWithholdingResult:
    withheld_amount: float
    benefit_after_withholding: float
    deduction_months_this_year: int
    figures_used: list[FigureUsage]

@dataclass
class EarningsTestRecreditResult:
    recredited_annual_benefit: float
    recredited_adjustment_factor: float
    months_recredited: int
    figures_used: list[FigureUsage]
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## New operations (`social_security_benefit`)

```python
# retirement_planner.mechanics.social_security_benefit:

def compute_earnings_test_withholding(
    annual_benefit: float,
    primary_insurance_amount: float,
    earned_income: float,
    is_fra_attainment_year: bool,
    tax_year: int,
) -> EarningsTestWithholdingResult:
    """Applies the SSA retirement earnings test to one member's one plan
    year (FR-001 through FR-005). annual_benefit is that member's own
    already claiming-age-adjusted benefit for the year
    (compute_social_security_benefit()'s own annual_benefit); this
    function does not itself decide whether the member has claimed or
    is past FRA -- callers only invoke it for a year the earnings test
    can apply to at all (025 research.md Decision 3). primary_insurance_amount
    is the member's raw PIA, used only to derive the monthly-benefit rate
    for deduction_months_this_year (data-model.md), not to recompute the
    benefit itself. is_fra_attainment_year selects the FR-003 (below-FRA)
    vs. FR-004 (FRA-year) threshold/ratio. Raises UnsupportedTaxYearError
    if either exempt-amount figure has no schedule entry for tax_year.
    Never returns a negative withheld_amount or benefit_after_withholding
    below 0.0."""


def compute_earnings_test_recredit(
    primary_insurance_amount: float,
    claiming_age: int,
    full_retirement_age: float,
    cumulative_months_withheld: int,
    tax_year: int,
) -> EarningsTestRecreditResult:
    """SSA's Adjustment of the Reduction Factor (ARF) at a member's
    FRA-attainment year (FR-006, FR-007): permanently reduces the
    early-claiming "months early" this member's original
    compute_social_security_benefit() call applied, by up to
    cumulative_months_withheld, capped so recredited_adjustment_factor
    never exceeds 1.0 (025 research.md Decision 4 -- ARF eliminates
    early-claiming reduction, it does not manufacture delayed-retirement
    credit). Returns recredited_annual_benefit ==
    primary_insurance_amount * 1.0 (adjustment_factor 1.0) when
    cumulative_months_withheld alone is enough to fully eliminate the
    original reduction; returns the member's unchanged original
    claiming-age-adjusted benefit when cumulative_months_withheld is 0.
    Raises UnsupportedTaxYearError if either exempt-amount figure (cited
    for audit-trail purposes even though this function consults no
    earnings itself) has no schedule entry for tax_year, consistent with
    compute_survivor_benefit()'s own "consulted purely for the citation
    trail" precedent."""
```

`retirement_planner.mechanics.__init__` re-exports both functions and both new result types
alongside the module's existing exports.

## Consumption expectations for downstream features

- `retirement_planner.comparison.run_plan_projection()`'s `_member_gross_social_security_benefits()`
  gains a new `member_earned_income: dict[str, float]` parameter (that year's already-computed
  `_member_earned_income_amounts()` result, called earlier in the loop than its existing 022 call
  site so both consumers share one result — 022's own "cheap and pure, recompute rather than thread"
  precedent is dropped in favor of sharing here specifically because this call now needs it too,
  narrowing rather than duplicating). For each member who has claimed
  (`ages_this_year[member] >= claiming_ages[member]`) and has not yet passed their FRA-attainment
  year (`ages_this_year[member] <= floor(full_retirement_age)`), it calls
  `compute_earnings_test_withholding()` with that member's own `member_earned_income` amount, then
  (in the member's FRA-attainment year specifically) calls `compute_earnings_test_recredit()` using
  `run_plan_projection()`'s own new local `cumulative_earnings_test_months_withheld` running state
  (data-model.md) before returning that member's final benefit for the year. Both results'
  `figures_used` flow into that plan year's existing `figures_used` list, exactly like every other
  benefit computation's already do.
- The spousal-benefit floor (`compute_spousal_benefit_floor()`, 017) is unaffected by this feature's
  own logic — it is called, as today, with each member's own final (possibly withheld, possibly
  recredited) benefit already resolved by `_member_gross_social_security_benefits()`, per this
  feature's explicit scope boundary (spec.md Assumptions).
- `retirement_planner.simulation` requires no direct change: every simulation path already calls
  `comparison.run_plan_projection()` internally (016 research.md Decision 4, unchanged by this
  feature), so it consumes the earnings-test fix transitively.
