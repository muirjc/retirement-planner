# Data Model: Social Security Earnings Test (Withholding + FRA Recredit)

No `scenario`-layer change — every input this feature needs (`ss_claim_age`, `full_retirement_age`,
`ss_annual_benefit`, and `earned_income`-type `IncomeStream`s) already exists (016, 021).

## New: `EarningsTestWithholdingResult` (`retirement_planner.mechanics`)

```python
@dataclass
class EarningsTestWithholdingResult:
    """One member's one plan-year earnings-test computation."""

    withheld_amount: float
    """$1-for-$2 (or $1-for-$3 in the FRA-attainment year) of that
    member's earned income above the applicable exempt threshold, capped
    so it never exceeds that year's own claiming-age-adjusted benefit
    (never negative benefit). 0.0 whenever earned income is at or below
    the threshold, or the earnings test doesn't apply this year at all
    (member not yet claimed, or already past their FRA-attainment year)."""
    benefit_after_withholding: float
    """The member's claiming-age-adjusted benefit for the year minus
    withheld_amount."""
    deduction_months_this_year: int
    """min(12, ceil(withheld_amount / (original_annual_benefit / 12))),
    or 0 when withheld_amount is 0 -- whole "deduction months" credited
    toward this member's eventual FRA recredit (research.md Decision 4);
    a month with only partial withholding still counts as one full
    month, per SSA's own crediting rule."""
    figures_used: list[FigureUsage]
```

## New: `EarningsTestRecreditResult` (`retirement_planner.mechanics`)

```python
@dataclass
class EarningsTestRecreditResult:
    """One member's one-time, permanent benefit recalculation at their
    FRA-attainment year, reflecting SSA's Adjustment of the Reduction
    Factor (ARF) -- the accumulated deduction_months_this_year total
    from every pre-FRA year this member was withheld converts into a
    permanently smaller early-claiming reduction from this year
    forward."""

    recredited_annual_benefit: float
    """primary_insurance_amount * recredited_adjustment_factor -- the
    member's new, permanently higher benefit from the FRA-attainment
    year forward. Equals the member's original claiming-age-adjusted
    benefit unchanged when cumulative_months_withheld is 0 (no earlier
    withholding occurred)."""
    recredited_adjustment_factor: float
    """The original adjustment_factor (compute_social_security_benefit())
    plus however much of the early-claiming reduction the credited
    months eliminate -- capped at 1.0 (100% of PIA). Never exceeds 1.0:
    ARF eliminates reduction, it does not manufacture delayed-retirement
    credit (research.md Decision 4)."""
    months_recredited: int
    """min(cumulative_months_withheld, months originally reduced for
    early claiming) -- the portion of the accumulated deduction-months
    total actually consumed; any surplus beyond full 100%-of-PIA
    restoration has no further effect."""
    figures_used: list[FigureUsage]
```

## New (private): `_EarningsTestRates`, `SS_EARNINGS_TEST_EXEMPT_AMOUNT_BELOW_FRA`, `SS_EARNINGS_TEST_EXEMPT_AMOUNT_FRA_YEAR`

```python
@dataclass
class _EarningsTestRates:
    withholding_ratio_below_fra: float   # 0.5 -- $1 withheld per $2 earned above threshold
    withholding_ratio_fra_year: float    # 1/3 -- $1 withheld per $3 earned above threshold
```

Both threshold `SourcedFigure`s (`SS_EARNINGS_TEST_EXEMPT_AMOUNT_BELOW_FRA` = $24,480/yr,
`SS_EARNINGS_TEST_EXEMPT_AMOUNT_FRA_YEAR` = $65,160/yr) and the one `_EarningsTestRates` constant
(ratios fixed by statute) follow `_ClaimingAgeAdjustmentRates`/`SS_CLAIMING_AGE_ADJUSTMENT`'s exact
existing shape — `schedule={year: <value> for year in _DOCUMENTED_YEARS}`, `verified=True` only after
cross-checking each figure against a primary source (research.md Decision 2).

## Modified: `PlanYearProjection` (`retirement_planner.comparison`, extended by `015`/`016`/`022`)

```python
@dataclass
class PlanYearProjection:
    # ... existing fields unchanged ...
    member_ss_earnings_test_withheld: dict[str, float] = field(default_factory=dict)
    """NEW. person_name -> that member's own EarningsTestWithholdingResult.
    withheld_amount for this plan year -- 0.0 for a member the earnings
    test doesn't apply to this year (not yet claimed, no earned_income,
    earnings at or below threshold, or already past their FRA-attainment
    year), never omitted. Mirrors member_social_security_benefits' and
    member_rmd_amounts' own "always present, 0.0 when inapplicable"
    convention (015)."""
```

No `PlanOutcome`-level cumulative field is added: unlike a tax (FICA, IRMAA, NIIT), withheld Social
Security is not a cost paid out of the household's accounts — it is fully recovered via the FRA
recredit (User Story 2), so a lifetime "cumulative withheld" figure would misleadingly read like a
lifetime loss the way `cumulative_fica_tax_paid` genuinely is one. `member_ss_earnings_test_withheld`
is retained per year (auditability) without an additional lifetime-total field this feature has no
requirement for.

## Cross-year local state in `run_plan_projection()` (not a new type — mirrors `roth_conversion_lots`)

`cumulative_earnings_test_months_withheld: dict[str, int]`, initialized `{}` at the top of
`run_plan_projection()`, exactly like `roth_conversion_lots: list[RothConversionLot] = []` (019) —
purely local to one projection call, never a function parameter, never threaded through
`comparison.compare` or `simulation.monte_carlo` (each of those already calls
`run_plan_projection()` fresh per candidate/path, so no cross-call leakage is possible, mirroring
019 research.md Decision 2 exactly).
