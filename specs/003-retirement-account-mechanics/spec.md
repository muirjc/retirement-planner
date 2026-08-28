# Feature Specification: Retirement Account Mechanics

**Feature Branch**: `003-retirement-account-mechanics`

**Created**: 2026-08-27

**Status**: Draft

**Input**: User description: "docs/initial_requirement.md continue with section 3. you can look to the spec 001-scenario-config-management to and 002-tax-calculation-engine to see what has already been done"

**Scope note**: `docs/initial_requirement.md` describes a five-phase retirement planning tool; feature `001-scenario-config-management` covered §3.1 (the input/configuration layer) and feature `002-tax-calculation-engine` covered §3.2 (federal/state tax calculation). This spec covers §3.3 (Retirement Account Mechanics): computing a household member's Required Minimum Distribution (RMD) for a plan year, drawing down accounts in a configured, swappable sequence to meet a year's spending need, and executing a Roth conversion for a plan year under a chosen strategy. It does not cover comparing multiple withdrawal-sequencing or Roth-conversion strategies against each other to find the best one (§3.4, the future "Strategy/Optimization Layer" feature, which will run this feature's mechanics repeatedly under different configurations), running a multi-year Monte Carlo simulation across market draws (§3.5, a separate future feature), computing federal or state tax itself (already delivered by `002-tax-calculation-engine`, which this feature calls as an input), or loading/validating scenario configuration (already delivered by `001-scenario-config-management`, which this feature consumes as an input). HSA contribution/eligibility timing, also listed in the source document's §3.3 table, is explicitly scheduled as Phase 5 work in the source document's phased delivery plan (§8) — separate from the Phase 2/3 account-mechanics work this feature corresponds to — and is deferred to a later feature, matching the precedent `002-tax-calculation-engine` set by deferring IRMAA/NIIT (also listed in its source table) to their own documented Phase 4 feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Compute the legally required minimum distribution for a plan year (Priority: P1)

A user wants to know, for a household member and a specific plan year, the Required Minimum Distribution that must be withdrawn from that member's traditional retirement account — computed using the IRS Uniform Lifetime Table, or the Joint Life and Last Survivor Table when the member's spouse is their sole beneficiary and more than 10 years younger.

**Why this priority**: RMD is a legally mandated floor that every other account mechanic in this feature builds on — withdrawal sequencing (User Story 2) cannot determine what else needs to be drawn until the mandatory RMD amount is known, and a Roth conversion (User Story 3) cannot be computed correctly without knowing the ordinary income the RMD already contributes. The source document flags the current prototype's Uniform-Lifetime-Table-only approach as incomplete for the case where a much-younger spouse is the sole beneficiary; getting the divisor table right is the single highest-value fix in this area because an incorrect RMD both understates required income (risking a real IRS penalty in an eventual live-use setting) and skews every downstream tax and withdrawal calculation.

**Independent Test**: Can be fully tested by feeding a household member's age, prior-year-end traditional account balance, and (where applicable) spouse's age and sole-beneficiary status for a specific plan year, and confirming the computed RMD divisor and resulting dollar amount match IRS Pub. 590-B reference values, for both the Uniform Lifetime Table case and the Joint Life Table case, without needing withdrawal sequencing or Roth conversion to be built yet.

**Acceptance Scenarios**:

1. **Given** a household member at or above the RMD-required starting age with a traditional account balance, **When** RMD is computed for a plan year, **Then** the result uses the IRS Uniform Lifetime Table divisor matched to that member's age in that year.
2. **Given** a married household member whose spouse is their sole beneficiary and more than 10 years younger, **When** RMD is computed, **Then** the result uses the IRS Joint Life and Last Survivor Table divisor for that age pair instead of the Uniform Lifetime Table.
3. **Given** a married household member whose spouse is not their sole beneficiary, or is not more than 10 years younger, **When** RMD is computed, **Then** the result uses the Uniform Lifetime Table, not the Joint Life Table.
4. **Given** a household member below the RMD-required starting age, **When** RMD is computed for that year, **Then** the result is $0.
5. **Given** a household member with no traditional account balance, **When** RMD is computed, **Then** the result is $0 without requiring an age-table lookup to fail or error.

---

### User Story 2 - Draw funds from accounts in a defined, swappable sequence to meet spending need (Priority: P2)

A user wants a plan year's spending need — after mandatory RMD income is counted — met by drawing from the household's remaining accounts (taxable, traditional, Roth) in a defined order, with that order swappable via configuration rather than fixed in code, since the source document notes sequencing order materially affects both tax drag and how long the money lasts.

**Why this priority**: This is the mechanic that actually depletes account balances and produces the income figures the tax engine (`002-tax-calculation-engine`) needs to compute a year's tax. It depends on User Story 1 (the RMD amount is always the first draw in the sequence) but is independently valuable and testable once an RMD figure exists. Building it as a swappable strategy now — even though only one default sequence ships in this feature — avoids the source document's warning against hardcoding a mechanic that a near-term future feature (§3.4) must be able to compare against alternatives.

**Independent Test**: Can be fully tested by feeding a spending need, an already-computed RMD amount, and starting balances across account types for one plan year, and confirming the resulting withdrawal plan draws in the configured order, never draws more than an account's available balance, and moves to the next account in sequence once the current one is exhausted — without needing Roth conversion or multi-strategy comparison to be built yet.

**Acceptance Scenarios**:

1. **Given** no sequencing configuration override, **When** a year's withdrawal plan is computed, **Then** funds are drawn in the default order: RMD, then taxable, then traditional, then Roth.
2. **Given** a year's spending need is fully met by the RMD amount alone, **When** the withdrawal plan is computed, **Then** no further withdrawals are drawn from any other account type.
3. **Given** the taxable account is exhausted partway through covering a year's remaining need, **When** the withdrawal plan is computed, **Then** the unmet remainder is drawn from the next account type in the configured sequence.
4. **Given** the combined available balance across all account types is less than a year's spending need, **When** the withdrawal plan is computed, **Then** the unmet shortfall is reported explicitly as part of the result, and no account balance is driven negative.
5. **Given** a different sequencing configuration (e.g., traditional before taxable), **When** the withdrawal plan is computed for the same inputs, **Then** the draw order honors the configured sequence, with no change to withdrawal mechanics code required.

---

### User Story 3 - Execute a Roth conversion within a defined window using a chosen strategy (Priority: P3)

A user wants, for a plan year that falls within the scenario's configured Roth conversion window, the conversion amount computed under a chosen strategy (fill ordinary income up to a bracket ceiling, or convert a fixed dollar amount each year) and applied — moving that amount from the traditional account to the Roth account and adding it to the year's ordinary taxable income.

**Why this priority**: A conversion amount cannot be computed correctly until the year's other ordinary income (RMD and any other withdrawals from User Story 2) is already known, so this depends on User Stories 1 and 2. It is independently valuable and testable once those income figures exist, and lower priority than the two withdrawal mechanics because a user can exercise and validate RMD and withdrawal-sequencing mechanics on their own before conversion logic is layered on top.

**Independent Test**: Can be fully tested by feeding a plan year, a conversion strategy configuration (bracket-ceiling amount or fixed dollar amount), the household's ordinary income already established for that year, and the traditional/Roth account balances, and confirming the computed conversion amount is correct and properly capped — without needing multi-strategy comparison across years to be built yet.

**Acceptance Scenarios**:

1. **Given** a plan year inside the configured conversion window and a "fill to bracket ceiling" strategy, **When** the conversion is computed, **Then** the amount converted brings the year's ordinary taxable income up to, but not over, the configured ceiling.
2. **Given** a plan year outside the configured conversion window, **When** the conversion is computed for that year, **Then** no conversion occurs.
3. **Given** a "fixed dollar amount" strategy, **When** the conversion is computed for a year inside the window, **Then** the amount converted equals the configured fixed amount, or the remaining traditional balance if it is smaller.
4. **Given** a computed conversion amount that would exceed the traditional account's available balance for that year, **When** the conversion is executed, **Then** the amount actually converted is capped at the available balance, and the traditional balance is never driven negative.
5. **Given** the household's ordinary income for the year (from RMD and other withdrawals) already meets or exceeds the configured bracket ceiling, **When** a "fill to bracket ceiling" conversion is computed, **Then** the conversion amount is $0, not negative.
6. **Given** the same year's income and account balances, **When** two different conversion strategies are applied, **Then** each produces its own independently correct conversion amount — one strategy's result never depends on or alters the other's.

---

### Edge Cases

- What happens when a household member's RMD amount, for a year that also falls inside the conversion window, is being computed alongside a Roth conversion? The RMD portion of that year's withdrawal is treated as already satisfied (non-convertible) before the conversion amount is computed, consistent with the federal rule that RMD dollars cannot themselves be converted to Roth (see FR-013).
- What happens when a household has only one member (single filer)? RMD is always computed via the Uniform Lifetime Table; the Joint Life Table branch simply never applies — this is not an error condition.
- What happens when a year's spending need is exactly $0? The withdrawal plan draws $0 from every account type without error.
- What happens on the final year of the conversion window versus the first year after it closes? The final window year still executes a conversion normally; the very next year, no conversion is computed at all, even if all other inputs are unchanged.
- What happens when the traditional account balance reaches $0 in an earlier year? RMD for that member is $0 in all subsequent years (per Acceptance Scenario 1.5), the withdrawal sequence skips the traditional leg since there is nothing to draw, and any configured Roth conversion for later years computes to $0 rather than erroring.
- What happens when withdrawal sequencing and Roth conversion are both configured for the same year? Withdrawal sequencing (User Story 2) is computed first to establish the year's ordinary income; Roth conversion (User Story 3) is computed second, using that already-established income figure — the two are never computed independently of each other for the same year.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST compute a household member's RMD for a given plan year from that member's traditional account balance, using the IRS Uniform Lifetime Table divisor matched to the member's age in that year.
- **FR-002**: The system MUST use the IRS Joint Life and Last Survivor Expectancy Table, instead of the Uniform Lifetime Table, to compute RMD for a household member whose spouse is their sole beneficiary and more than 10 years younger.
- **FR-003**: RMD computed for a household member below the RMD-required starting age, or with no traditional account balance, MUST be $0.
- **FR-004**: The system MUST determine, for a plan year, how the portion of spending need remaining after RMD income is drawn from the household's other account types (taxable, traditional, Roth), following a configured withdrawal sequencing strategy.
- **FR-005**: The system MUST ship at least one default withdrawal sequencing strategy — RMD, then taxable, then traditional, then Roth — implemented behind a common interface, so a different sequence can be substituted without changing withdrawal mechanics code.
- **FR-006**: Withdrawal sequencing MUST NOT draw more than an account type's available balance in a year; once an account type is exhausted, the unmet remainder MUST move to the next account type in the configured sequence.
- **FR-007**: When the combined available balance across all account types is insufficient to meet a year's spending need, the system MUST report the unmet shortfall explicitly as part of the withdrawal result, rather than allowing a negative account balance.
- **FR-008**: The system MUST execute a Roth conversion for a plan year only when that year falls within the scenario's configured conversion window.
- **FR-009**: Given a "fill to bracket ceiling" conversion strategy and the household's ordinary income already established for the year (from RMD and other withdrawals), the system MUST compute the conversion amount as the amount needed to bring that year's taxable ordinary income up to, but not over, the configured ceiling — computing $0 when income already meets or exceeds the ceiling.
- **FR-010**: Given a "fixed dollar amount" conversion strategy, the system MUST convert exactly the configured amount for each plan year in the window, or the remaining traditional balance if that is smaller.
- **FR-011**: A computed Roth conversion amount MUST NOT exceed the traditional account's available balance for that year.
- **FR-012**: A completed Roth conversion MUST move the converted dollar amount from the traditional account balance to the Roth account balance, and add it to that year's ordinary taxable income.
- **FR-013**: A household member's RMD amount for a plan year MUST be treated as already withdrawn and non-convertible before that year's Roth conversion amount is computed, consistent with the federal rule that RMD dollars cannot be converted to Roth.
- **FR-014**: RMD determination, withdrawal sequencing, and Roth conversion execution MUST each be implemented independently behind their own common, per-mechanic interface, so a new withdrawal sequencing strategy or Roth conversion strategy can be added without modifying RMD logic or another strategy's implementation.
- **FR-015**: The system MUST obtain ordinary income and Social Security taxability figures needed for bracket-ceiling conversion logic from the federal/state tax calculation engine (`002-tax-calculation-engine`) rather than recomputing tax bracket logic itself.
- **FR-016**: The system MUST accept household, account balance, spending, and Roth conversion configuration from a loaded Scenario (`001-scenario-config-management`) rather than requiring separately duplicated input.
- **FR-017**: The system MUST NOT require network access to compute RMD, withdrawal sequencing, or Roth conversion results for any supported plan year.
- **FR-018**: Every RMD, withdrawal sequencing, and Roth conversion computation MUST be reproducible — identical inputs (balances, ages, strategy configuration, plan year) MUST always produce identical outputs.
- **FR-019**: RMD table divisor values (Uniform Lifetime and Joint Life and Last Survivor) used by this feature MUST be sourced and individually citable, following the same Sourced Figure convention (citation, last-verified date, confirmed/needs-verification status) established in `002-tax-calculation-engine`.

### Key Entities

- **RMD Determination**: The computed Required Minimum Distribution for one household member in one plan year — the traditional account balance it was computed from, the divisor table used (Uniform Lifetime or Joint Life), the resulting dollar amount, and its Sourced Figure references.
- **Withdrawal Sequencing Strategy**: A configured, pluggable ordering of account types used to satisfy a year's spending need beyond RMD income. Ships with one default implementation (RMD → taxable → traditional → Roth) behind a common interface that later features (§3.4) can supply alternative implementations against.
- **Withdrawal Plan**: The result of applying a Withdrawal Sequencing Strategy for one plan year — the dollar amount drawn from each account type, the resulting account balances, and any unmet shortfall.
- **Roth Conversion Strategy**: A configured, pluggable rule for computing a plan year's conversion amount — ships with two implementations (fill-to-bracket-ceiling, fixed-dollar-amount) behind a common interface, active only during the scenario's configured conversion window.
- **Roth Conversion Execution**: The result of applying a Roth Conversion Strategy for one plan year — the dollar amount converted, the resulting traditional and Roth account balances, and the ordinary income added for that year.
- **Plan Year Mechanics Result**: The bundled per-year output of this feature for one household — RMD Determination(s), Withdrawal Plan, and Roth Conversion Execution — that a future simulation-engine feature (§3.5) will consume one plan year at a time.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: RMD amounts computed across a range of at least 10 reference ages match IRS Pub. 590-B Uniform Lifetime Table divisors exactly.
- **SC-002**: RMD amounts computed for at least 3 reference spouse-age-pair cases (sole beneficiary, more than 10 years younger) match IRS Joint Life and Last Survivor Table divisors exactly.
- **SC-003**: Given identical starting balances and spending need, switching the withdrawal sequencing strategy configuration changes which accounts are drawn down and by how much, with zero changes to withdrawal mechanics code required.
- **SC-004**: Given identical income and account balances, the two shipped Roth conversion strategies (fill-to-bracket-ceiling and fixed-dollar-amount) produce different, independently correct conversion amounts in 100% of test cases where the strategies' rules imply different amounts.
- **SC-005**: A shortfall — a year's spending need exceeding total available assets across all account types — is reported in 100% of cases where it occurs, and never silently absorbed as a negative account balance.
- **SC-006**: Adding one new withdrawal sequencing or Roth conversion strategy after the initial set ships requires changes to only that strategy's own module — zero other mechanic files need to change.

## Assumptions

- **RMD-required starting age and table sources**: This feature uses the RMD starting age and Uniform Lifetime / Joint Life divisor tables currently published in IRS Pub. 590-B; exact table values are populated during implementation and carry the same Sourced Figure citation/verification-status discipline established in `002-tax-calculation-engine` (FR-019), rather than a separate verification mechanism being built here.
- **This feature executes one given strategy per mechanic per call; it does not compare strategies.** Running multiple withdrawal-sequencing or Roth-conversion strategy configurations against the same year or the same market draws to find the best one is the future §3.4 "Strategy/Optimization Layer" feature's responsibility — this feature only guarantees the mechanics are swappable and independently correct so that comparison feature can call them repeatedly.
- **This feature computes one plan year at a time; it does not run a multi-year simulation.** Iterating this feature's mechanics across a multi-decade horizon under market-return uncertainty is the future §3.5 "Simulation Engine" feature's responsibility.
- **HSA contribution/eligibility timing (also listed in the source document's §3.3 table) is out of scope for this feature.** The source document's phased delivery plan (§8) places HSA coordination in Phase 5, separate from the Phase 2/3 work this feature and its immediate successor (§3.4) correspond to — mirroring how `002-tax-calculation-engine` deferred IRMAA/NIIT (Phase 4) out of its own §3.2-derived scope. It will be specified as a separate, later feature.
- **Income scope matches `002-tax-calculation-engine`**: "ordinary income" fed into bracket-ceiling conversion logic follows that feature's existing scope (traditional withdrawals/RMDs, wages; Roth withdrawals excluded as federally tax-free). This feature does not expand that scope.
- **Single-user, single-household scope only**, consistent with the source document's stated non-goals and the precedent set by both prior features.
- **No network access is required** to compute RMD, withdrawal sequencing, or Roth conversion results, consistent with the project's offline-first principle and the precedent set by both prior features.
