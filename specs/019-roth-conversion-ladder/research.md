# Phase 0 Research: Roth Conversion Ladder (Five-Year Rule) Tracking

No `[NEEDS CLARIFICATION]` markers remain in spec.md — the two open scope questions (age-59.5 check
shape; flag-only vs. computed-penalty scope) were resolved with the user during `/speckit-specify`
itself (see spec.md's Input section). This document records the remaining *implementation-shape*
decisions made during planning.

## Decision 1: A new sibling module, not a branch inside `roth_conversion.py`

**Decision**: `mechanics/roth_conversion_ladder.py`, a new module, houses
`compute_roth_ladder_consumption()`, `RothConversionLot`'s companion result type
(`RothLadderConsumptionResult`), and the new `ROTH_CONVERSION_SEASONING_YEARS` `SourcedFigure`.

**Rationale**: `roth_conversion.py`'s existing functions (`fill_to_bracket_ceiling()`,
`fixed_dollar_amount()`, `compute_roth_conversion()`) all share one shape — "how much gets
converted this year, given this year's income/balances" — and their signatures are a locked
contract (`003`/`010`). The new function is a materially different computation ("given a draw
amount and a list of prior conversions, how is that draw apportioned, and does it touch unseasoned
principal") with no dependency on `roth_conversion.py`'s own internals. This mirrors `012`'s own
precedent exactly: `inherited_rmd.py` is a sibling to `rmd.py`, not a branch inside
`compute_rmd()`, for the identical reason ("a conceptually and legally distinct computation",
`inherited_rmd.py`'s own module docstring).

**Alternatives considered**:
- *Add the new function to `roth_conversion.py`* — rejected: would mix two different call shapes
  in one module (a per-year "how much converts" function family vs. a "how does a draw consume
  prior conversions" function), and risks a future reader assuming `CONVERSION_STRATEGIES`-style
  registry dispatch applies to it too, which it does not (there is only one consumption algorithm,
  not a family of swappable strategies).

## Decision 2: The lot list is local, per-call state — never a caller-supplied parameter

**Decision**: Inside `run_plan_projection()`, `roth_conversion_lots: list[RothConversionLot] = []`
is declared and initialized fresh at the top of the function, exactly like the existing local
`years: list[PlanYearProjection] = []` — **not** added as a new function parameter.

**Rationale**: `012`'s `inherited_accounts` parameter exists because a scenario genuinely can
configure *pre-existing* inherited accounts as an input — real data a caller must supply. This
feature has no equivalent input: FR-002 establishes that a household's pre-existing Roth balance is
*always* treated as already-seasoned, precisely because there is no data-model concept for
"pre-existing lots" to begin with (spec.md Assumptions — explicitly out of scope, a materially
larger data-model expansion). Every lot this feature ever tracks is one this exact
`run_plan_projection()` call itself created via its own `compute_roth_conversion()` calls earlier
in the same call's own loop — there is nothing to pass in, and therefore nothing that could ever
leak between two different calls (unlike `inherited_accounts`, which are genuinely shared/mutated
in place and need the "fresh copy per candidate/path" discipline `012`'s research.md §10 and `004`'s
`compare.py`/`005`'s `monte_carlo.py` both had to adopt).

**Consequence (the scope-narrowing insight this plan's Summary calls out)**: because the list never
crosses a call boundary, `comparison/compare.py`, `simulation/monte_carlo.py`,
`services/bff/resolution.py`, and `apps/streamlit_ui` need **zero** changes — every one of them
already calls `run_plan_projection()` once per candidate/path, and each such call gets its own
independent, correctly-scoped lot list automatically, with no possibility of one candidate's or
one Monte Carlo path's conversions leaking into another's.

**Alternatives considered**:
- *Thread it as a parameter anyway, defaulting to `[]`, mirroring `inherited_accounts`'s shape for
  consistency* — rejected: would invite a caller to pass a non-empty list, implying pre-existing
  lots are a supported input when they explicitly are not (FR-002); adds an unused-in-practice
  parameter and its own "fresh copy" discipline burden for zero actual benefit, since nothing in
  this codebase would ever have a non-empty list to pass.

## Decision 3: Where the per-year attribution call happens in `run_plan_projection()`

**Decision**: Immediately after `mechanics_result = compute_plan_year_mechanics(...)` returns (so
both this year's withdrawal and this year's own conversion, if any, are already known), in this
order:

1. Compute `roth_draw_amount` from `mechanics_result.withdrawal_plan.sequence_withdrawals` (the
   `"roth"`-type line item, if present, else `0.0`).
2. Compute `non_lot_roth_balance` as `current_balances.roth` (this plan year's *starting* Roth
   balance, before this year's draw or conversion) minus the sum of every open lot's own `balance`
   — clamped to `>= 0.0` for floating-point safety.
3. Compute `age_condition_active` as `any(age <= 59 for age in ages_this_year.values())` (spec.md
   Edge Cases' whole-plan-year-age rule) — a small private helper, not exported.
4. Call `compute_roth_ladder_consumption(roth_conversion_lots, non_lot_roth_balance,
   roth_draw_amount, tax_year, age_condition_active)`, which returns (Decision 5) an updated lot
   list (consumed lots decremented) plus the flagged amount and any `figures_used`; reassign
   `roth_conversion_lots = result.updated_lots`.
5. **After** step 4 (never before — see Edge Cases' "a same-year conversion can never be its own
   year's draw source"): if `mechanics_result.conversion.amount_converted > 0`, append a new
   `RothConversionLot(conversion_tax_year=tax_year, balance=mechanics_result.conversion.amount_converted)`
   to `roth_conversion_lots`.

**Rationale**: `compute_plan_year_mechanics()` already internally sequences "withdrawal first, then
conversion" (`plan_year.py`'s own docstring: conversion uses the withdrawal's *ending* balances) —
step 5's ordering here simply preserves that same real sequencing one level up, so a lot created
this year is never available to satisfy this same year's own draw, matching spec.md's Edge Cases
bullet exactly.

## Decision 4: `figures_used` is populated only when a lot's seasoning is actually consulted

**Decision**: `compute_roth_ladder_consumption()`'s returned `figures_used` includes
`ROTH_CONVERSION_SEASONING_YEARS.usage_for_year(tax_year)` if and only if the draw actually reaches
past `non_lot_roth_balance` into at least one lot (i.e., `roth_draw_amount > non_lot_roth_balance`)
— regardless of whether that lot turns out to already be seasoned (no flag raised) or
`age_condition_active` is `False` (no flag raised either way). It is empty whenever the draw never
reaches a lot at all.

**Rationale**: Matches this codebase's existing "the figure is consulted, not merely the outcome
that mattered" convention — `compute_social_security_benefit()` already adds its own figure's usage
even when `adjustment_factor == 1.0` (claiming exactly at FRA, no actual adjustment). A lot's
5-year-elapsed test is genuinely evaluated the moment a draw reaches it, independent of whether the
household happens to also be past the age condition that turns that evaluation into a visible flag.

## Decision 5: `compute_roth_ladder_consumption()` is pure — it returns updated lots, it does not mutate its input

**Decision**: `compute_roth_ladder_consumption()` takes `lots: list[RothConversionLot]` and returns
a `RothLadderConsumptionResult` carrying `updated_lots: list[RothConversionLot]` (a fresh list with
each consumed lot's own `balance` decremented) alongside `unseasoned_amount_flagged` and
`figures_used` — it never mutates the `lots` argument it was handed. `run_plan_projection()`
reassigns its own local `roth_conversion_lots = result.updated_lots` after each call.

**Rationale**: `012`'s own contract states this explicitly for the whole `mechanics` package:
*"every function in this package remains a pure, side-effect-free computation over its explicit
arguments"* (`contracts/mechanics-api.md`'s Consumption expectations) — `compute_inherited_rmd()`
itself never mutates `InheritedAccountBalance.balance`; only `run_plan_projection()` (in the
`comparison` package) does that, based on `compute_inherited_rmd()`'s returned result. This
feature's function follows the identical division of responsibility: `mechanics` computes and
returns, `comparison` orchestrates and mutates its own local state. An initial draft of this
function mutated `lots` in place directly (matching `InheritedAccountBalance`'s own mutability
shape too closely, without noticing *who* is allowed to perform that mutation) — corrected here
before implementation to keep the whole `mechanics` package's existing purity guarantee intact.

**Alternatives considered**:
- *Mutate `lots` in place, return only the flagged total* — rejected: breaks `012`'s own explicit
  package-wide purity contract, and would make this function behave differently from every other
  `mechanics` function a reader might reasonably expect to compose the same way.
- *Return only per-lot deltas (index -> amount drawn) instead of the full updated list* — rejected:
  couples the caller to this function's internal indexing/ordering choices for no real benefit;
  returning the already-updated list is simpler for `run_plan_projection()` to consume (a plain
  reassignment) and mirrors how `compute_withdrawal_plan()` itself already returns a whole new
  `ending_balances` rather than a set of deltas against `starting_balances`.

## Decision 6: `docs/BRD.md` location

**Decision**: Extend the existing Roth conversion methodology subsection (`§6.6 Roth conversion &
withdrawal sequencing`, confirmed by reading `docs/BRD.md`'s current structure) with a description
of lot tracking and the unseasoned-withdrawal flag, and add this feature's own disclosed gaps to
`§7 Known Limitations & Open Items` (mirroring `018`'s own precedent for both sections).
