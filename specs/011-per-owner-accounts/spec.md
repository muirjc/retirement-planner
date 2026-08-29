# Feature Specification: Per-Owner Account Attribution

**Feature Branch**: `011-per-owner-accounts`

**Created**: 2026-08-29

**Status**: Draft

**Input**: User description: "Per-owner account attribution. Extend the scenario schema so every Account is attributed to exactly one household member (owner), not just held at the household level. Traditional, Roth, and taxable accounts are all individually owned (no joint accounts). This lets downstream engines (RMD calculation, withdrawal sequencing, Roth conversion, comparison projection, Monte Carlo simulation, reporting) compute each member's Required Minimum Distribution against that member's own traditional balance and own age, instead of the current documented simplification (specs/004-strategy-comparison-layer/research.md §4) that deems the older household member the owner of the household's entire traditional balance. The Streamlit UI's account-entry form must let the user pick an owner per account (dropdown of household members) instead of only entering a single combined total. The BFF API's scenario create/update/read schemas must carry the per-account owner field. Existing single-owner scenarios (single filers) are unaffected in behavior. For married-filing-jointly scenarios, this replaces the deemed-owner approximation with accurate per-member RMD computation while preserving each account type's existing withdrawal-sequencing and Roth-conversion behavior at the household level. Migration of existing saved scenario YAML files that have no owner field is in scope: define and implement a clear, documented migration/validation behavior rather than a silent default guess."

**Scope note**: `specs/004-strategy-comparison-layer/research.md` §4 records this exact gap as a deliberate, documented simplification: `001`'s `Scenario.accounts` has no per-owner split, so the full-horizon projection attributes the entire traditional balance to the older household member (`deemed_rmd_owner`) for RMD purposes, "conservative" but not accurate. `003`'s `compute_rmd()` is already genuinely per-member — it takes a member's own age and own traditional balance as separate arguments — so the gap is entirely upstream, in how `001` captures and every downstream feature (`003`–`008`) consumes account data. This feature closes that gap by attributing every account to one household member at data-entry time; it does not change how RMDs are calculated once a correct per-member balance is available (`003` already does that correctly), and it does not introduce joint account ownership.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Accurate RMDs for a married couple with unequal ages and balances (Priority: P1)

A user modeling a married-filing-jointly household where each spouse holds their own traditional retirement account (different balances, different ages, and therefore different RMD-required-starting years) sees the tool compute each spouse's Required Minimum Distribution from that spouse's own account and own age — not a single combined figure attributed entirely to whichever spouse happens to be older.

**Why this priority**: This is the accuracy gap driving the whole feature. Today, a younger spouse's RMD-required starting year is silently ignored (or a smaller-balance older spouse is charged an RMD sized to the whole household's traditional balance), which can materially misstate the household's tax bill and the year money is forced out of tax-deferred accounts — exactly the kind of silently-absorbed simplification Principle I (Accuracy Over Cleverness) forbids presenting as settled.

**Independent Test**: Can be fully tested by configuring a two-member household where each member owns a separate traditional account of a different size, with ages far enough apart that only one member has reached the RMD-required starting age in a given plan year, and confirming the tool reports an RMD for that member only, sized to that member's own account balance.

**Acceptance Scenarios**:

1. **Given** a married household where spouse A (older) and spouse B (younger) each own a separate traditional account with different balances, **When** the tool computes a plan year in which only spouse A has reached the RMD-required starting age, **Then** the reported RMD reflects spouse A's own account balance only, and no RMD is computed against spouse B's account.
2. **Given** the same household in a later plan year where both spouses have reached the RMD-required starting age, **When** the tool computes that plan year, **Then** each spouse's RMD is computed independently from that spouse's own account balance and own age, and the household total is their sum.
3. **Given** a married household where both spouses are the same age but hold traditional accounts of different sizes, **When** the tool computes a plan year in which both have reached the RMD-required starting age, **Then** each spouse's RMD is sized to their own balance, not an even split or a single combined figure.

---

### User Story 2 - Assign an owner to each account while entering scenario data (Priority: P2)

A user entering or editing a household's accounts in the planning tool picks, for each account, which household member owns it — instead of entering only a single combined balance per account type for the whole household.

**Why this priority**: Per-member RMD accuracy (User Story 1) is impossible unless the tool actually captures which member owns which account; this is the data-entry capability that makes it possible, so it's the necessary second step, not independently valuable on its own.

**Independent Test**: Can be fully tested by creating a two-member household, adding an account, and confirming the owner can be chosen from that household's actual members (not a free-text field, and not silently defaulted).

**Acceptance Scenarios**:

1. **Given** a household with two members, **When** a user adds a new account, **Then** the user is required to choose exactly one of that household's members as the account's owner before the account can be saved.
2. **Given** a household with a single member, **When** a user adds a new account, **Then** the account is automatically and unambiguously attributed to that sole member, with no extra step required of the user.
3. **Given** a user editing a household's membership (e.g., correcting a name), **When** an existing account's owner no longer matches any current household member, **Then** the tool flags this account clearly rather than silently keeping a stale attribution.

---

### User Story 3 - Existing saved scenarios are handled explicitly, not silently guessed (Priority: P3)

A user who opens a scenario they saved before this feature existed sees a clear, specific explanation that account ownership is now required and how to supply it — never a scenario that loads normally but has silently guessed which member owns which account.

**Why this priority**: Silently guessing ownership for pre-existing data would produce exactly the kind of unverified simplification Principle I forbids, and could misstate a real household's RMD picture without the user ever knowing a guess was made. This depends on User Stories 1 and 2 already existing (there must be a real ownership field to be missing from), so it is correctly sequenced last, but it is not optional — shipping without it would leave every current user's saved scenario in an undefined state.

**Independent Test**: Can be fully tested by loading a scenario file saved in the format that predates this feature (accounts with no owner field) and confirming the tool surfaces a specific, actionable message rather than proceeding with a guessed or empty attribution.

**Acceptance Scenarios**:

1. **Given** a saved scenario file with one or more accounts that have no owner recorded, **When** the tool loads that scenario, **Then** it reports a specific, actionable validation problem identifying which account(s) need an owner, rather than silently assigning one or proceeding as if the field were optional.
2. **Given** the same scenario, **When** the user supplies an owner for every account and re-saves it, **Then** the scenario loads and produces results normally from then on.
3. **Given** a single-filer scenario saved before this feature existed, **When** the tool loads it, **Then** every account is automatically and correctly attributed to the sole household member with no action required from the user (single-filer households are unambiguous by construction).

---

### Edge Cases

- What happens when an account's recorded owner is a name that does not match any current household member (e.g., after a household member is renamed or removed)? The tool must flag this as a specific validation problem, not silently drop the account or reattribute it.
- What happens for a single-filer household? Every account has exactly one possible owner, so ownership is unambiguous and requires no additional user decision at any point (data entry, migration, or editing).
- What happens when a married household member has zero traditional balance across all their owned accounts? That member's RMD must be computed as zero for that member, independent of their spouse's balance or age.
- What happens when a couple's real-world account is legally joint (e.g., a joint taxable brokerage account)? This feature does not model joint ownership; the user attributes it to one member as a data-entry choice, consistent with every account type being individually owned.
- What happens to a scenario comparison or simulation run's reproducibility (Principle II) once ownership data is added? Given the same scenario file and the same seed, results must remain identical on every run, exactly as before this feature.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow exactly one household member to be designated as the owner of each account (traditional, Roth, or taxable) — no account may be unowned or jointly owned.
- **FR-002**: The system MUST reject an account whose designated owner does not match one of the scenario's current household members, with a specific, actionable message identifying the affected account.
- **FR-003**: For a single-member (single-filer) household, the system MUST attribute every account to that sole member automatically, requiring no additional owner selection from the user.
- **FR-004**: When computing Required Minimum Distributions for a plan year, the system MUST compute each household member's RMD using only that member's own traditional-account balance(s) and own age.
- **FR-005**: The system MUST no longer attribute a household's entire traditional balance to a single "deemed owner" member for RMD purposes once per-account ownership data is available.
- **FR-006**: The system MUST NOT silently assign, guess, or default an owner for a saved scenario that predates this feature and has accounts with no recorded owner (other than the unambiguous single-member case in FR-003); it MUST instead surface a specific validation problem identifying every affected account.
- **FR-007**: The scenario-entry interface MUST let a user choose an account's owner from the household's actual configured members (not free-text entry), for every account type.
- **FR-008**: The system's scenario data contract (however scenarios are created, read, or updated) MUST carry each account's owner as part of that account's data, so no caller of that contract can create or read an account without an owner.
- **FR-009**: A single-member household's computed results (RMDs, withdrawals, tax, comparisons, simulation outcomes) MUST be identical, before and after this feature, for every existing reference scenario — this feature MUST NOT change single-filer behavior.
- **FR-010**: Every account-ownership validation problem this feature introduces MUST use the tool's existing validation-severity discipline (blocking vs. warning), consistent with how every other scenario validation problem is already surfaced.

### Key Entities

- **Account**: A single balance bucket (traditional, Roth, or taxable), extended by this feature to carry exactly one owner — a reference to one of the household's members. Previously held no owner information at all.
- **Household Member**: A person in the household (unchanged by this feature) — now also the referent every account's owner field points to.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a married household where each spouse owns a separate traditional account and reaches the RMD-required starting age in different plan years, the tool reports each spouse's RMD beginning in that spouse's own correct year, sized to that spouse's own account balance only, in 100% of scenarios structured that way.
- **SC-002**: 100% of scenario files saved before this feature that have any account missing owner data produce a specific, actionable message identifying the affected account(s) — none load silently with a guessed attribution.
- **SC-003**: A user can assign an owner to an account in a single choice at the point of entering that account's other data (no separate screen or multi-step detour).
- **SC-004**: Every existing single-filer reference scenario produces identical simulation, comparison, and reporting results before and after this feature ships.

## Assumptions

- Every account is individually owned by exactly one household member; no account type supports joint ownership, per the decision that drove this feature's scope (a couple's real-world joint account is attributed to one member as a data-entry choice — see Edge Cases).
- Whether withdrawal sequencing and Roth conversion continue to operate on household-level pooled balances per account type, or move to per-member balances now that ownership data exists, is a technical design question left to the planning phase's research — this specification requires only that per-member RMD accuracy (User Story 1) is achieved; it does not mandate a specific pooling behavior for withdrawals or conversions.
- The exact mechanism for handling scenarios saved before this feature (e.g., a blocking validation error prompting the user to re-enter ownership, versus an assisted migration step) is a planning-phase design decision; this specification requires only that no such scenario is silently guessed or reattributed (FR-006, SC-002).
- This feature changes how account data is captured and attributed; it does not change the RMD calculation itself (`003-retirement-account-mechanics`'s `compute_rmd()` already computes correctly per member) or introduce any new tax rule, figure, or citation requirement.
