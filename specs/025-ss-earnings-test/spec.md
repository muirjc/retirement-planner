# Feature Specification: Social Security Earnings Test (Withholding + FRA Recredit)

**Feature Branch**: `025-ss-earnings-test`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "Model the SSA retirement earnings test (42 U.S.C. §403(b)-(c), 20 C.F.R. §404.415-§404.442) per household member: for a member who claims Social Security before their own full retirement age (FRA) while still working (a configured `earned_income` stream), benefits are withheld above an annual exempt-earnings threshold ($1-for-$2 over the limit, or the more lenient $1-for-$3 in the calendar year FRA is reached), and withheld amounts are recredited starting at FRA via a permanently higher benefit — not simply lost. Addresses beads issue rp-acq, a documented gap in docs/BRD.md §5.3/§6.2a."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the near-term benefit actually withheld (Priority: P1)

A household member claims Social Security at 62 while still working a phased-retirement `earned_income` stream well above the annual exempt-earnings threshold. The household wants their projection's near-term Social Security income — and therefore near-term ordinary income, taxes, and Roth-conversion bracket headroom — to reflect the real SSA earnings-test withholding, not the full unwithheld benefit this engine currently assumes.

**Why this priority**: This is the core gap the issue exists to close — without it, any scenario combining early claiming with continued work overstates near-term Social Security income, and everything downstream of it (taxable Social Security, ordinary income, tax, IRMAA/NIIT exposure, Roth-conversion headroom) inherits that overstatement.

**Independent Test**: Configure a member claiming at 62 (FRA 67) with a $60,000/year `earned_income` stream, run a projection, and confirm that year's Social Security benefit is reduced below the unadjusted claiming-age-adjusted amount by the earnings-test withholding formula applied to the excess over that year's exempt amount.

**Acceptance Scenarios**:

1. **Given** a member claiming before FRA with earned income above the year's exempt-earnings threshold, **When** a projection year is computed, **Then** that member's Social Security benefit for the year is reduced by $1 for every $2 of earned income above the threshold, never below $0.
2. **Given** the same member's earned income at or below the year's exempt-earnings threshold, **When** a projection year is computed, **Then** no withholding applies — the benefit equals the full claiming-age-adjusted amount, unchanged from today's behavior.
3. **Given** a member who has already reached FRA (regardless of claiming age) or has not yet claimed, **When** a projection year is computed, **Then** the earnings test never applies, regardless of that member's earned income.

---

### User Story 2 - See withheld benefits recredited at FRA, not simply lost (Priority: P1)

The same household reaches the point where the working member turns FRA. The household wants their projection to show that member's benefit permanently step up from that year forward to account for the months of benefit withheld earlier — matching SSA's actual recalculation — rather than treating the earlier withholding as a permanent loss with no payback.

**Why this priority**: Modeling withholding alone, with no recredit, overstates the real financial penalty of early claiming-while-working exactly as much as modeling nothing overstates the benefit — the issue's acceptance criteria treats these as equally wrong. This is what makes User Story 1 accurate rather than merely partial.

**Independent Test**: Run the same household's projection through the member's FRA year and confirm that member's benefit from FRA forward is higher than their original claiming-age-adjusted amount, by an amount consistent with the cumulative benefit-months withheld pre-FRA — and confirm a household with identical claiming choices but zero pre-FRA withholding shows no such step-up.

**Acceptance Scenarios**:

1. **Given** a member whose pre-FRA benefit was withheld in one or more prior projection years, **When** that member's age reaches FRA, **Then** their benefit from that year forward is recalculated permanently higher, consistent with SSA's "as if claimed that many months later" recredit rule.
2. **Given** a member who claimed before FRA but was never subject to withholding (earned income always at or below the exempt threshold, or no `earned_income` stream configured), **When** that member reaches FRA, **Then** no recredit applies — their benefit is unaffected by this feature, identical to today's behavior.

---

### User Story 3 - See the more lenient rule apply in the FRA-attainment year (Priority: P2)

A household member reaches FRA partway through a projection year while still working. The household wants that transition year to use the real, more lenient earnings-test rule that applies specifically in the year FRA is reached — a materially higher exempt amount and a less punitive $1-for-$3 withholding ratio — rather than the stricter before-FRA rule applying for the whole year.

**Why this priority**: A real, distinct rule (a different threshold and ratio) that, if skipped in favor of always applying the stricter before-FRA rule, would overstate withholding specifically in each member's one transition year — a smaller error than User Stories 1-2 but still a named, citable SSA rule.

**Independent Test**: Configure a member whose FRA falls within a projection year, with earned income between the two years' exempt thresholds, and confirm that year's withholding uses the higher exempt amount and $1-for-$3 ratio rather than the stricter before-FRA figures.

**Acceptance Scenarios**:

1. **Given** a member reaching FRA during the current projection year with earned income above the FRA-year exempt amount but below what the stricter before-FRA threshold would allow, **When** that year is computed, **Then** withholding uses the FRA-year exempt amount and $1-for-$3 ratio, not the before-FRA figures.

---

### Edge Cases

- Withholding computed for a year can never exceed that year's own otherwise-payable benefit — the result floors at $0, it never goes negative or carries a negative balance into other income sources.
- A member has an `earned_income` stream but claims at or after their own FRA: the earnings test never applies, regardless of earned-income amount (matches real SSA rules and this engine's existing behavior).
- A household configures no `earned_income` streams anywhere (the common case, including every scenario predating this feature): every existing scenario's projection output is unaffected, byte-for-byte identical to this feature's absence.
- A married-filing-jointly household where the spousal-benefit floor (§6.2b) would otherwise raise a member's benefit above their own withheld/recredited amount: the spousal-benefit floor computation is unaffected by this feature except that it now reads whatever (possibly withheld, possibly recredited) own-benefit amount this feature produces — the earnings test itself is evaluated only against each member's own earned income, never applied to a spousal amount directly (out of scope, §5.3-style documented gap if it matters at all).
- A member's earned income varies year to year (e.g., a phased-retirement wind-down): withholding is recomputed independently each year from that year's earned income; only the cumulative withheld total carried toward the eventual FRA recredit persists across years.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST apply the earnings test only to a household member's own Social Security benefit, using only that member's own `earned_income`-type stream amounts for that year (never household-combined, never pension/annuity amounts) — mirroring this codebase's existing per-member SS benefit shape.
- **FR-002**: System MUST apply the earnings test only for years where that member has already claimed (age ≥ their configured claiming age) and has not yet reached their own full retirement age; a member at or past FRA is never subject to withholding, regardless of earned income.
- **FR-003**: For a year fully before the member's FRA-attainment year, System MUST withhold $1 of benefit for every $2 of that member's earned income above the year's (documented, citable) exempt-earnings threshold.
- **FR-004**: For the specific year a member reaches FRA, System MUST instead apply that year's higher, documented exempt-earnings threshold and withhold $1 of benefit for every $3 of earned income above it (a distinct, more lenient rule from FR-003).
- **FR-005**: Withholding for a given year MUST never reduce that member's benefit below $0, and MUST never affect any other household member's benefit or income.
- **FR-006**: System MUST track, per member, the cumulative amount of benefit withheld under FR-003/FR-004 across every year it occurs before that member reaches FRA.
- **FR-007**: Once a member reaches FRA, System MUST permanently recalculate that member's benefit upward from that year forward to recredit the cumulative amount withheld (FR-006) — consistent with SSA's rule of recalculating as if the member had claimed that many months later than they actually did — rather than treating withheld amounts as a permanent loss.
- **FR-008**: A member with no `earned_income` stream configured, or whose earned income never exceeds the applicable exempt threshold in any pre-FRA claimed year, MUST see no change in benefit from this feature at any point in the projection — output identical to this feature's absence.
- **FR-009**: The annual exempt-earnings thresholds and withholding ratios (FR-003/FR-004) MUST be documented, citable SSA figures, consistent with every other tax/benefit figure already in this tool.
- **FR-010**: docs/BRD.md's existing §5.3/§6.2a language describing this as an unmodeled gap MUST be updated to reflect what is now actually modeled (including any documented simplification from this engine's whole-plan-year granularity), leaving no orphaned claim that contradicts the implemented behavior.

### Key Entities

- **Earnings Test Result**: One member's one-year earnings-test computation — the exempt threshold and ratio applied (FR-003 vs. FR-004), the amount withheld, and the resulting benefit for that year. Derived from that member's already-computed claiming-age-adjusted benefit (existing `compute_social_security_benefit()`) and that year's own `earned_income`-type stream total (existing `_member_earned_income_amounts()`).
- **Cumulative Withholding State**: Per-member running total of benefit-months' worth withheld, carried across projection years until that member reaches FRA, at which point it is consumed to compute the permanent recredit (FR-007) and is no longer needed thereafter — mirrors this codebase's existing precedent for other running, cross-year per-member state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a household matching a published SSA worked example (a member claiming before FRA with earned income above the applicable exempt threshold), the computed withheld amount and resulting benefit exactly match SSA's own hand-calculated result.
- **SC-002**: A household whose member is withheld in one or more pre-FRA years shows a permanently higher post-FRA benefit than that member's original claiming-age-adjusted amount, by an amount consistent with the cumulative months withheld — verified against SSA's own description of the recredit recalculation.
- **SC-003**: Every existing scenario with no `earned_income` overlap during any pre-FRA claimed year (including every scenario predating this feature) produces projection output identical to its pre-feature result.
- **SC-004**: docs/BRD.md's Social Security gap language and figure-verification material are internally consistent with the implemented behavior — no reviewer reading both the code and the docs finds a contradiction.

## Assumptions

- This engine has no mid-year/calendar-month granularity (ages and claiming are whole plan years). The FRA-attainment year's real-world rule — counting only earnings in months before the birth month FRA is reached — is applied instead to that entire plan year's earned income against the FRA-year threshold/ratio, a documented whole-year simplification consistent with this module's existing "months early/delayed ... not a real calendar-month count" precedent (`mechanics/social_security_benefit.py`).
- The annual exempt-earnings thresholds are, in reality, wage-indexed and change every year; consistent with this codebase's existing convention for such figures (e.g. `tax/fica.py`'s `OASDI_WAGE_BASE`), they are pinned to their current published (2026) values and held flat across every documented year, disclosed as such in the figure's citation.
- The earnings test applies only to a member's own worker benefit. Spousal-benefit-floor amounts (§6.2b) are unaffected except through whatever (possibly withheld, possibly recredited) own-benefit amount this feature now produces; the earnings test is not applied a second time directly against a spousal amount. This mirrors the issue's own explicit scope boundary.
- No month-level claim-date modeling is introduced; the FRA-attainment-year rule (User Story 3) is approximated at whole-plan-year granularity per the assumption above.
- The recredit (FR-007) is computed from the cumulative dollar amount withheld, converted to whole benefit-months at that member's own monthly benefit rate, consistent with SSA's published description of the recalculation — not a dollar-for-dollar refund and not a real-time monthly reconciliation this engine has no mechanism to model.
