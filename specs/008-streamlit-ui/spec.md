# Feature Specification: Streamlit UI

**Feature Branch**: `008-streamlit-ui`

**Created**: 2026-08-28

**Status**: Draft

**Input**: User description: "008"

**Scope note**: `docs/frontend_architecture.md` lays out a three-feature program for putting a usable front end on the retirement-planning engine: `006` Reporting & Aggregation (implemented), `007` BFF API Service (implemented — a working HTTP/JSON API at `/api/v1/scenarios`, `/api/v1/reference/*`, `/api/v1/simulations`, `/api/v1/comparisons/{deterministic,simulated}`, `/api/v1/reports/*.csv`), and `008` — the first UI client, covered by this spec. This is the feature that finally lets a person answer the source document's three linked questions (§1: longevity, tax optimization, location comparison) without writing or reading Python. It talks to `007` exclusively over HTTP — it never imports `retirement_planner` directly (`docs/frontend_architecture.md` §7's explicit reasoning: this is what actually exercises the decoupled BFF boundary rather than merely claiming one exists) — and computes, caches, or derives nothing itself; every number and chart it shows comes verbatim from a `007` response. It does not add a second UI technology, does not change `007`'s HTTP contract (a genuine gap discovered while building this feature is a small, explicit, additive amendment to `007`, the same precedent every prior feature in this project has already followed — never a workaround inside this feature), does not add authentication or multi-user support (the source document's non-goals rule this out permanently), and does not expose any capability `007` itself doesn't expose (historical-bootstrap return generation, stress scenarios, and survival-adjusted scoring are not part of `007`'s contract today, so this feature can't surface them either).

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.

  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Enter and manage a retirement scenario (Priority: P1)

A user wants to describe their household, accounts, spending, state, market assumptions, and simulation settings through a form — see it validated as they go, save it under a name, come back and edit it later, and remove it when they no longer need it — without touching a YAML file or a line of code.

**Why this priority**: Every other capability in this feature operates on a scenario that must already exist. This is the foundational slice every later story builds on, the same way scenario management was the foundation `002`–`007` were each built against in turn.

**Independent Test**: Can be fully tested by filling in a new scenario's fields, saving it, confirming it appears in a list of saved scenarios, reopening and editing it, and removing it — without needing simulation, comparison, or export support to exist yet.

**Acceptance Scenarios**:

1. **Given** a blank scenario form, **When** a user fills in a household (members, ages, claiming ages, Social Security benefits), accounts, spending, a state, market assumptions, and simulation settings, and saves it under a name, **Then** the scenario is saved and reappears with the same data when reopened.
2. **Given** a scenario with a value that violates a validation rule (e.g., a negative account balance), **When** the user views or attempts to save it, **Then** the specific problem is shown inline, distinguishing a blocking problem (must be fixed before the scenario can be run) from a warning (informational, doesn't block saving or running).
3. **Given** the state, withdrawal-strategy, and conversion-strategy fields, **When** a user opens their selection options, **Then** only the choices the backend currently supports are offered — never a hardcoded option the backend would reject.
4. **Given** a previously saved scenario, **When** the user edits and re-saves it under the same name, **Then** the previous data is fully replaced, and when they remove it, it no longer appears anywhere in the interface.

---

### User Story 2 - Run a simulation and see the results (Priority: P2)

A user wants to pick a saved, valid scenario and one strategy configuration, run a Monte Carlo simulation, and see the resulting success rate together with a chart of ending-balance percentile bands over time (a fan chart) — the source document's core "how confident should I be" question, answered visually.

**Why this priority**: This is the first point at which the tool gives a user an actual financial answer rather than just managing input data. It depends on User Story 1 (a scenario must exist and be valid) but is independently the moment the tool starts paying off.

**Independent Test**: Can be fully tested by selecting one saved, valid scenario, running a simulation, and confirming a success rate and a percentile-band chart appear, matching what the backend's simulation response reports — without needing comparison or export support to exist yet.

**Acceptance Scenarios**:

1. **Given** a saved, valid scenario, **When** a user runs a simulation against it, **Then** the resulting success rate and a fan chart of ending-balance percentiles over time are both displayed.
2. **Given** a scenario with a blocking validation problem, **When** a user attempts to run it, **Then** a specific message names the problem and no chart or success rate is shown, distinct from a message that would appear if the scenario simply didn't exist.
3. **Given** a run request large enough that the backend rejects it as exceeding its performance budget, **When** that happens, **Then** the user sees a specific message explaining the request was too large, not a generic failure or an indefinite wait.
4. **Given** a run in progress, **When** the user is waiting for it to complete, **Then** a visible progress indicator is shown for the duration of the request.

---

### User Story 3 - Compare candidates and see the results overlaid (Priority: P3)

A user wants to compare several candidates — states, Roth conversion strategies, withdrawal orders, or Social Security claiming ages — against the same scenario, using either the deterministic or the Monte Carlo engine, and see every candidate's outcome overlaid on one chart and summarized in one table, answering the source document's tax-optimization and location-comparison questions side by side.

**Why this priority**: This is the tool's second and third core questions (§1: tax optimization, location comparison). It depends on User Story 2's run-and-display mechanics but is independently valuable once that exists — a comparison is fundamentally that same display, once per candidate, overlaid.

**Independent Test**: Can be fully tested by selecting a comparison axis and two or more candidates against one saved scenario, running the comparison, and confirming every candidate's outcome appears both on one overlay chart and in one summary table, in the order the candidates were entered.

**Acceptance Scenarios**:

1. **Given** a saved scenario and a chosen comparison axis with two or more candidates, **When** the user runs the comparison, **Then** every candidate's outcome appears on one overlay chart and in one summary table (success rate, ending balance, median lifetime tax paid, median depletion age), in the order entered.
2. **Given** the deterministic engine is selected, **When** the user is choosing a comparison axis, **Then** the state axis is not offered as a choice (the deterministic engine has no location-comparison capability), while it is offered when the Monte Carlo engine is selected.
3. **Given** a deterministic comparison's results, **When** they are displayed, **Then** the fields that engine doesn't produce (success rate, percentile bands) are visibly shown as not applicable, never as a fabricated zero or blank standing in for a real value.
4. **Given** a comparison with only one candidate entered, **When** it is run, **Then** the interface still displays a valid single-candidate result rather than requiring at least two.

---

### User Story 4 - See unverified figures flagged, wherever they appear (Priority: P4)

A user reading any success rate, chart, or table wants to know immediately whether a figure behind it is still an unverified placeholder (a state tax bracket pending confirmation, a synthetic historical-return series, an illustrative survival curve) — never discovering that fact only by reading source code or a citation buried in raw data.

**Why this priority**: The constitution's Auditability principle requires this explicitly, and every upstream feature (`002` through `007`) already carries this data end-to-end specifically so a UI can surface it. It's lower priority only because it depends on User Stories 2–3 already displaying something to attach the indicator to.

**Independent Test**: Can be fully tested by running a simulation or comparison known to involve at least one unverified figure and confirming a visible indicator appears on the corresponding results, distinct from results with no unverified figures involved.

**Acceptance Scenarios**:

1. **Given** a run or comparison whose results involve at least one unverified figure, **When** the results are displayed, **Then** a visible indicator appears identifying that fact, without requiring the user to inspect raw data to notice it.
2. **Given** a run or comparison whose results involve no unverified figures, **When** the results are displayed, **Then** the interface positively confirms nothing is unverified, rather than simply omitting an indicator a user can't tell apart from "not checked yet."

---

### User Story 5 - Download a spreadsheet-ready report (Priority: P5)

A user viewing a run's or comparison's results on screen wants to download the same results as a file they can open in a spreadsheet or paste into their own working document, without retyping anything.

**Why this priority**: This depends on results already being displayed (User Stories 2–3) and delivers the source document's explicit "feeding results into the working document" workflow — valuable, but the last mile once everything else works.

**Independent Test**: Can be fully tested by viewing a run's or comparison's results and downloading a report of them, confirming the downloaded content matches what's on screen.

**Acceptance Scenarios**:

1. **Given** a displayed run's results, **When** the user requests a downloadable report of it, **Then** the downloaded file contains the same figures shown on screen, in a spreadsheet-openable format.
2. **Given** a displayed comparison's results, **When** the user requests a downloadable report of it, **Then** the downloaded file contains one row per candidate, clearly labeled, matching the on-screen summary table.

---

### Edge Cases

- What happens when the backend service this feature depends on is unreachable? A clear, specific message is shown — never a blank screen, a raw stack trace, or a silent failure.
- What happens when a user navigates to run or compare against a scenario that was removed (by them, in another browser tab, or otherwise) since the page loaded? The specific "no such scenario" message from the backend is shown, distinguishable from every other failure reason.
- What happens when a user changes the comparison engine (deterministic vs. Monte Carlo) after already choosing an axis the newly-selected engine doesn't support (i.e., switching to the deterministic engine while "state" is selected)? The interface resolves this without submitting an invalid combination — at minimum by clearing or disabling the now-unsupported selection, never by silently submitting it and only then relaying the backend's rejection.
- What happens when a user submits a scenario missing a required field? The specific missing or invalid field is identified, not a generic "something went wrong."
- What happens when a user requests a run or comparison so large the backend's cost-estimation check rejects it? The specific "too large" message is shown, distinct from every other rejection reason, so the user understands to reduce scope (fewer paths, fewer candidates) rather than assuming something is broken.

## Requirements *(mandatory)*

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right functional requirements.
-->

### Functional Requirements

- **FR-001**: The system MUST allow a user to create, view, edit, and save a named scenario through a form covering every field the backend's scenario endpoint accepts (household members, accounts, spending, state, market assumptions, simulation settings, and an optional Roth conversion plan).
- **FR-002**: The system MUST show, inline, every validation flag the backend reports for a scenario, distinguishing a blocking flag (must be resolved before the scenario can be run) from a warning (informational only).
- **FR-003**: The system MUST populate the state, withdrawal-strategy, and conversion-strategy selection options only from the backend's current reference-data responses — never from a list this feature maintains independently (Acceptance Scenario US1.3).
- **FR-004**: The system MUST allow a user to remove a saved scenario, and MUST reflect that removal immediately in every list of saved scenarios the interface shows.
- **FR-005**: Saving a scenario under a name that already exists MUST fully replace the previous data under that name, matching the backend's own overwrite behavior.
- **FR-006**: The system MUST allow a user to run a Monte Carlo simulation against a saved, valid scenario and display the resulting success rate together with a chart of ending-balance percentile bands over time (Acceptance Scenario US2.1).
- **FR-007**: The system MUST show a specific, distinguishable message for each of the backend's documented rejection reasons for a run or comparison request (scenario doesn't exist; scenario has blocking validation flags; an unrecognized state/strategy/axis value was used; the request's estimated cost exceeds the performance budget) — never a single generic error message for all of them (Acceptance Scenarios US2.2–US2.3, Edge Cases).
- **FR-008**: The system MUST show a visible progress indicator for the duration of any run or comparison request (Acceptance Scenario US2.4).
- **FR-009**: The system MUST allow a user to request a comparison across a chosen axis (state, Roth conversion strategy, withdrawal sequencing order, or Social Security claiming ages) with two or more candidates, using either the deterministic or the Monte Carlo engine, and display every candidate's outcome on one overlay chart and in one summary table, in the order the candidates were entered (Acceptance Scenario US3.1).
- **FR-010**: The system MUST NOT offer the state axis as a choice when the deterministic engine is selected, since that engine has no location-comparison capability (Acceptance Scenario US3.2).
- **FR-011**: The system MUST visibly mark fields a deterministic comparison's results don't produce (success rate, percentile bands) as not applicable, never as a fabricated or blank value indistinguishable from a real one (Acceptance Scenario US3.3).
- **FR-012**: The system MUST support a comparison with as few as one candidate and still display a valid result (Acceptance Scenario US3.4).
- **FR-013**: Every display of a number or chart derived from a run or comparison MUST also visibly indicate whether any unverified figure informed it, including an explicit positive confirmation when nothing is unverified — never merely omitting the indicator either way (Acceptance Scenarios US4.1–US4.2).
- **FR-014**: The system MUST allow a user to download a spreadsheet-ready report of any run's or comparison's results they can view on screen, using the identical parameters already displayed (Acceptance Scenarios US5.1–US5.2).
- **FR-015**: The system MUST show a clear, specific, human-readable message when the backend service is unreachable or returns an error this feature doesn't otherwise recognize — never a blank screen or a raw technical error (Edge Cases).
- **FR-016**: The system MUST NOT compute, cache, or independently derive any tax, account-mechanics, comparison, simulation, or aggregation result itself — every number, chart, and exported file it presents MUST come verbatim from a backend response.
- **FR-017**: The system MUST NOT require the user to sign in, register, or otherwise authenticate.
- **FR-018**: The system MUST NOT perform any network communication other than to the backend service running on the user's own machine — no external service call of any kind.

### Key Entities *(include if feature involves data)*

- **Scenario Form**: The editable representation of a scenario a user builds, submits, and revisits — mirrors the backend's scenario shape field-for-field; holds no data of its own once saved (the backend's scenario storage is the single source of truth).
- **Run View**: The display of one simulation's results — success rate, fan chart, and the unverified-figure indicator — for one saved scenario and strategy configuration.
- **Comparison View**: The display of one comparison's results — an overlay chart and a summary table, one row/series per candidate, plus the axis and engine that produced it.
- **Verification Indicator**: The visible signal, attached to any displayed run or comparison result, of whether an unverified figure informed it — always present, positive or negative, never absent.
- **Report Download**: The exported file a user obtains from a displayed run or comparison, matching the on-screen figures exactly.

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.
-->

### Measurable Outcomes

- **SC-001**: A user can create, save, and later retrieve a complete retirement scenario without editing a file or writing code.
- **SC-002**: A user can obtain a success-rate answer and see it charted for a saved scenario in a single guided flow, without needing to understand the underlying computation.
- **SC-003**: A user comparing states, strategies, or claiming ages sees every candidate's outcome on one screen without manually running or aligning each one by hand.
- **SC-004**: 100% of unverified figures behind a displayed number or chart are visibly flagged to the user — the same 100% guarantee the underlying reporting and API layers already provide, now visible at the point a person actually looks.
- **SC-005**: A user can download a spreadsheet-ready file of anything they can see on screen without any manual reformatting or retyping.
- **SC-006**: A user encountering any backend failure (unreachable service, invalid scenario, oversized request, unrecognized value) sees a specific, actionable message rather than a blank screen, a stack trace, or an indefinite wait.

## Assumptions

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right assumptions based on reasonable defaults
  chosen when the feature description did not specify certain details.
-->

- **This feature talks to `007` exclusively over HTTP and never imports `retirement_planner` directly**, per `docs/frontend_architecture.md` §7's explicit reasoning: this is what actually exercises the decoupled BFF boundary the whole three-feature program exists to prove out, not an incidental implementation detail.
- **The concrete UI technology (a Python-native dashboard framework) was already decided during `docs/frontend_architecture.md`'s planning**, confirmed with the user at the time as the first of potentially several future client technologies — the exact framework choice is implementation detail for the planning phase, not a scope-defining choice for this spec, mirroring how `007`'s own spec kept its transport framework out of its functional requirements.
- **This feature holds no persistent state of its own.** Every piece of data it shows is either ephemeral (form inputs not yet saved) or sourced live from `007` on each request — no local database, no client-side cache that could go stale relative to the backend.
- **`reference_tax_year`/`start_plan_year`/`start_tax_year` remain user-supplied fields**, mirroring `007`'s own no-default policy for exactly these fields (its research.md §4, which itself extends a Reproducibility rule `004` established) — this feature pre-fills a sensible starting value (e.g., the current calendar year) but never silently substitutes one without the user seeing and being able to change it.
- **Advanced simulation parameters (path count, random seed) are optional, defaulting from the scenario's own settings**, mirroring `007`'s own optional-with-scenario-derived-default design for the same fields — exposed as an advanced option, not a required field on every run.
- **No multi-scenario dashboard beyond what comparison views already provide.** A user working with several scenarios switches between them one at a time; a unified overview of many scenarios at once is out of scope for this feature.
- **Historical-bootstrap return generation, stress scenarios, and survival-adjusted scoring are not exposed**, since `007`'s own contract doesn't expose them either (its spec's own scope note) — this feature cannot offer a capability its backend doesn't provide.
