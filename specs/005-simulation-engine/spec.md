# Feature Specification: Simulation Engine

**Feature Branch**: `005-simulation-engine`

**Created**: 2026-08-28

**Status**: Draft

**Input**: User description: "docs/initial_requirement.md continue with section 5. you can look to the spec 001-scenario-config-management to and 002-tax-calculation-engine and 003-retirement-account-mechanics and 004-strategy-comparison-layer to see what has already been done"

**Scope note**: `docs/initial_requirement.md` describes a five-phase retirement planning tool; feature `001-scenario-config-management` covered §3.1 (input/configuration), `002-tax-calculation-engine` covered §3.2 (federal/state tax calculation), `003-retirement-account-mechanics` covered §3.3 (RMD, withdrawal sequencing, and Roth conversion execution for one plan year), and `004-strategy-comparison-layer` covered §3.4 (running those single-year mechanics across a full multi-year horizon, and comparing Roth conversion strategies, withdrawal orders, and claiming-age pairs under one shared, fixed, deterministic return assumption). This spec covers §3.5 (Simulation Engine): replacing that single deterministic return path with genuine multi-path Monte Carlo simulation — many randomly drawn return sequences per configuration, aggregated into a probability-based success rate and percentile outcome bands — and generalizing the paired-draw comparison pattern (the same set of random return paths reused identically across every compared configuration) so it applies to *any* comparison axis, including the state-of-residence axis from the source document's §1 "Location comparison" question that no prior feature has yet delivered, not only the strategy/order/claiming-age axes `004-strategy-comparison-layer` already compares. It also adds an alternative historical-bootstrap return-generation mode, a parameterized sequence-of-returns stress test, and an optional mortality-adjusted survival framing for the success metric. It does not compute federal or state tax itself (delivered by `002-tax-calculation-engine`, consumed as an input), does not perform RMD, withdrawal, or Roth conversion execution itself (delivered by `003-retirement-account-mechanics`, consumed as an input for each simulated year), does not implement the single-configuration full-horizon projection mechanics themselves (delivered by `003`/`004`, which this feature invokes once per random return path per compared configuration instead of once under one fixed path), and does not render fan charts, overlay charts, summary tables, or verification-flag propagation into report output (§3.6, a separate future feature) — it produces structured, many-path simulation and comparison results for a future reporting feature to present. IRMAA/NIIT modeling and HSA contribution/eligibility timing, also listed in the source document's phased plan, remain deferred to their own documented future phases (§8 Phase 4 and Phase 5 respectively), matching the precedent set by `002` and `003`.

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

### User Story 1 - Run a probabilistic Monte Carlo simulation for one configuration (Priority: P1)

A user wants to know how confident they should be that their money lasts, given market uncertainty — not the single deterministic outcome `004-strategy-comparison-layer` produces, but a probability across thousands of plausible market futures. The user runs one strategy configuration (Roth conversion strategy, withdrawal order, claiming ages, state) through many randomly drawn annual-return sequences and receives a success rate and percentile bands on ending balance over time.

**Why this priority**: This is the source document's first linked question (§1: "Longevity") and the literal reason the prototype is called a Monte Carlo tool. Every other capability in this feature — paired-draw comparison, historical bootstrap, stress testing, mortality adjustment — is a variation on "run this many times with different returns and aggregate," so a single correct multi-path run is the foundation everything else builds on.

**Independent Test**: Can be fully tested by feeding one complete scenario and configuration (the same inputs `004`'s User Story 1 accepts, plus a path count and random seed) and confirming the system runs the full-horizon projection once per randomly drawn return path, then reports a success rate (share of paths that met spending need through the horizon without depletion) and percentile ending-balance bands over time — without needing more than one configuration or any comparison to be built yet.

**Acceptance Scenarios**:

1. **Given** a complete scenario, one strategy configuration, a path count, and a random seed, **When** the simulation is run, **Then** the system produces one full-horizon projection per path (per `003`/`004` mechanics, with that path's own randomly drawn annual returns substituted for the single deterministic assumption `004` uses) and aggregates them into a success rate and percentile ending-balance bands by plan year.
2. **Given** a completed simulation, **When** its success rate is inspected, **Then** it equals the share of paths in which spending need was met through the configured planning horizon without the accounts being depleted first, expressed as a percentage.
3. **Given** the same scenario, configuration, path count, and random seed run twice, **When** both simulations complete, **Then** every path's random returns, every path's projection, and the aggregated success rate and percentile bands are identical between the two runs.
4. **Given** a path in which the household's accounts are depleted before the horizon ends, **When** that path's projection completes, **Then** it is recorded as a failure for the success-rate calculation and its depletion age is retained individually, rather than being dropped from or silently smoothed into the aggregate.
5. **Given** a requested path count of zero or a negative number, **When** the simulation is requested, **Then** the system rejects the request rather than returning a success rate computed from no paths.

---

### User Story 2 - Compare configurations, including states, using paired random draws (Priority: P2)

A user wants to compare success rates across candidate configurations — states, Roth conversion strategies, withdrawal orders, or claiming-age pairs — the way the source document's second and third linked questions ask ("tax optimization" and "location comparison"). The user runs a paired-draw comparison: the identical set of randomly drawn return paths is reused across every compared configuration, so any difference in success rate or outcome is attributable to the compared dimension alone, never to different market luck.

**Why this priority**: This is the core methodology the source document calls out as "already implemented for state comparison" in the prototype and mandates as "the standard for *any* comparative run." `004-strategy-comparison-layer` built the comparison-result shape for strategy/order/claiming-age axes but under one shared deterministic path; this story is what makes those comparisons — and the still-undelivered state comparison — probabilistically meaningful. It depends on User Story 1's single-configuration Monte Carlo mechanics.

**Independent Test**: Can be fully tested by feeding one scenario, a path count and seed, and a list of two or more candidate configurations that vary along exactly one axis (e.g., two or more states, holding strategy/order/claiming-ages fixed), running the paired-draw simulation, and confirming every candidate's projections were computed from the exact same set of randomly drawn return paths (path-for-path) and that the comparison result reports one success rate and outcome distribution per candidate in a single structured result.

**Acceptance Scenarios**:

1. **Given** a scenario, a path count, a seed, and a list of two or more states (each already implemented as a state tax module per `002-tax-calculation-engine`), **When** the comparison is run, **Then** the result contains one success rate and one set of percentile outcome bands per state, each state's paths having reused the identical randomly drawn return sequences as every other state's.
2. **Given** a paired-draw comparison across Roth conversion strategies, withdrawal orders, or claiming-age pairs (the axes `004-strategy-comparison-layer` already supports deterministically), **When** run through this feature, **Then** the comparison uses the same shared random-draw set across all compared configurations, producing a success rate per configuration instead of `004`'s single deterministic outcome per configuration.
3. **Given** a completed paired-draw comparison, **When** the underlying random draws are inspected, **Then** path 1 of every compared configuration used the identical sequence of annual returns as path 1 of every other configuration, path 2 the identical sequence as path 2, and so on — the pairing holds path-by-path, not just in aggregate.
4. **Given** a comparison across two configurations that are financially identical for this scenario (e.g., two states with no material tax difference at this income level), **When** compared, **Then** their success rates and percentile bands are equal — the paired draws must not introduce a spurious difference between configurations the underlying mechanics treat identically.
5. **Given** a comparison requested with only one candidate configuration, **When** run, **Then** the system still returns a valid single-entry comparison result rather than requiring at least two candidates (matching the precedent set in `004-strategy-comparison-layer`'s Edge Cases).

---

### User Story 3 - Generate returns from resampled historical history instead of a parametric distribution (Priority: P3)

A user wants an alternative to normally-distributed random returns: annual return sequences resampled from actual historical market history (e.g., contiguous blocks of real annual returns from 1926–present), so that fat tails and genuine historical sequencing — not just a mean and standard deviation — inform the simulation.

**Why this priority**: The source document flags this explicitly as a needed addition ("fat tails and real sequencing... matter for sequence-of-returns risk") and as an open question (data source and date range). It is additive to User Stories 1–2 — the same aggregation and paired-draw machinery applies regardless of how a path's returns were generated — so it can be built and tested once the parametric mode already works.

**Independent Test**: Can be fully tested by requesting a simulation with the historical-bootstrap return mode instead of the parametric mode, on the same scenario and configuration used in User Story 1, and confirming each generated path's annual returns are contiguous blocks drawn from the configured historical return series (not independently drawn from a normal distribution), while the resulting success rate and percentile bands are produced through the identical aggregation and paired-draw logic as the parametric mode.

**Acceptance Scenarios**:

1. **Given** a scenario, a path count, a seed, and the historical-bootstrap return mode selected, **When** the simulation runs, **Then** each path's sequence of annual returns is built by resampling contiguous blocks from the configured historical annual-return series, rather than drawing from a parametric normal distribution.
2. **Given** the same scenario, configuration, path count, and seed run twice under historical-bootstrap mode, **When** both simulations complete, **Then** every path's resampled return sequence and the aggregated results are identical between the two runs.
3. **Given** a paired-draw comparison run under historical-bootstrap mode, **When** compared to the same comparison run under parametric mode, **Then** both modes produce a valid, internally paired comparison result using their respective return-generation method — a comparison is never a mix of bootstrap-generated paths for one candidate and parametric paths for another within the same comparison run.
4. **Given** a requested block length or historical date range that leaves fewer historical years available than the requested block length, **When** the simulation is requested, **Then** the system rejects the request with a specific reason rather than silently falling back to a shorter block or a different date range.

---

### User Story 4 - Apply a configurable sequence-of-returns stress scenario (Priority: P4)

A user wants to test a plan against a specific bad-market scenario — for example, a market shock of a configurable severity and duration occurring at a configurable point in retirement (not only "the first five years," as the existing prototype fixes it) — to see how that specific stress affects success rate and depletion risk, independent of the broader Monte Carlo distribution.

**Why this priority**: The source document notes this exists in the prototype only as a hardcoded "bad first 5 years" case and asks for it to become parameterized. It is a distinct, narrower analysis than full Monte Carlo (a single, deliberately adverse path or overlay applied to the return-generation step) and depends on the path-generation and single-configuration projection machinery from User Story 1, so it is naturally sequenced after the core Monte Carlo capability.

**Independent Test**: Can be fully tested by requesting a simulation with a stress scenario specifying shock magnitude, duration, and starting plan year, on the same scenario and configuration used in User Story 1, and confirming the specified years of the resulting path(s) reflect the configured shock while all other years follow the otherwise-configured return-generation mode.

**Acceptance Scenarios**:

1. **Given** a scenario, a configuration, and a stress scenario specifying a shock magnitude, a duration in years, and a starting plan year, **When** the stress-tested simulation runs, **Then** the specified consecutive plan years' returns are overridden to reflect the configured shock, and all other plan years use the otherwise-configured return-generation mode (parametric or historical-bootstrap).
2. **Given** two stress scenarios identical except for the plan year the shock begins, **When** each is run against the same configuration, **Then** the resulting success rates and depletion outcomes may differ, reflecting that sequence-of-returns risk depends on *when* a shock occurs relative to the withdrawal schedule, not only its magnitude and duration.
3. **Given** a stress scenario whose configured duration would extend beyond the planning horizon, **When** requested, **Then** the system rejects the request with a specific reason rather than silently truncating the shock or extending the horizon.
4. **Given** a stress scenario applied within a paired-draw comparison, **When** run, **Then** the identical shock (same magnitude, duration, and starting year) is applied to every compared configuration's paths, preserving the paired-draw guarantee that only the compared dimension differs.

---

### User Story 5 - Express success as survival-adjusted probability instead of a fixed horizon (Priority: P5)

A user wants the option to see "probability of running out of money while at least one spouse is still alive" as an alternative to (not a replacement for) the fixed-horizon success rate, using an actuarial survival curve for each household member, since a household member who has already died before running out of money by the fixed horizon isn't a real planning failure.

**Why this priority**: The source document explicitly lists this as "not yet modeled" and, in its Open Questions, as unresolved whether it is even wanted versus a fixed horizon remaining the preferred framing. It is the most speculative and lowest-priority item in §3.5's own requirement table ("Consider optional..."), and every other simulation capability in this feature is fully usable without it, so it is sequenced last and delivered as an additive, optional output rather than a required one.

**Independent Test**: Can be fully tested by running the same simulation from User Story 1 twice on an identical scenario, configuration, path count, and seed — once with survival-adjusted scoring enabled and once without — and confirming the fixed-horizon success rate is identical in both runs, while the survival-adjusted run additionally reports a probability of depletion occurring while at least one household member's survival curve indicates they are still alive.

**Acceptance Scenarios**:

1. **Given** a simulation run with survival-adjusted scoring enabled and each household member's configured current age, **When** the simulation completes, **Then** the result includes, in addition to the standard fixed-horizon success rate, a survival-adjusted probability that computes each path's failure only when depletion occurs while at least one member's actuarial survival curve places them as still living.
2. **Given** the same simulation run with survival-adjusted scoring disabled, **When** compared to the same run with it enabled, **Then** the fixed-horizon success rate, percentile bands, and every other output from User Stories 1–4 are unaffected by whether survival-adjusted scoring was requested.
3. **Given** a path where depletion occurs after the point at which both household members' survival curves place them as more likely deceased than alive, **When** survival-adjusted scoring is applied, **Then** that path counts as a survival-adjusted success even though it counts as a fixed-horizon failure (since it depleted before the fixed horizon), and both figures are reported without one overwriting the other.
4. **Given** a household member configuration with no survival curve data available, **When** survival-adjusted scoring is requested, **Then** the system rejects the request with a specific reason rather than silently omitting that member from the calculation or substituting an arbitrary default curve.

---

### Edge Cases

- What happens when a paired-draw comparison's candidate configurations differ along more than one axis at once (e.g., a different state *and* a different Roth conversion strategy in the same candidate list)? The system MUST still run a valid paired comparison — the paired-draw guarantee (identical random returns per path index across candidates) holds regardless of how many inputs differ between candidates — but a candidate list mixing axes cannot claim to isolate a single dimension the way a same-axis comparison can, and the comparison result MUST NOT mislabel a multi-axis comparison as single-axis.
- What happens when the requested path count is large enough that runtime would regress against the performance budget already established for 3,000–5,000 paths (per the source document's non-functional requirements)? The system MUST still complete and produce a correct result; a performance regression at very large path counts is a non-functional concern (see Success Criteria), not a correctness failure this feature suppresses.
- What happens when a plan year within a stress-test shock window is also a year in which a scheduled Roth conversion or withdrawal-sequencing rule would otherwise apply? The stress scenario overrides only that year's investment return; it MUST NOT alter or suppress that year's RMD, withdrawal, conversion, or tax mechanics, which continue exactly as `003`/`004` would compute them for that plan year.
- What happens when historical-bootstrap mode is requested but the configured historical return series has gaps or an insufficient date range for the requested horizon and block length? Per User Story 3's acceptance scenario 4, the system MUST reject the request with a specific reason rather than substituting a shortened block, a different series, or falling back to parametric mode silently.
- What happens when a paired-draw comparison mixes return-generation modes across candidates (e.g., one candidate under parametric mode, another under historical-bootstrap)? The system MUST reject this — every candidate within one comparison run MUST share the same return-generation mode, since paired draws are only meaningful when every candidate's paths came from the same generation method and the same underlying random draws.
- What happens when a household's spending need already exceeds what a scenario's accounts could plausibly cover under any of the configured return paths (an already-doomed scenario)? The simulation MUST still run to completion and report a low or zero success rate rather than detecting and short-circuiting on the condition — this feature does not pre-screen scenarios for viability, only measures outcomes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST generate, for a requested path count and random seed, that many independent sequences of annual returns spanning a scenario's planning horizon, using a parametric multivariate return model (per the scenario's configured market assumptions) as the default return-generation mode.
- **FR-002**: The system MUST run the full-horizon projection mechanics already delivered by `003-retirement-account-mechanics` and `004-strategy-comparison-layer` once per generated return path for a given strategy configuration, substituting that path's own annual returns for the single fixed return assumption `004` uses.
- **FR-003**: The system MUST aggregate the resulting per-path projections into a success rate (the share of paths that met spending need through the configured planning horizon without account depletion) and into percentile bands of ending account balance by plan year.
- **FR-004**: For every simulated path that depletes before the planning horizon ends, the system MUST retain that path's depletion plan year individually within the aggregated result, not only as a count.
- **FR-005**: Given identical scenario inputs, strategy configuration, path count, random seed, and return-generation mode, the system MUST produce identical per-path return sequences, per-path projections, and aggregated results on every run.
- **FR-006**: The system MUST reject a simulation request with a path count of zero or less, rather than returning a result computed over an empty or negative path set.
- **FR-007**: The system MUST support running a paired-draw comparison across a list of two or more candidate configurations that vary along a single comparison axis (state, Roth conversion strategy, withdrawal sequencing order, or claiming-age pair), reusing the identical set of randomly drawn return paths — path-for-path — across every candidate in the list.
- **FR-008**: The system MUST return, for each paired-draw comparison, one success rate and one set of percentile outcome bands per candidate configuration, in a single structured comparison result.
- **FR-009**: The system MUST support the state-of-residence comparison axis using the state tax modules already delivered by `002-tax-calculation-engine`, generalizing the paired-draw mechanism to a comparison axis not covered by `004-strategy-comparison-layer`.
- **FR-010**: The system MUST allow a paired-draw comparison to run with as few as one candidate configuration and still return a valid comparison result.
- **FR-011**: The system MUST reject a paired-draw comparison whose candidate configurations do not share the same return-generation mode (parametric or historical-bootstrap) and the same path count and seed.
- **FR-012**: The system MUST support an alternative historical-bootstrap return-generation mode that builds each path's annual-return sequence by resampling contiguous blocks from a configured historical annual-return series, selectable in place of the default parametric mode for any simulation or comparison request.
- **FR-013**: The system MUST reject a historical-bootstrap request whose configured historical series and block-length parameters cannot supply enough historical years to cover the requested block length, with a specific reason.
- **FR-014**: The system MUST support a parameterized sequence-of-returns stress scenario that overrides the return of each plan year within a configurable, contiguous window (configurable magnitude, duration, and starting plan year) while leaving every other plan year's return generation, and every plan year's RMD/withdrawal/conversion/tax mechanics, unaffected by the stress override.
- **FR-015**: The system MUST reject a stress scenario whose configured window (starting plan year plus duration) extends beyond the scenario's configured planning horizon, with a specific reason.
- **FR-016**: When a stress scenario is applied within a paired-draw comparison, the system MUST apply the identical stress window and magnitude to every compared candidate's paths.
- **FR-017**: The system MUST support an optional survival-adjusted success metric that, when requested with each household member's actuarial survival curve, computes an additional probability that failure occurs only when account depletion coincides with at least one household member's survival curve indicating them as still living, without altering the standard fixed-horizon success rate the same run also reports.
- **FR-018**: The system MUST reject a survival-adjusted scoring request for any household member lacking configured survival-curve data, rather than omitting that member or substituting a default curve.
- **FR-019**: Any verification flag attached to a tax figure by `002-tax-calculation-engine` for a simulated plan year MUST be retained, per path and per compared configuration, within the simulation's structured output — this feature MUST NOT discard or silently resolve those flags.

### Key Entities

- **Return Path**: One complete sequence of annual returns spanning a scenario's planning horizon, produced by exactly one return-generation mode (parametric or historical-bootstrap) and optionally overridden within a stress-scenario window; the unit that gets fed into one full-horizon projection.
- **Simulation Run**: A set of Return Paths (sized to a requested path count, generated from a given seed and mode) each projected through the full-horizon mechanics for one strategy configuration, together with the aggregated success rate, percentile ending-balance bands, and per-path depletion data derived from them.
- **Paired-Draw Set**: The shared set of Return Paths generated once from one seed and mode, then reused identically (path-for-path) across every candidate configuration within one comparison, so that any outcome difference between candidates is attributable only to the comparison axis.
- **Comparison Axis**: The single dimension varied across candidate configurations in a paired-draw comparison — state of residence, Roth conversion strategy, withdrawal sequencing order, or claiming-age pair — held as the only difference between candidates while every other input and the Paired-Draw Set stay fixed.
- **Stress Scenario**: A configurable override (magnitude, duration, starting plan year) applied to a contiguous window of a Return Path's returns, layered on top of either return-generation mode without altering non-stress plan years or non-return mechanics.
- **Survival Model**: An optional per-household-member actuarial survival curve used to compute the survival-adjusted success metric as an additional, non-replacing output alongside the standard fixed-horizon success rate.

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.
-->

### Measurable Outcomes

- **SC-001**: A user can obtain a probability-based success rate and percentile ending-balance bands for one strategy configuration from a single simulation request, without manually running or aggregating individual projections themselves.
- **SC-002**: A user comparing candidate states, Roth conversion strategies, withdrawal orders, or claiming-age pairs receives one success rate per candidate, computed from the identical set of randomly drawn return paths across every candidate, letting them attribute any difference in outcome solely to the compared dimension.
- **SC-003**: A reference-scale simulation (3,000–5,000 paths, per the source document's non-functional requirements) across up to 9 candidate states completes in well under a minute on a standard laptop, matching the existing prototype's established performance budget.
- **SC-004**: Running the same scenario, configuration, path count, seed, and return-generation mode twice always produces identical simulation and comparison results.
- **SC-005**: A user can switch a simulation from the default parametric return mode to historical-bootstrap resampling and receive a result in the same structure (success rate, percentile bands) without needing a different analysis workflow for each mode.
- **SC-006**: A user can apply a stress scenario with a configurable magnitude, duration, and starting year — not only a fixed "first five years" case — and see how success rate and depletion risk shift specifically because of when the shock occurs.
- **SC-007**: A user who enables survival-adjusted scoring receives both the standard fixed-horizon success rate and a survival-adjusted probability from the same run, letting them compare the two framings directly rather than running the simulation twice.

## Assumptions

- **Success rate default framing stays fixed-horizon; survival adjustment is additive, not a replacement.** The source document's own Open Questions flag this as unresolved ("does a fixed planning horizon... remain the preferred framing?"). This spec resolves it by keeping the fixed-horizon success rate as the default, always-computed metric (consistent with `003`/`004`'s planning-horizon-based depletion tracking) and adding the survival-adjusted probability as an optional, separately reported figure — so no existing or future consumer of the fixed-horizon metric is affected by whether survival scoring is requested.
- **Historical return series and date range follow the source document's own suggested default.** The source document proposes "e.g., 1926–present" for the historical-bootstrap series; this spec treats a broad-coverage historical equity/bond total-return series over that approximate range as the reasonable default data source, with the exact series and precise date boundaries decided during planning as an implementation detail, not a scope-defining choice.
- **Actuarial survival curve source is a reasonable-default implementation detail.** A standard published period life table (e.g., a Social Security Administration-style table) is assumed as the default survival-curve source for User Story 5; the exact table and its update cadence are decided during planning, consistent with how `002-tax-calculation-engine` treats specific rate tables as sourced, citable implementation detail rather than a spec-level decision.
- **State comparison reuses `002`'s existing state tax modules without adding new ones.** This feature generalizes the paired-draw mechanism to the state axis using whichever state tax modules `002-tax-calculation-engine` has already delivered; adding coverage for additional states beyond what `002` implements is out of scope here.
- **This feature produces structured simulation and comparison data, not rendered reports.** Fan charts, overlay charts, summary tables, and CSV export (source document §3.6) remain a separate future feature; this feature's responsibility ends at producing complete, structured Simulation Run and comparison results (including retained verification flags) for a future reporting feature to consume.
- **IRMAA, NIIT, and HSA modeling remain deferred.** Consistent with the precedent `002-tax-calculation-engine` and `003-retirement-account-mechanics` already established, this feature does not add IRMAA/NIIT tax effects (source document §8 Phase 4) or HSA contribution/eligibility timing (§8 Phase 5) to the per-path tax and account mechanics it invokes; those mechanics are consumed exactly as `002`/`003` currently deliver them.
