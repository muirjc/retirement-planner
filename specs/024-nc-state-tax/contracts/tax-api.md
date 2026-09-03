# Contract: `retirement_planner.tax.state` public API (addendum to `002`)

`compute_state_tax()` and `STATE_MODULES`' locked type keep their existing signature exactly (`specs/002-tax-calculation-engine/contracts/tax-api.md` §"Operations"/§99-127) — this is a registry-content addendum only, not a shape change.

## Modified registry (`tax.state`)

```python
STATE_MODULES: dict[str, Callable[[IncomeComponents, list[int], FilingStatus, int], StateTaxResult]] = {
    "SC": sc.compute_tax,
    "DE": de.compute_tax,
    "FL": fl.compute_tax,
    "NC": nc.compute_tax,   # NEW — this feature
}
```

`compute_state_tax(state, income, filer_ages, filing_status, tax_year)` now additionally accepts `state="NC"` and dispatches to `retirement_planner.tax.state.nc.compute_tax`, with no change to `compute_state_tax()`'s own body (`002`'s contract, line 106-113, is unmodified).

## New leaf module: `retirement_planner.tax.state.nc`

```python
def compute_tax(
    income: IncomeComponents,
    filer_ages: list[int],
    filing_status: FilingStatus,
    tax_year: int,
) -> StateTaxResult: ...
```

Same signature every registered state module already implements (data-model.md's `compute_tax()` section has the full behavior). Raises `UnsupportedTaxYearError` (already defined in `002`'s contract) if `tax_year` has no entry in `nc.py`'s one `SourcedFigure`'s schedule — the same failure mode every other state module already has, no new exception type.

## Consumption expectations for downstream features

- `services/bff/src/rp_bff/routes/reference.py`'s `GET /reference/states` route (`007`'s contract) returns `{"states": [..., "NC", ...]}` once this feature merges — no route code or `007` contract change (`002`'s own line 127 already anticipated this: `"until that state's module is added as follow-on work"`).
- Any caller already parametrizing a test or check over `STATE_MODULES.keys()` (e.g., a `dependency_containment` test) sees `"NC"` join the set automatically — this feature adds no new parametrization mechanism, it adds a fourth key to the existing one.
- `comparison/`, `simulation/`, and every other consumer of `compute_state_tax()` are unaffected — `"NC"` is just one more valid `state` string wherever a `Scenario`'s `state` config field is already validated against `STATE_MODULES` (or, for an unregistered state, raises `KeyError` exactly as `002`'s contract already documents for any unregistered code).
