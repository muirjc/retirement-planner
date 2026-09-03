# Quickstart: Social Security Earnings Test (Withholding + FRA Recredit)

## Prerequisites

- Repo checked out on `025-ss-earnings-test`, core deps installed.
- `pytest tests/` passing before starting (baseline for SC-003).

## 1. Compute withholding directly (US1)

```python
from retirement_planner.mechanics import compute_earnings_test_withholding

# Member claiming at 62 (FRA 67), PIA/benefit $20,000/yr, earning $60,000/yr well above
# the 2026 below-FRA exempt amount ($24,480).
result = compute_earnings_test_withholding(
    annual_benefit=20_000, primary_insurance_amount=20_000,
    earned_income=60_000, is_fra_attainment_year=False, tax_year=2026,
)
assert result.withheld_amount == pytest.approx((60_000 - 24_480) / 2)
assert result.benefit_after_withholding == 20_000 - result.withheld_amount

# Earnings at or below the threshold: no withholding at all.
result = compute_earnings_test_withholding(
    annual_benefit=20_000, primary_insurance_amount=20_000,
    earned_income=20_000, is_fra_attainment_year=False, tax_year=2026,
)
assert result.withheld_amount == 0.0
```

## 2. Verify the FRA-attainment year's more lenient rule (US3)

```python
result = compute_earnings_test_withholding(
    annual_benefit=20_000, primary_insurance_amount=20_000,
    earned_income=70_000, is_fra_attainment_year=True, tax_year=2026,
)
assert result.withheld_amount == pytest.approx((70_000 - 65_160) / 3)
```

## 3. Verify recredit at FRA (US2)

```python
from retirement_planner.mechanics import compute_earnings_test_recredit

result = compute_earnings_test_recredit(
    primary_insurance_amount=20_000, claiming_age=62, full_retirement_age=67.0,
    cumulative_months_withheld=24, tax_year=2026,
)
assert result.recredited_annual_benefit > 20_000 * 0.70  # original 62-vs-67 adjustment_factor
assert result.recredited_adjustment_factor <= 1.0

# No prior withholding -> no change.
result = compute_earnings_test_recredit(
    primary_insurance_amount=20_000, claiming_age=62, full_retirement_age=67.0,
    cumulative_months_withheld=0, tax_year=2026,
)
assert result.recredited_adjustment_factor == pytest.approx(0.70)
```

## 4. Verify the full withhold-then-recredit lifecycle in a real projection (US1 + US2)

```python
from retirement_planner.comparison import run_plan_projection
# ... household with one member: ss_claim_age=62, full_retirement_age=67.0, an earned_income
#     IncomeStream active from that member's age 62 through 66 ...
projection = run_plan_projection(household=household, ...)
withheld_years = [y for y in projection.years if y.member_ss_earnings_test_withheld.get("Alex", 0) > 0]
assert withheld_years  # withholding actually occurred pre-FRA

fra_year_index = next(i for i, y in enumerate(projection.years) if ...)  # the member's FRA-attainment plan year
pre_fra_benefit = projection.years[fra_year_index - 1].member_social_security_benefits["Alex"]
post_fra_benefit = projection.years[fra_year_index].member_social_security_benefits["Alex"]
assert post_fra_benefit > pre_fra_benefit  # permanent step-up at FRA, not a cliff back to the original unwithheld amount
```

## 5. Verify a no-earned-income (or already-past-FRA) scenario is unchanged (SC-003)

Run any existing scenario fixture (none combine early claiming with a concurrent `earned_income`
stream) through `run_plan_projection()` before and after this feature; every field, including
`member_ss_earnings_test_withheld` (all `0.0`), must match exactly.

## 6. Run the test suite

```bash
pytest tests/    # core: mechanics, comparison
```

## Expected outcome

- A member claiming before FRA with concurrent earned income above the exempt threshold shows a
  correctly reduced near-term Social Security benefit — and everything downstream (ordinary income,
  tax, IRMAA/NIIT exposure, Roth-conversion bracket headroom) reflects the true, lower figure.
- That same member's benefit steps up permanently at their FRA-attainment year, reflecting the real
  SSA recredit — never a modeled permanent loss.
- The FRA-attainment year itself uses the higher exempt amount and $1-for-$3 ratio, not the stricter
  before-FRA rule.
- Every scenario predating this feature produces byte-for-byte identical output.
- `docs/BRD.md` §5.3/§6.2a describe what is now modeled, with this engine's whole-plan-year
  simplifications (research.md Decisions 3-4) named explicitly, not silently absorbed.
