# Contract: `retirement_planner.comparison` public API (addendum to `004`, `010`, `011`, `012`)

Extends `specs/012-inherited-ira-rmd/contracts/comparison-api.md`'s `run_plan_projection()` contract.
**Signature UNCHANGED** — no new parameter. `compare_roth_conversion_strategies()`,
`compare_withdrawal_sequencing_strategies()`, and `compare_claiming_age_grid()` are unchanged in
signature and require no code change at all (research.md Decision 6) — every existing parameter,
including `household`, already reaches every candidate's own `run_plan_projection()` call.

## Modified data types (`models`)

```python
@dataclass
class PlanYearProjection:
    # ... every existing field, unchanged ...
    filing_status: Literal["single", "married_filing_jointly"] | None = None   # NEW
    effective_spending_need: float = 0.0   # NEW
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## Modified behavior (`run_plan_projection`)

Before the per-year loop begins, `run_plan_projection()` now also computes the household's **death
tax year** (data-model.md § Derived) from `household` and `reference_tax_year` — `None` for a
`"single"`-filing-status household or an MFJ household where no member has `predicted_death_age`
configured.

Each plan year, immediately after the existing `_member_gross_social_security_benefits()` call
(`017`'s already-modified step), a plan year is classified as **post-death** when its `tax_year` is
strictly greater than the death tax year above (data-model.md § Derived: the death year itself is
pre-death). For a post-death plan year only:

- The dying member's entry in `member_ss_benefits` becomes `0.0`; the surviving member's entry becomes
  `retirement_planner.mechanics.compute_survivor_benefit()`'s result, called with both members'
  already-computed benefit amounts for that year (research.md Decisions 2-3) — `household_ss_benefit`
  (this year's `IncomeComponents.social_security_gross_benefit`) equals the survivor's amount.
  `compute_survivor_benefit()`'s `figures_used` is folded into this year's `figures_used` list, same
  as every other figure-producing call already is.
- The *effective* filing status used for `compute_federal_tax()`, `compute_state_tax()`,
  `compute_irmaa_surcharge()`, and `compute_niit()` — every one of this loop's existing calls that
  currently passes `household.filing_status` — becomes `"single"` instead. `household.filing_status`
  itself is never mutated (it stays the household's configured value for every other purpose, e.g. a
  sibling candidate's own independent `run_plan_projection()` call).
- The `spending_need` passed into `compute_plan_year_mechanics()` becomes
  `annual_spending_need * (1 - household.survivor_spending_reduction_pct)` instead of
  `annual_spending_need` unchanged.

The resulting `PlanYearProjection` for that year carries `filing_status=<the effective status used
above>` and `effective_spending_need=<the effective spending_need used above>` — for every pre-death
(or no-death-configured) plan year, these equal `household.filing_status` and `annual_spending_need`
unchanged, so an unaffected household's `PlanYearProjection.filing_status`/`effective_spending_need`
simply repeat those two inputs every year (an informative addition, not a behavior change).

Every other step of `run_plan_projection()`'s documented per-year sequence (RMD, inherited-account
distributions, HSA, tax-funding withdrawal, investment growth) is unchanged in shape — only the
*inputs* two of those steps (tax computation, spending) receive can differ, for post-death years only.

## Consumption expectations for downstream features

- `simulation.run_simulation()` and every `simulation.compare_*()` (`005`) call
  `comparison.run_plan_projection()` internally, unchanged (`016` research.md Decision 4, still
  unchanged by this feature) — so a Monte Carlo *path*'s own deterministic per-year mechanics already
  reflects a configured death exactly as a plain projection would, for every path, on every single
  path's own fixed `household` input. What this feature explicitly does **not** do (FR-007) is draw a
  *probabilistic* death year that could differ path-to-path from `survival_curves` — every path still
  uses the same, single, household-configured `predicted_death_age` (or none), deterministically.
  `survival_curves`-based survival-adjusted scoring (`005` FR-017) remains entirely independent of this
  feature's switch, exactly as before.
- `services/bff`'s `routes/simulations.py` and `routes/comparisons.py` (`007`) need no change — both
  already pass a fully-resolved `Household` straight through to `retirement_planner`.
- A downstream reporting/UI feature wanting to show *when* the widow's-tax-penalty switch occurred
  should read `PlanYearProjection.filing_status` year-over-year, not attempt to infer it from
  `federal_tax`/`state_tax` results, which don't themselves echo back which filing status produced
  them.
