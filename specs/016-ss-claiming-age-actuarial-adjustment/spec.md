# Feature Specification: Social Security Claiming-Age Actuarial Adjustment

**Feature Branch**: `016-ss-claiming-age-actuarial-adjustment`

**Created**: 2026-08-30

**Status**: Draft

**Input**: User description: "Fix rp-n44: the Social Security claiming-age comparison currently varies only WHEN a member's flat ss_annual_benefit turns on, never the AMOUNT paid, so the 62-70 claiming-age grid mechanically favors claiming as early as possible instead of reflecting the real trade-off. Add a full_retirement_age (FRA) input per household member, and reinterpret ss_annual_benefit as the member's Primary Insurance Amount (PIA) -- the benefit payable AT their FRA -- rather than the benefit paid at whatever age they claim. The engine must derive the actual benefit paid at any claiming age (62-70) from the PIA and FRA using the standard SSA actuarial adjustment (early reduction / delayed retirement credit), cited per this project's SourcedFigure convention. Out of scope: spousal benefits, survivor benefits, earnings test (tracked separately as rp-52n/rp-g8y)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Claiming-age grid reflects the real trade-off (Priority: P1)

A household comparing Social Security claiming ages from 62 through 70 (per member) sees each candidate's benefit amount actually change with the claiming age chosen — reduced for claiming before the member's full retirement age (FRA), increased for delaying past it — rather than every candidate receiving the same flat annual amount for a different number of years. The comparison output shows genuine trade-offs between claiming earlier (smaller checks, more of them) and claiming later (larger checks, fewer of them), instead of mechanically favoring the earliest claiming age in every case.

**Why this priority**: This is the tool's headline Social Security feature (a full 62–70 grid per spouse) and the specific defect (rp-n44) that motivated this feature. Without this, the comparison is actively misleading rather than merely incomplete.

**Independent Test**: Configure a household member with a known PIA and FRA, run the claiming-age grid comparison across several ages, and confirm each candidate's annual benefit differs by the expected actuarial percentage of PIA (e.g., claiming at 62 against a 67 FRA yields ~70% of PIA; claiming at 70 yields ~124% of PIA) rather than 100% of PIA at every age.

**Acceptance Scenarios**:

1. **Given** a household member with PIA $30,000 and FRA 67, **When** the claiming-age grid includes ages 62, 67, and 70 for that member, **Then** the projected annual benefit is lower than $30,000 at age 62, exactly $30,000 at age 67, and higher than $30,000 at age 70.
2. **Given** a household member with PIA $30,000 and FRA 66, **When** claiming at age 64 (24 months before FRA), **Then** the reduction applied uses only the "first 36 months" early-reduction rate (no second-tier rate applies, since 24 ≤ 36).
3. **Given** a household member with PIA $30,000 and FRA 67, **When** claiming at age 62 (60 months before FRA), **Then** the reduction applies the first-tier rate to the first 36 months and the second-tier rate to the remaining 24 months.
4. **Given** a household member with PIA $30,000 and FRA 67, **When** claiming at age 70 (36 months after FRA), **Then** the delayed retirement credit applies for exactly 36 months and no further credit accrues past age 70.

---

### User Story 2 - Every projection (not just the grid) uses the correct benefit amount (Priority: P1)

A household running a single, non-comparison projection (one fixed claiming age per member, as configured in the scenario) also receives the actuarially-correct benefit amount for that claiming age relative to the member's FRA and PIA — not just when running the claiming-age comparison. Because the underlying input field's meaning changes for every consumer of it, every projection path (deterministic single-run, strategy comparisons along other axes, and Monte Carlo simulation) must derive the paid benefit the same way.

**Why this priority**: The claiming-age grid and a normal single-strategy run share the same underlying `ss_claim_age`/benefit fields. Fixing the grid alone while leaving a plain single-scenario run using the old (wrong) flat-amount behavior would produce inconsistent, silently different answers depending on which comparison axis the household happens to be using that day.

**Independent Test**: Run a plain (non-grid) projection for a household member claiming 3 years before their FRA and confirm the benefit used in that projection's income and tax calculations is the reduced amount, not the member's PIA.

**Acceptance Scenarios**:

1. **Given** a household member with `ss_claim_age` set below their FRA in an ordinary (non-grid) scenario, **When** a deterministic projection runs, **Then** the Social Security income used in that projection's tax and cash-flow calculations reflects the reduced benefit, not the PIA.
2. **Given** the same scenario, **When** a Monte Carlo simulation runs instead, **Then** it uses the identical reduced benefit amount as the deterministic projection (Principle II, reproducibility — the same inputs must yield the same derived benefit regardless of which engine path consumes it).

---

### User Story 3 - The adjustment rule is documented and auditable like every other regulated figure (Priority: P2)

A user or reviewer of this tool can find, next to the code that applies the early-reduction and delayed-retirement-credit rates, the legal citation and last-verified date for those rates — consistent with how every other regulated figure in this tool (tax brackets, NIIT, IRMAA, RMD tables) is already documented. `docs/BRD.md`'s Social Security section and its list of documented simplifications are updated to describe the new modeled behavior, so the BRD no longer implies (by omission) that claiming age has no effect on benefit amount.

**Why this priority**: This is the project's own stated principle (Accuracy Over Cleverness / Auditability) applied to a new figure, and is what turns "the code happens to compute the right number" into "a reviewer can independently verify the number is right." It doesn't block User Stories 1–2 functioning correctly, hence P2 rather than P1.

**Independent Test**: Locate the module implementing the adjustment and confirm it carries a citation and last-verified date in the same style as `tax/social_security.py`'s provisional-income thresholds; confirm `docs/BRD.md` describes the new behavior.

**Acceptance Scenarios**:

1. **Given** the implemented adjustment module, **When** a reviewer inspects it, **Then** it cites the specific statute/regulation establishing the early-reduction and delayed-retirement-credit rates and records a last-verified date, in the same structural pattern already used by the tool's other cited figures.
2. **Given** the completed feature, **When** a reader reviews `docs/BRD.md`'s Social Security section, **Then** it describes claiming-age-dependent benefit adjustment as modeled behavior (not a documented gap).

---

### Edge Cases

- Claiming exactly at FRA: benefit equals PIA unadjusted (0% reduction, 0% credit) — this is the baseline case both formulas must reduce to at the boundary.
- Claiming age below 62 or above 70: already rejected by existing claiming-age-grid validation (62–70 inclusive); a scenario's plain `ss_claim_age` field should be held to the same bound going forward, since ages outside it have no defined SSA benefit formula.
- FRA outside a plausible human range (e.g., below 65 or above 67, the range covering everyone the current Social Security rules apply to): flagged as an implausible-input warning rather than silently accepted, mirroring how other plausibility concerns are surfaced elsewhere in this tool (`ValidationFlag`, severity="warning").
- A claiming age exactly 36 months before FRA: the boundary between the first-tier (5/9 of 1%/month) and second-tier (5/12 of 1%/month) early-reduction rates — the 36th month must use the first-tier rate, not the second.
- A claiming age exactly at FRA + 36 months (i.e., FRA 67 and claiming at 70, or FRA 66 and a hypothetical claim past 69): delayed credit accrual stops at age 70 regardless of how much later than FRA that is, per statute.
- Existing scenario files (YAML fixtures, example scenarios) that currently set `ss_annual_benefit` under the old "amount actually paid at the configured claiming age" meaning: these need their stored values reinterpreted or updated to the member's actual PIA, since the field's meaning changes; this is a one-time data migration concern for this repository's own fixtures, not a runtime behavior of the tool itself.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each household member MUST have a full retirement age (FRA) input, expressed as a number of years (fractional years allowed, to represent birth-year-based FRAs that fall on a specific month rather than a whole year, e.g. 66 years and 10 months). When a scenario omits it, the system MUST default it to that member's own claiming age (i.e., assume no adjustment) rather than reject the scenario — this reproduces every pre-existing scenario's current, already-correct-for-its-one-configured-claiming-age behavior unchanged, and only engages the new adjustment once a household explicitly states a FRA that differs from its claiming age.
- **FR-002**: The existing per-member Social Security benefit input MUST be reinterpreted as that member's Primary Insurance Amount (PIA) — the benefit payable if claimed exactly at their FRA — rather than the benefit paid at whatever age is actually claimed.
- **FR-003**: For a member claiming before their FRA, the system MUST reduce the paid annual benefit below the PIA using the standard early-claiming reduction: 5/9 of 1% per month for each of the first 36 months claimed early, plus 5/12 of 1% per month for any additional months claimed early beyond the first 36 (bounded by the tool's existing 62–70 claiming-age range, so at most 60 months early against the latest FRA this range can produce).
- **FR-004**: For a member claiming after their FRA (up to age 70), the system MUST increase the paid annual benefit above the PIA using the standard delayed retirement credit: 2/3 of 1% per month (equivalent to 8% per year) delayed past FRA, with no further credit accruing for delay past age 70.
- **FR-005**: For a member claiming exactly at their FRA, the paid annual benefit MUST equal the PIA exactly (no reduction, no credit).
- **FR-006**: This derived, claiming-age-adjusted benefit amount MUST be used consistently everywhere a member's Social Security income feeds into the system — a single deterministic projection, every other comparison axis (state, withdrawal sequencing, Roth conversion strategy), the claiming-age grid comparison itself, and Monte Carlo simulation — rather than only within the claiming-age comparison path.
- **FR-007**: The early-reduction and delayed-retirement-credit rates MUST be implemented as a cited, dated figure in the same structural convention this project already uses for its other regulated figures (a named figure with a citation to the specific statute/regulation and a last-verified date, surfaced the same way an unverified figure would be if it were ever marked as such).
- **FR-008**: The system MUST continue to reject (as it already does for the claiming-age grid) any claiming age outside 62–70 inclusive, and SHOULD extend that same bound to a scenario's plain, non-grid claiming-age input if it does not already enforce it.
- **FR-009**: The system MUST flag (as a non-blocking plausibility warning, not a hard rejection) an FRA input outside the range that current Social Security rules can produce for any living claimant (approximately 65 to 67 years).
- **FR-010**: `docs/BRD.md`'s Social Security section and its list of documented simplifications MUST be updated to describe claiming-age-dependent benefit adjustment as modeled behavior.
- **FR-011**: This feature MUST NOT attempt to model spousal benefits, survivor benefits, or the Social Security earnings test for working before FRA — those remain tracked separately (rp-52n, rp-g8y) and are explicitly out of scope here.

### Key Entities

- **Household Member (Social Security facts)**: Gains a full retirement age. Its existing annual-benefit figure changes meaning from "benefit received" to "Primary Insurance Amount" — the benefit at FRA, from which the benefit actually received at any chosen claiming age is derived.
- **Claiming-Age Adjustment Figure**: A new cited, dated figure (in the same family as this project's existing tax-figure citations) describing the early-reduction and delayed-retirement-credit rates and the statute/regulation that fixes them.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a representative household, the claiming-age comparison grid no longer shows a monotonically-decreasing lifetime or year-by-year benefit total as claiming age increases from 62 to 70 under otherwise-identical assumptions — i.e., the comparison is capable of showing delaying as the better choice when it genuinely is, which it structurally cannot do today.
- **SC-002**: A benefit claimed exactly at a member's FRA equals that member's configured PIA, in every projection path, with zero deviation.
- **SC-003**: A benefit claimed at age 62 against a 67 FRA comes out within a small rounding tolerance of 70.0% of PIA, and a benefit claimed at age 70 against a 67 FRA comes out within a small rounding tolerance of 124.0% of PIA — the two textbook reference points most commonly cited for Social Security claiming decisions.
- **SC-004**: Every existing automated test suite that exercised Social Security benefit amounts before this change continues to pass after fixture values are updated to the new PIA-based meaning, with no reproducibility regression (identical scenario + seed still yields identical output).
- **SC-005**: `docs/BRD.md` no longer lists "claiming age has no effect on benefit amount" as an implicit gap; a reader can find the modeled adjustment described in the Social Security section alongside its citation.

## Assumptions

- FRA is supplied directly as a per-member input (in years, fractional allowed) rather than derived from a birth year and an internal FRA-by-birth-year table; this matches how the rest of this household member's profile already works (`current_age` is a direct input, not derived from a birth date).
- The 5/9%, 5/12%, and 2/3% monthly rates, and the 36-month first-tier/60-month total-early boundary, are fixed by statute and not subject to annual revision — consistent with how this project already treats the SS provisional-income thresholds (also fixed since 1983) in `tax/social_security.py`.
- Because FRA defaults to the member's own claiming age when omitted (FR-001), an existing scenario that never sets FRA keeps producing exactly its current output — its `ss_annual_benefit` remains correct as "the benefit paid at the one claiming age that scenario configures," with no reinterpretation forced on it. Only a scenario that wants the new claiming-age sensitivity (in particular, any scenario driving the claiming-age comparison grid across multiple ages) needs to be updated with the member's real PIA and FRA to get an actuarially meaningful comparison — this is an opt-in accuracy upgrade, not a breaking migration of every existing scenario file.
- Spousal benefits, survivor benefits, and the pre-FRA earnings test remain out of scope, per rp-52n and rp-g8y already tracking them separately.
- The claiming-age bound of 62–70 (already enforced for the comparison grid) is the correct bound for a plain scenario's `ss_claim_age` too, since no defined SSA benefit formula exists outside that range for a claim not yet filed.
