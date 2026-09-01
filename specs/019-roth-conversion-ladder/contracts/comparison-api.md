# Contract: `retirement_planner.comparison` public API (addendum to `004`, `010`, `011`, `012`, `018`)

**Signature UNCHANGED** — `run_plan_projection()` gains no new parameter (unlike `011`'s
`traditional_ownership_shares` or `012`'s `inherited_accounts`, both genuine caller-supplied
inputs). `compare_roth_conversion_strategies()`, `compare_withdrawal_sequencing_strategies()`, and
`compare_claiming_age_grid()` are unchanged in signature and require **no code change at all**
(research.md Decision 2) — the new lot-tracking state is entirely local to each
`run_plan_projection()` call, so it never needs threading through a comparison candidate the way
`inherited_accounts` does.

## Modified data types (`models`)

```python
@dataclass
class PlanYearProjection:
    # ... every existing field, unchanged ...
    unseasoned_roth_withdrawal: float = 0.0   # NEW
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## Modified behavior (`run_plan_projection`)

Before the per-year loop begins, `run_plan_projection()` now also declares
`roth_conversion_lots: list[RothConversionLot] = []` — purely local state, never a parameter,
never returned (research.md Decision 2).

Each plan year, immediately after `mechanics_result = compute_plan_year_mechanics(...)` returns
(so both this year's withdrawal and this year's own conversion are already known):

1. `roth_draw_amount` = the `"roth"`-type entry's `amount` in
   `mechanics_result.withdrawal_plan.sequence_withdrawals`, or `0.0` if none.
2. `non_lot_roth_balance` = `current_balances.roth` (this year's *starting* Roth balance) minus the
   sum of every entry in `roth_conversion_lots`' own `balance`, clamped to `>= 0.0`.
3. `age_condition_active` = `any(age <= 59 for age in ages_this_year.values())`.
4. `ladder_result = compute_roth_ladder_consumption(roth_conversion_lots, non_lot_roth_balance,
   roth_draw_amount, tax_year, age_condition_active)`; reassign
   `roth_conversion_lots = ladder_result.updated_lots`. `ladder_result.figures_used` is folded into
   this year's overall `figures_used` list, alongside every other figure-producing call already
   contributing to it.
5. If `mechanics_result.conversion.amount_converted > 0`: append a new
   `RothConversionLot(conversion_tax_year=tax_year, balance=mechanics_result.conversion.amount_converted)`
   to `roth_conversion_lots` — **after** step 4, so this year's own new conversion is never
   available to satisfy this same year's own draw (research.md Decision 3, matching
   `compute_plan_year_mechanics()`'s own existing "withdrawal before conversion" sequencing one
   level up).

The resulting `PlanYearProjection` for that year carries
`unseasoned_roth_withdrawal=ladder_result.unseasoned_amount_flagged` — `0.0` for every plan year a
household's projection doesn't flag, which is every plan year for a household with no Roth
conversion configured at all (an unaffected household's `roth_draw_amount` is either `0.0` or
always satisfied by `non_lot_roth_balance` alone, since no lot is ever created).

Every other step of `run_plan_projection()`'s documented per-year sequence (RMD, inherited-account
distributions, tax, tax-funding withdrawal, investment growth, `018`'s survivor-scenario switch) is
unchanged in shape — none of them read or write this feature's new local state.

## Consumption expectations for downstream features

- `simulation.run_simulation()` and every `simulation.compare_*()` (`005`) call
  `comparison.run_plan_projection()` internally, unchanged — each path's own call gets its own
  independent, correctly-scoped `roth_conversion_lots`, with zero risk of one path's conversions
  leaking into another's (unlike `inherited_accounts`, which genuinely requires the "fresh copy per
  path" discipline `005`'s own worker-shared-state mechanism implements — this feature needs none
  of that, since the list never leaves `run_plan_projection()`).
- A downstream reporting/UI feature wanting to show a Roth conversion ladder's own flagged years
  should read `PlanYearProjection.unseasoned_roth_withdrawal` year-over-year — it carries no dollar
  penalty of its own (FR-007); a future feature computing an actual early-withdrawal penalty (the
  separately-tracked, already-open early-withdrawal-penalty feature) is expected to consume this
  field as one of its own inputs rather than re-deriving lot seasoning itself.
