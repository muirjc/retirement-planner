# Feature Specification: Source-Attributed Retirement Income for State Exclusions (NC Bailey Settlement)

**Feature Branch**: `027-nc-bailey-exclusion`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "Model source-attributed retirement income for state exclusions (Bailey settlement, NC). Follow-on to 024-nc-state-tax: extend the household income-stream model and IncomeComponents so a pension/annuity stream can be marked as NC Bailey-settlement-qualifying (pre-8/12/1989-vested government/military pension), thread that income separately through comparison/projection.py, and have tax/state/nc.py exclude it from NC's taxable base while taxing the rest of ordinary income at NC's flat rate. SC/DE/FL and every other consumer of IncomeComponents must be unaffected. Update docs/BRD.md §5.4's NC row."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A NC retiree with a Bailey-qualifying pension gets an accurate state tax result (Priority: P1)

A household comparing North Carolina as a candidate retirement state has a member who draws a pension from a qualifying government plan (e.g. the NC Teachers' and State Employees' Retirement System, or a military pension) with five or more years of creditable service, or contributions, as of August 12, 1989. Today the tool taxes that pension income the same as any other ordinary income, overstating NC's real tax cost for that household relative to their actual, legally-exempt liability. The household wants to mark that pension as Bailey-qualifying in their scenario and see NC's computed tax reflect the real exemption.

**Why this priority**: This is the entire reason the feature exists — 024-nc-state-tax shipped NC's flat rate but explicitly deferred this case (spec.md Assumptions, research.md §3) as out of scope; without it, NC's modeled tax is systematically wrong for exactly the households most likely to be comparing NC as a destination (career government/military retirees).

**Independent Test**: Configure a household with one member's pension income stream marked Bailey-qualifying and a state of `"NC"`, run a projection for a documented tax year, and confirm the computed NC state tax excludes that stream's amount from the taxable base while taxing the household's remaining ordinary income at NC's existing flat rate.

**Acceptance Scenarios**:

1. **Given** a household with $40,000 of Bailey-qualifying pension income and $30,000 of other ordinary income (withdrawals), state `"NC"`, and tax year 2026, **When** NC state tax is computed, **Then** the result is `30,000 * 3.99%` = $1,197.00 — the $40,000 Bailey-qualifying amount contributes $0.
2. **Given** a household whose only ordinary income is $50,000 of Bailey-qualifying pension income, **When** NC state tax is computed for any documented tax year, **Then** the result is $0.00.
3. **Given** a household with no income stream marked Bailey-qualifying, **When** NC state tax is computed, **Then** the result is unchanged from 024-nc-state-tax's existing behavior (100% of ordinary income taxed at the flat rate).

---

### User Story 2 - Federal tax, FICA, IRMAA, and NIIT still see the full pension income (Priority: P1)

The same household's Bailey-qualifying pension is a real, fully federally-taxable pension — the Bailey settlement is a North Carolina state-law exemption only. The household needs their federal tax, IRMAA surcharge, and NIIT figures to still reflect that income in full, so marking a stream Bailey-qualifying for NC purposes must not leak into any other calculation.

**Why this priority**: A change that accidentally exempted Bailey-qualifying income from federal tax (or any other consumer of the household's ordinary income) would silently understate the household's real federal liability — a correctness regression worse than the gap this feature closes, and exactly the kind of cross-consumer leakage the constitution's Accuracy principle warns against.

**Independent Test**: Configure the same household as User Story 1 and confirm federal tax, FICA, IRMAA MAGI, and NIIT are computed against the household's full ordinary income (Bailey-qualifying pension included), identically to a household with the same income where no stream is marked Bailey-qualifying.

**Acceptance Scenarios**:

1. **Given** the household from User Story 1, **When** federal tax is computed for the same plan year, **Then** the result is identical to a household with the same $70,000 total ordinary income and no Bailey-qualifying flag set on any stream.

---

### User Story 3 - South Carolina, Delaware, and Florida results are unaffected (Priority: P2)

A household comparing multiple candidate states (SC, DE, FL, NC) alongside each other wants the addition of NC's Bailey handling to leave every other state's computed tax exactly as it was before this feature, so existing comparisons already trusted for SC/DE/FL don't shift for unrelated reasons.

**Why this priority**: This is a regression-safety guarantee, not new user-facing value — but a comparison tool whose non-NC results silently changed when NC-specific modeling was added would undermine trust in every state's numbers, not just NC's.

**Independent Test**: Run the existing SC/DE/FL test suites and a full four-state comparison (including a household with a stream marked Bailey-qualifying) and confirm SC/DE/FL's computed tax for that household is identical to the same household's SC/DE/FL tax before this feature (the Bailey-qualifying flag has no meaning outside NC).

**Acceptance Scenarios**:

1. **Given** a household with a stream marked Bailey-qualifying, **When** state tax is computed for SC, DE, or FL, **Then** the full stream amount is taxed (or exempted by that state's own existing age-based rule) exactly as it would be with no Bailey-qualifying flag set — the flag is inert outside NC.

---

### Edge Cases

- A household has multiple pension/annuity streams, only some marked Bailey-qualifying: only the marked streams' amounts are excluded from NC's taxable base; unmarked pension, annuity, earned-income, withdrawal, and RMD income is taxed normally.
- A Bailey-qualifying stream's configured amount exceeds the household's total ordinary income for the year (e.g. a stream ends mid-projection while other income streams are also winding down): NC's taxable base floors at $0, matching 024-nc-state-tax's existing floor behavior — never negative.
- A household marks a stream Bailey-qualifying but selects a state other than NC: the flag has no effect on that state's computed tax (User Story 3); no error is raised for an unused flag.
- An `earned_income`-type stream is marked Bailey-qualifying: this is a user configuration error (Bailey exempts pension/retirement-plan income, not wages) — the engine accepts the flag as configured (it does not re-derive real-world Bailey eligibility) and excludes that stream's amount from NC's base exactly as it would for a pension stream, consistent with the existing "the household attests to this fact" posture (see Assumptions); no new validation is introduced beyond what already exists for `stream_type`.
- A tax year outside NC's documented schedule range is requested: `UnsupportedTaxYearError` is raised, unchanged from 024-nc-state-tax — the Bailey exclusion introduces no new tax-year-dependent figure of its own.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A household's income stream (pension or annuity) MUST be configurable as Bailey-settlement-qualifying — a household-attested fact (pre-8/12/1989-vested qualifying government or military retirement benefit) that the engine accepts as given and does not itself verify or derive.
- **FR-002**: The Bailey-qualifying flag on a stream MUST default to "not qualifying" — an existing scenario file with no Bailey-related fields MUST parse and project identically to before this feature.
- **FR-003**: The household's total ordinary income used by federal tax, FICA, IRMAA, and NIIT calculations MUST include Bailey-qualifying stream income in full, unchanged from today — this feature MUST NOT reduce any figure derived from total ordinary income other than NC's own state taxable base.
- **FR-004**: North Carolina's `compute_tax()` MUST exclude the household's total Bailey-qualifying income for the year from its taxable base (100% exemption, no partial amount, no phase-out), taxing the remainder of ordinary income at NC's existing flat rate (024-nc-state-tax).
- **FR-005**: NC's taxable base after the Bailey exclusion MUST floor at $0 — never negative, matching 024-nc-state-tax's existing floor behavior.
- **FR-006**: Every other registered state module (SC, DE, FL) MUST compute an identical result, for the same household and income, whether or not any stream is marked Bailey-qualifying — the flag MUST be inert outside NC.
- **FR-007**: The mechanism used to carry Bailey-qualifying income from the household's income streams through to NC's `compute_tax()` MUST be additive to the existing `IncomeComponents` contract every state module receives — an unset or zero value MUST leave every existing state module's behavior byte-for-byte unchanged (matches 024-nc-state-tax research.md §3's two candidate shapes).
- **FR-008**: `docs/BRD.md` §5.4's North Carolina row MUST be updated to record Bailey-settlement support and its verification status once addressed.
- **FR-009**: The Bailey exclusion mechanism MUST be general enough that a future state's own source-attributed exclusion could reuse the same `IncomeComponents` extension without a further shape change, even though this feature implements and tests only NC's rule.

### Key Entities *(include if feature involves data)*

- **Bailey-qualifying income stream**: An existing household income stream (pension or annuity), now optionally attestable by the household as NC Bailey-settlement-qualifying. No new entity — an added attribute on the existing stream shape.
- **Bailey-qualifying income (household, per year)**: The sum, across all of a household's income streams marked Bailey-qualifying, of that stream's amount for the plan year — carried alongside (not instead of) the household's existing single ordinary-income total, for NC's exclusive use.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A NC household with a Bailey-qualifying pension sees that pension's full amount excluded from their computed NC state tax, for any tax year already supported by NC's existing schedule horizon.
- **SC-002**: Federal tax, FICA, IRMAA, and NIIT results for a household with a Bailey-qualifying stream are identical to the same household's results with no stream marked Bailey-qualifying (income totals unaffected).
- **SC-003**: SC, DE, and FL computed tax results are unchanged, dollar-for-dollar, from before this feature for every existing test case and for a household with a Bailey-qualifying stream.
- **SC-004**: The full existing test suite (`pytest tests/`, `pytest services/bff/tests/`) continues to pass once this feature is merged, with zero Bailey-specific special-casing added anywhere outside the income-stream model, `IncomeComponents`, `comparison/projection.py`'s income assembly, and `tax/state/nc.py`.

## Assumptions

- **The Bailey-qualifying flag is a household attestation, not a verified fact.** The engine has no way to independently confirm a real pension's plan type or a member's actual 1989 vesting status — exactly like `ss_claim_age`, `stream_type`, and every other user-supplied scenario input, the household is trusted to set this flag accurately for their real situation. This mirrors 024-nc-state-tax research.md §3's own framing of why an age-based proxy would be actively wrong: the engine models the household's stated fact, not an inferred approximation.
- **Only pension/annuity streams are expected to carry the flag**, but the engine does not restrict it to those `stream_type` values — see Edge Cases. Real-world Bailey eligibility is restricted to retirement-plan income by law; enforcing that restriction in the engine would be a validation feature, not a modeling feature, and is left out of this pass unless planning finds a low-cost way to add it.
- **The separate post-2021 NC military-retirement exemption (S.L. 2021-180) is out of scope.** It is a second, independent carve-out with no 1989 vesting cutoff (024-nc-state-tax research.md §3) and is not modeled by this feature.
- **No other state's source-attributed exclusion is implemented by this feature.** FR-009's generality requirement is about not precluding a future state from reusing the same `IncomeComponents` extension — it does not mean any other state's rule is built or tested here.
- **This feature does not re-open 024-nc-state-tax's flat-rate figures.** NC's rate schedule (4.25% for 2025, 3.99% for 2026+) is unchanged; this feature only changes what income enters that rate's base.
