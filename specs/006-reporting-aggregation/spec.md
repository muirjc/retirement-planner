# Feature Specification: Reporting & Aggregation

**Feature Branch**: `006-reporting-aggregation`

**Created**: 2026-08-28

**Status**: Draft

**Input**: User description: "docs/frontend_architecture.md"

**Scope note**: `docs/frontend_architecture.md` (itself grounded in `docs/initial_requirement.md` §3.6 "Reporting/Output" and `docs/remaining_scope.md`'s gap analysis) lays out a three-feature program — `006` Reporting & Aggregation, `007` BFF API Service, `008` first UI client — for putting a usable front end on the retirement-planning engine `001`–`005` already built. This spec covers only `006`: a pure, offline computation layer that turns `005`'s `SimulationRun`/`SimulationComparisonResult` and `004`'s `ComparisonResult` into decision-ready summary statistics (success rate, percentile ending balances, median depletion age, and the median lifetime tax figure the source document explicitly asks for and no existing feature computes) and into a spreadsheet/document-importable export, while keeping every "needs verification" flag those upstream features already attach fully visible rather than letting it get lost in aggregation. It does not cover HTTP/JSON serialization, an API service, chart rendering, or any UI (`docs/frontend_architecture.md` scopes all of those to `007`/`008`, which depend on this feature's output but are not delivered by it). It does not compute or re-derive any tax, account-mechanics, comparison, or simulation result itself — it consumes `002`–`005`'s existing output types as pure input and adds no new dependency, matching every prior feature's "no new third-party runtime dependency" precedent.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Get a decision-ready summary of one simulation run (Priority: P1)

A user who has run a Monte Carlo simulation (`005`) for one configuration wants a single, complete statistical summary — success rate, percentile ending balances over time, the age at which money ran out (for the paths where it did), and the median amount of lifetime tax paid — rather than manually deriving these from hundreds or thousands of individual per-path results.

**Why this priority**: This is the foundational capability every other story in this feature builds on — comparing candidates (User Story 2) and exporting a report (User Story 3) both start from "can this feature correctly summarize one run." Without it, a user still has everything `005` produces, but only as raw per-path data no one would read directly.

**Independent Test**: Can be fully tested by feeding one completed `SimulationRun` (from `005`) into the summarization function and confirming the result's success rate, percentile ending balances, median depletion age, and median lifetime tax paid all match hand-computed values for that same input — without needing comparison support or export support to exist yet.

**Acceptance Scenarios**:

1. **Given** a completed `SimulationRun` with a mix of successful and depleted paths, **When** it is summarized, **Then** the result's success rate matches the run's own `success_rate`, and its percentile ending balances match the run's own `percentile_bands`.
2. **Given** a `SimulationRun` where some paths deplete before the planning horizon ends, **When** it is summarized, **Then** the result's median depletion age is computed only from the paths that actually depleted, using the household's deemed age at each such path's first shortfall plan year.
3. **Given** a `SimulationRun` where no path ever depletes (100% success), **When** it is summarized, **Then** the median depletion age is reported as not applicable, never as zero or an arbitrary placeholder age.
4. **Given** a `SimulationRun` with paths of varying cumulative tax paid, **When** it is summarized, **Then** the median lifetime tax paid is the median of every path's cumulative tax paid — including paths that ultimately depleted, since tax was still paid along the way.
5. **Given** the same `SimulationRun` summarized twice, **When** both summaries are compared, **Then** they are identical in every field.

---

### User Story 2 - Compare candidates using the same summary shape (Priority: P2)

A user who ran a paired-draw comparison — across states, Roth conversion strategies, withdrawal orders, or claiming ages (`005`), or a deterministic comparison (`004`) — wants one summary per candidate, in the order the candidates were compared, so they can be read side by side without re-deriving statistics for each candidate by hand.

**Why this priority**: Comparison is one of the tool's core purposes (source document §1: tax optimization, location comparison) — a summary that only works for a single run isn't useful for the comparisons the tool exists to support. Depends on User Story 1's summarization logic, reused once per candidate.

**Independent Test**: Can be fully tested by feeding a `SimulationComparisonResult` with several candidate runs into the comparison-summarization function and confirming the result contains one summary per candidate, each matching what User Story 1's single-run summarization would produce for that candidate alone, in the same order the candidates appear in the input.

**Acceptance Scenarios**:

1. **Given** a `SimulationComparisonResult` with N candidate runs, **When** it is summarized, **Then** the result contains exactly N summaries, in the same order as the input's candidates, each one identical to what summarizing that single candidate's run directly would produce.
2. **Given** a deterministic `ComparisonResult` (`004`, no percentile bands or Monte Carlo success rate), **When** it is summarized, **Then** the result reports the fields a deterministic comparison genuinely has (ending balance, first shortfall plan year, cumulative tax paid) and explicitly marks the Monte-Carlo-only fields (success rate, percentile bands) as not applicable — never a fabricated or zero-filled value standing in for missing data.
3. **Given** a comparison result with only one candidate, **When** it is summarized, **Then** the result still contains exactly one summary — a comparison of one candidate is still a valid comparison, matching the precedent `004`'s and `005`'s own comparison functions already established.

---

### User Story 3 - Export a run or comparison as a spreadsheet-ready report (Priority: P3)

A user wants a simulation run's or comparison's results as a structured export they can open in a spreadsheet or paste into their own markdown working document, rather than retyping figures by hand.

**Why this priority**: The source document specifically names this workflow — feeding results into the existing markdown working-document pipe-table conventions. It depends on data this feature already computes (User Stories 1–2) or that `005`/`004` already produce, so it's naturally sequenced last: an export format for numbers this feature doesn't yet know how to compute would be premature.

**Independent Test**: Can be fully tested by feeding a `SimulationRun` (or comparison result) into the export function and confirming the output is well-formed tabular text (a header row plus one data row per observation) that a spreadsheet application or markdown pipe-table converter could consume directly, with every numeric value matching the underlying result.

**Acceptance Scenarios**:

1. **Given** a completed `SimulationRun`, **When** it is exported, **Then** the output is a header row followed by one data row per plan year, with columns for that year's percentile ending balances, and every value traceable back to the run's own `percentile_bands`.
2. **Given** a `SimulationComparisonResult`, **When** it is exported, **Then** the output contains one row (or row group) per candidate, clearly labeled with that candidate's identifying label, so a reader can tell which row belongs to which compared configuration without cross-referencing anything else.
3. **Given** a run or comparison whose underlying figures include at least one still-unverified figure, **When** it is exported, **Then** the exported output visibly indicates which rows or values were informed by an unverified figure — never presenting an unverified number indistinguishably from a verified one, in the export as much as in the summary.

---

### User Story 4 - See which figures are still unverified, prominently (Priority: P4)

A user reading any summary or export from this feature wants to immediately see whether any of the numbers behind it are still-unverified placeholder figures (a state tax bracket table pending confirmation, a synthetic historical-return series, an illustrative survival curve), rather than discovering that fact only by reading source code.

**Why this priority**: The constitution's Auditability principle requires this explicitly ("MUST NOT be indistinguishable from a verified figure in what the user sees") and the source document names it as its own line item. It's the lowest priority only because it depends on User Stories 1–3 already existing to attach this indicator to — on its own it has no summary or export to decorate.

**Independent Test**: Can be fully tested by feeding a `SimulationRun` known to include at least one unverified `FigureUsage` (e.g., `005`'s historical-bootstrap or survival-adjusted paths, which always carry unverified placeholder figures) into both the summarization and export functions, and confirming the unverified figures are named explicitly and completely in both outputs — not merely implied by their absence from a "verified" list.

**Acceptance Scenarios**:

1. **Given** a `SimulationRun` whose `figures_used` includes both verified and unverified entries, **When** it is summarized, **Then** the summary's list of unverified figure names includes every distinct unverified figure and excludes every verified one.
2. **Given** a `SimulationRun` whose `figures_used` contains no unverified entries at all, **When** it is summarized, **Then** the summary's unverified-figure list is present and empty — not omitted, so a reader can positively confirm "nothing here is unverified" rather than being unable to tell the difference between "checked, none unverified" and "not checked."

---

### Edge Cases

- What happens when a `SimulationRun`'s success rate is 100% (no path ever depletes)? Median depletion age is reported as not applicable (Acceptance Scenario US1.3) — never `0`, never omitted, never a fabricated horizon-end value.
- What happens when a `SimulationRun`'s success rate is 0% (every path depletes)? Median lifetime tax paid is still computed normally across all paths (Acceptance Scenario US1.4) — a failed plan still paid taxes along the way, and that figure remains meaningful.
- What happens when summarizing a deterministic `ComparisonResult` (`004`) that has no `percentile_bands` or `success_rate` at all? Those fields are explicitly marked not-applicable in the summary (Acceptance Scenario US2.2), not defaulted to a Monte-Carlo-shaped zero or omitted silently.
- What happens when exporting a run or comparison with zero unverified figures? The export still includes the verification-status indicator column/marker, showing it as "none" explicitly, mirroring User Story 4's "present and empty" requirement for the summary case.
- What happens when the same figure (e.g., a federal bracket table used by every plan year of every path) appears in `figures_used` thousands of times across a run? It is represented once in the unverified-figure list, not once per occurrence — this feature must deduplicate, consistent with `005`'s own existing `figures_used` deduplication discipline.
- What happens when summarizing an empty comparison result (this should not occur, since `004`/`005` both guarantee at least one candidate in FR-010/FR-011 of their own specs) — this feature is not required to handle a zero-candidate comparison, since none of its upstream inputs can ever produce one.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST compute, from a completed `SimulationRun`, a summary containing: the run's success rate, its percentile ending balances by plan year, the median depletion age across paths that depleted, and the median lifetime tax paid across all paths.
- **FR-002**: Median lifetime tax paid MUST be computed as the median of every path's cumulative tax paid, regardless of whether that path ultimately succeeded or depleted (Acceptance Scenario US1.4).
- **FR-003**: Median depletion age MUST be derived from the deemed household member's age (using the same age-translation convention `004`'s multi-year projection already established: current age plus elapsed years from the scenario's reference tax year) at each depleted path's first shortfall plan year, computed only across paths that actually depleted; when no path depletes, this figure MUST be reported as not applicable rather than a numeric placeholder (Edge Cases).
- **FR-004**: The summary MUST include the distinct names of every unverified figure (`verified=False`) present anywhere in the run's `figures_used`, deduplicated, and MUST include this list even when it is empty (Acceptance Scenarios US4.1–US4.2).
- **FR-005**: The system MUST produce one summary per candidate, in input order, from a `SimulationComparisonResult`, each matching what summarizing that single candidate's run directly would produce (Acceptance Scenario US2.1).
- **FR-006**: The system MUST also produce comparable summaries from a deterministic `ComparisonResult` (`004`), reporting the fields such a result genuinely has (ending balance, first shortfall plan year, cumulative tax paid) and explicitly marking Monte-Carlo-only fields (success rate, percentile bands) as not applicable (Acceptance Scenario US2.2).
- **FR-007**: The system MUST support a comparison result containing as few as one candidate and still produce a valid one-entry summary set (Acceptance Scenario US2.3).
- **FR-008**: The system MUST export a `SimulationRun` as tabular text: a header row followed by one data row per plan year, with that year's percentile ending balances as columns (Acceptance Scenario US3.1).
- **FR-009**: The system MUST export a comparison result (either `ComparisonResult` or `SimulationComparisonResult`) as tabular text with one row or row group per candidate, each clearly labeled with that candidate's identifying label (Acceptance Scenario US3.2).
- **FR-010**: Every export MUST visibly indicate, per row, whether any unverified figure informed that row's values — including an explicit "none" indication when no unverified figure was involved, mirroring FR-004's "present even when empty" requirement (Acceptance Scenarios US3.3, Edge Cases).
- **FR-011**: The system MUST NOT discard, alter, or fail to represent any unverified figure present in an input result's `figures_used` — every one already flagged by `002`–`005` MUST be traceable through this feature's summary and export output.
- **FR-012**: The system MUST NOT perform any network I/O and MUST NOT require any dependency beyond the Python standard library, matching `001`–`005`'s established dependency discipline.
- **FR-013**: Given the identical input result object, both the summary and the export output MUST be identical across repeated calls (no hidden state, no non-determinism).
- **FR-014**: This feature MUST NOT modify, re-derive, or duplicate any tax, account-mechanics, comparison, or simulation computation already performed by `002`–`005` — it consumes their output types only.

### Key Entities

- **SummaryStatistics**: The decision-ready summary of one simulation run or one candidate within a comparison — success rate (Monte Carlo inputs only), percentile ending balances by plan year (Monte Carlo inputs only), median depletion age (or not-applicable), median lifetime tax paid, and the deduplicated list of unverified figure names behind it.
- **Comparison Summary Set**: An ordered collection of `SummaryStatistics`, one per candidate in a `SimulationComparisonResult` or `ComparisonResult`, preserving the input's candidate order.
- **Export Report**: The tabular-text representation of a `SimulationRun` or comparison result — a header row, one data row per plan year (single run) or per candidate (comparison), and a per-row verification-status indicator.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can obtain a complete statistical summary of a simulation run — success rate, percentile ending balances, median depletion age, median lifetime tax paid — without manually computing any of these from raw per-path data.
- **SC-002**: A user comparing multiple candidates receives one directly comparable summary per candidate, in the order they were compared, without re-deriving statistics for each candidate separately.
- **SC-003**: A user can obtain a spreadsheet- or document-ready export of a run's or comparison's results without manually retyping any figure.
- **SC-004**: 100% of unverified figures present in a run's or comparison's underlying data are visibly represented in both its summary and its export — a user is never shown a report that treats a placeholder figure as settled.
- **SC-005**: Summarizing or exporting a reference-scale simulation run (5,000 paths) completes with no perceptible added delay beyond the simulation itself finishing.

## Assumptions

- **Chart rendering, JSON serialization, and HTTP transport are explicitly out of scope.** Per `docs/frontend_architecture.md`, these belong to the future `007` (BFF API Service) and `008` (first UI client) features, which consume this feature's output but do not overlap with it.
- **CSV is the concrete export format**, matching the source document's explicit "CSV/data export... pipe-table conventions" ask; the exact column layout is an implementation detail decided during planning, not a scope-defining choice — the requirement is a spreadsheet-importable, one-row-per-observation shape (FR-008/FR-009), not a specific file format library or column ordering.
- **No cross-run aggregation.** This feature summarizes and exports the contents of one run or one comparison result at a time; aggregating results across separately-run simulations from different points in time (e.g., "how has my success rate changed since last quarter") is out of scope.
- **"Deemed household member" for depletion age reuses `004`'s existing convention** (the older household member, or the sole member for a single-filer household) rather than introducing a second, competing notion of whose age represents the household.
- **Deduplication of unverified figures** is by figure name, matching `005`'s own `figures_used` deduplication convention (`(name, last_verified)`), so this feature's summaries don't reintroduce duplicate entries `005` already collapsed — and so a figure appearing under slightly different citation dates isn't miscounted as verified when it isn't.
