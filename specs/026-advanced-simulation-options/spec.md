# Feature Specification: Advanced Simulation Options (Historical Bootstrap + Stress Overlay)

**Feature Branch**: `026-advanced-simulation-options`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "Expose two engine-complete Monte Carlo capabilities that services/bff and the Streamlit UI currently cannot reach at all -- historical-bootstrap return generation (rp-741) and the sequence-of-returns stress overlay (rp-2bn) -- as 'Advanced' options on the Run Simulation and Compare pages. Both share the same root cause (rp-xxp audit), the same suggested UI slot, and both bead write-ups say to scope them together. Addresses rp-741 and rp-2bn."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Stress-test a plan against a bad early sequence of returns (Priority: P1)

A household wants to know how their plan holds up if the market has a bad stretch right after they retire — a materially different risk than the same average return spread evenly across the whole horizon. They configure a shock (how bad, how long, starting when) as an advanced option on a Monte Carlo run or comparison and see the success rate and fan chart reflect that stress.

**Why this priority**: This is the more broadly useful of the two capabilities — sequence-of-returns risk is one of the best-known, most consequential risks in retirement planning, and right now a household evaluating it has no way to do so through the app at all, only by a direct Python call.

**Independent Test**: Configure a stress scenario (magnitude, duration, starting plan year) on a Run Simulation request and confirm the resulting run's success rate is measurably worse than the same request with no stress configured.

**Acceptance Scenarios**:

1. **Given** a saved scenario and a configured stress scenario (a negative shock magnitude, a duration in years, a starting plan year within the run's horizon), **When** the household runs a Monte Carlo simulation with the stress option enabled, **Then** every path's returns are overridden to the shock magnitude for exactly that window, and the reported success rate reflects the worse outcome.
2. **Given** the same scenario with no stress option enabled, **When** the household runs the identical simulation, **Then** the result is unchanged from before this feature existed.
3. **Given** a configured stress window that extends past the run's own planning horizon, **When** the household submits the request, **Then** they see a clear, specific error explaining the window doesn't fit, not a generic failure.

---

### User Story 2 - Probe how much the parametric assumption itself matters (Priority: P2)

A household wants to see how their plan's outcome changes if returns are drawn from a resampled historical-style sequence (capturing fat tails and real historical clustering) instead of the default smooth, symmetric parametric model — directly probing a documented simplification of the tool's default mode.

**Why this priority**: Real, but narrower than User Story 1 — it's a power-user "what if the parametric assumption itself is wrong" check rather than the headline sequence-of-returns risk question, and depends on a return series the household must be told is illustrative, not real market history.

**Independent Test**: Configure a Run Simulation request with the historical-bootstrap return-generation mode instead of the default, and confirm the run completes, uses genuinely different (resampled, block-structured) returns than the parametric default, and is clearly flagged as using an unverified data source.

**Acceptance Scenarios**:

1. **Given** a saved scenario, **When** the household selects historical-bootstrap generation mode (with a block-length setting) instead of the default, **Then** the run's returns are drawn via block resampling from the documented historical series rather than parametric draws, and the result is visibly flagged as relying on an unverified figure.
2. **Given** the same scenario with the default (parametric) mode, **When** the household runs the identical simulation, **Then** the result is unchanged from before this feature existed.

---

### Edge Cases

- A household enables the stress overlay together with historical-bootstrap mode: the shock overrides the chosen window's returns regardless of which generation mode produced the underlying paths (the stress is a layer applied on top of whichever mode is selected, not an alternative to it).
- A household runs a *comparison* (not a single simulation) with either option enabled: every candidate in the comparison is built from the same configured mode/stress, consistent with this tool's existing paired-draw comparison methodology (same underlying market conditions across every candidate, varying only the dimension under test).
- A household submits a comparison using the Deterministic engine: neither option applies (both are Monte-Carlo-only engine capabilities) and the request is unaffected by whatever either option's UI control shows.
- A household submits a request with an invalid block-length (too long for the documented historical series, or non-positive): they see a clear, specific error, not a generic failure.
- A household never touches either option: every existing request and every existing saved scenario behaves byte-for-byte identically to before this feature existed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST let a household choose a return-generation mode (the existing default, or historical-bootstrap resampling with a configurable block length) when running a Monte Carlo simulation or a Monte-Carlo-based comparison.
- **FR-002**: System MUST let a household configure an optional stress scenario (shock magnitude, duration in years, starting plan year) applied on top of whichever return-generation mode is selected, when running a Monte Carlo simulation or a Monte-Carlo-based comparison.
- **FR-003**: Both options MUST default to today's existing behavior (parametric generation, no stress) when not explicitly configured, so every existing saved scenario and every existing request is unaffected.
- **FR-004**: A comparison built from multiple candidates MUST apply the same configured generation mode and stress scenario across every candidate, consistent with the tool's existing paired-draw comparison methodology.
- **FR-005**: An invalid stress window (extending past the run's own planning horizon) or an invalid block length MUST produce a clear, specific, actionable error message — never a generic failure.
- **FR-006**: When historical-bootstrap mode is used, the result MUST be visibly flagged to the household as relying on a data source that is not yet verified as real historical data (the same "needs verification" treatment every other unverified figure in this tool already receives) — never presented as equivalent to a verified, settled figure.
- **FR-007**: Neither option MUST apply to a Deterministic (non-Monte-Carlo) comparison — both are Monte-Carlo-only capabilities, and a household using the Deterministic engine is unaffected by them regardless of what either control shows.
- **FR-008**: Both options MUST be discoverable from an "advanced"/optional area of the Run Simulation and Compare pages, not the primary form a first-time user fills out — a first-time household should not need to understand sequence-of-returns risk or bootstrap resampling to run a basic simulation.

### Key Entities

- **Return-Generation Mode**: Which method produced a simulation's underlying market-return paths — the existing parametric (correlated-normal) default, or historical-bootstrap resampling from a documented historical annual-return series, with a configurable block length (how many consecutive years are resampled together).
- **Stress Scenario**: An optional shock overlay — how severe, how many years it lasts, and which plan year it starts in — applied on top of whichever return-generation mode produced the underlying paths.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A household can configure and run a stress-tested simulation, and see a measurably different (worse, for a negative shock) success rate than the identical unstressed run, without leaving the app.
- **SC-002**: A household can configure and run a historical-bootstrap simulation, and see it clearly and consistently flagged as relying on an unverified data source, without leaving the app.
- **SC-003**: Every existing saved scenario, run without touching either new option, produces output identical to its pre-feature result.
- **SC-004**: A misconfigured stress window or block length is rejected with a specific, actionable error message in 100% of cases tested, never a generic/unhandled failure.
- **SC-005**: Both options are available identically from a single simulation run and from a Monte-Carlo-based comparison of multiple candidates.

## Assumptions

- This feature exposes existing, already-tested core-engine capabilities (`retirement_planner.simulation.generate_historical_bootstrap_paths()`, `apply_stress_scenario()`) — no new market-modeling math is introduced.
- The historical return series these capabilities draw from is currently synthetic placeholder data (a documented, pre-existing limitation of the engine, not something this feature changes) — this feature's job is to make that limitation visibly and honestly reachable, not to fix the underlying data.
- Cost/runtime budgeting for a request is unaffected by which return-generation mode is chosen — both have the same per-path cost profile.
- Both options apply only to Monte Carlo work (a single simulation, or a Monte-Carlo-based comparison across candidates) — a Deterministic (single fixed-return) comparison has no return-path generation step for either option to affect.
- No new scenario-level (saved-scenario) configuration is introduced — both options are per-request choices, entered fresh each time a household runs or compares, the same way today's existing "override scenario defaults" advanced controls already work.
