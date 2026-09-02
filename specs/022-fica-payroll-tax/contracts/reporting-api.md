# Contract: `retirement_planner.reporting` public API (addendum to `006`, `010`, `020`)

`summarize_run()`, `summarize_simulation_comparison()`, `summarize_deterministic_comparison()` keep their existing locked signatures.

## Modified data type (`models`)

```python
@dataclass
class SummaryStatistics:
    # ... every existing field unchanged ...
    median_lifetime_fica_tax_paid: float   # NEW
```

## Modified operations (`aggregation`)

`summarize_run()` (Monte Carlo path): gains `median_lifetime_fica_tax_paid = statistics.median(outcome.cumulative_fica_tax_paid for outcome in <the run's per-path outcomes>)`, computed and returned alongside `median_lifetime_early_withdrawal_penalty_paid`.

`_summarize_plan_projection()` (deterministic path, used by `summarize_deterministic_comparison()`): gains `median_lifetime_fica_tax_paid=projection.outcome.cumulative_fica_tax_paid` (the single value, same "median of one" convention every other `median_lifetime_X_paid` field already follows for a deterministic candidate).

## Consumption expectations for downstream features

- `services/bff` needs no schema change — response bodies are generic `to_jsonable()` dataclass output (`schemas.py`'s own docstring), so the new field serializes automatically.
- `apps/streamlit_ui/src/rp_ui/narration.py` adds one new entry reading `summary["median_lifetime_fica_tax_paid"]`, immediately after the existing "Lifetime early-withdrawal penalty paid" entry — see plan.md's Project Structure.
