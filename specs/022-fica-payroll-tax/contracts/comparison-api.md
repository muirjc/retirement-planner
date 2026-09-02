# Contract: `retirement_planner.comparison` public API (addendum to `004`, `010`, `017`, `018`, `020`, `021`)

`run_plan_projection()` and every other existing public function keep their existing locked signatures — this is an internal-computation and result-shape addendum only.

## Modified data types (`models`)

```python
@dataclass
class PlanYearProjection:
    # ... every existing field unchanged (including 021's member_income_stream_amounts) ...
    fica_tax: FicaTaxResult   # NEW, required -- mirrors irmaa/niit/early_withdrawal_penalty's own precedent

@dataclass
class PlanOutcome:
    # ... every existing field unchanged ...
    cumulative_fica_tax_paid: float   # NEW
```

## Modified operation (`projection`)

Each plan year, after `_member_income_stream_amounts()` (`021`) has already run this year, `run_plan_projection()` now also calls a new private `_member_earned_income_amounts(household, ages_this_year, tax_year, reference_tax_year) -> dict[str, float]`: for each member, sums `compute_income_stream_amount()` (`021`'s `mechanics-api.md`) across only that member's `income_streams` entries where `stream_type == "earned_income"` (research.md §2 — independent of, not derived from, `021`'s own pooled-across-types helper).

Immediately after the existing `early_withdrawal_penalty = compute_early_withdrawal_penalty(...)` call, a new `fica_tax = compute_fica_tax(member_earned_income=<the dict above>, filing_status=effective_filing_status, tax_year=tax_year)` call runs (`tax-api.md` addendum).

`tax_owed` gains `+ fica_tax.total_fica_tax` as a sixth term (was: `federal_tax.federal_tax_owed + state_tax.state_tax_owed + irmaa.surcharge_owed + niit.surtax_owed + early_withdrawal_penalty.penalty_owed`) — every other part of the `tax_funding_withdrawal` sequence (data-model.md's existing per-year sequence) is unchanged, so FICA is funded from account balances exactly the way IRMAA/NIIT/the early-withdrawal penalty already are.

The constructed `PlanYearProjection` for the year sets `fica_tax=fica_tax`. `figures_used` (the year's overall union) gains `*fica_tax.figures_used` as an additional unioned source, alongside the existing `*early_withdrawal_penalty.figures_used`.

`_derive_outcome()` gains `cumulative_fica_tax_paid = sum(year.fica_tax.total_fica_tax for year in years)`, computed and returned alongside `cumulative_irmaa_paid`/`cumulative_niit_paid`/`cumulative_early_withdrawal_penalty_paid`.

`effective_filing_status` (the same value `018`'s survivor-scenario switch already produces) is what FICA's Additional Medicare Tax threshold lookup uses — a household mid-horizon-switched to `"single"` after a configured death uses the single threshold from that year forward, consistent with every other filing-status-dependent computation in this same loop.

## Consumption expectations for downstream features

- `reporting.aggregation.summarize_run()`/`summarize_deterministic_comparison()` read `outcome.cumulative_fica_tax_paid` the same way they already read `cumulative_early_withdrawal_penalty_paid` (`reporting-api.md` addendum).
- A household with no `earned_income` streams configured anywhere gets `member_earned_income == {}` for every member (every value `0.0`), so `fica_tax.total_fica_tax == 0.0` every year and `tax_owed`'s new term is a true no-op (spec.md FR-005/SC-003).
