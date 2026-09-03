# Phase 0 Research: Social Security Earnings Test (Withholding + FRA Recredit)

No `[NEEDS CLARIFICATION]` markers were left in spec.md (rp-acq's own design notes, plus this
session's scoping decision to fully model withholding + recredit, already fixed the biggest
ambiguities). This phase resolves the remaining design questions needed to turn the spec's
requirements into an implementation that fits this codebase's existing conventions and the real SSA
mechanics, verified against primary/authoritative sources rather than assumed.

## Decision 1: Both new operations join `mechanics/social_security_benefit.py`, not a new module

**Decision**: `compute_earnings_test_withholding()` and `compute_earnings_test_recredit()` are added
to the existing `mechanics/social_security_benefit.py` (016, extended by 017), not a new sibling
module.

**Rationale**: Both operate on the same domain primitives this module already owns — a member's PIA,
FRA, claiming age, and the claiming-age-adjusted benefit `compute_social_security_benefit()` already
derives. 42 U.S.C. §403 (earnings test) and §402(q) (early-claiming reduction, already cited by this
module) are both administered by SSA as one continuous "what does this claim actually pay" question
— the ARF recredit mechanism (Decision 4 below) is explicitly a recalculation of the *same* reduction
factor 016 already computes, not a separate legal concept. Splitting into a new module would
duplicate `_DOCUMENTED_YEARS` and this module's existing citation infrastructure for no benefit,
mirroring 017's own Decision 1 precedent.

**Alternatives considered**: A new `mechanics/earnings_test.py` — rejected for the reason above.

## Decision 2: Exempt-earnings thresholds — real, cited 2026 SSA figures, held flat

**Decision**: Two new `SourcedFigure`s, `SS_EARNINGS_TEST_EXEMPT_AMOUNT_BELOW_FRA` ($24,480/yr) and
`SS_EARNINGS_TEST_EXEMPT_AMOUNT_FRA_YEAR` ($65,160/yr), each `schedule={year: <2026 value> for year
in _DOCUMENTED_YEARS}` — pinned to their 2026 SSA-published values and held flat across every
documented year, mirroring `tax/fica.py`'s `OASDI_WAGE_BASE` precedent exactly (a genuinely
wage-indexed, annually-changing-in-reality figure this engine has no wage-growth projection to
re-derive, disclosed as such in the citation rather than silently treated as fixed-by-statute).
Withholding ratios ($1-for-$2 below FRA, $1-for-$3 in the FRA year) are fixed by statute, not
annually revised, and are bundled into the same `_EarningsTestRates` dataclass as constants —
mirrors `_ClaimingAgeAdjustmentRates`' own "rates fixed by regulation, thresholds not" split for
early-reduction vs. delayed-credit.

**Citation**: 42 U.S.C. §403(b) (deductions on account of excess earnings), §403(f) (excess-earnings
computation, the exempt-amount/ratio mechanics, and the higher FRA-year amount applying only to
earnings in months before FRA attainment — confirmed against Cornell LII's e-CFR/U.S. Code mirror);
20 C.F.R. §404.430 (monthly and annual exempt amounts defined; excess earnings defined) and §404.434
(excess earnings — method of charging, i.e. the $1-for-$2/$1-for-$3 ratios). Dollar figures: SSA,
"2026 Cost-of-Living Adjustment (COLA) Fact Sheet" (https://www.ssa.gov/news/en/cola/factsheets/2026.html)
— the same source `tax/fica.py`'s `OASDI_WAGE_BASE`/`OASDI_RATE` already cite — cross-checked against
an independent mirror of the same fact sheet (msubillings.edu) confirming $24,480/yr ($2,040/mo)
below FRA and $65,160/yr ($5,430/mo) in the FRA-attainment year for 2026.

**Rationale**: Matches FR-003, FR-004, FR-009. Two separate `SourcedFigure`s (not one figure with a
"which tier" parameter) mirrors this codebase's "one `SourcedFigure` per real-world citable rule"
convention — the two thresholds are two different dollar amounts from two different rows of the same
SSA table, not one number with a lookup key.

**Alternatives considered**: Treating the exempt amounts as fixed-by-statute like the Additional
Medicare Tax thresholds (`fica.py`) — rejected; unlike that tax's $200k/$250k thresholds (fixed since
2013, never inflation-indexed), the earnings-test exempt amounts are explicitly wage-indexed and
change annually by SSA's own published methodology, so "held flat" here is this engine's own
documented simplification, not a restatement of what the law actually does.

## Decision 3: Whole-plan-year granularity for the FRA-attainment year

**Decision**: A member's FRA-attainment year (the one plan year the earnings test's more lenient
FR-004 rule applies to) is identified as the plan year where `ages_this_year[member] ==
floor(full_retirement_age)` — the year the member turns the whole-number part of their FRA age,
during which their exact FRA birthday (whatever fractional month it falls on) also occurs. Years
where `ages_this_year[member] < floor(full_retirement_age)` use the stricter FR-003 rule; years where
`ages_this_year[member] > floor(full_retirement_age)` are past FRA entirely, and the earnings test no
longer applies (FR-002). The member's *entire* earned income for the FRA-attainment plan year is
tested against the FRA-year threshold/ratio — this engine has no month-level granularity to isolate
"earnings only in months before the FRA birthday," so the whole year is tested at the more lenient
FRA-year rate rather than split.

**Rationale**: Directly extends this module's own existing documented simplification for
`compute_social_security_benefit()` ("months early/delayed ... computed as a continuous linear
function of claiming_age and full_retirement_age ... not SSA's own whole-month administrative
processing ... this engine has no notion of a mid-year claim date"). Using `floor(full_retirement_age)`
rather than requiring FRA to be a whole integer keeps the same fractional-FRA input this module
already accepts (`HouseholdMember.full_retirement_age: float`) meaningful for this feature too.

**Alternatives considered**: Splitting the FRA-attainment year's earned income pro-rata by month
against both rules — rejected; this engine tracks no month-level earnings distribution for an
`earned_income` stream (it is a single annual amount), so a pro-rata split would fabricate precision
this engine has no actual data to support, worse than the documented whole-year simplification
already precedented elsewhere in this module.

## Decision 4: Recredit tracked in whole "deduction months," not raw withheld dollars

**Decision**: `run_plan_projection()` carries one new piece of local, per-member cross-year state —
`cumulative_earnings_test_months_withheld: dict[str, int]` — mirroring `roth_conversion_lots`'s own
"purely local, never a function parameter" precedent (019 research.md Decision 2). For each year
withholding occurs, this engine derives that year's own "deduction months" as
`min(12, ceil(withheld_amount_this_year / (original_annual_benefit / 12)))` when
`original_annual_benefit > 0`, else `0` — a whole month is credited even for a year with only
*partial*-month withholding, per SSA's own crediting rule (POMS RS 00615.482 B: "Proration of work
deductions has no effect on the adjustment of the reduction factor" — a month with any withholding at
all, full or partial, counts as one full deduction month). Once a member's age reaches their
FRA-attainment year (Decision 3), `compute_earnings_test_recredit()` converts the accumulated total
into a permanently smaller "months early" figure for `compute_social_security_benefit()`'s own
reduction formula — capped so the recredit can restore at most back to 100% of PIA (the reduction
factor's early-claiming penalty fully eliminated), never past it into delayed-credit territory, per
SSA's own framing of ARF as "eliminat[ing] the reduction for age applied for the months you were not
paid," not as manufacturing bonus delayed-retirement-credit months.

**Citation**: SSA POMS RS 00615.480 (Reduction Factor Adjustment (ARF) — automatic recalculation at
FRA of the early-claiming reduction to reflect months of full or partial benefit withholding) and RS
00615.482 (Requirements for ARF — Crediting Months: partial-withholding months count as full
deduction months); 20 C.F.R. §404.410 (the same reduction-factor regulation this module already
cites for the original early-claiming reduction — ARF recalculates that exact factor, it is not a
separate formula).

**Rationale**: Matches FR-006, FR-007. Tracking whole months (an integer) rather than raw dollars is
both more faithful to the real POMS crediting rule (which counts months, not a dollar-prorated
fraction of a month) and simpler state to carry — a running `int`, not a running `float` requiring a
separate "how many dollars equal one month" reconciliation at credit time.

**Alternatives considered**: Tracking cumulative raw dollars withheld and dividing by the monthly
benefit only once, at FRA — rejected; this would silently contradict the POMS rule that a
partial-withholding month still credits as a full month (a dollar-prorated approach would
under-credit any year where withholding was less than a clean multiple of the monthly benefit).
Allowing the recredit to exceed 100% of PIA (treating withheld months exactly like delayed-claiming
months) — rejected; no source found describing ARF as capable of producing an above-PIA benefit, and
every source consulted frames it strictly as reduction *elimination*, not credit generation.

## Decision 5: Earnings test evaluated per member, using only that member's own earned income

**Decision**: `compute_earnings_test_withholding()` takes one member's own claiming-age-adjusted
benefit and that same member's own `earned_income`-type stream total for the year — never
household-combined, unlike `tax/fica.py`'s Additional Medicare Tax threshold (FR-001).

**Rationale**: Matches 42 U.S.C. §403(b)'s own framing (deductions "from any payment... to such
individual," i.e., the earnings test is evaluated against the beneficiary's own earnings, not a
household aggregate) and mirrors this module's existing per-member shape for every other benefit
computation (`compute_social_security_benefit()`, `compute_spousal_benefit_floor()`) — explicitly
named in the issue's own design notes as the correct precedent to follow.

**Alternatives considered**: None seriously — the statute and this module's existing shape agree, and
the issue explicitly calls this out as the intended design.
