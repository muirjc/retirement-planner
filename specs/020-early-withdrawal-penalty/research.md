# Phase 0 Research: Early-Withdrawal Penalty (Pre-59.5)

No `[NEEDS CLARIFICATION]` markers remain in spec.md — the three open scope questions (penalty-only
vs. 72(t)/SEPP; per-owner vs. household-level age attribution; whether to fold in the separately-
discovered IRMAA/NIIT funding gap) were resolved with the user during `/speckit-specify` itself
(see spec.md's Input section). This document records the remaining *implementation-shape*
decisions made during planning.

## Decision 1: A new module in `tax/`, not `mechanics/`

**Decision**: `tax/early_withdrawal_penalty.py`, mirroring `tax/niit.py`'s exact shape — a flat-rate
surtax (`EARLY_WITHDRAWAL_PENALTY_RATE`, 10%) applied to a caller-computed base
(`compute_early_withdrawal_penalty(taxable_early_distribution_base, tax_year)`).

**Rationale**: IRC §72(t)'s 10% additional tax is a tax-liability concept (reported on Form 5329,
added to the taxpayer's total tax), not an account-mechanics concept — it belongs alongside NIIT
and IRMAA (both also flat-or-tiered surtaxes on a caller-computed base) rather than beside
`withdrawal_sequencing.py`, which only ever computes *how much* is drawn from which account type,
never an additional tax on top of that amount. `niit.py`'s own docstring establishes the exact
precedent this module follows: *"computed by the caller (comparison/projection.py) and passed in;
this module has no opinion about how investment_income was derived, only how the surtax applies to
it once given"* — this feature's own `taxable_early_distribution_base` is the direct analog.

**Alternatives considered**:
- *Add it to `mechanics/withdrawal_sequencing.py`* — rejected: that module's own contract (`003`) is
  locked and scoped to account-type draw ordering; an additional federal tax has no natural home
  there, and NIIT/IRMAA already established the "belongs in `tax/`" precedent for exactly this kind
  of computation.

## Decision 2: Per-member attribution happens in `comparison/projection.py`, not inside the new function

**Decision**: `compute_early_withdrawal_penalty()` itself is a pure, one-line-of-real-logic function
taking an already-computed `taxable_early_distribution_base: float` — the per-member split (via
`traditional_ownership_shares`) and the age-59-or-younger filter both happen in
`run_plan_projection()`'s own per-year loop, immediately before calling this function.

**Rationale**: `traditional_ownership_shares` and `ages_this_year` are both `comparison`-package
concepts already computed once per plan year in the existing loop (used identically for the
per-member RMD split, `research.md` of `011`) — duplicating that attribution logic inside a `tax/`
function would require passing both structures into a package that has never needed per-member
household concepts before (every existing `tax/` function takes a single pre-derived number or a
`filing_status`, never a `dict[str, float]` of ownership shares). Keeping the attribution in
`comparison/projection.py` also means this feature's version of "who owns what share of a pooled
withdrawal" reuses the *exact* mechanism `011`'s own RMD computation already established, rather
than inventing a second one.

## Decision 3: Combining the Traditional-side and Roth-side bases into one call

**Decision**: `run_plan_projection()` computes
`taxable_early_distribution_base = under_59_traditional_share + ladder_result.unseasoned_amount_flagged`
(a single float) and calls `compute_early_withdrawal_penalty()` exactly once per plan year — not
once per source.

**Rationale**: Spec.md FR-006 requires "a single combined amount, not two separately-reported
penalties" (Acceptance Scenario US2.2) — both amounts are subject to the identical 10% rate under
the identical statute, so there is no real-world reason to report them as two numbers a user would
then have to add themselves. `ladder_result` (`019`'s own `RothLadderConsumptionResult`, already
computed earlier in the same loop iteration) is consumed exactly as `019`'s own contract anticipated
(`contracts/comparison-api.md`, `019`: *"a future feature computing an actual early-withdrawal
penalty ... is expected to consume this field as one of its own inputs rather than re-deriving lot
seasoning itself"*) — this feature does not re-check age or re-derive seasoning for the Roth-side
contribution at all, only sums the already-gated amount in.

## Decision 4: RMD and inherited-account exclusions are structural, not explicit checks

**Decision**: No `if this was an RMD` or `if this was an inherited distribution` branch exists
anywhere in this feature's own code. FR-003/FR-004 (SC-004) are satisfied purely by *which*
existing field the per-member attribution reads from:

- The Traditional-side base sums only `mechanics_result.withdrawal_plan.sequence_withdrawals`
  entries with `account_type == "traditional"` — `WithdrawalPlan.rmd_drawn` (the RMD leg, always
  drawn first, entirely separate from `sequence_withdrawals`) is never touched. This is also true
  by real-world construction independent of this engine's own field layout:
  `RMD_START_AGE` (`73` before 2033, `75` from 2033 on) is always well past `59` — no plan year this
  engine can ever produce has an RMD-required distribution for a member who is also under the
  age-59-or-younger condition this feature checks, so even a hypothetical future refactor that
  merged the two legs would still need an explicit age check that already excludes every real RMD
  case.
- Inherited-account distributions (`inherited_account_distributions`,
  `WithdrawalPlan.inherited_distribution_drawn`) are tracked in an entirely separate list/field
  (`012`'s own `InheritedAccountBalance`, never pooled with `AccountBalances.traditional`) that this
  feature's own per-member attribution never reads at all.

**Rationale**: Mirrors this codebase's general preference for structural correctness (a field simply
isn't consulted) over a defensive `if` branch guarding against a case the data model already makes
impossible — matches `019`'s own "a same-year conversion is never its own year's draw source"
precedent, which is also structural (an ordering guarantee) rather than an explicit check.

## Decision 5: `figures_used` is always populated, mirroring NIIT/IRMAA, not `019`'s own convention

**Decision**: `compute_early_withdrawal_penalty()` always includes
`EARLY_WITHDRAWAL_PENALTY_RATE.usage_for_year(tax_year)` in its returned `figures_used`, regardless
of whether `taxable_early_distribution_base` is `0.0` that year.

**Rationale**: `compute_niit()` builds its own `figures_used` list before its threshold check and
returns it in both branches — this module's own closest structural sibling already establishes
"always cited, even when the computed amount is zero" as the convention for a `tax/`-package
surtax. This deliberately differs from `019`'s own `compute_roth_ladder_consumption()`, which only
cites its figure when a lot's seasoning was actually consulted — that was a `mechanics/`-package
function tracking a genuinely conditional, per-lot fact; this is a `tax/`-package flat-rate figure
applied (even if to a base of `0.0`) every single plan year, exactly like NIIT's own rate/threshold
figures are.

## Decision 6: Funding — added to `tax_owed`, unlike the separately-filed IRMAA/NIIT gap

**Decision**: `tax_owed = federal_tax.federal_tax_owed + state_tax.state_tax_owed +
early_withdrawal_penalty.penalty_owed` — the new penalty is included in the amount actually funded
via `compute_withdrawal_plan(spending_need=tax_owed, ...)`, so it genuinely reduces projected
account balances. `cumulative_tax_paid` (the existing `PlanOutcome` field) is **not** widened to
include it — a new, separate `cumulative_early_withdrawal_penalty_paid` field is added instead,
mirroring `010`'s own explicit precedent for `cumulative_irmaa_paid`/`cumulative_niit_paid`
(`010` research.md: *"Folding IRMAA/NIIT into `cumulative_tax_paid` directly — rejected; spec.md's
own FR-002/FR-006 require these to be 'reported separately'"*).

**Rationale**: `rp-yqf` (filed during this feature's own specification) found that IRMAA/NIIT are
computed and reported but never actually added to `tax_owed` — an undocumented gap, not a design
choice. This feature's own new cost must not repeat that mistake (spec.md Assumptions) — FR-007
requires it to genuinely reduce balances. Keeping `cumulative_tax_paid`'s existing meaning
unchanged, while still funding the new cost via the *local* `tax_owed` variable (a completely
separate code path from the `_derive_outcome()` reporting sum), lets this feature do both things at
once without conflict: fund correctly, and report under `010`'s own established "separate field"
convention.

## Decision 7: Regression triage approach — this is an accuracy correction, not purely additive

**Decision**: Unlike `017`'s/`018`'s/`019`'s own "confirmed via grep that zero existing fixtures need
correction" precedent, this feature is expected to change real computed output (ending balances,
shortfall, and any other value downstream of `tax_owed`) for every existing test fixture with a
household member under 60 taking a voluntary Traditional withdrawal — which, per a project-wide
grep, includes fixtures across `tests/unit/comparison/`, `tests/unit/simulation/`,
`services/bff/tests/`, and likely `apps/streamlit_ui/tests/`/`e2e/`. Rather than attempting to
pre-audit every affected fixture's exact expected numeric value by hand during planning (expensive,
error-prone via static analysis alone, since the actual penalty amount depends on each fixture's own
runtime withdrawal amounts, not just the ages present), the task list runs the full four-suite
quality gate early in implementation (immediately after the core computation lands, not deferred to
the final Polish task) and triages each failure individually, updating expected values with an
explicit code comment explaining the corrected number — mirroring `016`'s own precedent for the
Social Security claiming-age adjustment (the last feature to genuinely change the reference use
case's own numbers) rather than `017`'s/`018`'s/`019`'s own "confirmed non-disruptive" framing.

**Rationale**: `016`'s own spec/plan/tasks did exactly this — computed the correction first,
accepted that existing numeric expectations would shift, and treated updating them as expected,
documented implementation work rather than a sign something had gone wrong. This project's own
constitution (Principle I) explicitly prefers an accurate number that requires updating stale test
expectations over a stale number that silently stays "passing."

## Decision 8: `docs/BRD.md` location

**Decision**: A new `§6.6a Early-withdrawal penalty (pre-59.5)` subsection immediately after `§6.6`
(Roth conversion & withdrawal sequencing, extended by `019`'s own `§6.6`-adjacent content) — plus a
new bullet in `§7 Known Limitations & Open Items`, mirroring `018`'s/`019`'s own precedent for both
sections. Confirmed by reading `docs/BRD.md`'s current structure at planning time; exact insertion
point re-confirmed at implementation time in case another feature's own BRD edit has shifted section
numbering since this research was written.
