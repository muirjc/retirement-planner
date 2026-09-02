# Feature Specification: Monte Carlo Per-Path Probabilistic Death Draws

**Feature Branch**: `023-probabilistic-death-draws`

**Created**: 2026-09-02

**Status**: Draft

**Input**: User description: "Monte Carlo per-path probabilistic death-year draws for survivor scenarios (rp-vgv). Follow-on to 018-survivor-scenario-projection (rp-g8y) and explicitly anticipated as a future feature in 005-simulation-engine/research.md §5 ('Stochastic per-path death-year sampling, jointly drawn alongside each path's return sequence... a natural, larger follow-on if a future feature wants genuine joint mortality/market risk rather than this feature's threshold approximation').

Problem: 018-survivor-scenario-projection wired a household's configured predicted_death_age into deterministic/comparison projections (filing status switch, survivor Social Security income, spending reduction on death), but every Monte Carlo path in simulation/monte_carlo.py currently uses that SAME single, deterministic, household-configured death year -- it never draws its own probabilistic death year from simulation/survival_data.py's actuarial survival curves. This is disclosed in docs/BRD.md §6.2c/§7 as a known modeling gap. The engine's only mortality-risk-aware Monte Carlo output today is survival_adjusted_success_rate (005-simulation-engine, FR-017/FR-018): a fixed 'presumed alive >=50% survival probability' threshold check applied post-hoc at each path's own shortfall year -- it never touches what a path actually funds, so a path's raw success/failure and its ending-balance percentile bands never reflect survivor-scenario effects (filing status, survivor SS, spending reduction) at all.

Requested capability: give each Monte Carlo path its own seeded, probabilistic death-year draw per household member (drawn from simulation/survival_data.py's SurvivalCurve, conditioned on that member's current age), and feed the resulting per-path predicted_death_age into that path's own run_plan_projection() call (reusing 018's existing survivor-scenario mechanics unchanged) -- so a path's raw success_rate and percentile_bands themselves reflect survivor-scenario risk, not just a separate post-hoc metric. This is an ADDITIVE, opt-in capability alongside the existing survival_adjusted_success_rate (which stays as-is for a caller that wants the cheaper deterministic-threshold approximation) -- not a replacement.

Scope decisions made during specification: (1) Core-library only (src/retirement_planner/simulation/), an opt-in parameter -- no BFF route changes, no Streamlit UI changes, matching the established precedent that other not-yet-API-exposed Monte Carlo capabilities (historical-bootstrap return paths, stress scenarios) have followed since 005-simulation-engine. (2) Requires a new, independently-seeded per-path RNG stream (separate from the existing return-path RNG stream), consumed in a fully deterministic, documented order, and reused path-for-path across every candidate in a comparison exactly like return_paths already is (the paired-draw standard pattern). (3) SURVIVAL_TABLE remains an illustrative, verified=False placeholder -- this feature changes nothing about its verification status. (4) Each member's draw is conditioned on that member's current age (survives to at least today), a deliberate improvement over survival_adjusted_success_rate's own unconditional threshold check, documented as a divergence between the two features' precision."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A Monte Carlo run's own success rate reflects survivor risk (Priority: P1)

A planner has a married household with both members' actuarial survival curves supplied. Today, running a Monte Carlo simulation scores every path as if both members live to the end of the horizon (or, at best, applies one household-wide configured hypothetical death year to every single path identically) -- the survivor scenario's real cost (a lone widow(er) filing single, on a reduced Social Security check, against narrower tax brackets) never actually shows up in the raw success rate or the ending-balance percentile bands, because it never varies path to path. With this feature, each path draws its own plausible death year per member from the supplied survival curves, and that path is funded and scored as if that death actually happened on schedule -- so the aggregate success rate and percentile bands themselves come out lower (more realistic) for a household meaningfully exposed to survivor risk, without the planner having to hand-configure a single hypothetical death year.

**Why this priority**: This is the entire point of the feature -- without it, the two mortality-aware capabilities this engine offers (a post-hoc threshold check, and a hand-configured single death year) both stop short of actually letting Monte Carlo's headline success-rate number answer "how much does my plan's survival depend on which one of us dies first, and when?"

**Independent Test**: Configure a married household with both members' survival curves supplied and this capability enabled, run a Monte Carlo simulation, and confirm: (a) different paths show different applied death years (or none) per member; (b) a path's own success/shortfall and ending balances reflect the same filing-status/Social-Security/spending-reduction switch 018 already applies deterministically, driven by that path's own drawn death year, not the household's static configuration.

**Acceptance Scenarios**:

1. **Given** a married household with both members' survival curves supplied and this capability enabled, **When** a Monte Carlo simulation with more than one path runs, **Then** at least two paths' own applied predicted-death-age values (per member) differ from each other, across a sufficiently large sample.
2. **Given** one specific path whose drawn death year for one member falls within the plan horizon, **When** that path's projection is inspected, **Then** every plan year after that death year shows `single` filing status, the survivor-benefit Social Security amount, and the configured spending reduction (if any) -- exactly the same effect 018 already produces for a deterministic projection given that same death year.
3. **Given** a path whose draw places a member's death beyond the survival curve's documented age range, **When** that path's projection runs, **Then** it is funded exactly as if that member's `predicted_death_age` were never configured at all (survives the full horizon).
4. **Given** this capability is not requested (the default), **When** a Monte Carlo simulation runs, **Then** output (success_rate, percentile_bands, survival_adjusted_success_rate, figures_used) is byte-for-byte identical to this feature not existing.

---

### User Story 2 - Draws stay reproducible and paired across comparisons (Priority: P2)

A planner re-runs the same scenario, path count, and seed later (or compares withdrawal strategies, states, or claiming ages against the same household) and expects the tool's two foundational guarantees to keep holding even with this new capability turned on: the identical inputs always reproduce the identical answer, and every candidate in one comparison is scored against the identical set of "what happens to the market, and to us" draws so differences between candidates are never an artifact of one candidate getting luckier mortality draws than another.

**Why this priority**: Both guarantees are constitutional requirements (Reproducibility, and the paired-draw standard pattern) that already hold for return-path draws -- this feature must extend, not weaken, them. P2 because it's a correctness property of User Story 1's mechanism, not new user-facing behavior of its own.

**Independent Test**: Run the same scenario/path-count/seed twice (once under serial dispatch, once forced into parallel dispatch) and confirm every path's drawn death year(s) and the aggregated results match exactly. Separately, run a paired-draw comparison (e.g. across candidate states) against a household with this capability enabled and confirm every candidate's path *i* used the identical death draw as every other candidate's path *i*.

**Acceptance Scenarios**:

1. **Given** the same household, path count, and seed, **When** this capability's draws are generated twice, independently, **Then** the two runs produce identical per-path, per-member drawn ages in the same order.
2. **Given** the same inputs run once under serial dispatch and once forced into parallel dispatch (the existing path-count threshold), **When** results are compared, **Then** success_rate, percentile_bands, and every path's own outcome are identical regardless of dispatch mode.
3. **Given** a paired-draw comparison across two or more candidates (e.g. states) against the same household with this capability enabled, **When** each candidate's run completes, **Then** path *i* in every candidate reflects the identical drawn death year(s) as path *i* in every other candidate.

---

### User Story 3 - The new capability and its simplifications are documented (Priority: P3)

A reader of `docs/BRD.md` can find this new opt-in capability described alongside its own honestly-disclosed simplifications: draws are conditioned on each member's current age (a deliberate improvement over the older post-hoc metric's unconditional check, itself still documented as unchanged), the underlying survival table remains an illustrative, unverified placeholder, and mortality is drawn independently of market returns and of the other member's own draw (no joint/correlated sampling).

**Why this priority**: Same auditability standard as every other feature's documentation user story (016 US3, 017 US3, 018 US3). Doesn't block User Stories 1-2 functioning correctly, hence P3.

**Independent Test**: Locate `docs/BRD.md`'s simulation-engine / survivor-scenario section and confirm it describes this capability's modeled behavior, its opt-in/off-by-default status, and its disclosed simplifications.

**Acceptance Scenarios**:

1. **Given** the completed feature, **When** a reader reviews `docs/BRD.md`, **Then** it describes per-path probabilistic death draws as an opt-in Monte Carlo capability, distinct from the existing post-hoc survival-adjusted success rate, and lists its disclosed simplifications (unverified illustrative table, current-age conditioning, independence from returns and from the other member's own draw, no BFF/UI wiring yet).

---

### Edge Cases

- A member present in the supplied survival curves whose `current_age` falls below the curve's documented age range (today's table starts at age 50): treated as certain to be alive today (equivalent to a survival probability of 1.0 at that age) for conditioning purposes -- a documented simplification, not an error.
- A member present in the supplied survival curves whose `current_age` falls above the curve's documented age range (today's table ends at age 110): treated using the curve's own oldest documented age's survival probability for conditioning purposes -- a documented boundary simplification, not an error.
- A path's draw for a member lands exactly on the survival curve's oldest documented age: treated as a death in that path (not as "beyond the table"), consistent with the curve's own inclusive, no-interpolation lookup discipline.
- A household member with no entry in the supplied survival curves (the existing `survival_curves` opt-in is still per-member, not all-or-nothing at the household level... unless this feature requires every member be covered -- see Assumptions): that member's own `predicted_death_age`, if the household configured one, continues to apply identically to every path (unchanged from today), since this feature only overrides members it has a curve to draw from.
- Both household members draw a within-horizon death on the same path: reuses 018's own existing "earlier death wins; survivor's own later configured death has no further modeled effect" rule unchanged -- no new logic.
- A single-filing-status household, or a household where the (possibly path-varying) drawn death has no configured spending-reduction percentage: behaves identically to how 018 already handles those same conditions today, since this feature only changes *which* `predicted_death_age` value(s) a given path's projection call is passed, never the survivor-scenario logic itself.
- This capability requested together with the existing `survival_curves`-driven `survival_adjusted_success_rate`: both may be requested at once; `survival_adjusted_success_rate`'s own existing formula is computed unchanged, over whatever `path_results` this run produced (whether or not per-path draws shaped them) -- not a forbidden combination, but not specially reconciled either.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST offer an opt-in mode in which, given survival-curve data for one or more household members, each Monte Carlo path draws its own independent death age for each such member, rather than every path sharing the household's single statically-configured `predicted_death_age` (if any).
- **FR-002**: Each member's per-path drawn death age MUST be conditioned on that member's current age -- i.e., drawn from the distribution of "age at death, given alive today" -- not drawn from the survival curve's raw, unconditional probabilities. This is a deliberate divergence from the existing `survival_adjusted_success_rate` metric's own unconditional check, which MUST remain unchanged.
- **FR-003**: When a path's draw for a member falls beyond the survival curve's documented age range, the system MUST treat that path/member as if `predicted_death_age` were unset (survives the full horizon) -- consistent with this engine's existing "None = never dies" semantics (017, 018).
- **FR-004**: All paths' draws MUST be generated from a single, independently seeded random stream, consumed in a fully deterministic, documented order (a fixed per-path, per-member sequence), such that the same scenario configuration, path count, and seed always reproduce byte-for-byte identical draws, regardless of serial vs. parallel dispatch (Constitution Principle II).
- **FR-005**: The generated set of per-path draws MUST be produced once and reused, path-for-path, across every candidate in a paired-draw comparison (state, withdrawal-strategy, Roth-conversion-strategy, or claiming-age-grid comparisons) -- mirroring `return_paths`' own existing reuse -- and MUST NOT be redrawn per candidate.
- **FR-006**: When this mode is active, each path's own drawn death age(s) MUST be applied through the same existing survivor-scenario projection logic (018) unchanged -- filing-status switch, survivor Social Security benefit, spending reduction -- so that path's own success/shortfall outcome and ending balances already reflect that path's own survivor scenario.
- **FR-007**: This capability MUST default to off; a caller that does not opt in MUST see output (success_rate, percentile_bands, survival_adjusted_success_rate, figures_used) byte-for-byte identical to this feature not existing.
- **FR-008**: This capability MUST be able to coexist with the existing `survival_curves`-driven `survival_adjusted_success_rate` metric without changing that metric's own computation.
- **FR-009**: Every `FigureUsage` this capability attaches for a survival curve it draws from MUST carry that curve's own actual citation and verification metadata unchanged (today: `verified=False`, since `SURVIVAL_TABLE` remains an illustrative placeholder).
- **FR-010**: This capability MUST be implemented entirely within the core simulation engine (`src/retirement_planner/simulation/`); no new BFF route or Streamlit UI surface is in scope.
- **FR-011**: `docs/BRD.md` MUST be updated to describe this new opt-in capability, its current-age-conditioning design choice (and how it differs from the older unconditional threshold check), and its own remaining disclosed simplifications (independence from returns and from the other member's own draw; illustrative unverified table; reuse of 018's earlier-death-wins rule; no BFF/UI wiring yet).
- **FR-012**: A reference-scale Monte Carlo run (3,000-5,000 paths) using this capability MUST stay well under the Constitution's one-minute performance budget, confirmed by a benchmark or test rather than assumed.

### Key Entities

- **Per-Path Death Draw**: For one Monte Carlo path, a mapping from each covered household member's name to that path's own drawn death age (or "no death within the horizon"). Generated once per path, for every path, as a single ordered set alongside (but independent of) that same run's return paths; reused unchanged across every candidate in a paired-draw comparison.
- **Survival Curve** *(existing, reused unchanged)*: The actuarial data (`simulation/survival_data.py`) a draw is sampled from -- unchanged citation/verification metadata, unchanged documented age range.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a household meaningfully exposed to survivor risk (e.g. a large gap between one member's own claimed Social Security benefit and the household's combined benefit, or a significant configured spending need), enabling this capability produces a measurably different (typically lower) success rate than the same run without it, confirming the raw metric now reflects survivor risk rather than being invariant to it.
- **SC-002**: Across a large sample of draws (e.g. 10,000), 100% of draws that are not "no death within the horizon" place the drawn death age at or above that member's current age.
- **SC-003**: Re-running the identical scenario, path count, and seed reproduces byte-for-byte identical per-path draws and aggregated results, on repeated runs and regardless of serial vs. parallel dispatch.
- **SC-004**: A paired-draw comparison run against a household with this capability enabled shows every candidate scored against path-for-path identical draws, confirmed structurally (not merely by coincidentally equal outcomes).
- **SC-005**: Every existing test or usage that does not opt into this capability continues to produce byte-for-byte identical output to before this feature existed.
- **SC-006**: A reference-scale run (3,000-5,000 paths) with this capability enabled completes in well under one minute on typical hardware.
- **SC-007**: `docs/BRD.md` documents this capability's modeled behavior, its current-age-conditioning design choice, and its remaining disclosed gaps in one place.

## Assumptions

- Draws are conditioned on each covered member's `current_age` using that curve's own documented age range; a `current_age` outside the range is handled via the two boundary simplifications in Edge Cases above (treated as certain-alive below the range; the curve's oldest documented age's probability above it) rather than raising, so that every caller-supplied member/curve pairing can be drawn from without a runtime error.
- Each member's death age is drawn independently of that path's own return sequence (no modeled correlation between market performance and mortality) and independently of the other household member's own draw (no modeled correlation between spouses' mortality, e.g. the "broken heart" effect) -- both documented simplifications; joint/correlated draws are explicitly out of scope for this feature.
- A household where both members draw a within-horizon death on the same path reuses 018's existing "earlier death wins, survivor's own later configured death has no further modeled effect" rule unchanged -- no new end-of-projection concept is introduced.
- `SURVIVAL_TABLE` (`simulation/survival_data.py`) remains an illustrative, unverified placeholder; this feature changes nothing about its verification status or its documented age range (50-110).
- Out of scope: any BFF route or Streamlit UI change; joint/correlated mortality-market or spouse-spouse draws; any change to `survival_adjusted_success_rate`'s own formula; remarriage or Qualifying Surviving Spouse modeling (already out of scope per 018); a third mortality-scoring mode beyond the two that will now exist side by side.
