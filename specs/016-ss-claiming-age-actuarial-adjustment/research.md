# Phase 0 Research: Social Security Claiming-Age Actuarial Adjustment

No `[NEEDS CLARIFICATION]` markers were left in spec.md, so this phase focuses on the design
decisions needed to turn the spec's requirements into a plan that fits this codebase's existing
conventions and minimizes migration cost — decided by reading the actual modules involved rather
than by assumption.

## Decision 1: Where the adjustment logic lives

**Decision**: A new module, `src/retirement_planner/mechanics/social_security_benefit.py`, exposing
`compute_social_security_benefit(primary_insurance_amount, full_retirement_age, claiming_age,
tax_year) -> SocialSecurityBenefitResult`.

**Rationale**: `tax/social_security.py` computes *taxability* of an already-known gross benefit
(26 U.S.C. §86) — it takes `social_security_gross_benefit` as a given input, it does not derive it.
Deriving the *amount* of a cash-flow benefit from a household member's own facts (age, a table
lookup) is exactly what `mechanics/rmd.py` already does for RMDs — it reuses `SourcedFigure` from
`retirement_planner.tax` (proving that primitive is meant to be shared beyond the `tax` package)
for a table that determines a dollar amount owed to/from an account, not a tax rate. This feature is
that same shape: a table-driven, age-keyed dollar-amount derivation. `mechanics` is also where
`compute_plan_year_mechanics()` and its per-year callers already live, so a new mechanics function is
the smallest addition to the existing import graph (`comparison/projection.py` already imports from
`retirement_planner.mechanics`).

**Alternatives considered**:
- *Add it to `tax/social_security.py`*: rejected — that module's whole contract (per
  `specs/002-tax-calculation-engine/contracts/tax-api.md`) is "takes income components, returns a tax
  result"; it has no notion of claiming age or account-mechanics-style per-member state, and mixing
  the two would blur that module's one job.
- *Compute it inline in `comparison/projection.py`'s `_member_gross_social_security_benefits()`*:
  rejected — this project's own `RMD_START_AGE`/`UNIFORM_LIFETIME_TABLE`/`JOINT_LIFE_TABLE` precedent
  keeps every citable, tabular figure in its own module under `mechanics/`, not inlined into the
  projection loop; the projection loop only orchestrates calls to these modules (see
  `run_plan_projection()`'s structure: RMD → mechanics → tax → ...).

## Decision 2: How the reduction/credit rates are represented and cited

**Decision**: A private dataclass (`_ClaimingAgeAdjustmentRates`) holding the three per-month rates
and the 36-month tier boundary, wrapped in a `SourcedFigure[_ClaimingAgeAdjustmentRates]` named
`SS_CLAIMING_AGE_ADJUSTMENT`, with `schedule={year: <the one rate set> for year in
_DOCUMENTED_YEARS}` — mirroring `tax/social_security.py`'s own provisional-income-threshold pattern
(also a figure "fixed since [a past date], not annually revised," repeated flat across the schedule
so a multi-year caller never hits `UnsupportedTaxYearError`) and `mechanics/rmd.py`'s
`UNIFORM_LIFETIME_TABLE` (an age-keyed table wrapped the same way).

**Citation**: 42 U.S.C. §402(q) (early retirement reduction) and §402(w) (delayed retirement
credit), as implemented at 20 C.F.R. §404.410 (reduction) and §404.313 (delayed credit) — the
specific per-month rates (5/9 of 1% for the first 36 months early, 5/12 of 1% beyond that, 2/3 of 1%
per month delayed) are fixed by these regulations, not adjusted annually, exactly like the SS
provisional-income thresholds already in this codebase. `verified=True` only after cross-checking the
regulation text directly at implementation time, per this project's `verified-figure gate`
(constitution, Development Workflow & Quality Gates) — the plan does not pre-assert verification here.

**Rationale**: This is the smallest change that gives the figure the same auditability trail
(`FigureUsage`, `last_verified`, `citation`, `verified` flag) every other regulated number in this
codebase already carries, satisfying FR-007 and User Story 3 directly.

**Alternatives considered**: A bare module-level constant with a citation only in a comment (like
`_UNIFORM_LIFETIME_DIVISORS`'s raw dict, which itself has no `FigureUsage` — only its *wrapping*
`SourcedFigure`, `UNIFORM_LIFETIME_TABLE`, carries the citation). Rejected for the same reason
`UNIFORM_LIFETIME_TABLE` wraps `_UNIFORM_LIFETIME_DIVISORS`: only a `SourcedFigure` produces a
`FigureUsage` that flows into a `PlanYearProjection.figures_used` trail, and this feature needs that
trail (a household should be able to see this figure's citation the same way it can already see the
federal bracket table's).

## Decision 3: Backward-compatible default for `full_retirement_age` (revises spec.md Assumptions)

**Decision**: `full_retirement_age` is an **optional** field on `HouseholdMember`, defaulting —
when a scenario's YAML omits it — to that member's own `ss_claim_age` (cast to `float`). A member
with no configured FRA is therefore treated as claiming exactly at FRA: zero reduction, zero credit,
paid benefit equals the configured `ss_annual_benefit` exactly. This mirrors `010-advanced-tax-benefits`'s
own precedent for `hdhp_coverage: bool = False` and `hsa_contribution: HsaContributionPlan | None =
None` — "defaults to a value that reproduces every existing scenario's exact current behavior."

**Rationale (supersedes spec.md's original assumption of a required, breaking field)**: A repo-wide
grep found 34 files (test fixtures, BFF/UI tests, e2e tests, example scenarios) that construct a
`HouseholdMember`/YAML scenario with `ss_annual_benefit` under the *old* meaning ("the amount actually
paid at this member's one configured `ss_claim_age`"). None of those scenarios exercise more than one
claiming age per member, so for every one of them, "PIA" and "benefit paid at the one age configured"
are the same number by construction — defaulting FRA to that same claiming age reproduces that
identity exactly, needing zero fixture edits for correctness. Only scenarios that actually want
claiming-age sensitivity (chiefly, anything driving `compare_claiming_age_grid()`) need to be updated
with the member's real PIA and real FRA to get a meaningful comparison — an opt-in accuracy upgrade
a household requests by supplying more complete input, not a breaking change forced on every
scenario that doesn't care about this dimension. This also keeps the change consistent with
Principle I (Accuracy Over Cleverness): no scenario's output silently changes just because this
feature shipped — a changed output only ever follows from a household explicitly supplying a
different FRA than its claiming age.

**Alternatives considered**: A required field (spec.md's original assumption) — rejected after this
research step, once the 34-file blast radius and the exact-reproduction property of the
claim-age-as-default were confirmed; forcing every fixture to state a real PIA/FRA pair would be pure
churn for the ~30 files that aren't testing Social Security claiming behavior at all (RMD tests,
inherited-IRA tests, HSA tests, reporting tests, ...).

## Decision 4: Single call site to fix, reused everywhere by construction

**Decision**: Only `comparison/projection.py`'s `_member_gross_social_security_benefits()` needs to
change. No change is needed in `simulation/`.

**Rationale**: `simulation/monte_carlo.py` and `simulation/compare.py` both import and call
`comparison.run_plan_projection()` directly (confirmed by import trace) rather than reimplementing
the per-plan-year loop — `run_plan_projection()` is the single per-year orchestration point every
engine path (deterministic single-run, every comparison axis, every Monte Carlo path) already funnels
through. Fixing the benefit derivation inside it therefore automatically satisfies User Story 2 (every
projection path, not just the claiming-age grid) without touching `simulation/` at all — the earlier
BRD gap-review's characterization of `simulation/compare.py` needing its own fix does not hold up once
the import graph is traced; `simulation/compare.py`'s `compare_claiming_age_grid()` only builds
`StrategyConfiguration` objects and calls `run_simulation()`, which itself calls
`comparison.run_plan_projection()` per path.

**Alternatives considered**: Duplicating the fix into a hypothetical simulation-local benefit
function — rejected; no such function exists to duplicate into, and doing so would violate this
project's own "one parse/construct code path" precedent (`services/bff/routes/scenarios.py`'s
`_request_to_yaml_text()` docstring) applied to the projection loop instead of the parse path.

## Decision 5: Validation additions

**Decision**: `validation.py`'s `_validate_household()` gains one new **warning** (non-blocking) rule:
flag a member whose `full_retirement_age` falls outside `[65.0, 67.0]` — the range covering every FRA
Social Security's own rules can produce for a still-living claimant (age 65 for anyone born before
1938, rising in two-month steps to 67 for anyone born 1960 or later) — as an implausible-input
plausibility concern, following the same `ValidationFlag(severity="warning")` pattern already used
for the spending-vs-assets plausibility check. The existing `ss_claim_age` bound (62–70 inclusive,
`_validate_household()` lines 118-128) already covers FR-008 — confirmed by reading `validation.py`
directly — so FR-008 requires no new code, only confirmation it already holds.

**Rationale**: Matches FR-009 exactly, and the existing severity-and-message style used one function
above it in the same file.

**Alternatives considered**: A blocking flag for FRA outside the plausible range — rejected; spec.md's
Edge Cases explicitly calls for a warning, not a rejection, since an FRA slightly outside today's
real range is implausible but not definitionally impossible for this tool's own bounded-precision
purposes (and blocking would be a harsher gate than the analogous spending-plausibility check nearby
uses for a comparably "probably wrong but not incoherent" input).

## Decision 6: BFF and Streamlit UI changes are mechanical, not structural

**Decision**: `services/bff/src/rp_bff/schemas.py`'s `HouseholdMemberRequest` gains
`full_retirement_age: float | None = None`, mirroring `HouseholdMember` exactly (confirmed:
`_request_to_yaml_text()` does a generic `model_dump(mode="json")` → `yaml.safe_dump()` → the same
`parse_scenario()` every other route already uses, so no per-field BFF logic exists to update beyond
the schema declaration). Response serialization (`to_jsonable()`) is fully generic over dataclass
fields (`dataclasses.fields(obj)`), so the new field appears in every response automatically with no
`serialization.py` change. `apps/streamlit_ui/pages/1_Scenarios.py` needs the same repeated
per-member pattern every other member field already follows (session-state default, load-from-scenario
assignment, a `st.number_input` widget, and inclusion in the saved-scenario payload dict) — mechanical,
not a new pattern, applied twice (once per household member slot the page supports).

**Rationale**: Confirmed by reading both files directly rather than assuming; avoids over-scoping the
plan with speculative BFF/UI redesign this feature does not need.
