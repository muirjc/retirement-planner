# Feature Specification: Early-Withdrawal Penalty (Pre-59.5)

**Feature Branch**: `020-early-withdrawal-penalty`

**Created**: 2026-09-01

**Status**: Draft

**Input**: User description: "Early-withdrawal penalty (10%, pre-59.5) for Traditional withdrawals and unseasoned Roth conversion principal (rp-8z0). No reference to 59.5, early-withdrawal penalties, or 72(t)/SEPP anywhere in the codebase. The tool's own reference use case starts household members at ages 58/60 -- squarely pre-59.5 -- while drawing from Traditional IRA/withdrawal sequencing. A real plan at those ages needs either to avoid Traditional-account access before 59.5 or use a SEPP; neither the constraint nor the 10% penalty is modeled or flagged, so a household relying on this tool for an early-retirement bridge could be quietly missing a real cost.

Scope decisions already made during specification (resolved with the user): (1) This feature builds the 10% penalty computation only -- a 72(t)/SEPP substantially-equal-periodic-payment alternative is a materially larger, separate scope (its own IRS-approved calculation methods and modification-penalty rules) and is explicitly out of scope, disclosed as future work. (2) The age check for a household's pooled voluntary Traditional withdrawal uses PER-MEMBER attribution via the engine's existing traditional_ownership_shares (built for 011-per-owner-accounts' RMD attribution) -- each member's own share of a voluntary Traditional withdrawal is checked against that member's own translated age, not a household-level simplification. (3) A related but independent bug was found during specification -- IRMAA surcharges and NIIT surtax are computed and reported (labeled 'paid' in the UI) but never actually deducted from projected account balances -- and was filed separately (rp-yqf) rather than folded into this feature; this feature's own new penalty cost must be correctly funded (actually reduce account balances) from the start, not replicate that gap.

Design approach: a new cited tax module computes a flat 10% penalty on the household's total taxable early-distribution amount for a plan year -- the sum of (a) each household member's own share (via traditional_ownership_shares) of that year's voluntary (non-RMD) Traditional withdrawal, for any member whose translated age is under 59.5, and (b) the year's own unseasoned Roth conversion withdrawal amount already tracked by 019-roth-conversion-ladder's own PlanYearProjection.unseasoned_roth_withdrawal field (which that feature's own documentation explicitly anticipated a future early-withdrawal-penalty feature would consume, rather than re-deriving Roth lot seasoning itself). RMD-mandated Traditional distributions are never subject to this penalty (real IRS rule; also moot in this engine since RMDs never start before age 73, always past 59.5). Inherited-account distributions are never subject to this penalty either (a distinct provision -- the tax applies only to the original account owner's own early access, not a beneficiary's inherited-account distributions, which this engine already tracks as an entirely separate distribution stream). The resulting penalty dollar amount is added to the plan year's actually-funded tax obligation (so it genuinely reduces projected account balances, unlike the separately-filed IRMAA/NIIT gap) and reported on its own new PlanYearProjection/PlanOutcome fields, mirroring IRMAA's/NIIT's own existing reporting shape.

Out of scope: 72(t)/SEPP substantially-equal-periodic-payment modeling; every other real IRC §72(t)(2) exception beyond the age-59.5 test (disability, medical expenses, higher education, first-time homebuyer, health insurance while unemployed, IRS levy, qualified reservist distributions, birth/adoption, terminal illness, disaster relief, and others); the separately-tracked IRMAA/NIIT funding bug (rp-yqf). docs/BRD.md must be updated to describe the modeled behavior and these disclosed remaining gaps."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A projection shows the real cost of an early-retirement Traditional withdrawal (Priority: P1)

A household drawing from a Traditional account before a member turns 59.5 -- exactly the tool's own reference use case, which starts household members at ages 58/60 -- gets a projection that actually reflects the 10% additional tax that voluntary access would trigger in reality, funded like any other tax cost so it genuinely reduces the household's projected balances rather than only appearing as an informational note.

**Why this priority**: This is the entire point of the feature -- without it, the tool silently omits a real, often-material cost for the exact early-retirement scenario it's built to help plan around, which is worse than not offering the number at all because it looks complete while hiding a real risk.

**Independent Test**: Configure a household with a member under 59.5 taking a voluntary (non-RMD) Traditional withdrawal, run a projection, and confirm that plan year's output shows a penalty equal to 10% of that member's own share of the withdrawal, and that the household's ending balance is lower than an otherwise-identical projection with the penalty computation removed.

**Acceptance Scenarios**:

1. **Given** a single-member household whose translated age this plan year is 55, **When** that plan year's withdrawal sequencing draws $20,000 from the Traditional account beyond any RMD amount, **Then** that plan year's penalty equals $2,000 (10% of $20,000), and the plan year's account balances are reduced by that amount in addition to ordinary income tax.
2. **Given** the same household, **When** the withdrawal is instead entirely satisfied by the RMD leg (a member past RMD start age), **Then** no penalty applies to that amount -- an RMD-mandated distribution is never an early distribution.
3. **Given** a married-filing-jointly household where one member is 62 and the other is 55, each owning a distinct share of the household's Traditional balance (`traditional_ownership_shares`), **When** a voluntary Traditional withdrawal is drawn, **Then** only the 55-year-old member's own share of that withdrawal is subject to the penalty -- the 62-year-old member's own share is not, regardless of the household's combined total.
4. **Given** a household member whose translated age this plan year is 60 or older, **When** that member's own share of a voluntary Traditional withdrawal is drawn, **Then** no penalty applies to that member's share.
5. **Given** an inherited account distribution (a beneficiary's own required or forced distribution, tracked entirely independently of the household's pooled Traditional balance), **When** that distribution occurs regardless of the beneficiary's own age, **Then** no penalty applies to it -- this engine's inherited-account distribution stream is never subject to this feature's logic.

---

### User Story 2 - An unseasoned Roth conversion withdrawal is penalized the same way (Priority: P2)

A household running a Roth conversion ladder strategy (019-roth-conversion-ladder) whose withdrawal reaches into a not-yet-seasoned conversion, while at least one member is under 59.5 -- already flagged by that feature -- now also sees the real 10% cost that flagged amount represents, computed as part of the same combined penalty this feature adds.

**Why this priority**: Completes the picture 019 deliberately left open (its own documentation names this feature as the intended consumer of its flag) -- both early-access risks (Traditional and unseasoned Roth principal) are real applications of the identical statutory rule, so a household evaluating a conversion ladder strategy needs both reflected together. P2 because User Story 1 alone already delivers the larger, more commonly-triggered gap (a household without any Roth conversion configured at all still benefits from it).

**Independent Test**: Configure a household with a Roth conversion ladder whose withdrawal reaches into an unseasoned lot while under 59.5 (019's own flag fires), run a projection, and confirm that plan year's penalty includes 10% of the flagged unseasoned amount.

**Acceptance Scenarios**:

1. **Given** a plan year where 019's own `unseasoned_roth_withdrawal` is $8,000 for a household with no other early-distribution exposure that year, **When** this feature computes that year's penalty, **Then** the penalty equals $800 (10% of $8,000).
2. **Given** a plan year with both a $10,000 under-59.5 voluntary Traditional withdrawal and a $5,000 unseasoned Roth withdrawal flagged by 019, **When** this feature computes that year's penalty, **Then** the penalty equals $1,500 (10% of the combined $15,000) -- one combined computation, not two separately-reported penalties.
3. **Given** a household with no Roth conversion configured at all (019's flag is always 0.0), **When** a projection runs, **Then** this feature's own Roth-side contribution is always 0.0, and only the Traditional-side computation (User Story 1) can produce a nonzero penalty.

---

### User Story 3 - The penalty rule is documented and auditable, and its remaining gaps are disclosed (Priority: P3)

A reviewer of this tool can find, next to the code implementing the 10% penalty, the governing statute citation and a last-verified date -- consistent with every other regulated figure this tool already documents. `docs/BRD.md` is updated to describe the modeled penalty and honestly list what remains out of scope: 72(t)/SEPP, every other real statutory exception beyond age 59.5, and the separately-tracked IRMAA/NIIT funding gap.

**Why this priority**: Same auditability principle every other feature's documentation User Story already established for this project. Doesn't block User Stories 1-2 functioning correctly, hence P3.

**Independent Test**: Locate the module implementing the penalty calculation and confirm it carries a citation and last-verified date; read `docs/BRD.md` and confirm it describes the new behavior and its remaining gaps.

**Acceptance Scenarios**:

1. **Given** the implemented penalty calculation, **When** a reviewer inspects it, **Then** it cites the specific statute establishing the 10% additional tax and records a last-verified date, in the same structural pattern as this tool's other cited figures.
2. **Given** the completed feature, **When** a reader reviews `docs/BRD.md`, **Then** it describes the 10% early-withdrawal penalty (covering both voluntary Traditional withdrawals and unseasoned Roth conversion principal) as modeled behavior, and separately lists the disclosed remaining gaps.

---

### Edge Cases

- A household where every member has already reached 59.5: the Traditional-side contribution is always 0.0 for every subsequent plan year, regardless of withdrawal amount -- matching real law exactly (not a simplification).
- A plan year with a $0 voluntary Traditional withdrawal and a $0 unseasoned Roth withdrawal: the penalty is $0.0, and this feature's computation is still run (not skipped) so its own citation/audit trail is consistently present in output, mirroring how NIIT/IRMAA are already computed every year regardless of whether they end up owing anything.
- A `"single"`-filing-status household: the per-member attribution still applies -- it is simply attribution across one member instead of two, not a special case.
- Age precision: this tool tracks each household member's age only in whole years per plan year (no mid-year/birth-month precision anywhere in the engine); the age-59.5 condition is evaluated using this engine's existing convention (established by `018`/`019`): a member whose translated age for a given plan year is 59 or younger is treated as not yet past 59.5, and a member translated to age 60 or older is treated as past it.
- A member with a $0 traditional_ownership_shares entry (owns none of the household's Traditional balance): that member's own share of any voluntary Traditional withdrawal is always $0, so their own age is never load-bearing for the Traditional-side computation regardless of how young they are.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For each plan year, the system MUST determine each household member's own share (via `traditional_ownership_shares`) of that year's voluntary (non-RMD) Traditional withdrawal amount.
- **FR-002**: For each household member whose translated age that plan year is 59 or younger (the Edge Cases age-precision rule), the system MUST include that member's own share (FR-001) in the plan year's taxable early-distribution base; a member whose translated age is 60 or older MUST NOT contribute to it, regardless of the amount withdrawn.
- **FR-003**: The system MUST NOT apply this penalty to any portion of a plan year's Traditional distribution that was drawn to satisfy a Required Minimum Distribution.
- **FR-004**: The system MUST NOT apply this penalty to any inherited-account distribution, regardless of the beneficiary's own age.
- **FR-005**: The system MUST include the plan year's own Roth conversion-ladder unseasoned-withdrawal amount (019-roth-conversion-ladder's existing flag) in the same taxable early-distribution base as FR-002, without re-deriving Roth conversion-lot seasoning or the age condition that already gated that flag.
- **FR-006**: The system MUST compute the plan year's penalty as 10% of the combined taxable early-distribution base (FR-002 + FR-005), as a single combined amount, not two separately-reported penalties.
- **FR-007**: The computed penalty MUST be included in the amount actually funded from the household's accounts that plan year (i.e., it must genuinely reduce projected ending balances), not merely reported informationally.
- **FR-008**: The system MUST report the plan year's own penalty amount, and the projection's cumulative penalty paid across every plan year, on the projection's output -- mirroring the existing IRMAA/NIIT reporting shape (a per-year field and a lifetime-cumulative field).
- **FR-009**: The 10% penalty rate MUST be implemented as a cited, dated figure in this project's existing regulated-figure convention (a named figure with a citation to the specific statute and a last-verified date), the same structural pattern every other regulated figure in this tool already uses.
- **FR-010**: A household whose every member has always been 60 or older throughout the projection's horizon, and which never touches an unseasoned Roth conversion lot, MUST see a penalty of exactly 0.0 for every plan year -- no regression to households this feature doesn't affect.
- **FR-011**: `docs/BRD.md`'s Roth conversion / withdrawal sequencing section (or an appropriately-placed new section) and its list of known limitations MUST be updated to describe the 10% early-withdrawal penalty as modeled behavior, while honestly listing the disclosed remaining gaps: no 72(t)/SEPP alternative, no modeling of any real statutory exception beyond age 59.5, and the separately-tracked IRMAA/NIIT funding gap (not this feature's own scope, tracked as `rp-yqf`).

### Key Entities

- **Taxable Early-Distribution Base**: One plan year's combined amount subject to the 10% penalty -- the sum of every under-59.5 household member's own share of that year's voluntary Traditional withdrawal (FR-001-FR-002) and that year's own unseasoned Roth conversion withdrawal amount (FR-005).
- **Early-Withdrawal Penalty Rate**: A new cited, dated figure describing the flat 10% rate and the statute that establishes it.
- **Plan Year Projection (penalty fields)**: Gains a per-year penalty-owed amount and contributes to a new lifetime-cumulative penalty-paid figure, mirroring IRMAA's/NIIT's own existing reporting shape.

## Assumptions

- 72(t)/SEPP is out of scope (per the scope decision recorded in this spec's Input section) -- a household relying on a real SEPP schedule to avoid this penalty in reality will see this tool report a penalty this feature cannot yet suppress; this is a disclosed simplification, not silently absorbed.
- Every real IRC §72(t)(2) exception beyond age 59.5 (disability, medical expenses exceeding a threshold, higher education expenses, a first-time homebuyer's up-to-$10,000, health insurance premiums while unemployed, an IRS levy, qualified reservist distributions, birth/adoption up to $5,000, terminal illness, disaster relief, and others) is out of scope -- this tool has no data-model concept for any of these circumstances today, and adding one is a materially larger, separately-scoped effort. Documented as a disclosed gap, not silently omitted.
- Per-member attribution of a pooled voluntary Traditional withdrawal uses the household's existing, fixed `traditional_ownership_shares` -- the same attribution 011-per-owner-accounts' own RMD computation already uses for the identical pooled balance, so this feature introduces no new ownership concept, only a new consumer of the existing one.
- This feature's own new penalty cost is correctly funded (added to what actually reduces projected account balances) from the start -- it does not replicate the IRMAA/NIIT funding gap found during this feature's own specification and filed separately (`rp-yqf`). Fixing that pre-existing gap for IRMAA/NIIT themselves is out of scope here.
- `019-roth-conversion-ladder`'s own `unseasoned_roth_withdrawal` field already applies this same age-59.5 condition (household-level, for that feature's own reasons) before this feature ever sees it -- this feature does not re-check age for the Roth-side contribution, only sums the already-gated amount into the combined base.
- This feature changes what a plan year's own output reports and what its own funded withdrawal amount is; it does not change `run_plan_projection()`'s per-year sequence's shape otherwise, does not change RMD, federal/state tax, IRMAA, or NIIT computations themselves, and does not add any new scenario-configurable input (this is an always-on accuracy correction, like RMD or federal tax themselves, not an opt-in feature).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a projection where a household member under 59.5 takes a voluntary Traditional withdrawal, that plan year's penalty equals 10% of that member's own share of the withdrawal, within a small rounding tolerance, in 100% of such configurations, and the household's projected ending balance is correspondingly lower than an identical projection with the penalty removed.
- **SC-002**: In a projection where every household member has reached 59.5 and no unseasoned Roth conversion withdrawal occurs, the penalty is exactly 0.0 for every plan year -- no regression to households this feature doesn't affect (FR-010).
- **SC-003**: In a projection with both a qualifying Traditional withdrawal and an unseasoned Roth conversion withdrawal in the same plan year, the reported penalty equals 10% of their combined amount, with zero deviation.
- **SC-004**: No RMD-mandated distribution or inherited-account distribution ever contributes to the penalty base, in 100% of configurations tested.
- **SC-005**: `docs/BRD.md` no longer omits the 10% early-withdrawal penalty from its description of modeled withdrawal behavior; a reader can find the modeled penalty and its remaining disclosed gaps (72(t)/SEPP, other statutory exceptions, the separate IRMAA/NIIT gap) in one place.
