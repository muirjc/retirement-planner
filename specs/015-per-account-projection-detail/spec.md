# Feature Specification: Per-Account Year-by-Year Projection Detail

**Feature Branch**: `015-per-account-projection-detail`

**Created**: 2026-08-30

**Status**: Draft

**Input**: User description: "include by year on the simulation the actual
balances per account. the expected social security amount received, RMD
amounts and withdrawals required from each account." Scoped with the user
to: true per-account granularity (not just per account type); applies to
a Monte Carlo simulation's representative path and to a comparison's
candidates; surfaces as a new table in the Streamlit UI.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See each account's actual year-by-year detail on a simulation result (Priority: P1)

A user who has just run a Monte Carlo simulation for their scenario wants
to see, for one concrete example run, exactly what happened to each of
their accounts each year — not just the household's pooled ending
balance the existing fan chart already shows. They want to see, per
account, per year: the balance, how much Social Security each household
member received, how much RMD was required, and how much was withdrawn.

**Why this priority**: This is the most common way a user reaches this
tool's output (running a single scenario's simulation), and it's the
scenario the request names directly ("on the simulation"). It delivers
the whole feature's value on its own — nothing else needs to exist first.

**Independent Test**: Run a simulation for a scenario with at least two
accounts of the same type (e.g. two traditional accounts owned by
different household members) and at least one household member claiming
Social Security. Confirm the new detail is visible, one row per account
per year, showing that account's balance, RMD amount (traditional
accounts only), and withdrawal amount for that year, plus each claiming
member's own Social Security amount received that year.

**Acceptance Scenarios**:

1. **Given** a completed simulation result, **When** the user views it,
   **Then** they see a year-by-year table with one row per account per
   year, showing that account's balance, its RMD amount (if applicable),
   and the amount withdrawn from it that year.
2. **Given** a household with two members who have both started
   receiving Social Security, **When** the user views a year's detail,
   **Then** they see each member's own benefit amount received that
   year, not just a combined household figure.
3. **Given** an account whose year-by-year balance is derived by
   apportioning a combined total rather than tracked completely
   independently, **When** the user views that account's row, **Then**
   they can tell, at a glance, that this figure is an apportionment
   rather than an independently observed number.
4. **Given** a simulation with thousands of random paths, **When** the
   user views this detail, **Then** it reflects one specific, identified
   example run, not an average or a range — the existing percentile-band
   chart remains the place to see the range.

---

### User Story 2 - See the same year-by-year detail for each candidate being compared (Priority: P2)

A user comparing multiple candidates (states, withdrawal strategies,
conversion strategies, or claiming ages) wants the same per-account,
per-year detail available for each candidate side by side, so they can
see not just which candidate wins on a summary metric but *why* — e.g.
which account absorbed a given year's withdrawal, or how a claiming-age
choice changed a specific member's Social Security income.

**Why this priority**: Builds directly on User Story 1's same detail
concept, applied to a second, already-existing surface. Lower priority
because Compare already delivers its own standalone value (the summary
comparison) without this detail — this closes a gap in Compare rather
than being Compare's core reason to exist.

**Independent Test**: Run a comparison with at least two candidates.
Confirm each candidate has its own, independently viewable year-by-year
account detail, and that one candidate's detail is never mixed into
another's.

**Acceptance Scenarios**:

1. **Given** a comparison with three candidates, **When** the user views
   the results, **Then** each candidate has its own separate year-by-year
   account detail, all visible without losing the side-by-side summary
   comparison that already exists today.
2. **Given** a comparison run via Monte Carlo simulation (as opposed to a
   single deterministic run), **When** the user views a candidate's
   detail, **Then** it reflects one specific, identified example path for
   that candidate, consistent with User Story 1's same rule.

---

### Edge Cases

- What happens when an account's type has a combined household balance of
  zero (e.g., no Roth accounts exist)? No row should be shown for a type
  with no accounts, and nothing should error.
- What happens when a household member owns more than one account of the
  same type? Each of that member's own accounts gets its own row; the
  member's own RMD (an exact, not apportioned, figure per Edge Case 3
  above) is split across their own accounts, with that split itself
  disclosed as an apportionment.
- What happens for an inherited account? Its balance and distribution
  amount are shown exactly as computed — inherited accounts are already
  tracked individually, not apportioned from a combined total, and the
  detail table indicates this different sourcing.
- What happens when a member hasn't started claiming Social Security yet
  in a given year? Their benefit amount for that year shows as zero,
  not missing or blank — consistent with this tool's existing "present
  even when zero" convention (006-reporting-aggregation's own
  precedent).
- What happens if the user asks to view a Monte Carlo path that doesn't
  exist (e.g., a path number beyond how many were actually run)? The
  request is rejected with a clear, specific error rather than silently
  substituting a different path or crashing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For a single identified run (a deterministic candidate, or
  one specific path of a Monte Carlo simulation), the system MUST show,
  per plan year, each account's own balance.
- **FR-002**: For a single identified run, the system MUST show, per plan
  year, each household member's own Social Security benefit amount
  received that year (zero before that member starts claiming).
- **FR-003**: For a single identified run, the system MUST show, per plan
  year, each account's own Required Minimum Distribution amount, where
  applicable (accounts not subject to RMDs show none).
- **FR-004**: For a single identified run, the system MUST show, per plan
  year, the amount withdrawn from each account that year.
- **FR-005**: The system MUST distinguish, per account row, whether that
  account's figures are tracked completely independently or are
  apportioned from a combined total — never presenting an apportioned
  figure as if it were independently observed (constitution Principle
  I — Accuracy Over Cleverness).
- **FR-006**: Where a figure is apportioned rather than independently
  tracked, the apportionment MUST be a fixed, disclosed rule set once
  from the household's starting configuration — never a rule invented
  differently from one year to the next for the same account.
- **FR-007**: For a Monte Carlo simulation, this detail MUST always refer
  to one specific, identified path — never an average or a blend across
  paths, and never computed for every path in a run (only the one path
  actually being viewed).
- **FR-008**: When comparing multiple candidates, each candidate's
  year-by-year account detail MUST be viewable independently of every
  other candidate's, without merging or overwriting one another.
- **FR-009**: Requesting detail for a Monte Carlo path that doesn't exist
  in that run MUST be rejected with a specific, actionable error, never
  silently substituted or crashed on.
- **FR-010**: A household member who owns more than one account of the
  same type MUST have each of those accounts shown as its own row, not
  combined into one.

### Key Entities

- **Account year detail**: One account's record for one plan year —
  which account, its type, its owner, its balance, its RMD amount (if
  any), its withdrawal amount, and whether that record is independently
  tracked or apportioned from a combined total (FR-005).
- **Member Social Security detail**: One household member's own Social
  Security benefit amount received in one plan year.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user viewing any completed simulation or comparison
  result can find, without leaving that result, the year-by-year balance,
  RMD amount, and withdrawal amount for every individual account the
  scenario configured — not just a household-wide combined figure.
- **SC-002**: A user can identify each household member's own Social
  Security benefit amount for any plan year directly from the same view,
  without needing to derive it from other figures.
- **SC-003**: 100% of account rows that are apportioned rather than
  independently tracked are visibly marked as such — a user is never
  shown an apportioned figure indistinguishable from an independently
  observed one.
- **SC-004**: Viewing this detail for one path of a Monte Carlo
  simulation does not measurably slow down a run of that simulation
  itself — the detail is computed only for the path actually being
  viewed, regardless of how many total paths the simulation ran.
- **SC-005**: Comparing multiple candidates shows every candidate's own
  year-by-year account detail without any candidate's figures leaking
  into another's.

## Assumptions

- "Actual balances per account" means each account the scenario
  configures individually (matching the account each has in the
  household's own configuration), not merely a household-wide total per
  account type (traditional/Roth/taxable).
- Every account's own Required Minimum Distribution and Social Security
  detail that this tool's engine already computes per household member
  is treated as ground truth once retained — this feature does not
  change how any dollar amount is computed, only which already-computed
  figures are retained and shown, plus how a combined total is split
  across multiple accounts of the same type when a truly independent
  figure isn't available for that account specifically.
- Where this tool's account model has no independent way to know which
  specific account funded a given year's withdrawal or received a given
  year's Roth conversion (no purchase-date/cost-basis-level tracking
  exists anywhere in this tool), a fixed, disclosed apportionment by each
  account's own starting-balance share is used, established once from
  the scenario's starting configuration and held fixed for the life of
  the run — never re-derived differently year to year.
- A known, accepted limitation: because this tool has no per-member
  tracking of which specific accounts a Roth conversion's destination
  dollars belong to, a conversion could be apportioned across Roth
  accounts in a way that doesn't line up with which household member
  actually converted, when a household's existing Roth accounts aren't
  owned member-for-member the same way its converting traditional
  accounts are. This is inherent to how this tool already models
  withdrawals and conversions today, not something this feature
  introduces or is expected to resolve.
- This feature covers the Streamlit UI only, for this pass — CSV export
  and any change to what the underlying API returns beyond what the UI
  needs are out of scope, and would be considered separately if wanted
  later.
- A "representative path" for a Monte Carlo simulation defaults to the
  first path of that run unless the user chooses a different one to
  view.
