# Quickstart: FICA Payroll Tax on Earned-Income Streams

## Prerequisites

- Repo checked out on `022-fica-payroll-tax`, core deps installed.
- `pytest tests/` passing before starting (baseline for SC-003).

## 1. Compute FICA directly

```python
from retirement_planner.tax import compute_fica_tax

# US1: under wage base
result = compute_fica_tax(member_earned_income={"Alex": 40_000}, filing_status="single", tax_year=2026)
assert result.member_oasdi_tax["Alex"] == 40_000 * 0.062
assert result.member_medicare_tax["Alex"] == 40_000 * 0.0145
assert result.additional_medicare_tax == 0.0

# US2: over the wage base -- OASDI caps, Medicare doesn't
result = compute_fica_tax(member_earned_income={"Alex": 250_000}, filing_status="single", tax_year=2026)
assert result.member_oasdi_tax["Alex"] == 184_500 * 0.062
assert result.member_medicare_tax["Alex"] == 250_000 * 0.0145

# US3: over the Additional Medicare Tax threshold
result = compute_fica_tax(member_earned_income={"Alex": 250_000}, filing_status="single", tax_year=2026)
assert result.additional_medicare_tax == pytest.approx((250_000 - 200_000) * 0.009)

# US3 edge case: combined MFJ earnings trigger it even though neither spouse alone does
result = compute_fica_tax(
    member_earned_income={"Alex": 150_000, "Sam": 150_000}, filing_status="married_filing_jointly", tax_year=2026
)
assert result.additional_medicare_tax == pytest.approx((300_000 - 250_000) * 0.009)
```

## 2. Verify a full projection funds it

```python
from retirement_planner.comparison import run_plan_projection
# ... household with one member configured with an earned_income IncomeStream ...
projection = run_plan_projection(household=household, ...)
active_year = next(y for y in projection.years if y.fica_tax.total_fica_tax > 0)
assert active_year.mechanics.ending_balances != active_year.tax_funding_withdrawal.ending_balances  # confirms funding drew balances down further
assert projection.outcome.cumulative_fica_tax_paid > 0
```

## 3. Verify a no-earned-income scenario is unchanged (SC-003)

Run any existing scenario fixture (none configure `earned_income` streams) through `run_plan_projection()` before and after this feature; every field except the new `fica_tax`/`cumulative_fica_tax_paid` (both `0.0`) must match exactly.

## 4. Verify reporting surfaces it

```python
from retirement_planner.reporting import summarize_run
summary = summarize_run(run, household, reference_tax_year=2026)
assert summary.median_lifetime_fica_tax_paid > 0  # for a run with earned_income configured
```

## 5. Run the test suites

```bash
pytest tests/                        # core: tax, comparison, reporting
pytest apps/streamlit_ui/tests/      # narration display
```

## Expected outcome

- `earned_income` streams now correctly reduce projected ending balances by their true FICA cost, tiered correctly across all three components (regular, wage-base-capped, Additional Medicare Tax).
- `pension`/`annuity` streams remain completely unaffected — no FICA is ever computed from them.
- Every scenario predating this feature (and `021`'s own pension/annuity-only scenarios) produces byte-for-byte identical output.
- The lifetime FICA figure is visible in `PlanOutcome`, `SummaryStatistics`, and the Streamlit UI's narration, at the same level IRMAA/NIIT/the early-withdrawal penalty already are.
