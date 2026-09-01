# Contract: `retirement_planner.comparison` public API (addendum to `004`, `010`, `011`, `012`, `018`, `019`)

**Signature UNCHANGED** — `run_plan_projection()` gains no new parameter. `compare_roth_conversion_strategies()`,
`compare_withdrawal_sequencing_strategies()`, and `compare_claiming_age_grid()` are unchanged in
signature and require no code change at all — the new computation is entirely internal to
`run_plan_projection()`'s own per-year loop, reading state already available there.

## Modified data types (`models`)

```python
@dataclass
class PlanYearProjection:
    # ... every existing field, unchanged ...
    early_withdrawal_penalty: EarlyWithdrawalPenaltyResult   # NEW, required


@dataclass
class PlanOutcome:
    ending_balance: float
    first_shortfall_plan_year: int | None
    cumulative_tax_paid: float
    cumulative_irmaa_paid: float
    cumulative_niit_paid: float
    cumulative_early_withdrawal_penalty_paid: float   # NEW
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## Modified behavior (`run_plan_projection`)

Immediately after the existing `niit = compute_niit(...)` call (the same point IRMAA/NIIT
themselves are already computed each plan year), and before `tax_owed` is computed:

1. `traditional_sequence_draw` = the `"traditional"`-type entry's `amount` in
   `mechanics_result.withdrawal_plan.sequence_withdrawals`, or `0.0` if none — the RMD leg
   (`rmd_drawn`) is never included (research.md Decision 4).
2. `under_59_traditional_share` = `sum(traditional_ownership_shares[member.person_name] *
   traditional_sequence_draw for member in household.members if
   ages_this_year[member.person_name] <= 59)`.
3. `taxable_early_distribution_base` = `under_59_traditional_share +
   ladder_result.unseasoned_amount_flagged` (`019`'s own already-computed result for this same plan
   year — no re-derivation).
4. `early_withdrawal_penalty = compute_early_withdrawal_penalty(taxable_early_distribution_base,
   tax_year)`.

`tax_owed`'s existing computation:

```python
tax_owed = federal_tax.federal_tax_owed + state_tax.state_tax_owed
```

becomes:

```python
tax_owed = federal_tax.federal_tax_owed + state_tax.state_tax_owed + early_withdrawal_penalty.penalty_owed
```

— so the new penalty is included in what `compute_withdrawal_plan(spending_need=tax_owed, ...)`
actually funds (research.md Decision 6), unlike `irmaa.surcharge_owed`/`niit.surtax_owed` (a
separate, pre-existing gap tracked as `rp-yqf`, not touched by this feature).

`figures_used` gains `*early_withdrawal_penalty.figures_used` as an additional unioned source,
alongside every other figure-producing call already contributing to it.

The resulting `PlanYearProjection` for that year carries `early_withdrawal_penalty=early_withdrawal_penalty`.

`_derive_outcome()` gains:

```python
cumulative_early_withdrawal_penalty_paid = sum(year.early_withdrawal_penalty.penalty_owed for year in years)
```

folded into the returned `PlanOutcome`, alongside the existing `cumulative_irmaa_paid`/`cumulative_niit_paid`
derivations. `cumulative_tax_paid`'s own existing derivation (`federal_tax.federal_tax_owed +
state_tax.state_tax_owed` summed) is unchanged.

Every other step of `run_plan_projection()`'s documented per-year sequence is unchanged in shape.

## Consumption expectations for downstream features

- `simulation.run_simulation()` and every `simulation.compare_*()` (`005`) call
  `comparison.run_plan_projection()` internally, unchanged — every Monte Carlo path gets this
  feature's behavior transitively, funded identically to a deterministic projection.
- `reporting.aggregation` (`006`, extended by `010`) is the consumer of
  `PlanOutcome.cumulative_early_withdrawal_penalty_paid` — see
  [reporting-api.md](./reporting-api.md) addendum.
- `services/bff` requires no change — it already passes `PlanYearProjection`/`PlanOutcome` through
  generically (confirmed during `019`'s own investigation of the identical question).
- A downstream caller constructing a `PlanYearProjection` directly (not via `run_plan_projection()`)
  must now supply `early_withdrawal_penalty` explicitly — this is a required field, mirroring
  `irmaa`/`niit`'s own existing non-defaulted precedent, not an additive/defaulted one.
