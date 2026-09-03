# Data Model: North Carolina State Income Tax Module

No new dataclasses. This feature reuses `tax.models`' existing `BracketRow`, `BracketTable`, `SourcedFigure`, `FigureUsage`, and `StateTaxResult` exactly as SC/DE/FL already do — see `specs/002-tax-calculation-engine/contracts/tax-api.md` for their locked shapes.

## `_NC_FLAT_RATE` (new — `tax.state.nc`)

A `SourcedFigure[BracketTable]`, structurally identical to `sc.py`'s `_BRACKET_TABLE` except every `BracketTable` value in its `schedule` holds exactly one `BracketRow`:

| Field | Value |
|---|---|
| `name` | `"nc_flat_rate"` |
| `schedule` | `{year: _2025_BRACKETS for year in range(_DOCUMENTED_YEARS.start, 2026)} \| {year: _2026_BRACKETS for year in range(2026, _DOCUMENTED_YEARS.stop)}` (research.md §2) — where `_2025_BRACKETS = (BracketRow(rate=0.0425, income_up_to=None),)` and `_2026_BRACKETS = (BracketRow(rate=0.0399, income_up_to=None),)` |
| `citation` | `"N.C. Gen. Stat. §105-153.7, as amended by S.L. 2023-134; NCDOR Tax Rate Schedules"` |
| `last_verified` | `date(2026, 9, 3)` |
| `verified` | `True` (research.md §2 — confirmed against a primary source during this feature, not inherited placeholder debt) |

`_DOCUMENTED_YEARS = range(2020, 2075)`, matching every other module's convention (`sc.py`, `de.py`, `tax/federal.py`, `mechanics/rmd.py`).

## No exclusion `SourcedFigure`

Unlike `sc.py`'s `_AGE_65_EXCLUSION` and `de.py`'s `_AGE_60_EXCLUSION`, `nc.py` defines no second `SourcedFigure`. `_AGE_EXCLUSION_THRESHOLD` also does not exist in `nc.py` — there is nothing analogous to apply it to (research.md §3). This is a deliberate absence, not an oversight; the module docstring says so explicitly, mirroring how `fl.py`'s docstring explains its own "no figures at all" shape.

## `compute_tax()` (new — `tax.state.nc`)

```python
def compute_tax(
    income: IncomeComponents,
    filer_ages: list[int],
    filing_status: FilingStatus,
    tax_year: int,
) -> StateTaxResult: ...
```

Identical signature to every other registered state module (`specs/002-tax-calculation-engine/contracts/tax-api.md`). `filer_ages` and `filing_status` are accepted (contract-required) but not used in the computation — NC's tax depends on neither age nor filing status (no bracket varies by filing status, no exclusion keys off age) — mirroring `fl.py`'s own "accepts but ignores every parameter it doesn't need" precedent.

Body:

```python
brackets = _NC_FLAT_RATE.value_for_year(tax_year)  # raises UnsupportedTaxYearError
figures_used = [_NC_FLAT_RATE.usage_for_year(tax_year)]
return StateTaxResult(
    state="NC",
    state_tax_owed=apply_progressive_brackets(income.ordinary_income, brackets),
    figures_used=figures_used,
)
```

`income.social_security_gross_benefit` is never read (research.md §4) — only `ordinary_income` enters the computation, same as `sc.py`/`de.py`. `apply_progressive_brackets()` already floors at `$0` for `taxable_income <= 0` (`tax/bracket_math.py`), so no separate floor check is needed (FR-007).

## `STATE_MODULES` (extended — `tax.state.__init__`)

```python
STATE_MODULES: dict[str, StateTaxFunction] = {
    "SC": sc.compute_tax,
    "DE": de.compute_tax,
    "FL": fl.compute_tax,
    "NC": nc.compute_tax,   # NEW
}
```

## Relationships

- `tax.state.compute_state_tax()` is unchanged — it already looks `STATE_MODULES[state]` up generically (`tax/state/__init__.py:32-44`); adding the `"NC"` key is the entire integration.
- `services/bff/src/rp_bff/routes/reference.py`'s `list_states_route()` already returns `sorted(STATE_MODULES.keys())` on every request (research.md §5) — `"NC"` appears there automatically once registered, no route change.
