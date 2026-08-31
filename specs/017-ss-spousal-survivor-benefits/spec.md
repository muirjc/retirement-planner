# Feature Specification: Social Security Spousal and Survivor Benefits

**Feature Branch**: `017-ss-spousal-survivor-benefits`

**Created**: 2026-08-31

**Status**: Draft

**Input**: User description: "Social Security spousal and survivor benefits (rp-52n). Currently each HouseholdMember's Social Security benefit is modeled entirely independently (mechanics/social_security_benefit.py, extended by 016-ss-claiming-age-actuarial-adjustment) -- there is no spousal benefit (a lower/non-earning spouse can receive up to 50% of the higher earner's PIA at the spouse's own FRA, reduced for early claiming) and no survivor benefit (when one spouse dies, the survivor receives the higher of the two benefits; the lower one simply stops). For a married-filing-jointly household -- this project's own reference use case -- this is one of the largest income-preservation issues in retirement, and it is currently silently absent rather than documented as a disclosed simplification (BRD gap, found during a CFP-perspective review). Scope: add the SS spousal-benefit-floor and survivor-benefit calculation primitives, and extend the Household/HouseholdMember data model with whatever marital-status/mortality-event representation these calculations need, citing the governing SSA rules. Out of scope: wiring a mid-horizon spouse's death into the deterministic/Monte Carlo projection loop's filing-status/spending/income logic -- tracked separately as rp-g8y, a dependent follow-on feature that will consume whatever timeline/data model this feature produces. Update docs/BRD.md following this project's existing SourcedFigure/FigureUsage/verified conventions."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A lower-earning spouse's benefit is never less than the spousal floor (Priority: P1)

In a married-filing-jointly household where one spouse's own Primary Insurance Amount (PIA) is low relative to the other's, that spouse's Social Security income reflects the real SSA spousal-benefit rule: their claimed benefit is the greater of (a) their own claiming-age-adjusted benefit, or (b) a spousal amount derived from up to 50% of the higher-earning spouse's PIA, itself adjusted for the lower earner's own claiming age using the SSA's spousal-specific early-claiming reduction (no delayed-retirement credit applies to the spousal portion — SSA never pays a spousal benefit above 50% of the higher earner's PIA, regardless of how late the lower earner claims). This applies to every projection today — it requires nothing about either spouse's future mortality, only that both spouses are alive and the household is filing jointly.

**Why this priority**: This is the single largest, most common Social Security income gap this tool currently mis-states for its own reference use case (MFJ two-earner, often with one spouse earning meaningfully less). It requires no new mortality/timeline concept at all, so it delivers real value standalone and immediately, ahead of anything survivor-related.

**Independent Test**: Configure an MFJ household where one member's PIA is well under 50% of the other's, run a plain projection, and confirm the lower-earning member's Social Security income reflects the spousal-floor amount rather than their own (smaller) PIA-derived benefit.

**Acceptance Scenarios**:

1. **Given** a household with a higher earner (PIA $30,000) and a lower earner (PIA $6,000) both claiming at their own FRA, **When** a projection computes the lower earner's benefit, **Then** it equals $15,000 (50% of $30,000), not $6,000.
2. **Given** the same household, **When** the higher earner's PIA-derived, claiming-age-adjusted benefit already exceeds 50% of the other spouse's PIA for a member who is actually the higher earner, **Then** that member's own benefit is used unchanged — the spousal floor never reduces a benefit, only raises one that would otherwise fall below it.
3. **Given** a lower earner who claims 24 months before their own FRA, **When** their spousal-derived amount is computed, **Then** it is reduced using the SSA's spousal early-claiming reduction rate (not the worker's-own-benefit rate 016 already models), and the delayed-retirement credit never applies to the spousal portion even if the lower earner claims after their own FRA.
4. **Given** a `"single"` household (no second member), **When** any projection runs, **Then** no spousal-floor logic is consulted at all — this feature changes nothing for a single filer.

---

### User Story 2 - Survivor benefit calculation is available and correct (Priority: P2)

Given both spouses' claiming-age-adjusted benefits, a survivor-benefit calculation returns the amount the surviving spouse actually receives going forward: the higher of the two spouses' own benefit amounts, continuing unreduced; the lower one stops entirely. The calculation itself only needs both amounts — a caller already knows, from the scenario's own recorded facts, which spouse is the survivor, and applies the returned amount to that spouse's row. The household data model gains a place to record a spouse's (hypothetical, for-planning-purposes) death — the fact the projection engine will need, in a later feature (rp-g8y), to know when in a multi-year horizon this switch should take effect. This feature delivers the correct calculation and the data model to describe the event; it does not itself make a running projection change behavior mid-horizon when that recorded death year is reached — see Assumptions.

**Why this priority**: This is the calculation half of the widow(er)'s-benefit problem — real, citable, and independently verifiable — but its value is only fully realized once a projection actually consumes it (rp-g8y). P2 because User Story 1 alone already fixes the larger, always-applicable gap.

**Independent Test**: Given two members' independently-computed annual benefits (one larger, one smaller), call the survivor-benefit calculation and confirm it returns exactly the larger benefit — regardless of which of the two members the caller knows to be deceased, since the calculation is symmetric in its two inputs — with the smaller one no longer part of the total.

**Acceptance Scenarios**:

1. **Given** member A's own benefit of $30,000/year and member B's own benefit of $12,000/year, **When** member B is recorded as deceased, **Then** the household's ongoing Social Security income is $30,000/year (A's benefit, unchanged) — not $42,000 (both) and not $12,000 (B's alone).
2. **Given** the same two members, **When** member A (the higher benefit) is instead the one recorded as deceased, **Then** the surviving member B's benefit is raised to $30,000/year (A's higher amount), not left at B's own $12,000.
3. **Given** a household member, **When** a scenario records that member's hypothetical death (an optional field), **Then** every existing scenario that omits this field behaves exactly as it does today — this is a strictly additive, opt-in data-model change (mirrors 016's FRA-defaulting precedent).

---

### User Story 3 - The new rules are documented and auditable like every other regulated figure (Priority: P3)

A reviewer of this tool can find, next to the code implementing the spousal and survivor benefit rules, the governing statute/regulation citations and a last-verified date — consistent with every other regulated figure this tool already documents (tax brackets, NIIT, IRMAA, RMD tables, the 016 claiming-age adjustment). `docs/BRD.md`'s Social Security section and its list of known limitations are updated so it no longer implies (by omission) that spousal and survivor benefits are unmodeled, while still honestly describing what remains genuinely out of scope (the family maximum benefit, and the mid-horizon projection wiring tracked separately as rp-g8y).

**Why this priority**: Same "accuracy over cleverness / auditability" principle 016's own User Story 3 established for claiming-age adjustment, applied here. Doesn't block User Stories 1–2 functioning correctly, hence P3.

**Independent Test**: Locate the module(s) implementing spousal/survivor benefit math and confirm each carries a citation and last-verified date in this project's existing `SourcedFigure` convention; confirm `docs/BRD.md` describes the new behavior and its remaining limitations.

**Acceptance Scenarios**:

1. **Given** the implemented spousal and survivor benefit calculations, **When** a reviewer inspects them, **Then** each cites the specific statute/regulation establishing it and records a last-verified date, in the same structural pattern as this tool's other cited figures.
2. **Given** the completed feature, **When** a reader reviews `docs/BRD.md`'s Social Security section, **Then** it describes the spousal floor and survivor benefit as modeled behavior, and separately, honestly lists what is still not modeled (family maximum benefit; mid-horizon death not yet changing a running projection, tracked as rp-g8y).

---

### Edge Cases

- Both spouses have identical PIAs and claim at the same age: the spousal floor computation must not apply to either (each spouse's "other spouse's PIA × 50%" equals their own PIA, so their own benefit already meets the floor) — no double-counting, no negative adjustment.
- A lower earner whose own claiming-age-adjusted benefit already exceeds 50% of the higher earner's PIA (e.g., the "lower" earner delayed claiming to 70 while the higher earner claimed at 62): the spousal floor must not kick in just because one PIA is nominally larger — it compares actual computed benefits, not just PIAs, where the two diverge.
- A "higher earner" determination made once from PIA order, versus a claiming-age-adjusted-benefit order that could differ once actuarial adjustments are applied: this feature defines "the other spouse's PIA" for the 50%-of-PIA calculation using raw PIA, per the actual SSA rule (the spousal amount is always defined off the other spouse's PIA, not their adjusted benefit) — see Assumptions.
- A household member's hypothetical death age recorded outside a plausible human range (roughly age 50-110, a plausible span for an adult household member) is flagged as an implausible-input warning, mirroring how FRA plausibility is already flagged (016 FR-009), not silently accepted.
- A `"single"`-filing-status household: has exactly one member by existing validation (FR-013 in `001`); spousal/survivor logic is structurally inapplicable and must never be invoked.
- A member who has not yet claimed (translated age below their own claiming age): contributes $0 today, unaffected by this feature; the spousal floor and survivor benefit both operate on *claimed* benefit amounts, never an unclaimed member's hypothetical PIA.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For a married-filing-jointly household, the system MUST compute, for each member who has claimed, a spousal-floor amount derived from up to 50% of the other member's PIA, adjusted for the claiming member's own claiming age using the SSA's spousal-specific early-claiming reduction rate — distinct from the worker's-own-benefit reduction rate 016 already models — with no delayed-retirement credit applied to the spousal portion under any circumstance.
- **FR-002**: The system MUST use, as each claimed member's actual Social Security income, the greater of that member's own claiming-age-adjusted benefit (016) or their spousal-floor amount (FR-001) — never the sum of the two, and never a value below either individually.
- **FR-003**: The spousal-floor calculation MUST be based on the other member's raw PIA (not that other member's own claiming-age-adjusted benefit), matching the actual SSA rule that the spousal amount is defined off the higher earner's PIA regardless of when the higher earner themselves claims.
- **FR-004**: For a `"single"`-filing-status household, the system MUST NOT invoke any spousal-floor logic (there is no second member to derive one from).
- **FR-005**: The system MUST provide a survivor-benefit calculation that, given two members' own currently-claimed benefit amounts, returns the higher of the two amounts as the survivor's ongoing benefit — the lower one contributes $0 from that point. The calculation is symmetric in its two inputs; a caller determines which member is the survivor from the scenario's own recorded facts and applies the result there, rather than passing "which member died" into the calculation itself.
- **FR-006**: `HouseholdMember` MUST gain an optional field recording that member's hypothetical death (for planning purposes — this is a "what if" input, not a record of a past, certain event, unlike `012`'s `InheritedIraDetails.death_year`). When omitted, every existing scenario MUST behave exactly as it does today (strictly additive, opt-in — mirrors `010`'s `hdhp_coverage`/`hsa_contribution` precedent of an optional field defaulting to a no-op value, and 016's `full_retirement_age` precedent of never changing an existing scenario's output uninvited).
- **FR-007**: This feature MUST NOT itself change a running deterministic or Monte Carlo projection's filing status, spending need, or per-year income when a recorded hypothetical death year is reached mid-horizon — that wiring is explicitly out of scope here, tracked separately as `rp-g8y`, which will consume the data model and calculations this feature produces.
- **FR-008**: The system MUST NOT model the Social Security family maximum benefit (the aggregate cap on total benefits payable on one worker's record) — explicitly out of scope, documented as a disclosed simplification rather than silently omitted.
- **FR-009**: The spousal-specific early-claiming reduction rate and the survivor-benefit "higher of the two, lower stops" rule MUST each be implemented as a cited, dated figure in this project's existing `SourcedFigure` convention (a named figure with a citation to the specific statute/regulation and a last-verified date), the same structural pattern `016`'s claiming-age adjustment and every other regulated figure in this tool already use.
- **FR-010**: `docs/BRD.md`'s Social Security section and its list of known limitations MUST be updated to describe the spousal floor and survivor-benefit calculation as modeled behavior, while still honestly listing the family maximum benefit (FR-008) and the not-yet-wired mid-horizon projection effect (FR-007, tracked as `rp-g8y`) as remaining, disclosed gaps.

### Key Entities

- **Household Member (marital/mortality facts)**: Gains an optional hypothetical-death field, used only by the calculations this feature adds and by the future projection-wiring feature (`rp-g8y`) — never consulted by any existing computation path, so every scenario that omits it is unaffected.
- **Spousal Benefit Adjustment Figure**: A new cited, dated figure (in the same family as this project's existing tax/benefit-adjustment citations) describing the SSA spousal early-claiming reduction rate and the statute/regulation that fixes it, and the rule that no delayed-retirement credit applies to a spousal amount.
- **Survivor Benefit Rule**: A new cited, dated figure describing the "higher of the two continues, the lower stops" rule and the statute/regulation that establishes it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In an MFJ household where one spouse's PIA is less than 50% of the other's, that spouse's computed Social Security benefit in every projection equals the spousal-floor amount, not their own smaller PIA-derived benefit — within a small rounding tolerance, in 100% of such configurations.
- **SC-002**: In an MFJ household where both spouses' own claiming-age-adjusted benefits already meet or exceed their respective spousal-floor amounts, computed output is unchanged from before this feature (no regression to households the spousal floor doesn't affect).
- **SC-003**: Given any two benefit amounts and a designated deceased member, the survivor-benefit calculation returns exactly the higher of the two amounts, with zero deviation, in every case including a tie.
- **SC-004**: Every existing automated test suite that exercised Social Security benefit amounts before this change continues to pass unmodified — confirmed during planning that no existing fixture's PIA pair is close enough to the spousal floor's threshold to change any expected value — with no reproducibility regression (identical scenario + seed still yields identical output, including through Monte Carlo simulation).
- **SC-005**: `docs/BRD.md` no longer lists "no spousal or survivor Social Security benefits" as an implicit, undocumented gap; a reader can find both the modeled spousal floor and the survivor-benefit calculation described in the Social Security section alongside their citations and the explicitly remaining gaps (family maximum benefit; mid-horizon projection wiring).

## Assumptions

- The spousal floor is computed and applied in every plain and comparison projection immediately by this feature (User Story 1) — it requires no mortality/timeline concept, only that both members are alive and the household is MFJ, which is already true of every such household this tool models today. This is the one piece of this feature's scope that changes live projection output, and it is a strictly-more-accurate correction (SC-002 guards against regressing households it shouldn't affect).
- The survivor-benefit calculation (User Story 2) is a pure function of the two members' own benefit amounts alone — it does not take a "which member died" input, since the result (the higher of the two) is the same number either way; a future caller attributes that number to whichever member is actually the survivor. It also does not, by itself, require or consume the new hypothetical-death data-model field at runtime; that field exists so a scenario can *state* the fact `rp-g8y`'s future projection wiring will need, without yet acting on it. This mirrors how `012-inherited-ira-rmd`'s `InheritedIraDetails` first modeled decedent facts before `013` layered further behavior on top.
- "Higher earner" and "lower earner" are relative terms determined by raw PIA comparison, per FR-003 — this is what the real SSA spousal-amount rule keys off, not the two members' claiming-age-adjusted benefits (which could rank differently once claiming ages diverge).
- The exact SSA spousal early-claiming reduction rate(s) (distinct from 016's own-benefit rate) and any fine-grained rules this research surfaces (e.g., the "deemed filing" rule requiring simultaneous application/claiming in most cases since 2015) are confirmed against a primary source (20 C.F.R. Subpart D, 42 U.S.C. §402(b)/(k)) during planning/implementation, following this project's existing verification discipline (`014-figure-verification`'s methodology) — this spec fixes the *behavior* required, not the exact numeric rate, matching how `016`'s own spec deferred exact CFR sub-citations to implementation-time verification.
- The Social Security family maximum benefit (FR-008) is out of scope — this tool models households of at most two members (a single filer or an MFJ couple), the case where the family maximum least often binds in practice (it primarily affects families with multiple dependents claiming on one worker's record), so omitting it is a reasonable, disclosed simplification rather than a load-bearing gap for this tool's reference use case.
- Deemed filing (the rule that claiming a retirement benefit and a spousal benefit are treated as one combined application in most post-2015 cases, rather than a genuine free choice between the two) is not separately modeled as a user-facing choice — FR-002's "greater of" framing already produces the correct paid amount in the common case this tool targets, without needing to model the filing mechanics themselves as a distinct concept.
- This feature does not change `run_plan_projection()`'s per-year loop, `Household`/`HouseholdMember` validation rules beyond the new optional field, or any BFF/UI surface beyond what's needed to accept the new optional field — those integration points belong to `rp-g8y`.
