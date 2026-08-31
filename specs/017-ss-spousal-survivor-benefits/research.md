# Phase 0 Research: Social Security Spousal and Survivor Benefits

No `[NEEDS CLARIFICATION]` markers were left in spec.md (the user's own scoping answer — this
feature covers primitives + data model, `rp-g8y` covers wiring death into the live projection loop —
resolved what would otherwise have been the single biggest ambiguity). This phase focuses on the
design decisions needed to turn the spec's requirements into a plan that fits this codebase's
existing conventions, decided by reading the actual modules involved rather than by assumption.

## Decision 1: Both new functions join `mechanics/social_security_benefit.py`, not a new module

**Decision**: `compute_spousal_benefit_floor()` and `compute_survivor_benefit()` are added to the
existing `mechanics/social_security_benefit.py` (016), not a new sibling module.

**Rationale**: Both operate on the exact same domain primitives 016 already established in that
module — a member's PIA, FRA, and claiming age, cited via `SourcedFigure`, with no dependency on
`scenario/` (mirrors `compute_social_security_benefit()`'s own existing shape exactly). Splitting
into a new module would duplicate `_DOCUMENTED_YEARS` and the module's existing citation
infrastructure for no benefit — unlike `012`/`013`'s `inherited_rmd.py` sibling-module split from
`rmd.py`, which was justified by a genuinely different *legal* computation (a decedent's forced
depletion schedule vs. a living owner's own RMD, research.md §7 there); spousal/survivor benefits are
not a different legal computation from claiming-age adjustment, they're the next layer of the same
one (42 U.S.C. §402 covers old-age, wife's/husband's, and widow's/widower's benefits together, and
20 C.F.R. §404.410 — 016's own citation — covers the reduction formula for all of them in one
section, confirmed directly against Cornell LII's e-CFR mirror).

**Alternatives considered**: A new `mechanics/spousal_survivor_benefit.py` — rejected for the reason
above; would also force `comparison/projection.py` to import from two mechanics submodules for what
is conceptually one "what does this member actually receive" question.

## Decision 2: Spousal early-claiming reduction rate — a distinct figure, no delayed credit

**Decision**: A new private dataclass (`_SpousalAdjustmentRates`, holding `early_reduction_rate_tier_1`,
`early_reduction_rate_tier_2`, `early_reduction_tier_1_months`), wrapped in a
`SourcedFigure[_SpousalAdjustmentRates]` named `SS_SPOUSAL_CLAIMING_AGE_ADJUSTMENT`, following 016's
own `SS_CLAIMING_AGE_ADJUSTMENT` pattern (`schedule={year: <the one rate set> for year in
_DOCUMENTED_YEARS}` — fixed by regulation, not annually revised). `compute_spousal_benefit_floor()`
applies only the early-reduction side of this rate set (tier 1: 25/36 of 1% per month for the first 36
months claimed before FRA; tier 2: 5/12 of 1% per month beyond that — the same tier-2 rate 016's own
worker-benefit table already uses, but a *different*, larger tier-1 rate) and applies **no**
delayed-retirement-credit side at all: a spousal amount is capped at exactly 50% of the other
member's PIA for claiming at or after FRA, regardless of how much later than FRA the claiming member
actually files (confirmed directly against Cornell LII's e-CFR mirror of 20 C.F.R. §404.410, the same
regulation 016 already cites for the worker's-own-benefit reduction — this is the wife's/husband's
benefit paragraph of that same section, not a separate CFR citation).

**Citation**: 42 U.S.C. §402(b) (wife's insurance benefits), §402(c) (husband's insurance benefits);
20 C.F.R. §404.410 (reduction formula, wife's/husband's benefit paragraph: 25/36 of 1% per month for
the first 36 months early, 5/12 of 1% per month beyond that). `verified=True` only after cross-checking
the regulation text directly at implementation time, per the constitution's verified-figure gate — this
plan does not pre-assert verification.

**Rationale**: Matches FR-001, FR-003, FR-009. Keeping the spousal rate as its own `SourcedFigure`
(rather than reusing/extending 016's `SS_CLAIMING_AGE_ADJUSTMENT`) mirrors this codebase's existing
"one `SourcedFigure` per real-world citable rule" convention (`tax/models.py`'s own `SourcedFigure`
docstring) — the worker's-own-benefit and spousal reduction rates are two different numbers from two
different paragraphs of the same regulation, not one figure with two names.

**Alternatives considered**: Reusing 016's `SS_CLAIMING_AGE_ADJUSTMENT` rate set for the spousal
calculation too (treating the two as "close enough") — rejected; the tier-1 rate genuinely differs
(25/36 of 1% vs. 5/9 of 1%, roughly 4x smaller per month), so reusing it would silently mis-state the
spousal reduction at every claiming age before FRA, exactly the kind of unverified shortcut Principle I
forbids.

## Decision 3: Spousal floor eligibility gate — both members must have claimed

**Decision**: `_member_gross_social_security_benefits()` computes the spousal floor for a claiming
member only once **both** household members have individually reached their own configured claiming
age this plan year (i.e., both already have a nonzero own-benefit row from the existing per-member
loop) — not just the member whose benefit is being floored.

**Rationale**: The real SSA rule requires the *other* (higher-earning) spouse to have already filed
for their own retirement benefit before a spousal benefit is payable off that record at all — a
spousal amount cannot be derived from a PIA that hasn't yet been claimed. This project already
computes, for the exact same plan year, whether each member has reached their own claiming age
(`ages_this_year[member.person_name] >= claiming_ages[member.person_name]`, the existing gate in
`_member_gross_social_security_benefits()`) — reusing that same per-member gate for *both* members,
rather than introducing a new concept, is the smallest correct change. Mirrors the existing
`spouse_age=next((ages_this_year[other.person_name] for other in household.members if other is not
member), None)` idiom `run_plan_projection()`'s own `compute_rmd()` call site already uses to find
"the other member."

**Alternatives considered**: Applying the spousal floor as soon as the *other* member's PIA exists at
all (ignoring whether the other member has actually claimed) — rejected as a real accuracy regression
relative to the actual SSA rule, not merely a simplification; deemed filing and restricted-application
mechanics (spec.md Assumptions) are the only pieces of "who has actually filed" complexity this
feature intentionally does not model beyond this claimed/not-claimed gate.

## Decision 4: `compute_survivor_benefit()` needs no "which member died" parameter

**Decision**: `compute_survivor_benefit(member_a_benefit: float, member_b_benefit: float, tax_year:
int) -> SurvivorBenefitResult` returns `max(member_a_benefit, member_b_benefit)` as
`survivor_benefit` — it does not take a third "which member is deceased" argument.

**Rationale**: The SSA "higher of the two continues, the lower stops" rule is symmetric in the two
input amounts — the resulting *number* the survivor receives is `max(a, b)` regardless of which of
the two members is actually the one who died (if A dies, survivor B's new benefit is `max(a, b)`; if B
dies, survivor A's new benefit is the same `max(a, b)`). The only thing that differs between the two
cases is *which household member's row* that number gets attributed to going forward — a bookkeeping
concern for whichever caller eventually wires this in (`rp-g8y`'s per-year loop, deciding whose
income this now is), not something this pure calculation itself needs to know. This keeps the
function's contract minimal and matches spec.md SC-003's actual requirement ("returns exactly the
higher of the two amounts, with zero deviation, in every case including a tie") without adding an
unused parameter.

**Alternatives considered**: A `deceased_member: Literal["a", "b"]` parameter, as spec.md's own
Acceptance Scenarios describe at the user-observable level — rejected once the math was worked
through: the parameter would be accepted but never actually consulted inside the function body (the
result is identical either way), which is exactly the kind of dead/misleading parameter this
project's own "locked signature" discipline elsewhere (e.g. `compute_state_tax()`'s real `filer_ages`
each state module genuinely branches on) argues against introducing.

## Decision 5: Existing test fixtures need zero numeric correction

**Decision**: No existing test fixture, anywhere in the repo, needs its expected Social Security
benefit values corrected as a side effect of the spousal-floor fix going live.

**Rationale**: Confirmed by grepping every `ss_annual_benefit=`/`"ss_annual_benefit":` occurrence
across `tests/`, `services/bff/tests/`, `apps/streamlit_ui/tests/`, and `e2e/` (both Python-literal
and YAML/JSON-fixture forms). Every married-filing-jointly household fixture in this repository uses
one of exactly two PIA pairs — approximately \$32,000/\$24,000, or \$30,000/\$20,000 — and in both
pairs the lower PIA (\$24,000, \$20,000) already exceeds 50% of the higher (\$16,000, \$15,000
respectively), so the spousal floor never activates for any of them; every other fixture is a
`"single"`-filing-status household, structurally unaffected by FR-004. This means User Story 1 (the
one change with live projection-output impact) ships with **zero** pre-existing test breakage —
confirming SC-002 (no regression to households the floor shouldn't affect) empirically rather than by
assertion, and meaning only *new* tests written for this feature need a fixture with a larger PIA
disparity to actually exercise the fix.

**Alternatives considered**: None — this is a factual finding from reading the codebase, not a design
choice with alternatives, included here (rather than left implicit) because 016's own research.md set
the precedent of stating a grep-confirmed blast-radius finding explicitly (016 Decision 3's "34 files"
count) instead of leaving it to be discovered during implementation.

## Decision 6: `predicted_death_age` — an age, not a year; no new "marital status" entity

**Decision**: `HouseholdMember` gains `predicted_death_age: int | None = None` — an age (consistent
with `current_age`, `ss_claim_age`, and `full_retirement_age`, all of which are already ages relative
to `reference_tax_year`, translated per plan year by the existing `member_age_in_tax_year()` helper),
not a calendar year. No new top-level entity (e.g. a "MaritalStatus" or "MortalityEvent" type) is
introduced — `Household.filing_status` already captures the household's tax-filing marital state, and
a third state (widowed) is exactly the concept `rp-g8y` will need to introduce when it actually wires
mid-horizon death into the projection loop; introducing it here, unused, would be speculative.

**Plausibility range**: `[50, 110]`, reusing `simulation/survival_data.py`'s own `SURVIVAL_TABLE` age
range (`range(50, 111)`) for the same reason that module's docstring gives — a plausible span for an
adult retirement-planning household member — rather than inventing a new, uncited bound. Outside this
range: a **warning**-severity `ValidationFlag` (mirrors 016's own FRA-plausibility precedent exactly).
`predicted_death_age` strictly less than the member's own `current_age`: a **blocking** rule (not
merely implausible but incoherent — a "prediction" of a death age already in the past is a
contradiction, not a plausibility concern) — a new severity tier this field needs that 016's FRA field
didn't, since FRA has no analogous "already happened" case.

**Rationale**: Matches FR-006 and spec.md's Edge Cases exactly. Defaults to `None`, reproducing every
existing scenario's exact current behavior (strictly additive) — mirrors 016's `full_retirement_age`
defaulting precedent (spec.md FR-006 there) and `010`'s `hdhp_coverage`/`hsa_contribution` precedent
before it.

**Alternatives considered**: A `death_year: int | None` field, mirroring `012`'s
`InheritedIraDetails.death_year` — rejected; that field records a *certain, already-happened* fact
about a third party (the original account owner) the tool has no other age-tracking relationship
with, whereas this field is a *hypothetical, for-planning-purposes* input about an actual tracked
household member, for whom every other fact is already expressed as an age. Using a year would also
require this field to be re-anchored against `reference_tax_year` at every consumption site the way
`death_year` already must be for inherited accounts — unnecessary complexity when the member's own
age is already the natural unit every sibling field uses.

## Decision 7: Single call site for the spousal floor, reused everywhere by construction

**Decision**: Only `comparison/projection.py`'s `_member_gross_social_security_benefits()` needs to
change to make the spousal floor take effect. No change is needed in `simulation/`.

**Rationale**: Directly reuses 016's own research.md Decision 4 finding (`simulation/monte_carlo.py`
and `simulation/compare.py` both call `comparison.run_plan_projection()` internally rather than
reimplementing the per-plan-year loop) — nothing about that import graph changes for this feature, so
the same conclusion holds: fixing the benefit derivation inside `run_plan_projection()`'s one call
site automatically satisfies every engine path (deterministic single-run, every comparison axis,
Monte Carlo simulation).

**Alternatives considered**: None beyond what 016 already ruled out for the identical reason.

## Decision 8: `docs/BRD.md` updates are targeted, not a rewrite

**Decision**: Update exactly two existing locations, confirmed by reading `docs/BRD.md` directly:

- §5.3 ("Federal — not modeled")'s existing bullet — *"Social Security spousal and survivor
  benefits... are not modeled (tracked separately: rp-52n, rp-g8y)"* — is rewritten to describe the
  spousal floor as now modeled (and wired into every projection), the survivor-benefit *calculation*
  as now available but not yet wired into a running projection (`rp-g8y`), and to add the family
  maximum benefit and deemed-filing mechanics as the specific pieces that remain genuinely unmodeled
  (FR-008, spec.md Assumptions).
- §6.2a's closing paragraph — *"Explicitly not modeled: spousal benefits..., survivor benefits...,
  and the Social Security earnings test..."* — drops spousal/survivor benefits from that "not
  modeled" list (only the earnings test remains there) and gains a new subsection describing the
  spousal floor and survivor-benefit formulas and their citations, in the same structural style
  016's own claiming-age-adjustment subsection already uses immediately above it.

**Rationale**: Matches FR-010 and User Story 3 exactly; both locations are the same ones 016's own
`docs/BRD.md` update touched for the analogous claiming-age-adjustment gap, confirmed still current
by reading the file directly rather than assuming it hasn't drifted since.

**Alternatives considered**: None — these are the only two places in `docs/BRD.md` that currently
mention spousal/survivor benefits (confirmed by `grep -n "spousal\|survivor" docs/BRD.md`).
