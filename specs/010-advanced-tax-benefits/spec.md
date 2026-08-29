# Feature Specification: Advanced Tax & Benefits Modeling (IRMAA, NIIT, HSA)

**Feature Branch**: `010-advanced-tax-benefits`

**Created**: 2026-08-28

**Status**: Draft

**Input**: User description: "docs/remaining_scope.md, combined IRMAA + NIIT + HSA modeling"

**Scope note**: `docs/initial_requirement.md` §3.2 (Tax Engine) names IRMAA and NIIT modeling as required and explicitly deferred by `002-tax-calculation-engine`'s own Assumptions ("out of scope for this feature... will be specified as a separate feature"); §3.3 (Retirement Account Mechanics) names HSA contribution/eligibility timing, deferred the same way by `003-retirement-account-mechanics`. `005-simulation-engine` reconfirms all three remain deferred. This feature closes that gap, extending the tax and account-mechanics engines those three earlier features already built — it does not replace or restructure anything `001`–`009` deliver. It does not model Medicare plan selection, Medigap policy choice, or any non-financial healthcare factor — those remain the working document's job, per the source document's own §9 boundary, already respected by every prior feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the Medicare premium surcharge a strategy triggers, before choosing it (Priority: P1)

A user comparing Roth conversion strategies (or any other choice that changes a household's taxable income) can see when a candidate pushes income across a Medicare premium surcharge (IRMAA) threshold, and by how much that raises the household's costs — not just the income tax difference the tool already shows.

**Why this priority**: IRMAA is a cliff, not a slope — crossing a threshold by even a small amount raises Medicare Part B and Part D premiums for both spouses for a full year. A Roth conversion strategy that looks like the clear winner on tax paid alone could be the worse choice once this surcharge is counted, and today the tool cannot show that difference at all. This is the single largest currently-invisible cost the tool's own reference use case (a Roth conversion bridge, per `docs/initial_requirement.md` §2) is exposed to.

**Independent Test**: Can be fully tested by running two otherwise-identical scenarios that differ only in how much taxable income they generate in a plan year, one on each side of a known threshold, and confirming the tool reports a materially different total cost for the one that crosses it — independent of NIIT or HSA modeling.

**Acceptance Scenarios**:

1. **Given** a household whose income for a plan year is below every Medicare premium surcharge threshold, **When** the tool computes that year's costs, **Then** no surcharge is added and the reported cost matches what the tool already produces today.
2. **Given** a household whose income for a plan year crosses one Medicare premium surcharge threshold, **When** the tool computes that year's costs, **Then** the resulting surcharge is included as an additional, separately identifiable cost, distinct from ordinary income tax.
3. **Given** a household with two Medicare-enrolled members, **When** a surcharge applies, **Then** the cost reflects that each enrolled member's premium is affected, not a single shared figure.
4. **Given** a household with no member old enough for Medicare enrollment in a given plan year, **When** the tool computes that year's costs, **Then** no surcharge is considered for that year regardless of income.

---

### User Story 2 - See the investment-income surtax a strategy triggers (Priority: P2)

A user comparing strategies that affect taxable-account investment income and Roth conversion income together can see when the combination crosses the Net Investment Income Tax (NIIT) threshold, and how much that adds to the household's tax cost.

**Why this priority**: The source document names this directly as relevant to "taxable account balance and Roth conversion income stacking" — a household drawing from a large taxable account while also running Roth conversions is exactly the case where this 3.8% surcharge becomes material, and it currently isn't reflected in any comparison the tool produces. It's a smaller, more contained addition than IRMAA (a flat-rate surtax above a threshold, not a tiered cliff), so it follows IRMAA in priority.

**Independent Test**: Can be fully tested by running a scenario with a taxable account's investment income above and below the known threshold and confirming the surtax appears only when the threshold is crossed, independent of IRMAA or HSA modeling.

**Acceptance Scenarios**:

1. **Given** a household whose investment income for a plan year is below the NIIT threshold, **When** the tool computes that year's tax, **Then** no surtax is added.
2. **Given** a household whose investment income for a plan year exceeds the NIIT threshold, **When** the tool computes that year's tax, **Then** the surtax is applied only to the portion of income the surtax rules actually cover (investment income), not to the household's full income, and is reported as a separately identifiable amount.
3. **Given** a household whose Roth conversion pushes ordinary income higher without changing investment income, **When** the tool computes that year's tax, **Then** the conversion amount itself does not directly incur the surtax, but is correctly counted toward whichever income figure determines if the threshold is crossed.

---

### User Story 3 - Model HSA contribution eligibility as a real constraint, not manual tracking (Priority: P3)

A user planning around a Health Savings Account can see the tool reflect when each household member is actually eligible to contribute, including the effect of enrolling in Medicare, so a scenario can't accidentally assume a contribution that wouldn't really be allowed.

**Why this priority**: The source document specifically motivates this with two documented traps this tool can't currently catch: the 6-month retroactive Medicare Part A enrollment rule (which can retroactively end HSA eligibility earlier than a household expects), and the fact that a younger, not-yet-Medicare-eligible spouse keeps their own HSA eligibility independent of the older spouse. Unlike IRMAA/NIIT, this doesn't change a dollar outcome directly — it changes what a scenario is even allowed to model, so it's valuable on its own but doesn't block the higher-priority surcharge visibility above.

**Independent Test**: Can be fully tested by constructing a household where one member enrolls in Medicare mid-scenario and confirming HSA contribution eligibility for that member ends at the correct point, while an eligible younger spouse's contributions continue unaffected — independent of IRMAA/NIIT modeling.

**Acceptance Scenarios**:

1. **Given** a household member not yet enrolled in Medicare and otherwise HSA-eligible, **When** the tool models a plan year before their enrollment, **Then** their HSA contribution is allowed for that year.
2. **Given** a household member who enrolls in Medicare, **When** the tool models plan years from and after enrollment, **Then** their HSA contribution eligibility ends, including any retroactive effect from claiming Social Security at or after age 65 that backdates Medicare Part A enrollment.
3. **Given** a household with one Medicare-enrolled member and one younger, not-yet-enrolled member who is otherwise HSA-eligible, **When** the tool models a plan year, **Then** the younger member's contribution eligibility is unaffected by the older member's enrollment.
4. **Given** an HSA contribution the tool models as made in an eligible plan year, **When** the tool computes that year's taxable income, **Then** the contribution reduces taxable ordinary income for that year, consistent with how the tool already treats other income-reducing account activity.

---

### Edge Cases

- What happens when a household's income for a plan year lands exactly on an IRMAA threshold boundary? The tool must apply a documented, consistent rule (at-or-above vs. strictly-above) rather than an ambiguous result.
- What happens in the first plan years of a scenario, before the tool has modeled the two years of income history IRMAA determinations are actually based on? The tool must use a documented, explicitly flagged approach for those early years rather than silently omitting the surcharge or fabricating history.
- What happens when a household member enrolls in Medicare partway through a plan year rather than at a year boundary? The tool must reflect eligibility changes at the resolution the tool already models plan years at, with the transition handled consistently.
- What happens when neither household member is ever Medicare-eligible within the modeled planning horizon? IRMAA must never be considered for that scenario.
- What happens when a household has no taxable account investment income at all? NIIT must never apply regardless of other income.
- What happens when a household member is not covered by a qualifying high-deductible health plan at all? No HSA eligibility should ever be modeled for them, independent of age or Medicare status.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST determine, for each modeled plan year, whether a household's income crosses a Medicare premium surcharge (IRMAA) threshold, using the income figure and look-back timing that actual Medicare premium determinations are based on.
- **FR-002**: When a threshold is crossed, the system MUST include the resulting premium surcharge as a household cost for that plan year, reported separately from ordinary income tax owed.
- **FR-003**: The system MUST reflect the surcharge's effect for each Medicare-enrolled household member individually, not as a single household-wide figure that ignores how many members are actually enrolled and affected.
- **FR-004**: The system MUST NOT apply an IRMAA surcharge for any plan year in which no household member has reached Medicare enrollment.
- **FR-005**: The system MUST determine, for each modeled plan year, whether a household's investment income exceeds the Net Investment Income Tax (NIIT) threshold for the household's filing status.
- **FR-006**: When the NIIT threshold is exceeded, the system MUST apply the surtax only to the portion of income the surtax rules cover, and report the resulting amount separately from ordinary income tax owed.
- **FR-007**: The system MUST correctly distinguish, for NIIT purposes, income that counts as investment income from ordinary income (including Roth conversion income), so that conversion income affects only whether the threshold is crossed and never becomes itself directly subject to the surtax.
- **FR-008**: The system MUST determine, for each household member and modeled plan year, whether that member is eligible to make an HSA contribution, based on their qualifying health plan coverage, age, and Medicare enrollment status.
- **FR-009**: The system MUST reflect that a household member's Medicare Part A enrollment can retroactively end their HSA contribution eligibility, when that member claims Social Security at or after age 65, per the retroactive enrollment rule Medicare applies in that case.
- **FR-010**: The system MUST reflect that a household member's own HSA eligibility is independent of another household member's Medicare enrollment status — a younger, not-yet-enrolled spouse's eligibility MUST be unaffected by the older spouse enrolling.
- **FR-011**: An HSA contribution the system models as made in an eligible plan year MUST reduce that household member's contribution toward the household's taxable ordinary income for that plan year.
- **FR-012**: The system MUST reject an HSA contribution modeled for a household member in a plan year during which that member is not eligible, with a specific reason, rather than silently allowing it.
- **FR-013**: Every IRMAA threshold figure, NIIT threshold figure, and HSA contribution limit the system uses MUST carry the same source citation, last-verified date, and "needs verification" visibility already required of every other externally-sourced figure this tool uses — this feature introduces no exception to that discipline.
- **FR-014**: Because IRMAA thresholds, NIIT thresholds, and HSA contribution limits change over time (inflation-indexed or set by law), the system MUST accept each as a schedule of values by year rather than a single fixed figure, and MUST refuse to compute a plan year outside the years it has a documented figure for, rather than extrapolating.

### Key Entities

- **IRMAA Determination**: For one household member and one plan year, whether that member's Medicare premiums are subject to a surcharge, which threshold tier applies, and the resulting surcharge amount — derived from the household's income at the look-back timing Medicare premium determinations actually use.
- **NIIT Determination**: For one household and one plan year, whether investment income exceeds the applicable threshold, and the resulting surtax amount, computed only against the investment-income portion of the household's total income.
- **HSA Eligibility Window**: For one household member, the plan-year range during which they are eligible to contribute to an HSA, bounded by their qualifying health plan coverage, their age, and their own (not their spouse's) Medicare enrollment timing — including any retroactive effect from claiming Social Security at or after age 65.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Comparing two otherwise-identical strategies that differ only in whether one crosses an IRMAA threshold shows a different, correctly larger, total household cost for the one that crosses it, in every scenario where a crossing occurs.
- **SC-002**: A household whose investment income crosses the NIIT threshold shows the surtax reflected in total tax paid for every plan year the threshold is crossed, and shows none in every plan year it is not.
- **SC-003**: A scenario with a younger, not-yet-Medicare-eligible spouse can show that spouse's HSA contribution eligibility continuing unaffected after the older spouse enrolls in Medicare, in 100% of scenarios structured that way.
- **SC-004**: Every IRMAA, NIIT, and HSA figure this feature introduces is visibly flagged as verified or needing verification in the tool's output, with no figure from this feature exempt from that visibility.

## Assumptions

- This feature computes the financial effects of IRMAA, NIIT, and HSA eligibility; it does not model Medicare plan selection, HSA custodian/investment choices, or any qualitative healthcare factor — those remain the working document's responsibility, per the source document's existing §9 boundary.
- IRMAA and NIIT threshold figures and HSA contribution limits are treated the same way this tool already treats every other year-dependent tax figure (`002-tax-calculation-engine`'s existing schedule-by-year, refuse-rather-than-extrapolate discipline) — no new precedent is introduced.
- For plan years early in a scenario where the two years of income history an IRMAA determination is actually based on aren't available within the scenario's own modeled history, the feature uses a documented, explicitly flagged approximation rather than silently omitting the surcharge; the exact approximation is a planning-phase decision, not fixed here.
- Standard Medicare enrollment age (65) is assumed as the eligibility trigger for this feature's v1; early enrollment due to disability is out of scope.
- This feature extends the existing tax and account-mechanics engines (`002`, `003`) and whatever downstream comparison/simulation and reporting features already consume their output (`004`–`009`); it does not change how a user interacts with the scenario entry form beyond whatever new inputs these mechanics require — the exact form changes belong to the planning phase, not this specification.
