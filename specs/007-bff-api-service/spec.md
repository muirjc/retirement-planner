# Feature Specification: BFF API Service

**Feature Branch**: `007-bff-api-service`

**Created**: 2026-08-28

**Status**: Draft

**Input**: User description: "007"

**Scope note**: `docs/frontend_architecture.md` (itself grounded in `docs/remaining_scope.md`'s gap analysis) lays out a three-feature program for putting a usable front end on the retirement-planning engine: `006` Reporting & Aggregation (implemented), `007` BFF API Service, `008` first UI client. This spec covers `007`: a new, independently deployable HTTP/JSON service — decoupled from any specific UI technology per the project's explicit multi-UI goal — that wraps `001`'s scenario management, `002`–`003`'s tax/mechanics registries, `004`'s deterministic comparisons, `005`'s Monte Carlo simulation and comparisons, and `006`'s summary/export functions behind a request/response boundary a UI can call over HTTP. It does not cover any specific front-end UI (`008`, a separate future feature, consumes this service but is not delivered by it), authentication or multi-user support (the source document's own non-goals rule this out permanently), a results database (every response is regenerated on demand from its request, per the reproducibility guarantee `001`–`006` already provide), or asynchronous job/polling support (deferred until a request's estimated cost would exceed the constitution's performance budget — not yet the case at today's implemented scale). It also does not compute, re-derive, or duplicate any tax, account-mechanics, comparison, simulation, or aggregation logic itself — every number this service returns comes from calling `001`–`006`'s already-tested functions unchanged, plus one small, explicit prerequisite addition to `001` (a way to remove a saved scenario, which does not exist yet).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Save, load, and validate a scenario over HTTP (Priority: P1)

A front-end client wants to create, read, list, update, and validate a named retirement scenario through HTTP requests — the same operations `001` already provides as Python function calls — so that a data-entry UI has something to save a user's household, account, and assumption inputs to and read them back from.

**Why this priority**: Every other capability in this service operates on a scenario that must already exist and be inspectable — a simulation can't run, a comparison can't be built, and a report can't be exported without a saved, loaded scenario first. This is the foundational slice every other user story in this feature builds on, the same way `001` was the foundation `002`–`006` were each built against in turn.

**Independent Test**: Can be fully tested by sending an HTTP request to save a scenario, then separate requests to read it back, list it among saved scenarios, and validate it, and confirming each response matches what calling `001`'s `save_scenario()`/`load_scenario()`/`list_scenarios()`/`validate()` directly would produce for the same data — without needing simulation, comparison, or export support to exist yet.

**Acceptance Scenarios**:

1. **Given** a complete, valid scenario submitted as a request body, **When** it is saved under a name, **Then** a subsequent request to read that name returns the same household, account, spending, state, market-assumption, and simulation-setting data back, plus its validation status.
2. **Given** two scenarios saved under different names, **When** the list of saved scenarios is requested, **Then** both names are present, in the same stable order `001`'s own `list_scenarios()` already returns.
3. **Given** a scenario submitted with a value `001`'s validation rules flag as blocking (e.g. a negative account balance), **When** it is validated, **Then** the response reports that blocking flag explicitly — including when it is submitted for validation only, without being saved — never silently accepting it as valid.
4. **Given** a scenario saved under a name, **When** a new scenario is saved under that same name, **Then** the previous scenario's data is fully replaced, matching `001`'s own documented overwrite behavior — not merged or duplicated.
5. **Given** a saved scenario a client no longer wants, **When** a request to remove it by name is made, **Then** it no longer appears in the list of saved scenarios, and a subsequent request to read it reports it doesn't exist.
6. **Given** a request naming a scenario that was never saved, **When** it is read, updated-only-by-name-without-existing, or removed, **Then** the response reports clearly that no such scenario exists, rather than a generic or ambiguous error.

---

### User Story 2 - Discover what the engine currently supports (Priority: P2)

A front-end client wants to ask the service which states, withdrawal-sequencing strategies, Roth conversion strategies, and comparison axes are currently available, so that a data-entry form's dropdowns and a comparison-builder UI always reflect what the engine can actually run — never a hardcoded list that silently goes stale when the engine gains or loses support for something.

**Why this priority**: A data-entry UI (building on User Story 1) needs to know valid choices for state, withdrawal strategy, and conversion strategy before a user can meaningfully fill in a scenario; a comparison-builder UI needs to know which axes exist before it can offer "compare by state" as an option. This is lower priority than saving scenario data itself only because a client could, in principle, launch with a temporarily hardcoded list and still exercise User Story 1 — but no client should ship that way for long.

**Independent Test**: Can be fully tested by requesting each reference-data list and confirming it exactly matches what directly inspecting `002`'s state-tax registry, `003`'s withdrawal-sequencing and Roth-conversion registries, and `005`'s comparison-axis type would show — without needing any scenario, simulation, or comparison to exist yet.

**Acceptance Scenarios**:

1. **Given** the service is running against today's implementation, **When** the list of supported states is requested, **Then** it contains exactly the states `002`'s tax engine currently has real modules for — no more, no fewer, and no state the engine can't yet compute tax for.
2. **Given** a new state tax module is added to `002` in the future without any change to this service, **When** the list of supported states is requested again, **Then** the new state appears automatically.
3. **Given** the lists of withdrawal-sequencing strategies, Roth conversion strategies, and comparison axes are each requested, **Then** each matches its corresponding registry in `003`/`005` exactly, with no axis or strategy name invented or omitted by this service.

---

### User Story 3 - Run a simulation and receive a summarized result (Priority: P3)

A front-end client wants to request a Monte Carlo simulation for a saved scenario and one chosen strategy, and receive back both the full result and a decision-ready summary (success rate, ending balance, percentile bands, median depletion age, median lifetime tax paid, and any unverified figures behind those numbers) in one response, so a results screen has everything it needs without a second round trip.

**Why this priority**: This is the service's central "see an answer" capability — the whole reason a front end exists. It depends on User Story 1 (a scenario must be saved and loadable) and benefits from User Story 2 (valid strategy/state choices), but is independently the first point at which a client gets back the tool's actual financial answer rather than just managing input data.

**Independent Test**: Can be fully tested by saving one valid scenario, requesting a simulation run against it with one strategy configuration, and confirming the response contains both a full simulation result and a summary whose fields match what directly calling `005`'s `run_simulation()` followed by `006`'s `summarize_run()` on the same inputs would produce.

**Acceptance Scenarios**:

1. **Given** a saved, valid scenario and one strategy configuration, **When** a simulation run is requested, **Then** the response contains the full run result and a summary in one payload, with every summary figure matching what summarizing that same run directly would produce.
2. **Given** a saved scenario with at least one blocking validation flag, **When** a simulation run is requested against it, **Then** the request is rejected with those blocking flags reported explicitly, and no simulation is run.
3. **Given** the same scenario, strategy, and run parameters (including random seed) submitted twice, **When** both requests complete, **Then** both responses report identical results — the same reproducibility guarantee `005` already provides must hold end-to-end through this service, not just within the library.
4. **Given** a run request that omits an optional parameter with a documented default (such as random seed), **When** it is run, **Then** the service applies a deterministic default derived from the scenario's own configuration — never a non-reproducible source like the system clock or an unseeded random generator.

---

### User Story 4 - Run and retrieve a comparison (Priority: P4)

A front-end client wants to request a comparison across a chosen axis — states, Roth conversion strategies, withdrawal orders, or claiming ages, using either the deterministic (`004`) or Monte Carlo (`005`) engine — and receive back one summarized result per candidate, so a comparison screen can show every candidate side by side.

**Why this priority**: This is the service's second core capability (tax optimization and location comparison, per the source document's own three linked questions) but depends on User Story 3's single-run request/response shape already existing and working correctly — a comparison is fundamentally that same shape requested once per candidate.

**Independent Test**: Can be fully tested by saving one scenario and requesting a comparison across two or more candidates on one axis, and confirming the response contains one summarized result per candidate, in the candidates' own order, matching what directly calling the corresponding `004`/`005` comparison function followed by `006`'s corresponding summarization function would produce.

**Acceptance Scenarios**:

1. **Given** a saved scenario and a list of two or more states, **When** a Monte Carlo state comparison is requested, **Then** the response contains one summarized result per state, in the order requested, each attributable only to that state's own difference from the others.
2. **Given** a saved scenario and a list of Roth conversion strategy candidates, **When** a deterministic comparison is requested, **Then** the response contains one summarized result per candidate, with the Monte-Carlo-only fields (success rate, percentile bands) explicitly marked not applicable, matching `006`'s own established distinction.
3. **Given** a comparison request naming an axis this service doesn't recognize, or a candidate referencing a state/strategy User Story 2's own reference-data lists don't contain, **When** it is submitted, **Then** the request is rejected with a specific, actionable reason — never silently ignored or defaulted to something else.
4. **Given** a comparison request with only one candidate, **When** it is submitted, **Then** the response still contains a valid one-candidate result, matching the single-candidate support `004`/`005` already guarantee.

---

### User Story 5 - Export a run or comparison as a downloadable report (Priority: P5)

A front-end client wants to request a spreadsheet-ready export of a simulation run's or comparison's results, so a user can download a file they can open directly or paste into their own working document, without the client having to build CSV formatting itself.

**Why this priority**: This depends on the same request shape User Stories 3–4 already establish (a run or comparison must be requestable before it can be exported) and delivers the source document's explicit "feeding results into the working document" workflow — valuable, but the last of the five capabilities to become usable since every one before it is a prerequisite.

**Independent Test**: Can be fully tested by requesting a CSV export using the same parameters as a User Story 3 or User Story 4 request, and confirming the response is well-formed, spreadsheet-openable tabular text matching what directly calling `006`'s corresponding export function on the equivalent run/comparison would produce.

**Acceptance Scenarios**:

1. **Given** the same scenario and strategy parameters as a successful simulation run request, **When** a CSV export of that run is requested instead, **Then** the response is tabular text with one row per plan year, matching `006`'s `run_to_csv_text()` output for the equivalent run.
2. **Given** the same scenario and candidate parameters as a successful comparison request, **When** a CSV export of that comparison is requested instead, **Then** the response is tabular text with one row per candidate, clearly labeled, matching `006`'s corresponding comparison export function.
3. **Given** any export request, **When** the underlying run or comparison involves at least one unverified figure, **Then** the exported text visibly indicates that, matching `006`'s existing verification-status column — this service never strips that indicator on the way out.

---

### Edge Cases

- What happens when a run, comparison, or export request's projected computational cost would exceed the constitution's performance budget (e.g., an unusually large path count combined with a large candidate set)? The service MUST reject the request with a specific reason rather than accepting it and risking an indefinitely hanging response — this is the documented trigger for adding asynchronous job support in a future iteration, not something this feature silently absorbs by making a user wait.
- What happens when two requests for the identical run or comparison arrive at the same time? Each is computed and answered independently — this service holds no results database and no request-level locking; concurrent identical requests simply both do the same (deterministic) work and get the same answer.
- What happens when a request supplies a state, withdrawal strategy, or conversion strategy that isn't currently registered? The request MUST be rejected with a specific, actionable reason naming the invalid value — never silently substituting a default or ignoring the invalid field.
- What happens when a scenario named in a run, comparison, or export request was never saved (or was removed)? The request MUST be rejected with a specific reason distinguishing "no such scenario" from every other failure reason, so a client can tell a user exactly what to fix.
- What happens when a client requests a comparison mixing the deterministic and Monte Carlo engines in one call (e.g., asking for both a success rate and a `004`-only field in the same request)? The service MUST treat deterministic and Monte Carlo comparisons as two distinct request types (matching `006`'s own two distinct summarization functions) rather than inventing a hybrid response shape that doesn't correspond to anything `004`/`005`/`006` actually produce.
- What happens when a scenario is deleted while another client still holds a reference to it (e.g., mid-form-edit)? The next request naming that scenario is rejected as "no such scenario" (per the edge case above) — this service does not attempt to prevent or warn about concurrent deletion, consistent with there being no multi-user support to coordinate between clients in the first place.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow a client to save a complete scenario (household, accounts, spending, state, market assumptions, simulation settings) under a name, read it back by name, and list every currently saved scenario's name, using `001`'s existing `save_scenario()`/`load_scenario()`/`list_scenarios()` functions unchanged.
- **FR-002**: The system MUST allow a client to validate a scenario — either one being saved or one submitted for validation only — and report every resulting flag (blocking or warning) using `001`'s existing `validate()` function unchanged.
- **FR-003**: Saving a scenario under a name that already exists MUST fully replace the previously saved scenario under that name, matching `001`'s own documented overwrite behavior (Acceptance Scenario US1.4).
- **FR-004**: The system MUST allow a client to remove a previously saved scenario by name. This capability does not exist in `001` today and MUST be added there as a small, explicit, additive prerequisite (mirroring the precedent `004` set adding a registry entry to `003`) — not implemented as a workaround inside this service that bypasses `001`'s own storage functions.
- **FR-005**: A request naming a scenario that was never saved, or was subsequently removed, MUST be rejected with a reason clearly distinguishing "no such scenario" from every other failure reason (Edge Cases).
- **FR-006**: The system MUST expose the current list of states `002` has real tax modules for, read live from `002`'s own state-module registry — never a separately maintained or hardcoded list (Acceptance Scenarios US2.1–US2.2).
- **FR-007**: The system MUST expose the current lists of withdrawal-sequencing strategies and Roth conversion strategies, read live from `003`'s own registries, and the current list of comparison axes, read live from `005`'s own comparison-axis type (Acceptance Scenario US2.3).
- **FR-008**: The system MUST allow a client to request a Monte Carlo simulation run for a saved scenario and a strategy configuration, and MUST return, in one response, both the full run result and its summary as `006`'s `summarize_run()` would produce for that same run (Acceptance Scenario US3.1).
- **FR-009**: The system MUST reject a simulation, comparison, or export request against a scenario carrying at least one blocking validation flag, reporting those flags explicitly, and MUST NOT run any computation against it (Acceptance Scenario US3.2).
- **FR-010**: Given identical scenario, strategy, and run parameters (including random seed) submitted more than once, the system MUST return identical results every time (Acceptance Scenario US3.3).
- **FR-011**: When a run, comparison, or export request omits an optional parameter that has a documented default (such as random seed), the system MUST apply a deterministic default derived from the scenario's own configuration, never a non-reproducible source (Acceptance Scenario US3.4).
- **FR-012**: The system MUST allow a client to request a comparison across a named axis (state, Roth conversion strategy, withdrawal sequencing, or claiming-age grid) using either the deterministic (`004`) or Monte Carlo (`005`) engine, and MUST return one summarized result per candidate, in the order the candidates were requested, using `006`'s corresponding summarization function unchanged (Acceptance Scenarios US4.1–US4.2).
- **FR-013**: The system MUST treat a deterministic comparison request and a Monte Carlo comparison request as two distinct request types with two distinct response shapes, never a single hybrid shape (Edge Cases).
- **FR-014**: The system MUST reject a comparison request naming an axis it doesn't recognize, or a candidate referencing a state, withdrawal strategy, or conversion strategy not present in the current reference-data lists (FR-006–FR-007), with a specific, actionable reason (Acceptance Scenario US4.3).
- **FR-015**: The system MUST support a comparison request with as few as one candidate and still return a valid one-candidate result, matching the single-candidate support `004`/`005` already guarantee (Acceptance Scenario US4.4).
- **FR-016**: The system MUST allow a client to request a CSV export of a simulation run using the same parameters as a run request, and a CSV export of a comparison using the same parameters as a comparison request, producing text matching `006`'s corresponding export function unchanged (Acceptance Scenarios US5.1–US5.2).
- **FR-017**: Every export response MUST retain any verification-status indicator `006`'s export functions already produce — this service MUST NOT strip, alter, or fail to pass through that indicator (Acceptance Scenario US5.3).
- **FR-018**: The system MUST estimate the computational cost of a run, comparison, or export request before executing it, and MUST reject any request whose projected cost would exceed the constitution's performance budget, rather than executing it and risking an unbounded wait (Edge Cases).
- **FR-019**: The system MUST NOT persist any computed run, comparison, or export result — every such response MUST be freshly computed from its request's parameters on every call, using only `001`'s scenario storage as persisted state.
- **FR-020**: The system MUST NOT require any authentication, session, or multi-user coordination mechanism, consistent with the source document's permanent single-user, non-SaaS scope.
- **FR-021**: The system MUST NOT perform any network I/O beyond serving requests on the local machine — no external service call of any kind, consistent with `001`–`006`'s offline-first discipline.
- **FR-022**: This service MUST NOT compute, re-derive, or duplicate any tax, account-mechanics, comparison, simulation, or aggregation/export logic itself — every number or text it returns MUST originate from calling `001`–`006`'s existing functions unchanged.

### Key Entities

- **Scenario Resource**: The HTTP-addressable form of `001`'s `Scenario` — a named, saved, loadable, listable, removable, and independently validatable unit of household/account/assumption input data.
- **Reference Data**: The current, live-read lists of supported states, withdrawal-sequencing strategies, Roth conversion strategies, and comparison axes — never a separately maintained copy of what `002`/`003`/`005` already register.
- **Run Request/Response**: A request naming a saved scenario and a strategy configuration, and the paired full result plus summary this service returns for it.
- **Comparison Request/Response**: A request naming a saved scenario, a comparison axis, an engine choice (deterministic or Monte Carlo), and a candidate list, and the ordered list of summarized per-candidate results this service returns for it.
- **Export Response**: The tabular-text rendering of a run or comparison request's equivalent result, delivered as a downloadable artifact rather than a structured JSON payload.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A client can save, read, list, validate, and remove a scenario entirely through requests to this service, without ever needing direct access to the underlying scenario storage files.
- **SC-002**: A client building a data-entry or comparison-building UI can always retrieve a current, accurate list of supported states, withdrawal strategies, conversion strategies, and comparison axes, without that list ever going stale relative to what the engine actually supports.
- **SC-003**: A client can obtain a full simulation result and its decision-ready summary in a single request, without a second round trip or any client-side aggregation.
- **SC-004**: A client comparing candidates across any supported axis, using either engine, receives one directly comparable summarized result per candidate, in the order requested.
- **SC-005**: A client can obtain a spreadsheet-ready export of any run or comparison it could otherwise request, without building any CSV formatting itself.
- **SC-006**: Every response this service returns for a given request is reproducible — an identical request, submitted at a different time, always returns an identical result.
- **SC-007**: 100% of unverified figures present in an underlying run or comparison's data remain visible in this service's responses, in both the structured (JSON) and exported (CSV) forms.
- **SC-008**: A request whose computation would exceed the reference-scale performance budget is rejected quickly and clearly, rather than left pending indefinitely.

## Assumptions

- **Request/response format is JSON**, with CSV export responses as plain tabular text — the exact serialization mechanics (date formatting, non-string-keyed data shaping) are an implementation detail decided during planning per `docs/frontend_architecture.md`'s own guidance, not a scope-defining choice for this spec.
- **No results database, ever, for computed run/comparison/export data** — only `001`'s existing scenario storage persists anything, per `docs/frontend_architecture.md` §5's reproducibility-based reasoning (a disk-cached result's true identity includes the code version that produced it, which a naive cache keyed only on request parameters would not track, risking a stale answer surviving a correction to an underlying tax figure).
- **Synchronous request handling for this feature.** `docs/frontend_architecture.md` §6 established that today's reference-scale performance (a few seconds at most) doesn't yet require asynchronous job/polling support; FR-018's cost-estimation-and-rejection requirement is the interim safeguard until that trigger is actually hit, at which point async support becomes its own future addition to this same service rather than a `007` scope item now.
- **No authentication or multi-user support**, now or in any future iteration of this service, per the source document's permanent single-user, non-SaaS non-goal (`docs/initial_requirement.md` §1.1) — this is not deferred, it is out of scope by design.
- **This service is the first feature to depend on all six of `001`–`006`**, consuming each one's already-locked public contract unchanged; any gap this service finds in an underlying contract (such as `001`'s missing scenario-removal capability, FR-004) is resolved as a small, explicit, additive amendment to that feature's own contract — the same precedent `004`, `005`, and `006` each already followed when they needed a small addition to an earlier feature — never as a workaround confined to this service.
- **The specific transport/framework mechanics (HTTP methods, exact paths, status codes) are implementation detail for planning**, not this spec — `docs/frontend_architecture.md` §4 already sketches a concrete endpoint layout consistent with every requirement above, and the planning phase should treat that sketch as the starting point rather than re-deriving it from scratch.
