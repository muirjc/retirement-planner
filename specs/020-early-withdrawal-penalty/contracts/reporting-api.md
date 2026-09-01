# Contract: `retirement_planner.reporting` public API (addendum to `006`, `010`)

Adds one new field to `SummaryStatistics`, mirroring `010`'s own `median_lifetime_irmaa_paid`/
`median_lifetime_niit_paid` addition to the identical dataclass. Every existing `reporting`
operation and type is unchanged in signature and behavior otherwise.

## Modified data type (`models`)

```python
@dataclass
class SummaryStatistics:
    # ... every existing field, unchanged ...
    median_lifetime_early_withdrawal_penalty_paid: float   # NEW
```

Placed immediately after `median_lifetime_niit_paid`, mirroring that field's own placement
immediately after `median_lifetime_irmaa_paid`.

## Modified behavior (`aggregation`)

`summarize_run()` and `_summarize_plan_projection()` (the two existing derivation sites, one per
Monte Carlo/deterministic candidate shape — `006`/`010`'s own precedent of updating both together)
each gain:

```python
median_lifetime_early_withdrawal_penalty_paid = statistics.median(
    path.outcome.cumulative_early_withdrawal_penalty_paid for path in run.path_results
)  # summarize_run() — median across paths

# _summarize_plan_projection():
median_lifetime_early_withdrawal_penalty_paid=projection.outcome.cumulative_early_withdrawal_penalty_paid,
```

exactly mirroring the existing `median_lifetime_irmaa_paid`/`median_lifetime_niit_paid` derivations
in both functions.

## Modified behavior (`export`)

`_SUMMARY_FIELDNAMES` gains `"median_lifetime_early_withdrawal_penalty_paid"` immediately after
`"median_lifetime_niit_paid"`; `_summary_to_row()` gains the matching dict entry. No change to
`run_to_csv_text()`'s own per-plan-year row shape (that function has never included any
`SummaryStatistics` field — it renders `SimulationRun.percentile_bands` directly).

## Consumption expectations for downstream features

- `apps/streamlit_ui/src/rp_ui/narration.py` is the only UI consumer expected to read
  `median_lifetime_early_withdrawal_penalty_paid` directly — see this feature's plan.md Project
  Structure for the new narration entry, mirroring the existing "Lifetime Medicare IRMAA surcharge"/
  "Lifetime Net Investment Income Tax" entries exactly (same `tax_qualifier` phrasing pattern).
- `services/bff` requires no change — `SummaryStatistics` (like `PlanYearProjection`/`PlanOutcome`)
  is passed through generically wherever the BFF surfaces reporting output.
