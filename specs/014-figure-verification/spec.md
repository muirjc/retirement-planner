# Feature Specification: Figure Verification (Placeholder Tax Figures)

**Feature Branch**: `014-figure-verification`

**Created**: 2026-08-30

**Status**: Draft

**Input**: User description: "specs/014-figure-verification/" — plan the work for rp-9wi
("Verify all unverified placeholder SourcedFigures against primary sources"),
covering the 8 figures a real run against scenario B surfaced with
`verified=False`: `federal_brackets_mfj`/`_single`, `hsa_contribution_limits`,
`irmaa_tiers_mfj`/`_single`, `niit_rate`, `niit_threshold_mfj`/`_single`,
`rmd_start_age`, `ss_provisional_income_thresholds_mfj`/`_single`, and
`uniform_lifetime_table`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Statutory figures re-verified (Priority: P1)

A user reviewing a projection's Verification Indicator sees that the
Net Investment Income Tax (NIIT) rate/thresholds and the Social Security
taxability thresholds are backed by a specific, cited statute rather than
flagged as unverified placeholders.

**Why this priority**: These figures are fixed by statute and have not
changed since enactment, so confirming them is the lowest-risk, highest-
confidence win — it removes 5 of the 8 flagged figures from the
Verification Indicator without touching any computed output, establishing
the pattern the rest of this feature follows.

**Independent Test**: Run a projection that exercises NIIT and Social
Security taxability; confirm the Verification Indicator no longer lists
`niit_rate`, `niit_threshold_mfj`, `niit_threshold_single`,
`ss_provisional_income_thresholds_mfj`, or `ss_provisional_income_thresholds_single`
as unverified, and that the computed tax amounts are unchanged from before
(these figures were already numerically correct — only their sourcing was
unconfirmed).

**Acceptance Scenarios**:

1. **Given** a scenario whose income exceeds the NIIT threshold, **When** a
   projection is run, **Then** the NIIT figures used are marked verified and
   cite the specific statutory subsection, with the surtax amount unchanged
   from the prior run.
2. **Given** a scenario claiming Social Security benefits, **When** a
   projection is run, **Then** the provisional-income threshold figures used
   are marked verified and cite the specific statutory subsection, with the
   taxable Social Security amount unchanged from the prior run.

---

### User Story 2 - Current-year figures re-verified against published tables (Priority: P2)

A user reviewing a projection's Verification Indicator sees that the
federal income tax brackets, IRMAA (Medicare surcharge) tiers, and HSA
contribution limits are backed by a specific, cited government publication
for a named year, with any previously-placeholder dollar figures corrected
to match that publication.

**Why this priority**: These figures are published annually by the
government and were entered as round-number stand-ins during development;
confirming them (and correcting any placeholder that doesn't match the real
published figures) removes the 3 largest sources of unverified-figure risk
from the indicator, but carries a real chance of changing computed tax and
surcharge amounts where a placeholder was wrong — worth doing only after
User Story 1 has proven out the verification workflow on figures where no
such change is possible.

**Independent Test**: Run a projection that exercises federal brackets,
IRMAA, and HSA eligibility; confirm the Verification Indicator no longer
lists any of these figures as unverified, and that each figure's cited
source names a specific year and publication (not "pending verification").

**Acceptance Scenarios**:

1. **Given** a scenario with taxable income in every bracket, **When** a
   projection is run, **Then** the federal bracket figures used are marked
   verified, cite a specific IRS revenue procedure and year, and reflect
   that publication's actual thresholds.
2. **Given** a scenario with Medicare-enrolled members above the lowest
   IRMAA tier, **When** a projection is run, **Then** the IRMAA tier figures
   used are marked verified and cite a specific CMS.gov table and year.
3. **Given** a scenario with HDHP-eligible members, **When** a projection is
   run, **Then** the HSA contribution limit figures used are marked verified
   and cite a specific IRS revenue procedure and year.

---

### User Story 3 - RMD start age's scheduled 2033 change is modeled (Priority: P3)

A user running a projection that spans the year 2033 or later sees the
Required Minimum Distribution (RMD) start age used in that later year
reflect the law's actual scheduled increase, instead of the same
placeholder age being silently applied to every year of the projection.

**Why this priority**: This is the one figure the underlying law itself
says will change on a known future date — treating it as a flat forever
value isn't just an unconfirmed citation (like User Stories 1-2), it's a
known-wrong simplification for any projection that reaches 2033, so it
needs a schedule, not just a citation update.

**Independent Test**: Run a projection for a household whose members turn
73 both before and after 2033; confirm the earlier RMD start uses today's
age and the later one uses the increased age, and the Verification
Indicator marks the RMD start age figure verified with a citation to the
specific statute and its amending act.

**Acceptance Scenarios**:

1. **Given** a household member turning the current RMD start age before
   2033, **When** their first RMD year is computed, **Then** the age used
   matches today's law.
2. **Given** a household member turning the current RMD start age in or
   after 2033, **When** their first RMD year is computed, **Then** the age
   used matches the increased age scheduled to take effect in 2033.

---

### User Story 4 - RMD divisor table corrected and fully covered (Priority: P4)

A user running a projection for a household member of any age from RMD
start through the oldest age the projection models sees a Required Minimum
Distribution computed from the actual published IRS divisor for that exact
age, not a placeholder value or a lookup gap for ages the current table
doesn't cover.

**Why this priority**: Lowest priority because it's the most work (every
existing divisor needs cross-checking, not just the citation, following the
precedent where a sibling table's placeholder values turned out to be
measurably wrong) and the table's current gap only bites long-horizon
projections reaching the oldest ages — a real but narrower audience than
User Stories 1-3.

**Independent Test**: Run a projection for a household member aged 100+
who has no spouse-beneficiary exception; confirm an RMD is computed (no
lookup failure) using a divisor that matches the published IRS table for
that exact age, and that the Verification Indicator marks the table
verified.

**Acceptance Scenarios**:

1. **Given** a household member at an age already covered by today's
   table, **When** their RMD is computed, **Then** the divisor used matches
   the published IRS table for that age (correcting it if today's
   placeholder value differs).
2. **Given** a household member at an age beyond today's table's coverage
   (over 100), **When** their RMD is computed, **Then** a divisor is found
   (no error) and matches the published IRS table for that age.

---

### Edge Cases

- What happens when a projection spans years both before and after the
  2033 RMD start-age change for the same household member (e.g., they turn
  the pre-2033 age in 2032 but their spouse turns it in 2034)? Each
  member's own applicable-year lookup must apply independently.
- What happens when a projection reaches an age beyond even the corrected
  RMD divisor table's top-covered age? The system's existing behavior for
  "no entry for this key" (a clear, typed error rather than a silent
  fallback) is unchanged by this feature — this feature only shrinks how
  often that gap is hit, per the published table's actual top age.
- What happens when a corrected real-year figure (User Story 2) differs
  from the previously-placeholder value enough to change a household's
  headline result (e.g., success rate, a recommended state)? That's an
  expected, intended consequence of replacing a wrong number with a right
  one — not a defect to guard against — and should be visible in the
  Verification Indicator's history/diff, not silently absorbed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST source the NIIT rate and both NIIT MAGI
  thresholds from the specific U.S. Code subsection that fixes them, mark
  them verified, and show that citation wherever the figure's source is
  displayed.
- **FR-002**: System MUST source both Social Security taxability
  (provisional-income) threshold pairs from the specific U.S. Code
  subsections that fix them, mark them verified, and show that citation
  wherever the figure's source is displayed.
- **FR-003**: System MUST source the federal income tax bracket tables
  (both filing statuses) from a specific, named IRS revenue procedure for
  a specific year, correcting any figure that does not match that
  publication, and mark them verified with that citation.
- **FR-004**: System MUST source the IRMAA tier tables (both filing
  statuses) from a specific, named CMS.gov publication for a specific
  year, correcting any figure that does not match that publication, and
  mark them verified with that citation.
- **FR-005**: System MUST source the HSA contribution limits (self-only,
  family, catch-up) from a specific, named IRS revenue procedure for a
  specific year, correcting any figure that does not match that
  publication, and mark them verified with that citation.
- **FR-006**: System MUST use today's RMD start age for any RMD first
  triggered before 2033, and the age scheduled to take effect in 2033 for
  any RMD first triggered in 2033 or later, sourced from the statute and
  the specific act that amended it, and mark the figure verified.
- **FR-007**: System MUST compute RMDs using divisor values that match the
  published IRS Uniform Lifetime Table for every age from RMD start through
  the oldest age the table publishes, correcting any age already covered
  whose current value doesn't match, extending coverage to every age the
  publication covers, and mark the table verified with that citation.
- **FR-008**: For each of the 8 figures in scope, the Verification
  Indicator MUST stop listing that figure as unverified once its citation
  and correctness have been confirmed against the primary source named in
  FR-001-FR-007.
- **FR-009**: Where a figure in scope turns out to be genuinely
  time-varying within the projection horizon (as with the RMD start age's
  2033 step, FR-006), that variation MUST be modeled as a real schedule —
  never verified as a single flat value that silently ignores its own
  known future change.

### Key Entities

- **SourcedFigure**: An externally-sourced number or table the engine
  relies on (a tax rate, a bracket table, an age threshold, a divisor
  table) — carries a citation, a last-verified date, and a verified
  flag. This feature changes 8 existing instances' citation and verified
  status (and, for two of them, their underlying schedule), and adds
  none.
- **Verification Indicator**: The existing report-facing signal (from
  006-reporting-aggregation) that surfaces which SourcedFigures a given
  run relied on were still unverified. This feature is measured by what
  it removes from that indicator's output, not by anything new added to
  it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Re-running the scenario that originally surfaced this work
  (scenario B) shows 0 of these 8 figures listed as unverified by the
  Verification Indicator, down from 8.
- **SC-002**: Every one of the 8 figures' citations names a specific
  source document (statute subsection, revenue procedure, or publication)
  and, where applicable, a specific year — none read as "placeholder" or
  "pending verification" language.
- **SC-003**: A projection for a household member reaching RMD age in
  2033 or later uses the increased start age, not the age that applies
  before 2033 — verifiable by comparing the first RMD year computed for
  otherwise-identical members born far enough apart to straddle the change.
- **SC-004**: A projection for a household member aged 100 or older
  produces an RMD (not a lookup error) using the correct published
  divisor for that exact age.
- **SC-005**: Every figure correction that changes a previously-placeholder
  number is traceable to the specific primary-source figure it now matches
  — a reviewer can compare old vs. new value against the cited source and
  see why it changed, not just that it changed.

## Assumptions

- The 8 figures named in this spec are exactly the set rp-9wi's own
  description and children enumerate; a figure verification finding
  surfacing later against a different scenario is out of scope for this
  feature and would be tracked as its own follow-on work.
- "Current year" for the figures verified against an annually-published
  source (federal brackets, IRMAA tiers, HSA limits) means the most recent
  year with an actual published primary source available at implementation
  time — this feature does not mandate a specific calendar year up front.
- The RMD start age's 2033 change is modeled as a step keyed by the
  calendar year an RMD first applies, not by the household member's birth
  year. The law's actual rule additionally varies by birth-year cohort
  (someone born earlier may have already been subject to an even earlier
  start age); modeling that finer birth-year distinction is explicitly
  out of scope for this feature and would be its own follow-on work.
- The RMD Joint Life and Last Survivor Table (a sibling table to the
  Uniform Lifetime Table covered by User Story 4) is not one of the 8
  figures in scope and is unaffected by this feature.
- Figures already correctly sourced by the current placeholder values
  (i.e., where the underlying number turns out to already match the real
  published figure) still require their citation updated and verified
  flag flipped — "already numerically correct" does not exempt a figure
  from this feature's citation requirement.
