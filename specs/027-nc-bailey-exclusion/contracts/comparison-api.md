# Contract: `retirement_planner.comparison` public API (addendum to `004`, `010`, `011`, `012`, `017`, `018`, `020`, `021`, `022`)

`run_plan_projection()` and every other existing public function keep their existing locked
signatures — this is an internal-computation addendum only, mirroring
`022-fica-payroll-tax/contracts/comparison-api.md`'s own shape.

## New private operation (`projection`)

```python
def _household_bailey_qualifying_income(
    household: Household,
    ages_this_year: dict[str, int],
    tax_year: int,
    reference_tax_year: int,
) -> float: ...
```

Sums `compute_income_stream_amount()` (`mechanics-api.md`, 021's addendum) across every member's
`income_streams` where `stream.bailey_qualifying` is `True`, using that member's translated age
this year — same per-stream call `_member_income_stream_amounts()` already makes, filtered to
Bailey-qualifying streams only, mirroring `_member_earned_income_amounts()`'s own
"filter-and-recompute rather than thread a subtotal through" shape (022's precedent). Returns no
`figures_used` — `_member_income_stream_amounts()` (called earlier the same iteration, unchanged)
already collects every stream's `FigureUsage` including Bailey-qualifying ones (research.md §6).

## Modified operation (`run_plan_projection`)

Each plan year, after the existing `_member_income_stream_amounts()` call, `run_plan_projection()`
now also calls `_household_bailey_qualifying_income(household, ages_this_year, tax_year,
reference_tax_year)`.

The `IncomeComponents` construction gains one keyword — every other keyword unchanged:

```python
income = IncomeComponents(
    ordinary_income=mechanics_result.ordinary_income,
    social_security_gross_benefit=household_ss_benefit,
    government_pension_income=household_bailey_qualifying_income,   # NEW
)
```

`mechanics_result.ordinary_income` itself is unchanged — Bailey-qualifying stream income is still
folded into it exactly as every income stream already is (021's own addendum); this feature only
adds a second, read-only view of a subset of that same total, for `tax.state.nc.compute_tax()`'s
use (`tax-api.md` addendum, this feature).

Every downstream use of `income` in the same loop iteration (`compute_federal_tax()`,
`compute_state_tax()`, `_approximate_magi()`, NIIT) is unchanged — none reads
`government_pension_income`.

## Consumption expectations for downstream features

- `simulation.monte_carlo` needs no change — every Monte Carlo path already calls
  `run_plan_projection()` internally, so a Bailey-qualifying stream is automatically reflected in
  every path's own NC tax computation with no separate simulation-layer wiring (mirrors
  021-pension-annuity-income's own "Consumption expectations" note).
- `reporting.aggregation` needs no change — it reads `PlanYearProjection.federal_tax`/`state_tax`
  totals, not `IncomeComponents` fields directly; `state_tax.state_tax_owed` already reflects the
  Bailey exclusion once `tax.state.nc.compute_tax()` applies it.
