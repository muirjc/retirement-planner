# Contract: `retirement_planner.comparison` public API (addendum to `004`, `010`, `011`, `012`, `017`, `018`, `020`)

`run_plan_projection()`, `compare_withdrawal_sequencing_strategies()`, `compare_claiming_age_grid()`, and every other existing public function keep their existing locked signatures — this is an internal-computation and result-shape addendum only.

## Modified data type (`models`)

```python
@dataclass
class PlanYearProjection:
    # ... every existing field unchanged ...
    member_income_stream_amounts: dict[str, float] = field(default_factory=dict)   # NEW
```

`person_name -> that member's own summed gross income-stream amount this year` (data-model.md § PlanYearProjection extension) — `0.0` for a member with no configured streams, or none active this year; never omitted, mirroring `member_social_security_benefits`.

## Modified operation (`projection`)

Each plan year, immediately after the existing `_member_gross_social_security_benefits()` call, `run_plan_projection()` now also calls a new private `_member_income_stream_amounts(household, ages_this_year, tax_year, reference_tax_year) -> tuple[dict[str, float], list[FigureUsage]]` (mirrors `_member_gross_social_security_benefits()`'s own shape): for each member, sums `compute_income_stream_amount()` (`mechanics-api.md` addendum) across that member's own `income_streams`, using that member's translated age this year (`member_age_in_tax_year()`, unchanged).

The `compute_plan_year_mechanics()` call gains `income_stream_total=<sum of the dict's values above>` and `income_stream_figures_used=<the union of figures_used returned alongside it>` as two additional arguments (`mechanics-api.md`, this feature) — every other argument to that call is unchanged.

The constructed `PlanYearProjection` for the year sets `member_income_stream_amounts=<the dict above>` — every other field's construction is unchanged; in particular, `IncomeComponents.ordinary_income=mechanics_result.ordinary_income` needs no change, since `income_stream_total` is already folded into that value by `compute_plan_year_mechanics()` (mechanics-api.md addendum) before it's returned.

018-survivor-scenario-projection's own filing-status/SS/spending-need switching, 012's inherited-account handling, and every other existing step are unchanged.

## Consumption expectations for downstream features

- `reporting.account_attribution.attribute_plan_projection()` copies `year.member_income_stream_amounts` into the corresponding `PlanYearAccountDetail.member_income_stream_amounts` the same way it already copies `member_social_security_benefits` (`reporting-api.md` addendum).
- `simulation.monte_carlo` needs no change — every Monte Carlo path already calls `run_plan_projection()` internally, so income streams are automatically included in every path's own income/tax/success-rate computation with no separate simulation-layer wiring (spec.md FR-011/SC-004).
