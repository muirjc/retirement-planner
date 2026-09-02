# Data Model: FICA Payroll Tax on Earned-Income Streams

## FicaTaxResult (new — `tax.models`)

One plan year's payroll-tax computation, mirroring `EarlyWithdrawalPenaltyResult`'s shape (a derived amount plus `figures_used`), extended per-member for the two per-worker components.

| Field | Type | Notes |
|---|---|---|
| `member_oasdi_tax` | `dict[str, float]` | `person_name -> that member's own 6.2% OASDI tax`, computed on that member's own combined `earned_income` amount for the year, capped at `OASDI_WAGE_BASE`. `0.0` for a member with no `earned_income` this year, never omitted. |
| `member_medicare_tax` | `dict[str, float]` | `person_name -> that member's own 1.45% regular Medicare tax`, uncapped. |
| `additional_medicare_tax` | `float` | `0.9% * max(0, combined_earned_income - threshold[filing_status])` — computed once per household, not per member (research.md §3). |
| `total_fica_tax` | `float` | `sum(member_oasdi_tax.values()) + sum(member_medicare_tax.values()) + additional_medicare_tax`. |
| `figures_used` | `list[FigureUsage]` | `OASDI_RATE`, `OASDI_WAGE_BASE`, `MEDICARE_RATE`, `ADDITIONAL_MEDICARE_TAX_RATE`, `ADDITIONAL_MEDICARE_TAX_THRESHOLDS`' usages for `tax_year` — always all five, even when `total_fica_tax == 0.0` (mirrors `compute_niit()`/`compute_early_withdrawal_penalty()`'s own "always cited" precedent, research.md of `020`). |

## `compute_fica_tax()` (new — `tax.fica`)

```python
def compute_fica_tax(
    member_earned_income: dict[str, float],
    filing_status: FilingStatus,
    tax_year: int,
) -> FicaTaxResult: ...
```

Pure function. `member_earned_income` is caller-computed and opaque to this function (mirrors `compute_early_withdrawal_penalty()`'s "does not itself determine which dollars are early" precedent) — it does not itself determine which stream amounts count as earned income; it only applies statutory rates to whatever per-member totals it's given. Raises `UnsupportedTaxYearError` if any figure has no schedule entry for `tax_year`.

## New `SourcedFigure`s (`tax.fica`)

| Figure | Value | Notes |
|---|---|---|
| `OASDI_RATE` | 0.062 | Fixed by statute. |
| `OASDI_WAGE_BASE` | $184,500 | 2026 SSA-published taxable maximum, held flat across every documented year (research.md §4). |
| `MEDICARE_RATE` | 0.0145 | Fixed by statute, uncapped. |
| `ADDITIONAL_MEDICARE_TAX_RATE` | 0.009 | Fixed by IRC §3101(b)(2). |
| `ADDITIONAL_MEDICARE_TAX_THRESHOLDS` | `{"single": 200_000, "married_filing_jointly": 250_000}` | Fixed by IRC §3101(b)(2) since 2013, genuinely not inflation-indexed (research.md §4) — `dict[FilingStatus, SourcedFigure[float]]`, mirroring `tax/federal.py`'s own `_FEDERAL_BRACKETS`/`_STANDARD_DEDUCTIONS` shape exactly (one `SourcedFigure` per filing status, not one figure whose value is itself filing-status-keyed). |

## PlanYearProjection (extended — `comparison.models`)

```python
fica_tax: FicaTaxResult
```

Required, no default — mirrors `irmaa`/`niit`/`early_withdrawal_penalty`'s own "always computed by `run_plan_projection()`, never opt-in" precedent (data-model.md of `010`/`020`).

## PlanOutcome (extended — `comparison.models`)

```python
cumulative_fica_tax_paid: float
```

`sum(year.fica_tax.total_fica_tax for year in years)` — mirrors `cumulative_irmaa_paid`/`cumulative_niit_paid`/`cumulative_early_withdrawal_penalty_paid` exactly, computed in `_derive_outcome()`.

## SummaryStatistics (extended — `reporting.models`)

```python
median_lifetime_fica_tax_paid: float
```

Same derivation as `median_lifetime_early_withdrawal_penalty_paid`: `statistics.median(outcome.cumulative_fica_tax_paid for outcome in ...)` for a Monte Carlo run, or the single deterministic value directly.

## Relationships

- `tax.fica.compute_fica_tax()` consumes `comparison.projection._member_earned_income_amounts()`'s output (a `dict[str, float]` of each member's own `earned_income`-type stream total for the year) — independent of `021`'s `_member_income_stream_amounts()` (research.md §2).
- `comparison.projection.run_plan_projection()`'s existing `tax_owed` local (already summing `federal_tax.federal_tax_owed + state_tax.state_tax_owed + irmaa.surcharge_owed + niit.surtax_owed + early_withdrawal_penalty.penalty_owed`) gains `+ fica_tax.total_fica_tax` as a sixth term, funded by the same `tax_funding_withdrawal` call immediately after (data-model.md's own existing per-year sequence, unchanged in shape).

## Consumption expectations for downstream features

- `apps/streamlit_ui/src/rp_ui/narration.py` reads `summary["median_lifetime_fica_tax_paid"]` off the BFF's already-generic summary serialization — no BFF schema change needed (research.md §6).
- No new `Scenario`/`HouseholdMember`/`IncomeStream` field — this feature is purely a new tax consequence of `021`'s already-shipped `earned_income` stream type.
