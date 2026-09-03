# Phase 0 Research: Year-by-Year Results Walkthrough

No `NEEDS CLARIFICATION` markers remain in the Technical Context (spec.md's own Clarifications
session already resolved the two decisions — tax-change threshold, batch size — that would
otherwise have needed research). The decisions below are the implementation-shape questions the
spec deliberately left to planning.

## 1. Where do the new dataclasses live: `narrative.py` or `models.py`?

**Decision**: `NarrativeEntry`, `YearStory`, and `RunNarrative` are added to
`reporting/models.py`, alongside the existing `SummaryStatistics`. `narrative.py` holds only the
three functions (`select_representative_path`, `build_year_stories`, `build_narrative_for_run`)
and imports its dataclasses from `.models` — exactly the shape `aggregation.py` already has with
`SummaryStatistics`.

**Rationale**: Every existing concern-module in `reporting/` (`aggregation.py`,
`account_attribution.py`, `export.py`) follows the same split: shared dataclasses in
`models.py`, computation in the concern-module, which imports its types from `.models`. Matching
that existing, consistent internal convention keeps the package's own shape predictable for the
next feature that touches it, and is what `reporting/__init__.py`'s export list already expects
(one place — `models.py` — to look for "what shapes does this package hand back").

**Alternatives considered**: Defining the dataclasses directly inside `narrative.py` (a literal
reading of the parent bead's shorthand description, which lists the new module and the new
dataclasses in the same sentence). Rejected — it would be the one concern-module in `reporting/`
that breaks the models.py/concern-module split every sibling module follows, for no functional
benefit; the bead's phrasing groups them for brevity, not as an architectural instruction.

## 2. Driver detection: transition-based, not current-value-based

**Decision**: Every driver in FR-003 is detected by comparing a plan year's relevant field(s)
against the *prior* plan year's same field(s) (or, for plan year 1, against that year's own
starting values) — never by testing only the current year's value in isolation. `RmdResult`/
`member_rmd_amounts` "start" means the specific transition zero → nonzero for a given household
member, not "RMDs are nonzero this year" (which would re-fire identically every subsequent year).

**Rationale**: The parent bead's design notes are explicit on this point ("walks
`projection.years` pairwise to detect transitions, e.g. RMD 0->nonzero, not just current-year
values"). A current-value-only check would make the story repeat the same "you are taking RMDs"
sentence for every one of the remaining 20+ plan years, which is noise, not narration — it
defeats SC-001's "plain-language story... for every plan year" by drowning the one meaningful
event (the start) in identical restatements.

**Alternatives considered**: Having the simulation/comparison engine itself emit an explicit
event log alongside each `PlanYearProjection` (rejected — touches the simulation core and
`PlanYearProjection`'s schema, which the bead explicitly rules out and Principle IV's module-
boundary discipline argues against: a reporting concern should not require a core-engine change to
add). Re-deriving events from only each year's raw values with no pairwise comparison (rejected
per above — produces repeated noise, not a story).

## 3. Field sources per v1 driver (FR-003/FR-004) — no new computation

Every driver reads only fields `PlanYearProjection` (and its nested results) already carries,
confirming FR-004/FR-014 (no new tax/mechanics/simulation computation):

| Driver | Source field(s) | Transition detected |
|---|---|---|
| RMD start | `member_rmd_amounts[person] ` (011/015) | Per member: `0.0` (or absent) → `> 0` |
| SS claiming | `member_social_security_benefits[person]` (015; already net of 025's earnings-test withholding) | Per member: `0.0` → `> 0` |
| Roth conversion | `mechanics.conversion.amount_converted` | Every year `> 0` (an occurrence-based driver like shortfall, not just its first year — the conversion amount can vary year to year under a bracket-fill strategy, and there is no separate "strategy started" event to detect since `withdrawal_strategy`/`conversion_strategy` are fixed for the whole run) |
| Withdrawal-source sequencing | `mechanics.withdrawal_plan.sequence_withdrawals` (list of `WithdrawalLineItem{account_type, amount}`); cites `WITHDRAWAL_STRATEGIES[strategy.withdrawal_strategy]` for the ordered source list used in the sentence | Per account_type: `0.0` → `> 0` (a new source starts being tapped) or `> 0` → `0.0` (a source is exhausted) |
| Meaningfully large tax change | `federal_tax.federal_tax_owed + state_tax.state_tax_owed` | `abs(this_year - prior_year) / prior_year >= 0.15` (per Clarifications; when `prior_year == 0`, treat any `this_year > 0` as crossing the threshold, avoiding a division by zero) |
| IRMAA start / lookback↔proxy switch | `irmaa.surcharge_owed`, `irmaa.income_basis` (`"two_year_lookback"` \| `"current_year_proxy"`) | `surcharge_owed`: `0.0` → `> 0`; `income_basis`: any change from the prior year's value |
| Survivor death | `filing_status` (effective, 018), `effective_spending_need` | `filing_status` changes from `"married_filing_jointly"` → `"single"` (018's own documented transition) |
| Shortfall | `shortfall` (on `PlanYearProjection`, from `WithdrawalPlan.shortfall`) | Every year `> 0` (occurrence-based, per spec.md Edge Cases — not just the first) |

Deferred-out-of-v1 detail (FR-007: HSA, FICA, SS earnings-test withholding, inherited-account
detail, state exclusions, NIIT) is simply never read by `narrative.py` — it remains visible
wherever the page already surfaces raw per-year numbers (the existing account/detail tables),
untouched by this feature.

## 4. Per-year unverified-figure scoping (US3, FR-011)

**Decision**: `YearStory` carries its own `unverified_figure_names: list[str]` field, computed by
`build_year_stories()` from that plan year's own `PlanYearProjection.figures_used` — the same
dedup-by-name derivation `aggregation.py` already uses for `SummaryStatistics.unverified_figure_names`,
promoted from `aggregation._unverified_figure_names()` (private) to a public
`reporting.unverified_figure_names()` function both modules import from one place.
`4_Walkthrough.py` passes each shown year's list straight into the existing
`render_verification_indicator()` — no new flagging mechanism, no re-derivation in the UI layer.

**Rationale**: Mirrors `SummaryStatistics.unverified_figure_names`'s own precedent exactly: the
reporting layer computes "which figures are unverified" once, ready-made, and every UI surface
(2_Run_Simulation.py, 3_Compare.py, and now 4_Walkthrough.py) only ever renders a name list it
was handed — there is exactly one place in the codebase that decides what "unverified" means for
a given set of figures (Principle III's own spirit: one auditability source of truth). Promoting
the existing private helper to public, rather than writing a second copy of the same dedup logic
inside `narrative.py`, follows the same precedent 006-reporting-aggregation set when it promoted
`_member_age_in_tax_year`/`_deemed_rmd_owner` to public for exactly this reason ("so that feature
can reuse this exact formula rather than re-implementing it").

**Alternatives considered**: Having `4_Walkthrough.py` re-derive each year's unverified names
live from the existing `run["path_results"][index]["years"][i]["figures_used"]` JSON already
present in `run_last_result` (no `YearStory` field needed). Rejected — it would duplicate
`_unverified_figure_names()`'s dedup-by-name logic a second time in UI code (Python operating on
plain dicts, not the typed `FigureUsage` dataclass), the one place this project has otherwise
kept as a single reporting-layer source of truth.

## 5. `select_representative_path` input shape

**Decision**: `select_representative_path(run: SimulationRun) -> int` operates on the
`SimulationRun` POST /simulations already produces — `run.percentile_bands[-1].percentiles[0.50]`
(the final plan year's median ending balance) is the target; the returned index is
`argmin(abs(path.outcome.ending_balance - target) for path in run.path_results)`, ties broken by
the lower index.

**Rationale**: `percentile_bands` is populated for every `SimulationRun` regardless of
`n_paths` (`_percentile_bands()` only returns `[]` when `path_results` itself is empty, which
`run_simulation()` never produces), so the FR-001 "no percentile bands" fallback case does not
arise through this feature's one call site (`POST /simulations`, always a Monte Carlo
`SimulationRun` per FR-012's scope). The fallback is kept in FR-001's wording anyway as a defensive
contract for `narrative.py`'s own unit tests and any future caller — `build_narrative_for_run`
selects path `0` outright when `run.path_results` has length 1, without touching
`percentile_bands` at all in that case.

**Alternatives considered**: Accepting a bare `PlanProjection` (deterministic single-path
candidate) as an alternate input the way `aggregation.py` offers both `summarize_run()` and
`_summarize_plan_projection()`. Rejected for v1 — FR-012 scopes this feature to the Run Simulation
page only, which always calls the Monte Carlo `run_simulation()` path; adding a second entry
point for a caller that doesn't exist yet is speculative and can be added later without
changing `RunNarrative`'s shape.

## 6. BFF wiring: no new module

**Decision**: `run_simulation_route()` in `services/bff/src/rp_bff/routes/simulations.py` calls
`build_narrative_for_run(run, household=context.household, reference_tax_year=body.reference_tax_year)`
directly and adds `"narrative": to_jsonable(narrative)` to the existing response dict — no new
`rp_bff` module.

**Rationale**: Matches how `summarize_run()` is already called directly in that same route with
no wrapper module. `account_detail.py` exists as a separate module only because it has real
branching logic of its own (path-index validation, two build functions for two candidate shapes)
— `build_narrative_for_run()` has neither; introducing a module for a single one-line call would
be an unjustified indirection.

## 7. UI wiring: no new HTTP call

**Decision**: `4_Walkthrough.py` reads `st.session_state["run_last_result"]["narrative"]` — the
same dict `2_Run_Simulation.py` already stores after a successful `run_simulation()` call — and
renders it with local batch/pagination state (`st.session_state["walkthrough_batch_index"]`,
reset whenever a new `run_last_result` is stored). If `"run_last_result"` is absent, the page
shows guidance to run a simulation first (FR-013), matching how `2_Run_Simulation.py`'s own
results section is itself gated on `"run_last_result" in st.session_state`.

**Rationale**: Direct requirement of FR-008 (no new round trip) and the existing page's own
established pattern for reading a stored simulation result.
