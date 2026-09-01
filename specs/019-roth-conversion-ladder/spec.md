# Feature Specification: Roth Conversion Ladder (Five-Year Rule) Tracking

**Feature Branch**: `019-roth-conversion-ladder`

**Created**: 2026-09-01

**Status**: Draft

**Input**: User description: "Roth conversion five-year rule / conversion-ladder tracking (rp-886). Roth conversion mechanics currently execute a conversion each plan year and add the converted amount straight into the household's single pooled Roth balance -- there is no tracking of when each conversion happened, so nothing distinguishes a converted dollar that has satisfied its own individual 5-year seasoning clock (the 'conversion ladder' rule) from one that hasn't. Withdrawal sequencing draws from the pooled Roth balance with no awareness of this at all, so a projection can silently draw against unseasoned converted principal before age 59.5 without the 10% early-withdrawal penalty exposure that would create in reality -- exactly the scenario a Roth conversion ladder strategy exists to manage (the tool's own BRD reference use case names a defined conversion bridge window for an early-retiree household, the classic case where this matters).

Scope decisions already made during specification: (1) Age-59.5 check uses a conservative household-level simplification (the engine pools Roth at the household level, with no per-member ownership) -- for a married-filing-jointly household, the check only matters in a plan year while at least one member hasn't yet reached age 59.5; once every household member has cleared it, no further flagging occurs. (2) This feature flags a plan year where a withdrawal touches unseasoned converted principal while that age condition applies -- it does not compute or apply an actual 10% penalty dollar amount, which remains separate, disclosed scope for a related but distinct open feature (rp-8z0, early-withdrawal penalty / 72(t)-SEPP modeling).

Design approach: each Roth conversion actually executed during a projection becomes a tracked 'conversion lot' (the converted amount and the tax year it happened), threaded through the per-year projection loop the same way the tool already threads a parallel, independently-tracked list of inherited accounts alongside the household's pooled balances. The household's pre-existing Roth balance as of the scenario's start is treated as already-seasoned/fully accessible by default -- a documented simplification, since the tool's scenario input has no way today to know that starting balance's own composition or age. A conversion lot is seasoned once 5 full tax years have elapsed since its own conversion tax year. When a plan year's withdrawal needs to draw past the already-seasoned/pre-existing balance into one or more not-yet-seasoned conversion lots (drawn oldest-lot-first, matching real IRS Roth distribution ordering) while the age condition applies, the amount actually sourced from an unseasoned lot is flagged on that plan year's output rather than silently allowed.

Out of scope: computing or applying the actual 10% early-withdrawal penalty dollar amount (tracked separately as rp-8z0); per-member/per-owner Roth ownership attribution; tracking Roth contribution basis vs. earnings within the pre-existing starting balance; modeling the separate account-level 5-year rule governing whether Roth earnings are a 'qualified distribution.' docs/BRD.md must be updated to describe the modeled behavior and these disclosed remaining gaps."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A projection flags an unseasoned Roth conversion withdrawal (Priority: P1)

A household running a Roth conversion ladder strategy — converting Traditional dollars to Roth in years before retirement income needs kick in, intending to later withdraw the converted principal penalty-free once each conversion clears its own 5-year clock — gets a projection that actually tracks each conversion's own seasoning. If a later plan year's withdrawal need is large enough that it must draw into a conversion that hasn't yet cleared 5 years, and at least one household member hasn't yet reached age 59.5 that year, the projection's output for that year shows this rather than silently treating the money as freely available.

**Why this priority**: This is the entire point of the feature — without it, a Roth conversion ladder strategy this tool's own reference use case names as a goal cannot be distinguished, in this tool's output, from one that quietly breaks IRS ordering rules and would trigger a real penalty.

**Independent Test**: Configure a household with a multi-year Roth conversion window ending several years before any member turns 59.5, followed by a withdrawal need large enough to require drawing more from Roth than the already-seasoned/pre-existing balance covers, and confirm the plan year where that draw reaches into an unseasoned conversion is flagged, naming the amount involved.

**Acceptance Scenarios**:

1. **Given** a household with no pre-existing Roth balance and one Roth conversion executed in tax year Y, **When** a later plan year's withdrawal draws from Roth in tax year Y+3 (before the conversion's 5-year clock closes) while at least one household member is under 59.5, **Then** that plan year's output flags the amount of that draw sourced from the still-unseasoned conversion.
2. **Given** the same household, **When** a plan year's withdrawal from Roth instead occurs in tax year Y+5 or later (the conversion has fully seasoned), **Then** no flag is raised for that draw, regardless of any member's age.
3. **Given** the same household, **When** every household member has reached age 59.5 or older by the plan year of an unseasoned-conversion draw, **Then** no flag is raised for that draw — the rule's own age condition no longer applies to anyone in the household.
4. **Given** a household with a pre-existing Roth balance present before the projection's first plan year, **When** a plan year's Roth withdrawal is fully covered by that pre-existing balance without reaching into any tracked conversion lot, **Then** no flag is raised, regardless of any conversion's own seasoning status or any member's age.
5. **Given** a household whose scenario configures no Roth conversion at all, **When** any projection runs, **Then** this feature's tracking and flagging logic has nothing to track and never raises a flag.

---

### User Story 2 - Multiple conversions season and draw down independently, oldest first (Priority: P2)

A household that converts different amounts across several different years gets each conversion tracked as its own lot with its own 5-year clock — a withdrawal that needs to reach into converted principal draws from the oldest still-tracked lot first, matching the real ordering rule, so a household can see exactly how a partial draw is apportioned across conversions of different ages rather than the tool treating all converted money as one undifferentiated pool once it's no longer covered by the pre-existing balance.

**Why this priority**: A conversion ladder is inherently a multi-year strategy — a single conversion's seasoning is necessary but not sufficient coverage for a tool meant to actually validate a ladder strategy across its full window. P2 because User Story 1 alone already delivers the core flag for the common single-conversion-year case.

**Independent Test**: Configure a household with Roth conversions executed in two different tax years of different amounts, followed by a withdrawal that only partially reaches into converted principal, and confirm the draw is apportioned to the older conversion lot before the newer one.

**Acceptance Scenarios**:

1. **Given** two conversions of $20,000 (tax year Y) and $15,000 (tax year Y+2), both still unseasoned, **When** a plan year's withdrawal reaches $10,000 past the pre-existing balance into converted principal, **Then** that $10,000 is drawn from the Y conversion's lot (the older one), leaving the Y+2 lot fully intact.
2. **Given** the same two lots, **When** a plan year's withdrawal reaches $25,000 past the pre-existing balance, **Then** the full $20,000 Y lot is exhausted first and the remaining $5,000 is drawn from the Y+2 lot.
3. **Given** the same two lots, **When** the Y lot has since seasoned (5 full tax years have elapsed) but the Y+2 lot has not, and a withdrawal reaches into converted principal while at least one member is under 59.5, **Then** only the portion of that draw sourced from the still-unseasoned Y+2 lot is flagged — a draw that stays within the now-seasoned Y lot's amount is not.

---

### User Story 3 - The rule and its limits are documented and auditable (Priority: P3)

A reviewer of this tool can find, next to the code implementing conversion-lot seasoning tracking, the governing statute citation and a last-verified date — consistent with every other regulated figure this tool already documents. `docs/BRD.md` is updated so it describes the modeled seasoning-flag behavior and honestly lists what remains out of scope: the 10% penalty dollar amount itself, per-member Roth ownership, and the separate account-level earnings qualified-distribution rule.

**Why this priority**: Same auditability principle every other feature's documentation User Story already established for this project. Doesn't block User Stories 1-2 functioning correctly, hence P3.

**Independent Test**: Locate the module implementing conversion-lot seasoning tracking and confirm it carries a citation and last-verified date; read `docs/BRD.md` and confirm it describes the new behavior and its remaining gaps.

**Acceptance Scenarios**:

1. **Given** the implemented seasoning-tracking logic, **When** a reviewer inspects it, **Then** it cites the specific statute establishing the 5-year conversion-seasoning rule and records a last-verified date, in the same structural pattern as this tool's other cited figures.
2. **Given** the completed feature, **When** a reader reviews `docs/BRD.md`, **Then** it describes conversion-lot seasoning tracking and the unseasoned-withdrawal flag as modeled behavior, and separately lists the disclosed remaining gaps (no penalty dollar amount, no per-member ownership, no earnings-qualified-distribution rule).

---

### Edge Cases

- A withdrawal that exactly exhausts the pre-existing balance with nothing left over, and nothing further needed that plan year: no flag, since no conversion lot was touched at all.
- A withdrawal that draws from Roth in the same plan year a conversion is executed: this projection's own existing sequencing always computes that year's withdrawal before that year's conversion happens, so a same-year conversion can never itself be the source of that same year's draw — the new lot only becomes a possible draw source starting the following plan year.
- A plan year where the withdrawal need is fully met by other account types before RMD/sequencing ever reaches Roth: no lot is touched, no flag, regardless of any lot's own seasoning status.
- A "single"-filing-status household (one member): the age condition still applies — the check is simply that one member's own age, not a household-of-two comparison.
- A conversion lot that is fully drawn down to zero by an earlier plan year's withdrawal: it is skipped entirely (never drawn from again, never flagged again) once exhausted, exactly like an already-depleted inherited account is already skipped elsewhere in this tool.
- Age precision: this tool tracks each household member's age only in whole years per plan year (no mid-year/birth-month precision anywhere in the engine today); the age-59.5 condition is therefore evaluated conservatively — a member whose translated age for a given plan year is 59 or younger is treated as not yet past 59.5 (they might not be, even though some are), and a member translated to age 60 or older is treated as past it. This mirrors the tool's own existing "whole plan-year age, no mid-year date" simplification elsewhere (e.g. Social Security claiming-age adjustment) and the deliberately conservative, over-flag-rather-than-miss bias already adopted for this feature's household-level age check.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST track each Roth conversion actually executed during a projection as its own record (the amount converted and the tax year it happened), independent of the household's pooled Roth balance figure.
- **FR-002**: The system MUST treat the household's pre-existing Roth balance as of a projection's start as already available for withdrawal without regard to seasoning or age — a documented simplification, since the tool has no input describing that starting balance's own composition or age.
- **FR-003**: The system MUST consider a tracked conversion "seasoned" once 5 full tax years have elapsed since its own conversion tax year, independent of any other conversion's seasoning status.
- **FR-004**: When a plan year's withdrawal from the household's pooled Roth balance must draw more than the pre-existing balance (FR-002) plus any already-seasoned conversion amount covers, the system MUST attribute that excess draw to tracked, not-yet-seasoned conversions in order from the oldest conversion tax year to the newest, never drawing from a newer lot while an older one still has a remaining balance.
- **FR-005**: For any plan year in which a household member's translated age is 59 or younger (FR's Edge Cases age-precision rule), the system MUST flag the portion of that year's Roth withdrawal, if any, sourced from a not-yet-seasoned conversion lot (FR-003, FR-004) — naming at least the amount of the flagged draw for that plan year.
- **FR-006**: Once every household member's translated age for a plan year is 60 or older, the system MUST NOT raise this feature's flag for that plan year's Roth withdrawal, regardless of any lot's own seasoning status.
- **FR-007**: The system MUST NOT compute or apply a dollar penalty amount for a flagged draw — this feature's output is a flag, not a cost, consistent with the separate, disclosed scope of a related open feature covering the 10% early-withdrawal penalty itself.
- **FR-008**: A household whose scenario configures no Roth conversion strategy MUST see no tracked lots and no flags raised by this feature, ever — output for such a household MUST be unaffected by this feature (no regression).
- **FR-009**: The 5-year conversion-seasoning rule (FR-003) MUST be implemented as a cited, dated figure in this project's existing regulated-figure convention (a named figure with a citation to the specific statute and a last-verified date), the same structural pattern every other regulated figure in this tool already uses.
- **FR-010**: `docs/BRD.md`'s Roth conversion section and its list of known limitations MUST be updated to describe conversion-lot seasoning tracking and the unseasoned-withdrawal flag as modeled behavior, while honestly listing the disclosed remaining gaps: no penalty dollar amount computed (FR-007), no per-member Roth ownership attribution, no modeling of the separate account-level rule governing whether Roth earnings are a "qualified distribution."

### Key Entities

- **Roth Conversion Lot**: One conversion actually executed during a projection — the amount converted, the tax year it happened, and its own remaining (not-yet-drawn) balance as later withdrawals may partially or fully consume it. Ordered oldest-first for withdrawal purposes; a fully-drawn-down lot no longer participates in future draws or flags.
- **Unseasoned Roth Withdrawal Flag**: A plan year's record that a withdrawal reached into a not-yet-seasoned conversion lot while at least one household member's age condition (FR-005/FR-006) applied — carries at least the flagged dollar amount for that year; carries no dollar penalty of its own (FR-007).
- **Conversion Seasoning Rule**: A new cited, dated figure describing the 5-year-from-conversion seasoning period and the statute that establishes it.

## Assumptions

- The pre-existing Roth balance a household configures at a scenario's start is always treated as fully available (FR-002) — the tool has no data-model concept today for that starting balance's own age or contribution/conversion/earnings composition, and adding one is out of scope here (a materially larger, separately-scoped data-model expansion).
- The age-59.5 condition (FR-005/FR-006) is evaluated at the household level using a conservative simplification: while pooled Roth has no per-member ownership in this engine (unlike Traditional's per-owner RMD attribution), the check applies whenever *any* household member hasn't yet cleared it, and stops applying only once *every* member has. This deliberately over-flags relative to the real per-owner rule (a specific member's own Roth might individually be fine even while a co-member's isn't) rather than risk under-flagging a real violation — documented as a simplification, not silently narrowed to be more "convenient."
- Whole-plan-year age precision (no birth month) means the 59.5 threshold itself can't be evaluated exactly; translated age 59-or-younger is conservatively treated as not-yet-59.5, translated age 60-or-older as past it (Edge Cases) — mirrors this engine's existing claiming-age whole-year-age precedent.
- This feature's flag is a structural marker for a plan year's output, not a computed cost — the actual 10% early-withdrawal penalty dollar amount (and any 72(t)/SEPP alternative) is separate, disclosed scope tracked by a distinct, already-open feature; this feature's flag is positioned so that future feature can consume it without this feature needing to anticipate its exact computation.
- This feature does not track Roth contribution basis separately from the pre-existing starting balance, and does not model the separate account-level 5-year rule governing whether Roth *earnings* (growth) are part of a "qualified distribution" — both are distinct IRS provisions from the per-conversion ladder rule this feature covers, and are out of scope, disclosed in `docs/BRD.md` rather than silently absorbed.
- This feature changes what a plan year's own output can flag; it does not change any dollar amount a projection reports for spending, tax, shortfall, or ending balances — a projection's numeric output for a household is identical with or without this feature's flags present.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a projection where a Roth conversion ladder's own conversion has not yet cleared 5 years and a withdrawal draws into it while at least one household member is under 59.5, that plan year's output flags the draw in 100% of such configurations, within a small rounding tolerance on the flagged amount.
- **SC-002**: In a projection where every tracked conversion has cleared 5 years, or every household member has reached 59.5, no flag is ever raised for a Roth withdrawal, regardless of the amount drawn.
- **SC-003**: Given multiple conversion lots of different ages, a partial draw into converted principal is attributed to the oldest unexhausted lot first, with zero deviation, in every case tested.
- **SC-004**: Every existing automated test suite that exercises Roth conversions or Roth withdrawals before this change continues to pass unmodified for any household that configures no Roth conversion — no regression to households this feature doesn't affect.
- **SC-005**: No projection's reported spending, tax, shortfall, or ending-balance figures differ between two otherwise-identical runs that differ only in whether this feature's flag was raised that year.
- **SC-006**: `docs/BRD.md` no longer omits the Roth conversion 5-year seasoning rule from its description of modeled Roth conversion behavior; a reader can find the modeled flag and its remaining disclosed gaps (penalty dollar amount, per-member ownership, earnings-qualified-distribution rule) in one place.
