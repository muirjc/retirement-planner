# Feature Specification: Strategy Comparison Layer

**Feature Branch**: `004-strategy-comparison-layer`

**Created**: 2026-08-27

**Status**: Draft

**Input**: User description: "docs/initial_requirement.md continue with section 3. you can look to the spec 001-scenario-config-management to and 002-tax-calculation-engine and 003-retirement-account-mechanics to see what has already been done"

**Scope note**: `docs/initial_requirement.md` describes a five-phase retirement planning tool; feature `001-scenario-config-management` covered §3.1 (input/configuration), `002-tax-calculation-engine` covered §3.2 (federal/state tax calculation), and `003-retirement-account-mechanics` covered §3.3 (RMD, withdrawal sequencing, and Roth conversion execution for one plan year under one chosen strategy). This spec covers §3.4 (Strategy / Optimization Layer): running those single-year mechanics repeatedly across a full multi-year retirement horizon, and comparing multiple candidate configurations — Roth conversion strategies, withdrawal sequencing orders, and Social Security claiming-age pairs — against each other under identical market-return assumptions, so a user can see which choice produces the better outcome. It does not cover generating random, multi-path Monte Carlo return draws or a probability-based "success rate" across many simulated futures — the source document's §3.5 "Simulation Engine" (paired-draw random return generation, historical bootstrap, sequence-of-returns stress testing, mortality modeling) is explicitly out of scope here and remains a separate future feature; this feature instead runs each multi-year projection under one fixed, deterministic return-path assumption per comparison, so that every compared configuration is evaluated on identical terms. It does not compute federal or state tax itself (delivered by `002-tax-calculation-engine`, consumed as an input), does not perform RMD determination, withdrawal execution, or Roth conversion execution itself (delivered by `003-retirement-account-mechanics`, consumed as an input for each year of the horizon), and does not render charts, tables, or verification-flag propagation into reports (§3.6, a separate future feature) — it produces structured comparison results for a future reporting feature to present.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Project a single plan across its full retirement horizon (Priority: P1)

A user wants to see what happens to a household's accounts, income, and taxes over their entire retirement — not just one plan year — by running RMD, withdrawal sequencing, Roth conversion, and tax calculation for one chosen strategy configuration, year after year, from the start of retirement through the scenario's planning horizon.

**Why this priority**: Every comparison this feature offers (Roth conversion strategies, withdrawal orders, claiming ages) is the same multi-year projection run more than once with one input changed. Without the ability to run a single full-horizon projection correctly first, there is nothing to compare, and no way to tell whether a difference between two comparison results is real or a projection bug.

**Independent Test**: Can be fully tested by feeding one complete scenario (household, accounts, spending, one Roth conversion strategy, one withdrawal sequencing order, one state, one market return assumption) and confirming the system produces a year-by-year record of income, tax, withdrawals, conversions, and account balances from the first retirement year through the planning horizon, with each year's ending balances correctly carried forward as the next year's starting balances — without needing more than one strategy configuration or comparison to be built yet.

**Acceptance Scenarios**:

1. **Given** a complete scenario with one chosen Roth conversion strategy and one chosen withdrawal sequencing order, **When** a full-horizon projection is run, **Then** the result contains one entry per plan year from the first retirement year through the configured planning horizon, each with that year's RMD, withdrawals by account, conversion amount, income, tax owed, and ending account balances.
2. **Given** a projected year's ending account balances, **When** the next year's projection step runs, **Then** it starts from exactly those ending balances plus that year's configured investment growth — never from the original starting balances.
3. **Given** a scenario whose accounts are depleted before the spending need for a plan year can be fully met, **When** the projection reaches that year, **Then** it records the shortfall and the year it first occurred, and continues (or stops, per a documented rule) rather than raising an unhandled error.
4. **Given** the same scenario, strategy configuration, and market return assumption run twice, **When** both projections complete, **Then** every year's results are identical between the two runs.

---

### User Story 2 - Compare Roth conversion strategies against each other (Priority: P2)

A user wants to run the same full-horizon projection under each of several Roth conversion strategies — fill-to-10%-bracket-ceiling, fill-to-22%-bracket-ceiling, a fixed dollar amount each year, and no conversion at all — with every other input (accounts, spending, withdrawal order, claiming ages, market return assumption) held identical, so the only thing that differs between results is the conversion strategy itself.

**Why this priority**: Roth conversion strategy is one of the tool's three core comparison questions from the source document and the one it calls out first in this section; a user cannot judge whether converting is worthwhile, or how aggressively, without seeing multiple strategies' full-horizon outcomes side by side. It depends on User Story 1 (a working single-strategy projection) but is independently valuable and testable once that exists.

**Independent Test**: Can be fully tested by feeding one scenario and a list of Roth conversion strategy configurations, running the full-horizon projection once per strategy under the identical market return assumption, and confirming the returned comparison holds one outcome per strategy with the same market assumption applied to every one, and that the strategies' outcomes differ only where the strategies' rules actually imply a difference.

**Acceptance Scenarios**:

1. **Given** a scenario and the four named Roth conversion strategies, **When** the comparison is run, **Then** the result contains one full-horizon outcome per strategy, each computed under the identical deterministic market return assumption.
2. **Given** the "no conversion" strategy and a "fill to bracket ceiling" strategy applied to the same scenario, **When** compared, **Then** the two outcomes' cumulative lifetime tax paid and ending account balance differ in the direction implied by moving money from traditional to Roth earlier.
3. **Given** a comparison of two strategies whose configured amounts happen to produce identical annual conversions for this scenario, **When** compared, **Then** their outcomes are identical — the comparison never fabricates a difference that the strategies' actual behavior doesn't produce.
4. **Given** a completed comparison, **When** its results are inspected, **Then** every compared strategy's outcome is present in a single structured result, not as separate, uncorrelated reports the user must manually align.

---

### User Story 3 - Compare withdrawal sequencing orders against each other (Priority: P3)

A user wants to run the same full-horizon projection under two or more withdrawal sequencing orders — for example, drawing traditional-account funds before taxable funds, versus the reverse — with the Roth conversion strategy, claiming ages, and market return assumption held identical, to see how sequencing choice alone affects tax drag and how long the money lasts.

**Why this priority**: The source document identifies withdrawal order as materially affecting both tax drag and longevity, using the same paired-comparison approach already established for states. It depends on User Story 1's projection mechanics but is independently valuable and testable on its own once at least two sequencing orders exist to compare.

**Independent Test**: Can be fully tested by feeding one scenario and two or more withdrawal sequencing configurations, running the full-horizon projection once per order under the identical market return assumption, and confirming the returned comparison holds one outcome per order with identical non-sequencing inputs across all of them.

**Acceptance Scenarios**:

1. **Given** a scenario and two withdrawal sequencing orders, **When** the comparison is run, **Then** the result contains one full-horizon outcome per order, each computed under the identical deterministic market return assumption and the identical Roth conversion strategy.
2. **Given** two sequencing orders that draw down taxable versus traditional accounts in a different order, **When** compared, **Then** the two outcomes' cumulative lifetime tax paid or ending account balance differ, reflecting the different tax treatment of each account type drawn earlier.
3. **Given** a scenario where one account type is exhausted early enough that both compared orders draw from the same remaining accounts in the same way thereafter, **When** compared, **Then** the outcomes converge after that point rather than the comparison inventing an artificial continued difference.

---

### User Story 4 - Compare Social Security claiming-age combinations against each other (Priority: P4)

A user wants to run the same full-horizon projection across a grid of Social Security claiming ages (62 through 70) for each spouse, with the Roth conversion strategy, withdrawal order, and market return assumption held identical, to see how claiming-age choice alone affects household outcomes.

**Why this priority**: This is the least commonly revisited of the three comparison axes in the source document (claiming age is typically a small, discrete decision made once, not a rerun-every-quarter question), and it depends on both a working full-horizon projection (User Story 1) and the paired-comparison mechanism already proven out by Roth conversion and withdrawal-order comparisons. It stands alone once those exist.

**Independent Test**: Can be fully tested by feeding one scenario and a grid of claiming-age pairs for a two-person household, running the full-horizon projection once per pair under the identical market return assumption, and confirming the returned comparison holds one outcome per claiming-age pair with every other input identical across the grid.

**Acceptance Scenarios**:

1. **Given** a two-person household and the full 62–70 claiming-age grid for each spouse, **When** the comparison is run, **Then** the result contains one full-horizon outcome per claiming-age pair in the grid, each computed under the identical deterministic market return assumption, Roth conversion strategy, and withdrawal order.
2. **Given** two claiming-age pairs where one spouse claims earlier in one pair and later in the other, **When** compared, **Then** the outcomes' Social Security income timing, taxable income, and ending balance differ in the direction implied by the earlier or later claim.
3. **Given** a claiming-age pair identical to the scenario's originally configured claiming ages, **When** it appears in the grid comparison, **Then** its outcome matches the User Story 1 single-projection result for that same scenario exactly.

---

### Edge Cases

- What happens when a comparison is requested with only one candidate configuration (one strategy, one sequencing order, or one claiming-age pair)? The system MUST still run and return a valid single-entry comparison result rather than requiring at least two candidates.
- What happens when a household's accounts are fully depleted partway through the horizon for one compared configuration but not another? Each configuration's projection records its own depletion year (if any) independently; the comparison result MUST make it possible to tell, for each configuration, whether and when depletion occurred, without one configuration's depletion truncating or corrupting another's results.
- What happens when a claiming-age pair in the grid would have a spouse claiming before the earliest allowed age or after the latest allowed age? Ages outside 62–70 (already rejected at scenario load time per `001-scenario-config-management`'s validation) MUST NOT be accepted as grid parameters either — the same bound applies to every claiming age this feature evaluates, not only the scenario's originally configured one.
- What happens when a Roth conversion strategy's configured window has already ended before the horizon begins, or hasn't started, in a given plan year? The projection MUST compute a $0 conversion for that year — matching `003-retirement-account-mechanics` — for every compared strategy, so an inactive window never appears as an artificial difference between strategies.
- What happens when two candidate configurations in the same comparison produce identical year-by-year results because their rules never actually diverge for this scenario? The comparison MUST report both outcomes as given, including their equality, rather than needing them to differ to be considered a valid comparison.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST run a full-horizon plan projection for one strategy configuration (one Roth conversion strategy, one withdrawal sequencing order, one set of claiming ages) by applying, for each plan year in sequence from the first retirement year through the scenario's configured planning horizon: RMD determination, withdrawal sequencing, and Roth conversion execution (each per `003-retirement-account-mechanics`), followed by federal and state tax calculation for that year's resulting income (per `002-tax-calculation-engine`).
- **FR-002**: The system MUST carry each plan year's ending account balances forward as the starting balances for the following plan year, applying the scenario's configured market return assumption to grow unwithdrawn balances between years.
- **FR-003**: The system MUST apply one fixed, deterministic annual return derived from the scenario's configured market assumption (not a randomly drawn value) to every plan year of a projection, and MUST document this as a simplification standing in for genuine multi-path Monte Carlo simulation, which is deferred to the future Simulation Engine feature (§3.5).
- **FR-004**: For each full-horizon projection, the system MUST produce plan-level outcome metrics: the real-terms ending account balance at the end of the horizon, the first plan year (if any) in which spending need could not be fully met, and the cumulative tax paid across all projected years.
- **FR-005**: The system MUST support running the identical full-horizon projection under each of a list of Roth conversion strategy configurations — at minimum fill-to-10%-bracket-ceiling, fill-to-22%-bracket-ceiling, a fixed dollar amount, and no conversion — while holding every other input (accounts, spending, withdrawal order, claiming ages, market return assumption) identical across the list, and MUST return one outcome per strategy in a single structured comparison result.
- **FR-006**: The system MUST support running the identical full-horizon projection under each of a list of two or more withdrawal sequencing order configurations while holding every other input (Roth conversion strategy, claiming ages, market return assumption) identical across the list, and MUST return one outcome per sequencing order in a single structured comparison result.
- **FR-007**: The system MUST provide at least one withdrawal sequencing order configuration in addition to the single default order shipped by `003-retirement-account-mechanics`, so that a withdrawal-order comparison has at least two genuinely different orders to compare.
- **FR-008**: The system MUST support running the identical full-horizon projection across a grid of Social Security claiming-age pairs, where each spouse's claiming age independently ranges across the scenario's allowed claiming-age bounds, while holding every other input (Roth conversion strategy, withdrawal order, market return assumption) identical across the grid, and MUST return one outcome per claiming-age pair in a single structured comparison result.
- **FR-009**: Within any single comparison (Roth conversion strategy, withdrawal order, or claiming-age grid), the system MUST apply the exact same deterministic market return assumption to every compared configuration, so that any difference between outcomes is attributable only to the dimension being compared.
- **FR-010**: The system MUST reject or flag comparison requests containing a claiming age outside the scenario's allowed claiming-age bounds, using the same bounds enforced at scenario load time.
- **FR-011**: The system MUST allow a comparison to run with as few as one candidate configuration and still return a valid comparison result.
- **FR-012**: Given identical scenario inputs, strategy configuration, and market return assumption, the system MUST produce identical full-horizon projection and comparison results on every run.
- **FR-013**: Any verification flag attached to a tax figure by `002-tax-calculation-engine` for a plan year MUST be retained, per year and per compared configuration, in the projection's structured output — this feature MUST NOT discard or silently resolve those flags, even though rendering them into a report is out of scope here.

### Key Entities

- **Plan Projection**: The year-by-year record produced by running one strategy configuration across the full retirement horizon — one entry per plan year, each carrying that year's RMD, withdrawals, conversion, income, tax (including any verification flags), and ending account balances.
- **Strategy Configuration**: The complete set of choices held fixed for one projection — a Roth conversion strategy, a withdrawal sequencing order, and a claiming-age pair — distinct from the market return assumption, which is held constant across an entire comparison rather than varied per configuration.
- **Plan Outcome**: The summary metrics derived from one Plan Projection — ending account balance, first shortfall year (if any), and cumulative tax paid — used to compare configurations against each other.
- **Comparison Result**: A set of Plan Outcomes (and their underlying Plan Projections), one per candidate configuration in a single comparison request, computed under one shared deterministic market return assumption so the set is fairly comparable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can obtain a complete full-horizon projection (30+ plan years) for one strategy configuration, with every year's balances, income, tax, and metrics populated, without needing to run or wire together the account-mechanics and tax calculations manually year by year.
- **SC-002**: A user comparing the four named Roth conversion strategies against the same scenario receives one ending balance and one cumulative lifetime tax figure per strategy, computed under identical market conditions, letting them identify which strategy leaves more after-tax wealth without recomputing anything by hand.
- **SC-003**: A user comparing two or more withdrawal sequencing orders against the same scenario receives one outcome per order, computed under identical market conditions, letting them identify which order reduces lifetime tax or extends how long the money lasts.
- **SC-004**: A user comparing Social Security claiming-age combinations receives one outcome per combination across the full 62–70 grid for each spouse, without needing to manually reconfigure and rerun the scenario once per combination.
- **SC-005**: In 100% of comparisons run by this feature, every compared configuration's outcome is generated using the identical underlying market return assumption, so a user can attribute any outcome difference solely to the dimension being compared.
- **SC-006**: Running the same scenario, strategy configuration, and market return assumption twice always produces identical projection and comparison results.

## Assumptions

- **Deterministic projection stands in for full Monte Carlo.** This feature evaluates every full-horizon projection under one fixed, deterministic annual return derived from the scenario's configured market assumption (e.g., the mean real return), not a probability distribution across many randomly drawn return paths. The source document's "compare success rates" language for this section describes an eventual outcome that requires genuine multi-path Monte Carlo simulation — explicitly cataloged as prototype-only ("implemented" in the existing scripts) and separated out as its own future §3.5 "Simulation Engine" feature. This feature delivers the strategy/claiming-age comparison mechanism and the paired-assumption discipline now, so that plugging in real stochastic return generation later changes only how returns are produced, not how comparisons are structured or reported.
- **A second withdrawal sequencing order is added for comparison purposes.** `003-retirement-account-mechanics` shipped exactly one default withdrawal sequencing order behind a swappable interface. Since a comparison needs at least two genuinely different orders to be meaningful, this feature adds at least one additional order (e.g., drawing traditional funds before taxable funds) using that same interface; the exact additional order(s) are an implementation detail decided during planning, not a scope-defining choice.
- **The four Roth conversion strategies match the source document's naming.** "Fill to 10% bracket," "fill to 22% bracket," "fixed dollar amount," and "no conversion" are treated as the required comparison set; the two bracket-ceiling variants reuse `003-retirement-account-mechanics`'s existing fill-to-bracket-ceiling mechanic with the federal bracket edge for the named bracket (per `002-tax-calculation-engine`) supplied as the ceiling.
- **Claiming-age grid parameters override, rather than mutate, the base scenario.** Running a claiming-age comparison does not create or persist new named scenarios (per `001-scenario-config-management`) for every grid cell; each grid cell's claiming-age pair is a per-run parameter substituted into an otherwise identical in-memory copy of the scenario.
- **This feature produces structured comparison data, not rendered reports.** Charts, tables, and CSV export (source document §3.6) are a separate future feature; this feature's responsibility ends at producing a complete, structured Plan Projection and Comparison Result that a reporting feature can consume.
