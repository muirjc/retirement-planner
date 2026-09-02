# Feature Specification: FICA Payroll Tax on Earned-Income Streams

**Feature Branch**: `022-fica-payroll-tax`

**Created**: 2026-09-02

**Status**: Draft

**Input**: User description: "Add employee-side FICA payroll tax (Social Security/OASDI 6.2% up to the annual wage base, plus Medicare/HI 1.45% uncapped, plus the 0.9% Additional Medicare Tax on combined wages above a filing-status threshold) computed specifically on earned_income-type income streams (never on pension/annuity streams, which are not wages). This closes a documented gap from 021-pension-annuity-income (rp-pid), which explicitly scoped FICA out. The computed FICA tax must reduce projected cash flow the same way federal/state income tax, IRMAA, NIIT, and the early-withdrawal penalty already do (funded from account withdrawals each year), and must be surfaced in reporting (a new PlanOutcome.cumulative_fica_tax_paid, SummaryStatistics.median_lifetime_fica_tax_paid) and the Streamlit UI's lifetime-figures narration, consistent with how NIIT/IRMAA/the early-withdrawal penalty are already surfaced. This addresses beads issue rp-elp."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the true cost of phased-retirement work (Priority: P1)

A household member plans to keep working part-time (an `earned_income` income stream) during phased retirement, and wants their projection to reflect the payroll tax withheld from that income, not just their income-tax liability — so the "how much does working part-time actually net us" answer is accurate.

**Why this priority**: This is the entire reason the issue exists — `earned_income` streams currently overstate after-tax cash flow by omitting payroll tax entirely, a documented gap from `021-pension-annuity-income`.

**Independent Test**: Configure a household member with an `earned_income` stream well under both the Social Security wage base and the Additional Medicare Tax threshold, run a projection, and confirm the standard 7.65% (6.2% + 1.45%) employee-side FICA is withdrawn from the household's accounts each year that stream is active, on top of ordinary income tax.

**Acceptance Scenarios**:

1. **Given** a member with a $40,000/year `earned_income` stream (well under the Social Security wage base), **When** a projection is run for a year that stream is active, **Then** that year's FICA tax equals `40,000 * (6.2% + 1.45%)` = $3,060, funded from the household's accounts the same way federal/state tax already is.
2. **Given** the same household with no `earned_income` stream configured (only a pension), **When** a projection is run, **Then** no FICA tax is computed or funded for that year — pensions and annuities are not wages.

---

### User Story 2 - See the Social Security wage base cap apply (Priority: P2)

A household member's earned income exceeds the annual Social Security taxable wage base, and the household wants the projection to reflect that the 6.2% OASDI portion stops applying beyond that cap, while the 1.45% Medicare portion keeps applying to every dollar.

**Why this priority**: Without the cap, a household with high phased-retirement earnings would see its FICA cost significantly overstated — a real, well-known mechanic of the tax that a household evaluating a high-earning consulting arrangement needs modeled correctly.

**Independent Test**: Configure an `earned_income` stream above the current wage base, run a projection, and confirm the OASDI portion caps out while the Medicare portion continues scaling with the full amount.

**Acceptance Scenarios**:

1. **Given** a member with a $250,000/year `earned_income` stream (above the $184,500 wage base), **When** a projection is run, **Then** the OASDI portion equals `184,500 * 6.2%` (capped), and the Medicare portion equals `250,000 * 1.45%` (uncapped).

---

### User Story 3 - See the Additional Medicare Tax apply at high household earnings (Priority: P3)

A household's combined earned income (one member's, or the sum of both spouses' `earned_income` streams) is high enough to trigger the Additional Medicare Tax, and the household wants that reflected too.

**Why this priority**: A real but narrower case — it only matters for households with unusually high phased-retirement/consulting earnings, unlike User Stories 1-2 which apply to essentially any household with earned income at all.

**Independent Test**: Configure combined earned income above the household's filing-status threshold, run a projection, and confirm the additional 0.9% applies only to the excess over that threshold.

**Acceptance Scenarios**:

1. **Given** a single filer with $250,000/year of `earned_income` (above the $200,000 single threshold), **When** a projection is run, **Then** Additional Medicare Tax equals `(250,000 - 200,000) * 0.9%` = $450, on top of the regular 1.45% Medicare portion.
2. **Given** a married-filing-jointly household where each spouse has a $150,000/year `earned_income` stream (combined $300,000, above the $250,000 MFJ threshold), **When** a projection is run, **Then** Additional Medicare Tax equals `(300,000 - 250,000) * 0.9%` = $450, computed once for the household, not per spouse.

---

### Edge Cases

- A household has multiple `earned_income` streams across two members, each individually under the wage base but combined enough to change the Additional Medicare Tax outcome: the wage-base cap (User Story 2) applies per member (each member's own earnings are capped independently), while the Additional Medicare Tax threshold (User Story 3) applies to the household's combined earned income.
- A household has `pension`/`annuity` streams alongside `earned_income` streams: FICA is computed only from the `earned_income` amounts; pension/annuity amounts never enter the FICA calculation, even though all three types count toward ordinary income tax identically.
- A member's `earned_income` stream amount is `$0` for a given year (outside its active window): that year's FICA contribution from that stream is `$0`, not omitted from computation.
- A household with zero `earned_income` streams configured anywhere (the common case, including every scenario predating this feature): FICA tax is `$0` every year, and every existing scenario's projection output is otherwise unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST compute, for each plan year, each household member's own Social Security (OASDI) payroll tax as 6.2% of that member's own combined `earned_income`-type stream amounts for that year, capped at the year's Social Security wage base — never applied to `pension` or `annuity` stream amounts.
- **FR-002**: System MUST compute, for each plan year, each household member's own Medicare (HI) payroll tax as 1.45% of that member's own combined `earned_income`-type stream amounts for that year, with no cap.
- **FR-003**: System MUST compute, for each plan year, an Additional Medicare Tax of 0.9% on the household's *combined* `earned_income`-type stream amounts (summed across every member) that exceed the household's filing-status threshold, computed once per household per year (not once per member).
- **FR-004**: The total FICA tax for a plan year (sum of FR-001 through FR-003) MUST be funded from the household's account balances the same way federal income tax, state income tax, the IRMAA surcharge, the Net Investment Income Tax, and the early-withdrawal penalty already are — i.e., it reduces projected account balances, not merely reported alongside them.
- **FR-005**: A household with no `earned_income` streams configured anywhere contributes `$0` FICA tax every year, and every other existing figure in that household's projection MUST be unaffected (byte-for-byte identical to this feature's absence).
- **FR-006**: The Social Security wage base and the Additional Medicare Tax filing-status thresholds MUST be documented, citable figures (not silently assumed), consistent with every other tax figure already in this tool.
- **FR-007**: Each plan year's FICA tax MUST be retained on that year's own result (not only summed into a running total), and a lifetime cumulative total MUST be available at the same level every other lifetime tax figure (income tax, IRMAA, NIIT, early-withdrawal penalty) already is — both for a single deterministic projection and as a median across Monte Carlo paths.
- **FR-008**: The Streamlit UI's lifetime-figures summary MUST show the lifetime FICA tax paid, consistent with how it already shows lifetime IRMAA surcharge, lifetime NIIT, and the lifetime early-withdrawal penalty.

### Key Entities

- **FICA Tax Result**: One plan year's payroll-tax computation — each member's own OASDI and Medicare amounts, the household's Additional Medicare Tax amount, and the total. Derived entirely from that year's `earned_income`-type stream amounts (already computed by `021-pension-annuity-income`'s `IncomeStream` mechanism) and the household's filing status; introduces no new scenario-configuration input.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For 100% of plan years in acceptance testing, the computed FICA tax exactly matches hand-calculated expected values across all three tiers (regular OASDI+Medicare, wage-base cap, Additional Medicare Tax threshold).
- **SC-002**: A household with a meaningful `earned_income` stream shows measurably lower projected ending balances than an otherwise-identical household whose FICA tax is (hypothetically) not modeled — i.e., the tax genuinely reduces modeled cash flow, not just a reported-but-inert figure.
- **SC-003**: Every existing scenario (none of which configure `earned_income` streams in a way that would change under this feature, since none currently exist) produces output identical to its pre-feature result.
- **SC-004**: The lifetime FICA figure is visible and correctly labeled everywhere the tool already surfaces lifetime IRMAA/NIIT/early-withdrawal-penalty figures (core `PlanOutcome`, `SummaryStatistics`, and the Streamlit UI narration).

## Assumptions

- This models the **employee side of W-2 FICA only** (6.2% + 1.45%, plus the 0.9% Additional Medicare Tax) — not the self-employment (SECA) 15.3% combined rate a 1099/sole-proprietor household member would actually owe. `earned_income` streams remain a generic "wages during phased retirement" concept; a household whose phased-retirement income is genuinely self-employment income will see this feature understate their true payroll-tax burden. This mirrors the same "documented simplification, not silently absorbed" treatment other figures in this tool already receive.
- The Social Security wage base is expressed in this tool's existing real-dollar convention: pinned to its current published value and held flat across every documented year, the same way federal tax brackets and the standard deduction already are (no separate nominal wage-growth projection this tool doesn't otherwise model).
- The Additional Medicare Tax's $200,000/$250,000 filing-status thresholds are fixed by statute (not inflation-indexed since the tax took effect), so holding them flat across every documented year is not a modeling simplification — it is what the actual law does.
- FICA tax is not itself deductible for federal/state ordinary income tax purposes in this engine (consistent with real law — the employee-side FICA withholding is not a deduction against income tax); this feature does not change how `ordinary_income` is computed, only adds a new, separate funded cost.
- No self-employment tax deduction, no employer-side FICA modeling (irrelevant to a household's own cash flow), and no Social Security earnings-test interaction (already a documented gap for claimed benefits before FRA) are in scope here.
