# Feature Specification: Federal & State Tax Calculation Engine

**Feature Branch**: `002-tax-calculation-engine`

**Created**: 2026-08-27

**Status**: Draft

**Input**: User description: "docs/initial_requirement.md continue with section 2. you can look to the spec 001-scenario-config-management to see what has already been done"

**Scope note**: `docs/initial_requirement.md` describes a five-phase retirement planning tool; feature `001-scenario-config-management` covered §3.1 (the input/configuration layer). This spec covers §3.2 (Tax Engine) — computing federal and state income tax liability for a household in a given tax year, with genuine per-state bracket logic (replacing the prototype's blended-rate approximation), real Social Security taxability rules, and an auditable, per-figure verification/citation trail. It does not cover IRMAA or NIIT (source doc explicitly defers these — "Not in current prototypes" — to a later phase; see Assumptions), account withdrawal/RMD mechanics that produce the income figures this engine consumes (§3.3, a separate future feature), Roth conversion or withdrawal-sequencing strategy selection (§3.4, a separate future feature), or rendering verification flags into charts/reports (§3.6, a separate future feature). This feature is a pure calculator: given a household's income for one tax year, it returns the tax owed and which figures it used are still unverified.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Compute accurate federal tax, including real Social Security taxability (Priority: P1)

A user wants the federal income tax owed on a household's income for a given tax year, computed with genuine progressive bracket math and the actual Social Security taxability rule (0%/50%/85% of benefits included in taxable income depending on provisional income) — not the prototype's flat 85%-inclusion shortcut.

**Why this priority**: Every other capability in this feature (state comparison, verification flags, legislative schedules) sits on top of a correct federal calculation. The source document specifically flags the current flat-85% Social Security approximation as a known accuracy gap; fixing it is the single highest-value, most decision-relevant change, since it changes the federal number every scenario depends on.

**Independent Test**: Can be fully tested by feeding a household's income for a tax year (ordinary income, Social Security gross benefit, filing status) into the calculation and confirming the returned federal tax matches hand-calculated values for a range of published reference cases (low, middle, and high income; below and above each provisional-income threshold).

**Acceptance Scenarios**:

1. **Given** a household's ordinary income, Social Security gross benefit, and filing status for a tax year, **When** federal tax is computed, **Then** the result reflects genuine progressive bracket math against that tax year's thresholds, not a flat-rate shortcut.
2. **Given** a household whose combined income keeps their provisional income below the first Social Security taxability threshold, **When** federal tax is computed, **Then** none of their Social Security benefit is included in taxable income.
3. **Given** a household whose provisional income falls between the first and second thresholds, **When** federal tax is computed, **Then** up to 50% of their Social Security benefit is included in taxable income, per the federal formula.
4. **Given** a household whose provisional income exceeds the second threshold, **When** federal tax is computed, **Then** up to 85% of their Social Security benefit is included in taxable income, per the federal formula — never more.

---

### User Story 2 - Compute state tax through real, pluggable per-state modules (Priority: P2)

A user wants a household's state income tax liability computed using that state's actual rules — genuine bracket-by-bracket math for graduated-bracket states, not the prototype's blended-rate approximation — so that comparing states is based on real numbers.

**Why this priority**: State comparison is one of the tool's three core questions (source doc §1), but a comparison built on a blended-rate shortcut for graduated states isn't decision-grade (source doc §3.2 says so explicitly). This depends on User Story 1's income/taxability handling but is independently valuable and testable once that exists.

**Independent Test**: Can be fully tested by computing tax for the same household income under each state module and confirming each state's result matches a hand-calculated example for that state's actual published rules, without needing verification flags or legislative-schedule handling to be built yet.

**Acceptance Scenarios**:

1. **Given** a household's income and a specific state, **When** state tax is computed, **Then** the result is produced by that state's own module — no state's calculation reuses another state's logic or a shared blended rate.
2. **Given** a graduated-bracket state (South Carolina or Delaware), **When** state tax is computed, **Then** the result reflects genuine bracket-by-bracket math against that state's published brackets, not a single blended rate.
3. **Given** a zero-income-tax state, **When** state tax is computed, **Then** the result is zero.
4. **Given** two households with identical income but different states of residence, **When** state tax is computed for each, **Then** the two results are independent — computing one never affects the other.

---

### User Story 3 - See which figures are unverified, and get correct results across tax years with scheduled law changes (Priority: P3)

A user wants to know, for any tax result, which of the underlying rates/thresholds/exclusion amounts haven't yet been confirmed against a primary source — and wants a tax year with an already-scheduled law change (e.g., Georgia, North Carolina, or Mississippi's rate changes through 2028–2029) to use the correct rate for that specific year, not a single static value frozen at whatever year the module was written.

**Why this priority**: This is the auditability layer on top of Stories 1 and 2 — it matters, but a user can get and act on tax numbers (P1/P2) before every figure carries a citation. Skipping this risks the tool quietly treating a placeholder number as settled fact, which the source document explicitly calls out as unacceptable.

**Independent Test**: Can be fully tested by requesting the citation/verification status of a specific figure used in a computed result, and by computing the same state's tax for two different tax years that fall on either side of a documented rate change, confirming each year's result uses that year's rate.

**Acceptance Scenarios**:

1. **Given** a computed federal or state tax result, **When** a user inspects which figures were used, **Then** every rate, bracket edge, and exclusion amount used is identified along with whether it has been confirmed against a primary source.
2. **Given** a figure that has not yet been confirmed against a primary source, **When** it is used in a computation, **Then** the result carries a visible "needs verification" indicator naming that figure — it is never indistinguishable from a confirmed figure.
3. **Given** a state with a documented, scheduled rate change (e.g., Georgia, North Carolina, or Mississippi through 2028–2029), **When** tax is computed for two different years that fall before and after a scheduled change, **Then** each year's result uses the rate scheduled for that specific year.
4. **Given** a tax year outside any documented schedule for a given figure, **When** tax is computed for that year, **Then** the system refuses to compute that figure and reports which figure and year are unsupported (FR-016), rather than silently guessing.

---

### Edge Cases

- What happens when a household's Social Security gross benefit is zero? Federal taxability calculation should include $0 of benefit in taxable income without error.
- What happens when ordinary income is zero but Social Security benefit is not? Provisional income is still computed from what's present; taxability rules apply normally.
- What happens when a state's module is asked to compute tax for a filing status or household shape (e.g., single vs. married-filing-jointly) that changes which bracket table or exclusion amount applies? The module must select the correct table/amount for the filing status given, not assume MFJ.
- What happens when two different figures used in the same computation have different verification statuses (some confirmed, some not)? Every figure's status is reported independently — one confirmed figure does not "cover" an unconfirmed one, and one unconfirmed figure does not block the computation from returning a result (see FR-011).
- What happens when a state has no income tax at all (e.g., Florida, Tennessee)? Its module returns zero tax without needing bracket or exclusion data, and does not raise unverified-figure flags for figures it doesn't use.
- What happens when the requested tax year predates any documented rate/threshold schedule for a figure? Same policy as a too-far-future year (FR-016): the system refuses and reports it — it never assumes the earliest known year's rate applies retroactively.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST compute federal income tax for a household given its filing status, ordinary income, and Social Security gross benefit for a specified tax year, using genuine progressive bracket math against that tax year's federal thresholds.
- **FR-002**: The system MUST determine how much of a household's Social Security benefit is included in taxable income using the actual federal provisional-income rule (0%, up to 50%, or up to 85% inclusion depending on provisional income thresholds) — never a flat percentage applied regardless of income.
- **FR-003**: The system MUST express federal bracket edges in a single, explicitly documented set of terms (e.g., today's real dollars, consistent with the rest of the tool) rather than leaving the basis for those numbers implicit or undocumented.
- **FR-004**: The system MUST compute state income tax for a household given its filing status, income, ages, state of residence, and tax year, using that state's own rules.
- **FR-005**: Each state's tax calculation MUST be implemented independently of every other state's — no state's result may be produced by reusing another state's bracket table, exclusion amount, or a shared blended-rate shortcut.
- **FR-006**: For a graduated-bracket state, the system MUST compute tax using genuine bracket-by-bracket math against that state's published brackets, not a single blended effective rate. At minimum, this applies to every state named in the reference use case as graduated-bracket (South Carolina, Delaware) — see FR-017 for the rest of the candidate state set.
- **FR-007**: For a zero-income-tax state, the system MUST return zero tax without requiring bracket, exclusion, or citation data for figures that state doesn't use.
- **FR-008**: The system MUST select the correct bracket table and/or exclusion amount for the filing status and ages given, rather than assuming a single filing status or age bracket.
- **FR-009**: Every rate, bracket edge, exclusion amount, or other externally-sourced figure used by the federal or a state calculation MUST carry a citation (source reference) and a last-verified date, and MUST be individually identifiable as "confirmed" or "needs verification."
- **FR-010**: A computed tax result MUST make it possible to identify every figure that was used to produce it, and the verification status of each one.
- **FR-011**: An unconfirmed ("needs verification") figure MUST NOT block a computation from returning a result, and MUST NOT be visually or programmatically indistinguishable from a confirmed figure in that result.
- **FR-012**: A figure whose value is scheduled to change by tax year (e.g., a state's legislated rate change) MUST be defined as a year-to-value schedule, not a single static value, and the system MUST use the value scheduled for the specific tax year requested.
- **FR-013**: The system MUST support computing tax for any tax year a caller specifies, not just a single hardcoded year.
- **FR-014**: The system MUST NOT require network access to compute federal or state tax for any supported tax year.
- **FR-015**: The system MUST report every problem or unusual condition it encounters while computing a result (e.g., a missing figure for a requested year) rather than silently substituting a guessed value — see FR-016 for the specific resolution policy.
- **FR-016**: When a tax year is requested for which a figure has no scheduled value (before the earliest or after the latest year in that figure's documented schedule), the system MUST refuse to compute a result for that figure/year and clearly report which figure and which year are unsupported — it MUST NOT fall back to the nearest documented year's value or otherwise extrapolate silently. A caller that needs coverage for years beyond a documented schedule (e.g., a multi-decade simulation) MUST supply a schedule that explicitly covers those years, with its own documented extrapolation assumption (per FR-009's citation requirement) — this feature does not manufacture that assumption on the caller's behalf.
- **FR-017**: This feature MUST deliver real, working tax modules for: (a) South Carolina and Delaware — the two graduated-bracket states the source document explicitly flags as needing real bracket-by-bracket logic — and (b) at least one zero-income-tax state (e.g., Florida), to exercise the zero-tax behavior required by FR-007 and Acceptance Scenario 2.3. All three conform to the same pluggable module interface (FR-005, SC-006). Modules for the remaining candidate states (GA, NC, TN, MS, PA, NH) are follow-on work against that same interface and are not required for this feature to be considered complete.

### Key Entities

- **Income Components**: The pieces of a household's income for one tax year that tax calculations need — ordinary income (e.g., retirement account withdrawals, wages) and Social Security gross benefit. Supplied by the caller; this feature does not derive these from account balances or withdrawal activity (that belongs to a future account-mechanics feature).
- **Filing Status & Filer Ages**: Household filing status (single or married-filing-jointly) and each filer's age, needed because some states' exclusion amounts and eligibility depend on age, and federal/state bracket tables depend on filing status.
- **Tax Year**: The specific year a computation applies to — determines which scheduled figure values are in effect.
- **Federal Tax Result**: The computed federal tax owed for a household/year, including how much of their Social Security benefit was included in taxable income and which figures were used.
- **State Tax Module**: One state's independent tax calculation, conforming to a common shape (same kind of inputs and outputs as every other state's module) so a new state can be added without changing how any other state — or the federal calculation — works.
- **State Tax Result**: The computed state tax owed for a household/year/state, and which figures were used.
- **Sourced Figure**: Any individual rate, bracket edge, or exclusion amount used in a computation — carries a citation, a last-verified date, a verification status (confirmed / needs verification), and, where the figure changes by law over time, a year-to-value schedule instead of a single value.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Federal tax computed for a range of published reference income scenarios (below, at, and above each Social Security provisional-income threshold) matches hand-calculated values exactly, for both single and married-filing-jointly households.
- **SC-002**: Every graduated-bracket state's tax, computed for at least one hand-calculated reference income scenario, matches that hand calculation exactly — not merely "close" under a blended-rate approximation.
- **SC-003**: 100% of rate/bracket/exclusion figures used in any computed result can be traced to a citation, a last-verified date, and a verification status — none are silently unlabeled.
- **SC-004**: A user can tell, from a single result, whether every figure behind it has been confirmed, in under the time it takes to read one line of output per figure (i.e., without cross-referencing source code).
- **SC-005**: Computing tax for a state with a scheduled rate change, in two different years on either side of that change, produces two different, individually correct results — not the same result applied to both years.
- **SC-006**: Adding a new state's tax module does not require changing the federal calculation or any other state's module — verified by adding one new state after the initial set ships and confirming zero other files needed to change.

## Assumptions

- **Income scope**: "Ordinary income" for this feature covers income types the reference use case actually produces (traditional retirement account withdrawals/RMDs, wages) — Roth withdrawals are excluded because they are federally tax-free by design, consistent with the source document's reference use case. Investment income requiring preferential capital-gains treatment is out of scope for this feature (see NIIT deferral below); if the reference use case later needs it, that's a follow-on feature, not a gap in this one.
- **IRMAA and NIIT are out of scope for this feature.** The source document explicitly marks both as "not in current prototypes" and schedules them for a later phase (Phase 4) distinct from the phase this feature corresponds to (Phase 2's tax-module accuracy work). They will be specified as a separate feature.
- **This feature is a pure calculator, not integrated with the Scenario config layer (`001-scenario-config-management`) yet.** It takes income components, filing status, ages, state, and tax year directly as inputs. A future feature (likely the account-mechanics or simulation-engine work in §3.3/§3.5) is responsible for deriving those inputs from a saved `Scenario` and its account withdrawal activity, and for calling this engine once per simulated year.
- **Verification-flag granularity matches the pattern already established in `001-scenario-config-management`**: a per-figure status (confirmed / needs verification) rather than a single all-or-nothing flag per state, so one unconfirmed exclusion amount doesn't hide the fact that every other figure in the same result is already confirmed.
- **The candidate state set is the nine states named in the source document's reference use case** (FL, GA, NC, SC, TN, MS, PA, NH, DE). This feature delivers real, working modules only for South Carolina, Delaware, and one zero-tax state such as Florida (FR-017); the other six are follow-on work built against the same pluggable interface.
- **No network access is required** to compute a result, consistent with the project constitution's offline-first principle — updating a figure's citation, value, or schedule is a separate, explicit maintenance action, not something a computation triggers.
