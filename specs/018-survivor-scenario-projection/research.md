# Phase 0 Research: Survivor Scenario Projection Wiring

No `[NEEDS CLARIFICATION]` markers remain in spec.md — the two open scope questions (Monte Carlo
integration depth; spending-reduction assumption shape) were resolved with the user during
`/speckit-specify` itself (see spec.md's Input section). This document records the remaining
*implementation-shape* decisions made during planning.

## Decision 1: Where the death-tax-year computation lives

**Decision**: A new private helper in `comparison/projection.py`, computed **once** before
`run_plan_projection()`'s per-year `while True` loop starts (not recomputed every iteration):

```python
def _household_death_tax_year(household: Household, reference_tax_year: int) -> tuple[HouseholdMember, int] | None:
    """Returns (dying_member, death_tax_year) for an MFJ household with at
    least one member's predicted_death_age configured, or None. death_tax_year
    is the first tax year that member's translated age reaches
    predicted_death_age (member_age_in_tax_year's own formula, inverted).
    When both members have it configured, returns the EARLIER of the two
    (018 spec.md Edge Cases) -- the survivor's own later configured death has
    no further effect this feature models."""
```

**Rationale**: `run_plan_projection()` already computes several such "fixed for the life of this
call" values before its loop (`deemed_owner`, `traditional_ownership_shares` eager check) — this
follows the same shape. Computing it once avoids re-deriving the same tax year on every iteration and
keeps the per-iteration diff small (one `tax_year > death_tax_year` comparison).

**Alternatives considered**:
- *Recompute every iteration from `ages_this_year`* — rejected: `ages_this_year` is already
  per-member per-year, but deriving "which year does age X first occur" from it needs the same
  inversion arithmetic either way; hoisting it once is strictly simpler and cheaper.
- *A method on `Household`* — rejected: `scenario/models.py`'s dataclasses are documented as
  shape-only, no behavior (`"Field-level validation rules live in validation.py, not here — this
  module only defines shape"`) — this project's existing convention keeps derivations in the
  consuming module (`comparison/projection.py`), not on the data model itself.

## Decision 2: Survivor benefit inputs — post-spousal-floor amounts, not raw PIA-derived amounts

**Decision**: `compute_survivor_benefit()` is called with each member's **already-computed**
`member_ss_benefits[...]` value for that plan year (i.e., whatever `_member_gross_social_security_benefits()`
already produced, which for an MFJ household already reflects `017`'s spousal-benefit floor when it
applied) — not a fresh, spousal-floor-free recomputation from each member's raw PIA.

**Rationale**: The real SSA survivor rule is "the higher of what each spouse was actually being paid
immediately before the death" — for a lower-earning spouse who was already receiving a spousal-floor
amount, that spousal-floor amount *is* what they were "actually being paid," so it's the correct input,
not a synthetic own-PIA-only figure that was never actually paid. This also means no new calculation
path is needed: the existing `_member_gross_social_security_benefits()` call already sitting at the
top of the loop supplies both inputs directly.

**Alternatives considered**:
- *Recompute each member's own claiming-age-adjusted benefit from scratch, ignoring the spousal floor*
  — rejected: this would use a number that was never actually the benefit paid, and would require a
  second, parallel calculation path purely for this feature, duplicating `017`'s own logic rather than
  reusing its output.

## Decision 3: Attribution — deceased member's benefit becomes 0, survivor's becomes the survivor amount

**Decision**: In `member_ss_benefits` (the per-member breakdown dict, also exposed on
`PlanYearProjection.member_social_security_benefits` per `015`), the dying member's entry is set to
`0.0` and the surviving member's entry is set to `compute_survivor_benefit()`'s result, for every
post-death plan year. `household_ss_benefit` (the summed total used by `IncomeComponents`) equals the
survivor's entry exactly (the deceased contributes 0), consistent with `017`'s "the lower one
contributes $0 from that point" framing (017 FR-005) even though `017` itself never wired this
attribution into a projection.

**Rationale**: Matches `015`'s existing "each member's own gross benefit, 0.0 before that member's own
claiming age, never omitted" precedent — a dict entry disappearing or staying at a stale pre-death
value would silently mislead a per-member reporting consumer.

## Decision 4: `Household.survivor_spending_reduction_pct` — fraction (0.0-1.0), not a whole percentage

**Decision**: The new field is a fraction in `[0.0, 1.0]` (e.g. `0.2` for a 20% reduction), applied as
`annual_spending_need * (1 - household.survivor_spending_reduction_pct)`, defaulting to `0.0`.

**Rationale**: Matches this codebase's existing convention for reduction/adjustment factors expressed
as fractions of 1 (e.g. `mechanics/social_security_benefit.py`'s `adjustment_factor`,
`monte_carlo.py`'s `growth_factor` -- always `1.0 +/- <fraction>`), rather than introducing a
0-100-scaled percentage field with no precedent elsewhere in the data model.

**Alternatives considered**:
- *0-100 whole-number percentage* — rejected: no existing field in this codebase uses that scale;
  would require its own bespoke `/100.0` conversion at the one point it's consumed, for no benefit.

## Decision 5: `PlanYearProjection` gains `filing_status` and `effective_spending_need` — new additive fields, not derived/computed properties

**Decision**: Add `filing_status: Literal["single", "married_filing_jointly"] | None = None` and
`effective_spending_need: float = 0.0` to `PlanYearProjection` (mirrors `015`'s "additive field with a
default, populated by `run_plan_projection()`, existing hand-built instances elsewhere unaffected"
pattern exactly). `run_plan_projection()` always populates both with that year's *effective* values
(`household.filing_status`/`annual_spending_need` before/through the death year, `"single"`/the
reduced amount after) — every plan year gets a concrete value; the defaults only appear if some other
future caller builds a `PlanYearProjection` by hand without setting them.

**Rationale**: Without these, a reporting/UI/BFF consumer has no per-year signal that either switch
happened at all — every existing surface reads `household.filing_status` once, statically, assuming it
never changes mid-horizon (confirmed via grep, plan.md Technical Context), and no existing `mechanics`
result type echoes back its own `spending_need` input at all (checked directly against
`mechanics/models.py`). `household.filing_status`/`annual_spending_need` themselves must stay the
household's *configured* values, never runtime-mutated, for User Story 2's independent-candidate
correctness and Principle II reproducibility — so the per-year *effective* values need their own home,
and `PlanYearProjection` (a type this feature already modifies, already the per-year audit record for
every other derived figure) is the natural one rather than reaching into the `mechanics` package for a
type this feature has no other reason to touch.

**Alternatives considered**:
- *Don't expose it at all this feature; a future reporting feature adds it when needed* — rejected:
  spec.md User Story 1's Independent Test explicitly requires confirming "filing status is
  `married_filing_jointly` through the death year and `single` in every subsequent year" from a
  projection's own output — without a per-year field, that assertion has no field to check, since
  `federal_tax`/`state_tax` results don't themselves echo back which filing status produced them.

## Decision 6: `comparison/compare.py` needs no code change (User Story 2)

**Decision**: No modification to `compare_roth_conversion_strategies()`, `compare_withdrawal_sequencing_strategies()`,
or `compare_claiming_age_grid()`. Confirmed by reading `compare.py`: all three already pass the same
`household` argument, unmodified, into every candidate's own `run_plan_projection()` call — so once
that function applies the death-tax-year switch internally, every candidate gets it automatically.

**Rationale**: Matches the `004` research.md's own original design intent (paired-draw comparison:
every comparison axis holds every *other* input, including `household`, fixed) — this feature adds no
new comparison axis and doesn't need one; it changes what one already-shared input (`household`, via
its new field, and the loop that consumes it) produces.

## Decision 7: `docs/BRD.md` location

**Decision**: Update the existing Social Security subsection `017` already touched (spousal/survivor
benefit rules) to add a short "mid-horizon projection wiring" note referencing this feature, plus (if
the BRD has a general "known limitations" or "projection engine" section, as `016`/`017` used) add
this feature's own disclosed gaps there — confirmed by reading `docs/BRD.md`'s existing structure at
implementation time, not duplicated here since exact section numbering may have shifted since `017`
merged.
