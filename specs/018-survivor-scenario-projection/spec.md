# Feature Specification: Survivor Scenario Projection Wiring

**Feature Branch**: `018-survivor-scenario-projection`

**Created**: 2026-08-31

**Status**: Draft

**Input**: User description: "Wire a mid-horizon spouse's death into the deterministic projection engine (rp-g8y). Currently simulation/survival_data.py's optional actuarial survival curves only redefine the Monte Carlo success metric ('probability of not running out of money while at least one spouse is alive') after the fact -- they never change filing status, spending need, or income mid-projection. A projection runs the entire horizon as if both spouses are alive and still MFJ, no matter what survival draw occurs. This means the tool cannot show the 'widow's tax penalty' (filing single with narrower brackets and lower SS-taxability/NIIT/IRMAA thresholds, while typically retaining only one Social Security check via the just-added survivor-benefit rule, and near-full household expenses) in deterministic and comparison projections.

This feature consumes what 017 (Social Security spousal/survivor benefits, rp-52n) just built: HouseholdMember.predicted_death_age (the hypothetical-death field 017 added specifically for this feature to consume) and the survivor-benefit calculation primitive in the SS benefit module. 017 explicitly did NOT wire a recorded death year into a running projection's filing-status/spending/income logic -- that wiring is this feature's whole scope.

Scope decisions made during specification: (1) Monte Carlo simulation continues to use simulation/survival_data.py's curves exactly as it does today (post-hoc success-rate scoring only) -- this feature does not draw a per-path probabilistic death year and does not change Monte Carlo's reproducibility contract; that remains a disclosed follow-on gap in BRD.md, not built here. (2) Household spending reduction after a death is an optional, opt-in Household-level percentage defaulting to 0% (a true no-op) when omitted, mirroring this project's existing 'strictly additive, opt-in field' precedent (010's hdhp_coverage, 016's full_retirement_age, 017's predicted_death_age itself).

Acceptance criteria: for a married-filing-jointly household with one member's predicted_death_age configured, a deterministic (and any comparison-layer, since comparisons are built on the same run_plan_projection() loop) projection MUST: (1) switch filing status from married-filing-jointly to single starting the tax year after the configured death year, continuing for the remainder of the horizon; (2) replace the household's combined Social Security income with the survivor-benefit amount (017's compute_survivor_benefit(), the higher of the two members' own claimed benefits) from the death year forward; (3) apply the household's configured spending-reduction percentage (0% if unspecified) to annual_spending_need starting the tax year after death; (4) leave every existing scenario that omits predicted_death_age completely unaffected (byte-for-byte identical output). docs/BRD.md must be updated to describe the modeled behavior and the remaining disclosed simplifications (no remarriage, no Qualifying Surviving Spouse or MFJ-in-year-of-death status -- switches straight to single, no Monte Carlo per-path wiring, no re-plan of a detailed budget beyond the single percentage).

Out of scope: Monte Carlo per-path probabilistic death-year wiring (disclosed follow-on); the Social Security family maximum benefit (already disclosed as out of scope in 017); modeling remarriage; Qualifying Surviving Spouse / MFJ-in-year-of-death filing status; a detailed post-death budget re-plan beyond the single documented spending percentage; a household where both members' predicted_death_age fall within the horizon (the survivor's own later configured death is not itself modeled as an end to the projection)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A projection shows the widow's tax penalty after a configured death (Priority: P1)

In a married-filing-jointly household where one member has a `predicted_death_age` configured, a deterministic full-horizon projection reflects that member's death starting the following tax year: the household files as `single` for every remaining plan year, its Social Security income becomes the survivor-benefit amount (017's higher-of-the-two rule) instead of both members' combined benefits, and spending need is reduced by the household's configured percentage (or left unchanged if none is configured). Every year before the death year is completely unaffected.

**Why this priority**: This is the entire point of the feature — without it, `predicted_death_age` (added by 017) is inert data with no effect on any output, and the tool still cannot demonstrate the single largest, most commonly-cited retirement-income risk for a married couple.

**Independent Test**: Configure an MFJ household with `predicted_death_age` set on one member such that the death year falls in the middle of the horizon, run a deterministic projection, and confirm: filing status is `married_filing_jointly` through the death year and `single` in every subsequent year; total Social Security income equals `compute_survivor_benefit()`'s result from the year after death forward; every year before death is byte-for-byte identical to a projection with `predicted_death_age` unset.

**Acceptance Scenarios**:

1. **Given** an MFJ household where one member's `predicted_death_age` translates to tax year Y within the horizon, **When** a deterministic projection runs, **Then** every plan year through Y uses `married_filing_jointly` filing status, and every plan year after Y uses `single`.
2. **Given** the same household, **When** the projection reaches tax year Y+1 (the first full year after death), **Then** the household's Social Security income for that year and every year after equals the higher of the two members' own claimed benefit amounts (via `compute_survivor_benefit()`), not the sum of both.
3. **Given** the same household with no spending-reduction percentage configured, **When** the projection reaches tax year Y+1, **Then** `annual_spending_need` is unchanged from its pre-death value.
4. **Given** the same household with a configured spending-reduction percentage of, e.g., 20%, **When** the projection reaches tax year Y+1, **Then** `annual_spending_need` for that year and every subsequent year is 80% of its pre-death value.
5. **Given** an MFJ household where `predicted_death_age` is unset on both members, **When** a deterministic projection runs, **Then** its output is unchanged from before this feature (filing status stays `married_filing_jointly` throughout, Social Security income is the sum of both members' benefits every year).
6. **Given** a `"single"`-filing-status household (one member, existing validation already forbids a second), **When** a projection runs, **Then** this feature's logic is never invoked, regardless of any `predicted_death_age` value present.

---

### User Story 2 - The strategy comparison layer reflects the same survivor scenario (Priority: P2)

Because `comparison/compare.py`'s multi-candidate comparisons are built on repeated calls to the same `run_plan_projection()` loop User Story 1 changes, every comparison candidate (different claiming ages, conversion strategies, withdrawal orders, etc.) run against a household with a configured `predicted_death_age` reflects the identical mid-horizon filing-status/income/spending switch, with no separate wiring needed in the comparison layer itself.

**Why this priority**: Confirms the single-loop design actually propagates — a household planning around a widow's-penalty scenario needs to compare strategies *within* that scenario, not just view one plain projection of it. P2 because it is a consequence of User Story 1's design rather than new logic of its own.

**Independent Test**: Run a strategy comparison (at least two candidates differing only in, e.g., claiming age) against the same MFJ household with `predicted_death_age` configured, and confirm every candidate's post-death years show `single` filing status and the survivor-benefit Social Security amount, exactly as a plain projection of that candidate would.

**Acceptance Scenarios**:

1. **Given** two comparison candidates differing only in withdrawal strategy, **When** both are run against a household with the same configured `predicted_death_age`, **Then** both candidates' post-death plan years independently show `single` filing status and the survivor-benefit Social Security amount.

---

### User Story 3 - The modeled behavior and its limits are documented (Priority: P3)

A reader of `docs/BRD.md` can find the survivor-scenario projection behavior (filing-status switch, survivor Social Security, spending-reduction assumption) described as modeled, alongside an honest list of what remains out of scope: Monte Carlo per-path wiring, Qualifying Surviving Spouse / MFJ-in-year-of-death status, remarriage, and a detailed post-death budget re-plan.

**Why this priority**: Same auditability principle as every other feature's User Story covering documentation (016 US3, 017 US3). Doesn't block User Stories 1-2 functioning correctly, hence P3.

**Independent Test**: Locate `docs/BRD.md`'s Social Security and/or projection-engine section and confirm it describes this feature's modeled behavior and its disclosed remaining gaps.

**Acceptance Scenarios**:

1. **Given** the completed feature, **When** a reader reviews `docs/BRD.md`, **Then** it describes the mid-horizon filing-status switch, survivor Social Security income, and spending-reduction assumption as modeled behavior for deterministic and comparison projections, and separately lists the Monte Carlo per-path gap and the other out-of-scope items above.

---

### Edge Cases

- A `predicted_death_age` that translates to a tax year *before* `start_tax_year` (the death is already "in the past" relative to the projection's start): the household is treated as `single` (survivor benefit, reduced spending) for the *entire* horizon — there is no year in the projection where the deceased member is still alive.
- A `predicted_death_age` that translates to a tax year *after* the projection's last plan year (`plan_to_age` reached before the configured death): the death never takes effect — output is identical to `predicted_death_age` being unset, for that specific horizon.
- A member's `predicted_death_age` set below their `current_age` (already implausible per 017 FR — flagged as a warning there, not re-validated here): this feature computes whatever tax year that translates to using the same age-translation formula as everywhere else in the engine (`member_age_in_tax_year`), consistent with the "before start_tax_year" case above rather than special-cased.
- Both household members have `predicted_death_age` configured within the horizon: the earlier death year drives the single switch and survivor benefit as described; the surviving member's own later configured `predicted_death_age` has no further effect (the projection does not end early, spending does not change again, and no second filing-status change occurs) — a documented simplification, since this engine has no notion of "no living household member" that would end a projection.
- The death year itself (tax year Y, where the member's translated age first reaches `predicted_death_age`): treated as the last year of `married_filing_jointly` filing, full combined Social Security, and full spending — the switch takes effect starting Y+1. This mirrors real income-tax law allowing a joint return for the year a spouse dies, without this engine needing to model Qualifying Surviving Spouse status for the years after.
- A spending-reduction percentage outside a plausible 0-100% range: flagged as an implausible-input warning, mirroring how FRA and `predicted_death_age` plausibility are already flagged (017 edge cases, 016 FR-009), not silently accepted or silently clamped.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For a married-filing-jointly household where exactly one member has a `predicted_death_age` configured, the system MUST determine that member's death tax year using this engine's existing age-translation formula (`member_age_in_tax_year`), and treat every plan year strictly after that tax year as post-death.
- **FR-002**: For every post-death plan year (FR-001), the system MUST use `single` filing status in every computation that currently consumes `household.filing_status` (federal tax, state tax, IRMAA, NIIT) — the death year itself and every year before it MUST continue using `married_filing_jointly`.
- **FR-003**: For every post-death plan year (FR-001), the system MUST compute the household's Social Security income as `compute_survivor_benefit()`'s result (017) applied to the two members' own currently-claimed benefit amounts for that year, replacing the sum of both members' individual benefits used in every prior year.
- **FR-004**: `Household` MUST gain an optional field for a household-specified spending-reduction percentage, applied by multiplying `annual_spending_need` by `(1 - percentage)` for every post-death plan year (FR-001) — the death year itself and every year before it MUST use the full, unreduced `annual_spending_need`. Omitting this field MUST behave identically to a value of 0% (no reduction).
- **FR-005**: When no household member has a `predicted_death_age` configured, or the household's filing status is `"single"`, the system MUST NOT alter filing status, Social Security income, or spending need from this feature's logic at all — output MUST be identical to this feature not existing.
- **FR-006**: This feature's death-year, filing-status, survivor-benefit, and spending-reduction logic MUST live in the same per-plan-year loop (`run_plan_projection()`) that both plain projections and every strategy-comparison candidate already share, so User Story 2 requires no separate wiring.
- **FR-007**: This feature MUST NOT change Monte Carlo simulation's (`simulation/monte_carlo.py`) behavior in any way — `survival_curves`-based scoring continues exactly as it does today, with no per-path death-year draw and no change to Monte Carlo's reproducibility contract. This gap MUST be documented, not silently left implicit.
- **FR-008**: `docs/BRD.md` MUST be updated to describe the mid-horizon filing-status switch, survivor Social Security income, and spending-reduction assumption as modeled behavior for deterministic and comparison projections, and MUST separately, honestly list the remaining disclosed gaps: Monte Carlo per-path wiring (FR-007), no Qualifying Surviving Spouse / MFJ-in-year-of-death status, no remarriage modeling, no detailed post-death budget re-plan beyond the single percentage, and no handling of a second (survivor's own) configured death ending the projection.

### Key Entities

- **Household (spending-reduction assumption)**: Gains an optional percentage field, consulted only for plan years after a configured death year; every household that omits it is unaffected (mirrors `017`'s `predicted_death_age` opt-in precedent).
- **Plan Year Projection (post-death state)**: Each plan year's filing status, Social Security income, and spending need are now derived per-year rather than fixed for the whole horizon, keyed off whether that year falls before or after a configured death year.

## Assumptions

- `HouseholdMember.predicted_death_age` (017) is the sole input this feature consumes to determine *when* a death occurs — no new "death year" field is introduced; the existing age-translation formula (`member_age_in_tax_year`, already used identically for RMD/Social Security/HSA eligibility per-year age lookups) converts it to a concrete tax year for a given projection's `reference_tax_year`/`start_tax_year`.
- Real U.S. federal income tax law permits a joint return for the tax year a spouse dies, with Qualifying Surviving Spouse status potentially available for up to two years after that before reverting to Single/Head of Household. This engine does not model Qualifying Surviving Spouse status at all (that remains a disclosed gap, consistent with the tool's existing "single filer" tax bracket coverage). To stay conservative and simple rather than silently understating tax, this feature switches straight from `married_filing_jointly` (through the death year, inclusive) to `single` (from the following year), skipping the more favorable QSS treatment entirely — this may overstate the survivor's tax burden in the one-to-two years immediately following death relative to real law, and is called out in `docs/BRD.md` as a documented simplification, not silently absorbed.
- The spending-reduction percentage is a single flat household-level assumption, not a detailed re-planned budget — consistent with this project's existing "documented simplification over unbuilt precision" pattern (e.g. the IRMAA MAGI proxy, the flat inherited-account growth-rate assumption).
- Monte Carlo simulation's existing `survival_curves` machinery (`simulation/survival_data.py`) is unchanged by this feature (FR-007) — it continues to answer "what fraction of paths had at least one member alive at the end" as a post-hoc scoring question, entirely independent of this feature's new per-year filing-status/income/spending switch, which only deterministic and comparison-layer projections apply. Wiring a per-path probabilistic death draw into Monte Carlo's own loop is a distinct, larger scope (new RNG stream, reproducibility contract change) deferred to a future follow-on.
- A household where both members have `predicted_death_age` configured within the horizon is not specially handled beyond the first (earlier) death's switch — the survivor's own later configured death does not end the projection or trigger any further change, since this engine has no concept of a household with zero living members. This is a documented simplification, not a silent gap.
- This feature changes `run_plan_projection()`'s per-year loop and `Household`'s data model only — it does not change `Household`/`HouseholdMember` validation rules beyond the new optional field, any BFF/UI surface beyond what's needed to accept the new optional field, or `simulation/monte_carlo.py` (FR-007).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In an MFJ household with one member's `predicted_death_age` configured mid-horizon, every plan year through the death year uses `married_filing_jointly` filing status and combined Social Security income; every plan year after uses `single` filing status and the survivor-benefit amount — in 100% of such configurations, within a small rounding tolerance.
- **SC-002**: Every existing scenario/test that does not configure `predicted_death_age` produces output identical to before this feature — no regression to any household this feature doesn't affect (mirrors 017's SC-002 precedent).
- **SC-003**: A configured spending-reduction percentage is applied to exactly the post-death plan years' `annual_spending_need`, and to no year before or including the death year, with zero deviation.
- **SC-004**: A strategy comparison run against a household with `predicted_death_age` configured shows the identical post-death filing-status/income/spending switch in every candidate, with no candidate-specific wiring required.
- **SC-005**: Monte Carlo simulation's output (success rate, percentile bands, survival-adjusted success rate) is byte-for-byte unchanged by this feature for any input that produced output before it, confirming FR-007's non-interference.
- **SC-006**: `docs/BRD.md` no longer implies that a configured hypothetical death has no effect on a projection; a reader can find the modeled behavior and its remaining disclosed gaps (Monte Carlo, QSS/MFJ-in-year-of-death, remarriage, budget re-plan, second-death handling) in one place.
