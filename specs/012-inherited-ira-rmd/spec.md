# Feature Specification: Inherited IRA (Already-in-RMD-Status) Modeling

**Feature Branch**: `012-inherited-ira-rmd`

**Created**: 2026-08-29

**Status**: Draft

**Input**: User description: "Model an inherited IRA that is already in Required Minimum Distribution (RMD) status — the original account owner has died on or after their own Required Beginning Date, and the beneficiary must take annual mandatory distributions and fully deplete the account within 10 years of the owner's death (SECURE Act 2.0 10-year rule), as distinct from the tool's existing RMD logic, which only handles a living owner's own RMDs. Builds on the `rp-2cs` design pass recorded in `research.md`/`data-model.md` in this directory."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Correct annual distribution for an inherited account (Priority: P1)

A user is building a retirement plan for a household where one member has inherited a traditional IRA from a parent who had already started taking their own RMDs before dying. The user wants their plan's projected withdrawals, taxes, and balances to reflect the inherited account's own mandatory distribution — sized correctly for an inherited account, not treated as if it were the beneficiary's own retirement account.

**Why this priority**: Without this, the tool either ignores the inherited account's distribution requirement entirely or silently applies the wrong rule (the living-owner Uniform Lifetime Table), producing a plan whose tax and cash-flow projections are wrong in a way the user has no way to detect. This is the core capability the feature exists to deliver.

**Independent Test**: Configure a scenario with one household member and one inherited traditional account (decedent's death year, age at death, and "already taking RMDs" all specified); run a plan projection; confirm the projected withdrawal and tax figures for each plan year include a distribution amount for the inherited account, computed independently of any account the household member owns outright.

**Acceptance Scenarios**:

1. **Given** a scenario with an inherited traditional account whose decedent died after starting their own RMDs, **When** a plan is projected, **Then** each plan year's total withdrawal and tax figures include that account's own required distribution amount, computed using the inherited account's own decedent/beneficiary facts rather than the beneficiary's own age.
2. **Given** a household member who both inherited an account and separately owns their own traditional account, **When** a plan is projected, **Then** the inherited account's balance and required distribution are computed and reported independently of the member's own account — never combined into one pooled balance or one combined distribution figure.

---

### User Story 2 - Mandatory full depletion within 10 years (Priority: P2)

A user's plan includes an inherited account subject to the 10-year rule. The user wants the plan to show that account fully emptied by the 10th year after the original owner's death, regardless of what the year-by-year required distribution amounts alone would otherwise leave behind.

**Why this priority**: The 10-year depletion deadline is a hard legal requirement independent of the annual distribution amount; a plan that never forces the account to zero materially overstates the household's projected assets and understates the taxes actually owed in the deadline year.

**Independent Test**: Configure a scenario with an inherited account and a plan horizon extending past the 10-year deadline; run a plan projection; confirm the account's balance is exactly zero in the deadline year and every year after, and that the deadline year's withdrawal/tax figures reflect the full remaining balance being distributed that year.

**Acceptance Scenarios**:

1. **Given** an inherited account with a computed annual distribution smaller than its remaining balance in the 10th year after the owner's death, **When** that plan year is projected, **Then** the entire remaining balance is distributed that year, not just the computed annual amount.
2. **Given** a plan horizon that extends beyond an inherited account's 10-year deadline, **When** later plan years are projected, **Then** the account contributes zero balance and zero further distributions to every subsequent year.

---

### User Story 3 - Clear rejection of unsupported inherited-IRA cases (Priority: P3)

A user enters an inherited-account scenario the tool does not yet know how to compute correctly — for example, the original owner died before starting their own RMDs, or the beneficiary is a spouse or other beneficiary type entitled to different rules than the 10-year rule. The user wants to be told plainly which case isn't supported, rather than receiving a plan that silently computed the wrong numbers.

**Why this priority**: Presenting a confident-looking wrong number for a case this feature doesn't actually model would be worse than refusing to compute it — it would look authoritative while being financially wrong. This protects the accuracy of every other scenario the tool already handles correctly.

**Independent Test**: Configure a scenario with an inherited account where the decedent had not yet started their own RMDs at death (or where the beneficiary is marked as an eligible designated beneficiary); attempt to validate/run the scenario; confirm the tool reports a specific, human-readable message naming the unsupported case and blocks the plan from running until corrected, rather than producing a plan.

**Acceptance Scenarios**:

1. **Given** an inherited account whose decedent had not started their own RMDs before death, **When** the scenario is validated, **Then** the tool reports a blocking message specifically naming that this case ("owner died before beginning RMDs") is not yet supported.
2. **Given** an inherited account whose beneficiary is classified as an eligible designated beneficiary (spouse or other), **When** the scenario is validated, **Then** the tool reports a blocking message specifically naming that this beneficiary classification is not yet supported.
3. **Given** an inherited account with no designated beneficiary recorded, **When** the scenario is validated, **Then** the tool reports a blocking message consistent with how it already handles a missing owner on any other account.

---

### Edge Cases

- What happens when a household member holds two or more inherited accounts from different decedents at once? Each account's distribution schedule and 10-year deadline must be computed and enforced independently — one account reaching its deadline must never affect another's balance or schedule.
- What happens when an inherited account's balance is already at or near zero before its 10-year deadline (e.g., due to a distribution larger than the computed minimum)? The account should show no further required distribution once its balance reaches zero, and should not be forced to distribute a negative or non-existent amount.
- What happens when the plan horizon ends before an inherited account's 10-year deadline is reached? The account's distributions continue to be computed and enforced for every plan year that falls within the horizon; the deadline year's full-depletion behavior only applies if that year is actually reached within the horizon.
- What happens when the original owner's death year, or the resulting deadline year, falls outside the range of years this tool has documented distribution-table figures for? The tool must report this as an unsupported/unverifiable case rather than silently extrapolating a figure.
- What happens when an inherited account and the beneficiary's own account are both traditional accounts? They must never be pooled together for balance, distribution, or tax purposes — each is tracked and reported separately even though they share the same tax treatment.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow a scenario to designate any account as inherited, recording: the year the original owner died, the original owner's age at death, whether the original owner had already begun their own required distributions before death, the beneficiary's relationship to the original owner, and the beneficiary's classification for distribution-rule purposes.
- **FR-002**: System MUST compute an annual required distribution for an inherited account whose original owner had already begun their own required distributions before death, using a distribution-table method specific to inherited accounts (distinct from the table used for a living owner's own account).
- **FR-003**: System MUST enforce full distribution of an inherited account's entire remaining balance no later than the 10th calendar year following the original owner's death, regardless of the annual amount computed under FR-002 for that year.
- **FR-004**: System MUST track an inherited account's balance, annual required distribution, and depletion deadline entirely independently of any other account — never combining an inherited account's balance with the beneficiary's own account balance, or with a different inherited account's balance, for any computation (distribution sizing, ownership attribution, tax-funding withdrawals, or investment growth).
- **FR-005**: System MUST support a single beneficiary holding multiple inherited accounts from different original owners at the same time, each computed and enforced independently.
- **FR-006**: System MUST identify, and block from computing a plan, any inherited account whose original owner had not yet begun their own required distributions before death — this case is not supported by this feature and must be reported to the user with a specific, actionable message rather than silently computed.
- **FR-007**: System MUST identify, and block from computing a plan, any inherited account whose beneficiary is classified as an eligible designated beneficiary (a spouse, or any other beneficiary entitled to stretch or rollover treatment) — this case is not supported by this feature and must be reported to the user with a specific, actionable message.
- **FR-008**: System MUST require every inherited account to have a designated beneficiary recorded, using the same ownership-attribution rules and blocking-message behavior already applied to every other account in the scenario.
- **FR-009**: System MUST apply the same tax treatment (traditional vs. Roth) to an inherited account as it would to an equivalent non-inherited account of the same type; being inherited MUST NOT change how the account's distributions are taxed.
- **FR-010**: System MUST include every plan year's inherited-account distributions (both the annual amount under FR-002 and, in the deadline year, the full remaining balance under FR-003) in that year's total household withdrawal, tax, and reported-balance figures.
- **FR-011**: System MUST cite a documented, dated source for any distribution-table figures introduced for inherited accounts, and MUST visibly flag any such figure not yet confirmed against a primary source as unverified — consistent with how every other tax or distribution figure in this tool is already sourced and flagged.
- **FR-012**: System MUST identify, and block from computing a plan, any inherited account that is not a traditional (pre-tax) account — this feature computes distributions for inherited traditional accounts only; an inherited Roth or taxable account follows different rules this feature does not yet compute and must be reported to the user with a specific, actionable message rather than silently computed or silently ignored.
- **FR-013**: System MUST reject, with a specific, actionable message, a request for a probabilistic (Monte Carlo-style) simulation run against a scenario containing any inherited account — this feature supports inherited accounts for single-projection and deterministic-comparison results only; probabilistic simulation support is out of scope and must never silently omit an inherited account's distributions from a produced result.

### Key Entities

- **Inherited Account**: An account originally owned by someone who has died, now held by a beneficiary. In addition to everything an ordinary account records (type, balance, current owner), it records who the original owner was in enough detail to compute the correct distribution schedule (year of death, age at death, whether required distributions had already begun) and how the beneficiary is classified for distribution-rule purposes. This feature computes distributions only when the account is a traditional (pre-tax) account (FR-012); an inherited Roth or taxable account is recorded but blocked from computation.
- **Beneficiary Classification**: Categorizes a beneficiary as either a non-eligible designated beneficiary (subject to the 10-year full-depletion rule this feature computes) or an eligible designated beneficiary of one of several kinds (subject to different rules this feature recognizes but does not yet compute), determining which distribution rules apply to their inherited account.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every supported inherited account in a scenario, the plan's projected withdrawal and tax figures include that account's required annual distribution in 100% of the plan years within its 10-year distribution window.
- **SC-002**: Every supported inherited account's projected balance reaches exactly zero no later than the 10th plan year after the original owner's death, in 100% of generated plans that reach that year within the plan horizon.
- **SC-003**: A user who configures an unsupported inherited-account case (original owner died before beginning required distributions, an eligible-designated-beneficiary case, or a non-traditional inherited account) receives a specific, actionable message identifying which case is unsupported before any plan results are produced, in 100% of such cases — never a plan that silently used the wrong rule. A user who requests a probabilistic simulation against a scenario with an inherited account receives an equally specific rejection rather than a result silently missing that account's distributions.
- **SC-004**: A household with two or more inherited accounts from different original owners sees each account's balance and distribution schedule computed with zero cross-account effects — changing one account's facts (e.g., its owner's age at death) never changes another account's computed figures.

## Assumptions

- This feature covers only the case where the original account owner died **on or after** the date they were required to begin their own distributions ("already in RMD status," per this feature's originating design task). An account whose original owner died **before** that date follows different rules (no annual distribution required in years 1–9, only a year-10 deadline) and is explicitly out of scope — the tool records enough data to detect and block this case rather than silently mis-handling it.
- Only the non-eligible-designated-beneficiary case (the SECURE Act 2.0 10-year rule) is computed by this feature. Eligible-designated-beneficiary cases (a surviving spouse, a minor child, a disabled or chronically ill beneficiary, or a beneficiary less than 10 years younger than the original owner) are recognized as distinct, storable data so a future feature can add their computation, but this feature blocks rather than computes them.
- The original owner's death and the beneficiary's inheritance are always modeled as having already happened before a scenario's planning horizon begins. This feature does not model a death occurring during the projected plan itself (e.g., a currently-living household member dying partway through the plan and their account becoming newly inherited).
- A spousal beneficiary who has elected to treat an inherited account as their own (a spousal rollover) is not modeled by this feature — such an account is an ordinary owned account, not an inherited one, and falls outside this feature's scope entirely.
- Roth inherited-account rules (FR-012), multiple-beneficiary or trust/entity-beneficiary accounts, and state-specific tax treatment of inherited accounts are out of scope for this feature.
- Distribution-table figures this feature introduces will initially have partial, illustrative coverage and will be marked as unverified pending confirmation against a primary source, consistent with how this tool's existing distribution and tax tables are already handled.
- This feature's inherited-account support applies to a single deterministic projection and to deterministic strategy comparisons. Probabilistic (Monte Carlo-style) simulation support for scenarios with inherited accounts is out of scope for this feature (FR-013) and is expected as later follow-on work — supporting it correctly requires giving each simulated path its own independent copy of every inherited account's state, a larger extension than this feature's own scope.
- An inherited account is assumed to grow using the same investment return assumption as the rest of the household's accounts; this feature does not model a separate return assumption for an inherited account's own actual investments.
