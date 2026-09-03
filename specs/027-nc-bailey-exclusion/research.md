# Research: Source-Attributed Retirement Income for State Exclusions (NC Bailey Settlement)

This feature's core legal research (what the Bailey settlement actually exempts, its 8/12/1989
vesting cutoff, and why an age-based proxy would misrepresent it) was already done in
024-nc-state-tax's `research.md` §3 and is not repeated here. This document covers only the design
decisions specific to *how* that already-researched fact gets modeled, which 024 explicitly
deferred.

## 1. Which `IncomeComponents` shape: additive field vs. separate exclusion-input object

**Decision**: Extend `IncomeComponents` with one additive, defaulted field —
`government_pension_income: float = 0.0` — populated by `comparison/projection.py`. This is
024-nc-state-tax research.md §3's candidate (1).

**Rationale**: `IncomeComponents` is the one shared input every registered state module already
receives (`compute_state_tax()`'s locked signature, `specs/002-tax-calculation-engine/contracts/
tax-api.md`). A defaulted field on it costs nothing for SC/DE/FL/NC's own non-Bailey path — they
already read only the fields they need (NC's own docstring: "accepts but ignores every parameter
it doesn't need"), so an unread field changes nothing. It keeps the interface single: one household
income snapshot per year, not two parallel objects a caller must remember to keep in sync.

**Alternatives considered**:
- *A separate opt-in per-state exclusion-input object, passed alongside `IncomeComponents`.*
  Rejected — it would mean widening `compute_state_tax()`'s and every module's `compute_tax()`
  signature (or threading an optional second parameter through all four registered modules for a
  fact only one of them uses), a larger surface change than a single defaulted field for the same
  outcome. `StateTaxResult`/`FederalTaxResult`'s own precedent (a request-scoped struct with
  liberally-defaulted fields, e.g. `EarlyWithdrawalPenaltyResult`'s caller-computed-base pattern)
  favors folding new, optional, state-relevant facts into the existing shared struct instead of
  multiplying request objects.

## 2. Field naming: state-specific vs. general

**Decision**: Name the field `government_pension_income`, not `bailey_qualifying_income` or
`nc_bailey_income` — matching 024's own research note's proposed name.

**Rationale**: `IncomeComponents` is consumed by every state module, not just NC's. A name scoped
to "government pension income, as attested by the household" describes the real-world category
(what kind of income this is) rather than which state's rule currently reads it — spec.md FR-009's
requirement that the mechanism not preclude a future state's own source-attributed exclusion from
reusing the same field without a further shape change. The household-facing *flag* that produces
this figure (see §3 below) is named concretely for what it represents today (`bailey_qualifying`)
since that is the actual, specific fact being attested — mirroring how SC's and DE's exclusion
`SourcedFigure`s are named for their own state (`_AGE_65_EXCLUSION`, `_AGE_60_EXCLUSION`) even
though `IncomeComponents.social_security_gross_benefit` (the input those two read) is itself
generally named. A future state's own different source-attributed rule, if one is ever built, would
add its own concretely-named `IncomeStream` flag or reuse `bailey_qualifying` where the underlying
fact is genuinely the same rule (e.g. another state with its own Bailey-style pre-1989 government-
pension grandfather clause) — this feature does not need to resolve that possibility today.

## 3. Where the flag lives: `IncomeStream`, not `HouseholdMember` or a new top-level entity

**Decision**: Add `bailey_qualifying: bool = False` to `IncomeStream` (scenario layer).

**Rationale**: Bailey exempts income by *plan/source*, not by person — a member could plausibly
have one Bailey-qualifying government pension stream and one non-qualifying private annuity or
earned-income stream in the same household (Edge Cases, spec.md). `IncomeStream` is already the
project's per-source income entity (021-pension-annuity-income); attaching the flag there, rather
than to `HouseholdMember` (which would force an all-or-nothing per-person exemption, wrong per the
Edge Cases) or a new top-level entity (unnecessary — no new relationships, cardinality, or
lifecycle beyond what `IncomeStream` already has), keeps the shape minimal and correct.

**Alternatives considered**:
- *A `bailey_qualifying_amount: float` sub-split within one stream* (part of a stream's amount
  qualifies, part doesn't). Rejected — not supported by real Bailey law (a given pension plan
  either is or isn't a qualifying government/military plan the member was vested in by 8/12/1989;
  there's no partial-stream case), and spec.md's Edge Cases already cover the actually-occurring
  case (multiple streams, some flagged) without it.

## 4. No new `SourcedFigure`

**Decision**: No `SourcedFigure` is introduced for the Bailey exclusion itself. It is documented as
a structural rule (100%-or-nothing, no rate/threshold/dollar-amount schedule to key by tax year) in
`nc.py`'s module docstring and `test_nc.py`, citing N.C. Gen. Stat. §105-134.6 history and *Bailey
v. State of North Carolina* (1998), the same citations already surfaced in 024's own research.md §3.

**Rationale**: `SourcedFigure` exists to schedule a *number* by tax year (`SourcedFigure.
value_for_year()`); Bailey has no number to schedule — it is a categorical exemption of whatever
amount the household attests is Bailey-qualifying. `nc.py` already draws exactly this distinction
for Social Security ("this is not a SourcedFigure, it's simply never read") — the Bailey exclusion
is documented the same way: a real, cited rule, honestly represented as a structural fact rather
than forced into a schedule shape that doesn't fit it. NC's existing `_NC_FLAT_RATE` `SourcedFigure`
is unaffected and remains the only figure NC's module cites with `usage_for_year()`.

## 5. Federal/FICA/IRMAA/NIIT must not see a reduced income figure

**Decision**: `government_pension_income` is populated as a *subset* of, not an addition to,
`mechanics_result.ordinary_income` — `IncomeComponents.ordinary_income` is unchanged from today's
construction (`comparison/projection.py`'s existing `IncomeComponents(ordinary_income=mechanics_
result.ordinary_income, ...)` line). Federal tax, `_approximate_magi()`, FICA, IRMAA, and NIIT all
already consume `ordinary_income` (or `mechanics_result.ordinary_income` directly) unchanged, so
none of them need to change or even be touched.

**Rationale**: Bailey is a North Carolina *state* exemption; the income itself is real and fully
federally taxable (spec.md User Story 2 / FR-003). Keeping `government_pension_income` a read-only,
additive side-channel — never subtracted from `ordinary_income` itself — is what guarantees every
other consumer is unaffected by construction, not by a test asserting it after the fact (though
that test is added too, per the Constitution Check's test-coverage note).

## 6. Computing the household's Bailey-qualifying total

**Decision**: A new private helper in `comparison/projection.py`,
`_household_bailey_qualifying_income(household, ages_this_year, tax_year, reference_tax_year) ->
float`, mirrors `_member_earned_income_amounts()`'s own shape: it iterates every member's
`income_streams`, calls the existing `compute_income_stream_amount()` for each stream where
`stream.bailey_qualifying` is `True`, and sums the result. It returns no `figures_used` of its own.

**Rationale**: `_member_income_stream_amounts()` (called earlier in the same loop iteration, for
the same `household`/`ages_this_year`/`tax_year`/`reference_tax_year`) already iterates every
stream — Bailey-qualifying ones included — and already collects each stream's own
`INFLATION_RATE` `FigureUsage` for `fixed_nominal` streams. A second helper collecting the same
figures again would only duplicate entries an unaffected downstream reader (`reporting.
aggregation._unverified_figure_names()`) already dedupes — exactly the precedent
`_member_earned_income_amounts()`'s own docstring already states for the analogous 022-fica-
payroll-tax case. `compute_income_stream_amount()` is cheap and pure (constitution Principle VI),
so recomputation is not a real performance concern, matching that same precedent.

**Alternatives considered**:
- *Extend `_member_income_stream_amounts()` to also return a per-member Bailey-qualifying subtotal
  dict, avoiding a second pass.* Rejected for this feature — it would change that function's return
  shape (and therefore `PlanYearProjection.member_income_stream_amounts`'s existing contract,
  021-pension-annuity-income's locked addendum), a larger blast radius than a second, independent,
  cheap helper. Left as a possible future optimization if a later feature needs the same per-member
  breakdown for another reason.
