# Data Model: Source-Attributed Retirement Income for State Exclusions (NC Bailey Settlement)

Two existing entities gain one additive field each. No new entity is introduced (research.md §3).

## `IncomeStream` (scenario layer) — extended

`src/retirement_planner/scenario/models.py`, originally defined by 021-pension-annuity-income.

| Field | Type | Default | Notes |
|---|---|---|---|
| `label` | `str` | — | unchanged |
| `stream_type` | `Literal["pension", "annuity", "earned_income"]` | — | unchanged |
| `start_age` | `int` | — | unchanged |
| `annual_amount` | `float` | — | unchanged |
| `inflation_adjustment` | `Literal["cola_adjusted", "fixed_nominal"]` | — | unchanged |
| `end_age` | `int \| None` | `None` | unchanged |
| **`bailey_qualifying`** | **`bool`** | **`False`** | **NEW.** Household attestation that this stream's income is a North Carolina Bailey-settlement-qualifying government or military retirement benefit (five or more years of creditable service, or contributions, as of August 12, 1989 — N.C. Gen. Stat. §105-134.6 history; *Bailey v. State of North Carolina*, 1998). Not verified or derived by the engine — an existing household fact the user supplies, exactly like `ss_claim_age` or `hdhp_coverage`. Has no effect on any computation unless the household's state is `"NC"` (research.md §5, spec.md FR-006/Edge Cases). Defaults to `False` so every scenario YAML written before this feature parses and projects identically. |

**Validation**: none added. `bailey_qualifying` is an unconstrained boolean like `hdhp_coverage` —
there is no plausibility range to check (unlike `annual_amount`'s existing non-negative check,
untouched). A stream of any `stream_type` (including `earned_income`) may carry the flag; the
engine does not attempt to re-validate real-world Bailey eligibility (spec.md Edge Cases,
Assumptions).

## `IncomeComponents` (tax layer) — extended

`src/retirement_planner/tax/models.py`, originally defined by 002-tax-calculation-engine.

| Field | Type | Default | Notes |
|---|---|---|---|
| `ordinary_income` | `float` | — | unchanged — still the household's full ordinary income for the year, Bailey-qualifying amounts included (research.md §5) |
| `social_security_gross_benefit` | `float` | — | unchanged |
| **`government_pension_income`** | **`float`** | **`0.0`** | **NEW.** The portion of `ordinary_income` (a subset, never additional) sourced from streams the household has attested are source-and-vesting-date-qualifying government/military retirement income — today, only NC's Bailey rule reads this field. `0.0` (the default) for any household with no Bailey-qualifying stream, or for any non-NC household — leaves SC/DE/FL and NC's own pre-existing behavior unchanged (research.md §1, spec.md FR-002/FR-007). |

**Invariant**: `0.0 <= government_pension_income <= ordinary_income` for any `IncomeComponents`
constructed by `comparison/projection.py` — it is always a sub-sum of the same year's ordinary
income, never independently supplied. Not enforced by a runtime assertion (this module remains a
pure calculator per its existing docstring, "no sign/range validation is performed here"); NC's own
`compute_tax()` floors its taxable base at `$0` regardless (FR-005), so a caller that violated the
invariant would still never produce a negative NC tax.

## `StateTaxResult` (tax layer) — unchanged

No new field. NC's `compute_tax()` continues returning the same shape (`state`, `state_tax_owed`,
`figures_used`); the Bailey exclusion changes *how* `state_tax_owed` is computed, not the result
shape. `figures_used` is also unchanged — no new `SourcedFigure` is introduced (research.md §4).

## Relationships

```text
HouseholdMember
  └── income_streams: list[IncomeStream]      (unchanged relationship, 021)
        └── bailey_qualifying: bool = False    (NEW field, this feature)

comparison.projection.run_plan_projection()
  ├── existing: sums every stream into ordinary_income (unchanged, 021)
  └── NEW: sums streams where bailey_qualifying is True into
           IncomeComponents.government_pension_income

tax.state.nc.compute_tax(income: IncomeComponents, ...)
  └── NEW: taxable_base = max(0.0, income.ordinary_income - income.government_pension_income)
      (previously: taxable_base = income.ordinary_income)
```
