# Feature Specification: Pension, Annuity & Phased-Retirement Income Streams

**Feature Branch**: `021-pension-annuity-income`

**Created**: 2026-09-02

**Status**: Draft

**Input**: User description: "Add support for one or more generic fixed income streams (pension/annuity payouts, and earned income for phased retirement) at the household/scenario level. Each stream should have a start age, optional end age, annual amount, and an inflation-adjustment mode (COLA-adjusted or fixed-nominal), similar in spirit to how Social Security benefits are modeled. These streams must feed into the same tax and cash-flow pipeline as Social Security benefits (ordinary taxable income for pensions/annuities/earned income, subject to appropriate withholding/FICA considerations for earned income if in scope). Document as a modeled income source in docs/BRD.md. This addresses beads issue rp-pid."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Model a lifetime pension (Priority: P1)

A household member with a defined-benefit pension wants their projection to reflect that fixed, taxable income starting at a chosen age and continuing for the rest of the plan, growing with inflation the same way their Social Security benefit does (or, alternatively, staying flat in nominal dollars if their pension has no COLA).

**Why this priority**: Pensions remain common for public-sector and legacy private-sector retirees. Without this, the tool cannot be used at all for a large class of households — the only alternative today is Social Security and account withdrawals. This is the acceptance bar the originating issue calls out as the minimum ("covering pensions and annuities at minimum").

**Independent Test**: Configure a household with one member who has a pension starting at their current age with no end age, run a projection, and confirm the pension's after-tax contribution to cash flow and its effect on the household's tax bill appear in the year-by-year output for every remaining plan year.

**Acceptance Scenarios**:

1. **Given** a household member with a COLA-adjusted pension of $30,000/year starting at age 65, **When** a projection is run for any plan year that member is 65 or older, **Then** the year's household ordinary taxable income includes the pension at its full configured $30,000 (today's-dollar) amount, unadjusted — consistent with how this tool already holds Social Security and every other input flat in real, inflation-adjusted terms.
2. **Given** a household member with a fixed-nominal pension of $20,000/year starting at age 62, **When** a projection is run for plan years at ages 62 and 82, **Then** the age-82 year shows a smaller real (today's-dollar) amount than the age-62 year, since a fixed *nominal* payment loses purchasing power over time in a tool that otherwise works entirely in real dollars.
3. **Given** a household member with no income streams configured, **When** a projection is run, **Then** the output is identical to the same scenario run before this feature existed.

---

### User Story 2 - Model a term-certain annuity (Priority: P2)

A household member holds an annuity contract that pays out only for a fixed number of years (e.g., a 10-year period-certain annuity), and wants the projection to stop counting that income once the term ends.

**Why this priority**: Annuities with defined payout windows are a distinct, common case from lifetime pensions and require the optional end-age boundary to be honored correctly — this is called out explicitly in the originating issue.

**Independent Test**: Configure a stream with both a start age and an end age, run a projection spanning years before, during, and after that window, and confirm the income appears only for years within the window.

**Acceptance Scenarios**:

1. **Given** an annuity of $15,000/year configured from age 65 through age 74 (inclusive), **When** a projection is run for ages 64, 65, 74, and 75, **Then** the annuity contributes $0 at age 64, its full (inflation-adjusted per its mode) amount at ages 65 and 74, and $0 at age 75.
2. **Given** a household with two members who each have their own annuity with different start/end windows, **When** a projection is run, **Then** each member's annuity is tracked and applied independently based on that member's own age each year.

---

### User Story 3 - Model phased-retirement earned income (Priority: P3)

A household member plans to keep working part-time for a few years after their primary retirement date and wants that salary counted as taxable income during the plan, without needing to model it as an account withdrawal.

**Why this priority**: Useful and explicitly requested, but a smaller slice of the target audience than pensions/annuities, and — per the Assumptions below — this iteration does not model payroll tax, so its accuracy bar is lower than the P1/P2 stories.

**Independent Test**: Configure an earned-income stream ending before the member's Social Security claiming age, run a projection, and confirm the income is included as ordinary taxable income only in the years before it ends.

**Acceptance Scenarios**:

1. **Given** a member with $25,000/year of fixed-nominal earned income from age 63 through age 66, **When** a projection is run for ages 63-66 and 67+, **Then** the earned income is included in ordinary taxable income for ages 63-66 and excluded from age 67 onward.

---

### Edge Cases

- A stream's `start_age` equals the member's `current_age` at scenario start: the stream MUST pay starting in the first plan year.
- A stream has no `end_age`: it MUST continue paying for every remaining plan year (a lifetime stream), matching how `ss_annual_benefit` behaves once claimed.
- Two or more streams overlap in years for the same member (e.g., a pension and phased-retirement earned income both active at once): all of them MUST be included and summed, independently of each other.
- A member has zero configured streams: behavior MUST be unchanged from before this feature (empty list is the default and existing scenarios do not set it).
- `end_age` configured earlier than `start_age`, or a negative/zero `annual_amount`: the scenario MUST be rejected by validation with a clear error, the same way other malformed scenario inputs are rejected today.
- A stream's window ends in the same plan year a member's configured `predicted_death_age` (017/018) takes effect: the stream is treated like any other income source for that year — no special interaction is required beyond the existing post-death spending/filing-status handling.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow each household member to be configured with zero or more income streams; a scenario with no streams configured for any member MUST behave exactly as it did before this feature existed.
- **FR-002**: Each income stream MUST specify: a type (`pension`, `annuity`, or `earned_income`), a start age, an optional end age, an annual amount (expressed in today's dollars as of the scenario's start year, the same convention used elsewhere in the scenario), and an inflation-adjustment mode of either `cola_adjusted` or `fixed_nominal`.
- **FR-003**: For every plan year in which a member's age falls within a stream's active window (`start_age` through `end_age` inclusive, or `start_age` onward indefinitely when no `end_age` is set), that stream's gross amount for that year MUST be included in household income for tax and cash-flow purposes.
- **FR-004**: A `cola_adjusted` stream MUST pay exactly its configured `annual_amount` (today's dollars), unadjusted, for every year it is active — this tool already works entirely in real, inflation-adjusted terms with no separate nominal-dollar projection (the same convention applied to federal tax brackets, Social Security PIA, and every other input), so a cost-of-living-adjusted income source is, in that convention, simply flat.
- **FR-005**: A `fixed_nominal` stream — one that does NOT keep pace with inflation, unlike `cola_adjusted` — MUST have its real (today's-dollar) amount erode over time relative to its configured `annual_amount`, using a documented, cited planning inflation-rate assumption compounded from the scenario's start year. This is the one place this tool needs an explicit inflation-rate figure, since a non-COLA payment cannot otherwise be distinguished from a COLA'd one in an all-real-dollar engine.
- **FR-006**: Pension, annuity, and earned-income stream amounts MUST be fully included in household ordinary taxable income (federal and state) for every year they are active — unlike Social Security, none of a stream's amount is excluded via a provisional-income test.
- **FR-007**: This feature does NOT compute or apply payroll/self-employment tax (FICA/SECA) on `earned_income` streams; such income is modeled purely as ordinary taxable income (see Assumptions).
- **FR-008**: Each income stream's gross amount MUST be surfaced in year-by-year reporting output, broken out by member and by stream, consistent with how Social Security benefits are already surfaced (015-per-account-projection-detail).
- **FR-009**: System MUST validate, for every configured stream, that `end_age` (when set) is greater than or equal to `start_age` and that `annual_amount` is not negative, rejecting the scenario with a clear validation error otherwise — consistent with existing scenario validation behavior.
- **FR-010**: A member MUST be able to have multiple income streams of any mix of types simultaneously; their applicable amounts for a given plan year MUST be summed into that member's and the household's income for that year.
- **FR-011**: Income streams MUST be included consistently across every projection mode a household can run through — the single deterministic projection, strategy comparison, and Monte Carlo simulation — so results are consistent across engines for the same configured inputs.

### Key Entities

- **Income Stream**: A generic fixed (optionally inflation-adjusted) income source belonging to one household member — a pension, an annuity payout, or phased-retirement earned income. Attributes: type, start age, optional end age, annual amount (today's dollars), inflation-adjustment mode. Feeds into the same household ordinary-income total that Social Security and account withdrawals already feed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A household with any combination of pension, annuity, and phased-retirement earned-income streams can be fully modeled through the tool's existing scenario configuration, with no workaround (e.g., artificially inflating withdrawal assumptions) needed to approximate that income.
- **SC-002**: For 100% of plan years in acceptance testing, a configured stream's gross amount matches its expected value exactly, for both `cola_adjusted` and `fixed_nominal` modes, and is $0 outside its configured active window.
- **SC-003**: Every existing scenario (none of which configure income streams) produces output identical to its pre-feature result after this feature ships.
- **SC-004**: A household's income-stream configuration produces consistent income totals whether viewed through the single-path projection, the strategy comparison view, or the Monte Carlo simulation, for the same underlying inputs.

## Assumptions

- Payroll/self-employment tax (FICA/SECA — Social Security and Medicare payroll tax) on `earned_income` streams is explicitly out of scope for this iteration; that income is modeled purely as ordinary taxable income, consistent with the originating issue's "at minimum" bar of pensions and annuities. A follow-on issue can add payroll-tax modeling later if needed.
- `annual_amount` is expressed in the scenario's "today's dollars" convention (the same convention used for `ss_annual_benefit` and spending inputs), not in the dollars of the year the stream starts paying. `fixed_nominal` erosion compounds from the scenario's start year, not from the stream's own `start_age` — a stream that hasn't started paying yet still loses the same real value while waiting, matching how its nominal dollars would actually behave.
- The inflation rate used to erode `fixed_nominal` streams is a planning assumption (this tool's first), not a government-published rate the way tax brackets or RMD divisors are — it will therefore ship marked as needing verification, the same way another already-shipped, not-yet-fully-verified figure (the Joint Life RMD table) is handled today, rather than silently presented as settled.
- Income streams are configured per household member, not pooled at the household level, mirroring how Social Security benefits are already modeled per member.
- No automatic survivor/joint-and-survivor continuation is modeled for pension or annuity streams (e.g., no automatic reduction to a 50% survivor benefit on the owning member's death); a household that wants survivor pension income should model it as a second, independent stream. This mirrors the existing scope boundary already documented for non-SS income in 018-survivor-scenario-projection.
- No regulatory caps (e.g., IRC §415(b) defined-benefit limits) are modeled — the configured `annual_amount` is taken as given, the same way other user-provided scenario inputs are trusted as given.
