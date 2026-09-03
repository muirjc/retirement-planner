# Feature Specification: Year-by-Year Results Walkthrough

**Feature Branch**: `028-results-walkthrough`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "rp-bm8.1 — Templated year-by-year walkthrough of a representative simulation path: a new core reporting module builds a deterministic, plain-language 'story' per plan year for one representative simulated path selected from a Run Simulation result, and a new dedicated Streamlit step-through page presents it. Fully offline, zero new dependencies, fully reproducible given the same seed."

## Clarifications

### Session 2026-09-03

- Q: What should count as a "meaningfully large" year-over-year tax change worth narrating as a driver (FR-003)? → A: Percentage-based — a change of ≥15% in total taxes owed year-over-year triggers the driver.
- Q: How many plan years should the walkthrough page show at once as the user steps through with Next/Previous? → A: A small fixed batch of 3 plan years per screen; a final batch with fewer than 3 remaining years shows just those remaining years.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Step through a representative year-by-year story (Priority: P1)

A user who has just completed a Run Simulation opens a new walkthrough page. Instead of only seeing percentile bands and summary statistics, they see one specific simulated path told out one plan year at a time, in plain language: "In 2041, you began taking Required Minimum Distributions from your Traditional IRA, adding $18,400 to taxable income" — paired with that year's existing numeric detail. They step forward and backward through the years with Next/Previous controls, three plan years at a time, building an intuitive feel for how the plan actually unfolds rather than just its endpoint statistics.

**Why this priority**: This is the entire deliverable of rp-bm8.1 — without it there is no walkthrough feature at all. Every other behavior in this spec (path selection, reproducibility, verification flagging) exists in service of this one journey.

**Independent Test**: Run a simulation, open the new walkthrough page, and step through all plan years of the selected path. Delivers value on its own: a user can understand *why* their plan looks the way it does, year by year, without needing P2's AI rewrite (rp-bm8.2) or any other follow-on work.

**Acceptance Scenarios**:

1. **Given** a completed simulation run with percentile bands, **When** the user opens the walkthrough page, **Then** the page shows the first batch of up to three plan years of one specific simulated path, with a plain-language explanation of each shown year's most notable driver(s) alongside that year's existing numeric detail.
2. **Given** the walkthrough page is showing a batch that is not the last, **When** the user clicks "Next", **Then** the page advances to the next batch of up to three plan years (fewer if less than three plan years remain) and shows each of those years' stories.
3. **Given** the walkthrough page is showing a batch that is not the first, **When** the user clicks "Previous", **Then** the page goes back to the prior batch of up to three plan years and shows each of those years' stories.
4. **Given** the walkthrough page is showing the first batch, **When** the user looks at the controls, **Then** "Previous" is disabled or otherwise unavailable.
5. **Given** the walkthrough page is showing the last batch, **When** the user looks at the controls, **Then** "Next" is disabled or otherwise unavailable.
6. **Given** a plan year in which nothing notable changed from the prior year, **When** the user views that year's story, **Then** the page still shows a story for the year (a plain baseline statement) rather than an empty or broken section.

---

### User Story 2 - Trust that the story matches a specific, reproducible path (Priority: P2)

A user re-runs the exact same scenario configuration with the exact same random seed on a later day (e.g., to check a plan is still on track). They want the walkthrough to select the same representative path and tell the identical story both times, so they can be confident that any difference they see reflects a changed assumption, not run-to-run noise in which path got picked or how it got described.

**Why this priority**: Directly required by constitution Principle II (Reproducibility). Without it, the walkthrough would undermine trust in the whole tool rather than build it — a user cannot tell a changed input from a changed narration.

**Independent Test**: Run the same scenario+seed twice, capture the walkthrough's selected path index and full narrative text both times, and diff them. Testable independently of the UI by calling the underlying reporting functions directly with fixture data.

**Acceptance Scenarios**:

1. **Given** two Run Simulation invocations using an identical scenario configuration and random seed, **When** the walkthrough is built for each result, **Then** both walkthroughs select the same simulated path (by index) and produce byte-identical narrative text for every plan year.
2. **Given** a completed simulation run with multiple simulated paths, **When** the representative path is selected, **Then** it is the path whose final outcome is closest to the run's median (50th-percentile) outcome — not an arbitrary or first-listed path.

---

### User Story 3 - See which numbers in the story are still unverified (Priority: P3)

A user reading a year's story sees a driver that depends on a tax or exclusion figure the tool has flagged elsewhere as not yet verified against a primary source (e.g., a state-specific exclusion amount). They see the same visible "needs verification" indicator on the walkthrough page that they would see anywhere else in the tool, so they don't mistake a provisional figure for a settled one just because it's now presented in narrative form.

**Why this priority**: Required by constitution Principle III (Auditability) — a simplified or unverified figure must never become indistinguishable from a verified one. Lower priority than P1/P2 because the underlying flagging mechanism already exists elsewhere in the tool (`render_verification_indicator`); this story is about not losing that signal in the new surface, not building it from scratch.

**Independent Test**: Run a scenario known to touch at least one currently-unverified figure, open the walkthrough, and confirm the same figure name appears flagged on the walkthrough page as it does on the existing Run Simulation results page.

**Acceptance Scenarios**:

1. **Given** a plan year whose story or numeric detail depends on a figure already flagged unverified elsewhere in the tool, **When** the user views that year on the walkthrough page, **Then** that figure is visibly flagged as unverified on the walkthrough page too.
2. **Given** a plan year whose story and numeric detail depend only on already-verified figures, **When** the user views that year, **Then** no unverified-figure flag is shown for it.

---

### Edge Cases

- What happens for a plan year in which several notable drivers occur simultaneously (e.g., RMDs start in the same year Social Security is claimed)? The story surfaces all of that year's applicable drivers, not just one, per the v1 driver priority list.
- What happens for a deterministic (non-Monte Carlo) run that has no `percentile_bands`? Representative-path selection falls back to the single available path (there is only one path to select).
- What happens if a plan's shortfall (running out of money) occurs partway through the projection? Every shortfall occurrence is always surfaced as a driver (per the v1 priority list), even in years after the plan has already gone into shortfall.
- What happens when the user has not yet run a simulation and opens the walkthrough page directly? The page shows guidance to run a simulation first, consistent with how other results-dependent pages in the tool behave when their prerequisite state is absent.
- What happens for the very first plan year, which has no prior year to compare against for transition detection? It is treated as its own baseline; drivers are detected against that year's own starting-state values rather than a nonexistent prior year.
- What happens on the Compare (multi-candidate) page? Out of scope for this feature — the walkthrough applies to Run Simulation results only.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST, given a completed simulation run, deterministically select one representative simulated path: the path whose final outcome is closest to the run's median (50th-percentile) outcome. For a run with only one path (no percentile bands), that path MUST be selected.
- **FR-002**: The system MUST build a plain-language "story" for every plan year of the selected path, covering the full span of the projection from the first plan year to the last.
- **FR-003**: For each plan year, the system MUST detect notable drivers by comparing that year's state against the prior plan year (or, for the first plan year, against that year's own starting state), including at minimum: the start of Required Minimum Distributions, a Social Security claiming event, a Roth conversion, a change in withdrawal-source sequencing, a change in total taxes owed of at least 15% year-over-year, the start of IRMAA surcharges or a switch between an IRMAA lookback year and a proxy estimate, a modeled survivor's death (and the resulting filing-status and spending-need change), and any occurrence of a shortfall (every occurrence, not just the first).
- **FR-004**: Each detected driver in a year's story MUST be paired with the specific dollar amount(s) that support it, drawn only from figures already computed elsewhere in the tool (no new tax, mechanics, or simulation computation).
- **FR-005**: A plan year with no detected notable driver MUST still produce a story for that year (a plain baseline statement), never an empty or missing section.
- **FR-006**: Given identical scenario configuration and random seed, the system MUST select the same representative path and produce byte-identical narrative text on every run.
- **FR-007**: The system MUST NOT compute or narrate figures for classes of detail explicitly deferred out of this feature's v1 scope (HSA activity, FICA, Social Security earnings-test withholding, inherited-account detail, state-specific exclusions such as NC Bailey, and NIIT) — that numeric detail continues to be shown as raw numbers elsewhere on the page, just not narrated as a driver in v1.
- **FR-008**: The system MUST run entirely offline, using only data already computed as part of the simulation run, with no new runtime dependency and no additional round trip to build or view the story once the simulation result is available.
- **FR-009**: Users MUST be able to view the walkthrough in batches of up to three plan years at a time (the final batch showing fewer years if the projection's remaining years don't fill a full batch), and move forward and backward through the sequence of batches via explicit Next/Previous controls.
- **FR-010**: The walkthrough's Next control MUST be unavailable (or a no-op) at the last batch, and its Previous control MUST be unavailable (or a no-op) at the first batch.
- **FR-011**: Any figure shown on the walkthrough page that is flagged unverified elsewhere in the tool MUST remain visibly flagged as unverified on the walkthrough page, scoped to the specific plan year being viewed.
- **FR-012**: The walkthrough MUST be scoped to a completed Run Simulation result; the multi-candidate Compare page is out of scope for this feature.
- **FR-013**: If no simulation result is available yet, the walkthrough page MUST guide the user to run a simulation first rather than error or show a blank page.
- **FR-014**: This feature MUST NOT change the numeric output of any existing simulation, tax, mechanics, or reporting computation — it only adds a new narrative derived from already-computed figures.

### Key Entities

- **NarrativeEntry**: One detected driver within a plan year's story — a driver key, a short label, a plain-language explanation, and the specific dollar amount(s) that support it (sourced only from already-computed figures).
- **YearStory**: The full narrative for one plan year of the selected path — its plan year, the member age(s) relevant to that year, and the ordered list of NarrativeEntry driver items detected for it (possibly a single baseline entry when nothing notable changed).
- **RunNarrative**: The complete walkthrough for a simulation run — the selected representative path's identifying index and the ordered sequence of YearStory entries spanning every plan year of the projection.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can open the walkthrough after a completed simulation run and read a plain-language story for every plan year of one representative path, with no plan year showing missing or empty narrative.
- **SC-002**: Re-running an identical scenario and seed produces an identical selected path and identical narrative text 100% of the time (byte-for-byte).
- **SC-003**: Every figure the tool already flags as unverified elsewhere remains visibly flagged when it appears in the walkthrough — zero unverified figures presented as settled.
- **SC-004**: A user can move from the first to the last plan year of a walkthrough, and back again, using only the Next/Previous controls, without the page erroring or losing its place.
- **SC-005**: Adding this feature causes zero change to the numeric output of any other feature in the tool (existing test suites for simulation, tax, mechanics, comparison, and reporting pass unchanged).

## Assumptions

- "Representative path" means the single simulated path whose final `PlanOutcome.ending_balance` is numerically closest to the run's median (50th-percentile) outcome, per the parent bead's design notes; ties are broken by the lowest path index for determinism.
- The tax-change driver's threshold (≥15% year-over-year change in total taxes owed, per Clarifications) is not a user-facing configuration option in v1.
- The walkthrough page reads simulation results already held in the UI's existing session state for the Run Simulation page (the same result object that page already populates) rather than re-fetching from the backend, so opening the walkthrough after a completed run requires no new network round trip.
- The step-through view shows fixed batches of three plan years per screen (per Clarifications); the underlying data and narrative contract remains per-plan-year regardless of batch size, so this batch size can be revisited later without changing FR-001–FR-008.
- This feature's plain-language text is fully templated (deterministic string composition from computed data) in v1; no language model or other opt-in AI rewrite is included — that is explicitly the separate, additive P2 follow-on (rp-bm8.2).
- No new regulated figure, tax rule, or financial calculation is introduced by this feature, so no update to the figure-verification/BRD documentation of *what* is computed is required — only documentation of the new page/module/response field itself.
