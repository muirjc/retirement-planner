# Phase 0 Research: Per-Account Year-by-Year Projection Detail

## 1. Decision: extend `011`'s fixed-share pattern to the account level, don't rearchitect pooled balances

**Decision**: Compute one fixed apportionment share per ordinary
(non-inherited) account, once, from `Scenario.accounts`' starting
balances — never restructure `AccountBalances`/`WithdrawalPlan` into a
per-account ledger tracked independently through the engine's own
year-over-year arithmetic.

**Rationale**: `specs/011-per-owner-accounts/research.md` §1 already
evaluated and rejected a true independent per-member balance ledger for
this exact reason: *"there's no principled way to decide whose dollars
funded this year's household spending draw or this year's conversion
without inventing a rule the spec's Assumptions explicitly didn't ask
for."* This project's schema has no cost basis, no lot-level detail, no
per-account withdrawal preference — a true per-account ledger would need
to invent the identical rule, just inside the engine's own arithmetic
(implicitly presented as fact) rather than in a clearly-labeled
reporting-layer derivation. That's a regression on the constitution's
Accuracy-Over-Cleverness principle, not an improvement, and it would
touch `compute_rmd()`, `withdrawal_sequencing.py`, `roth_conversion.py`,
`plan_year.py`, `projection.py`, `compare.py`, `monte_carlo.py`, and
every existing test asserting a pooled float — a large, high-regression
change to already-locked contracts for no real accuracy gain.

**Alternatives considered**: A true independent per-account ledger
(`AccountBalances` → `list[AccountBalance]` everywhere) — rejected per
above. A per-account-*type*-only breakdown (no true per-account
detail) — rejected because it's what the user explicitly said isn't
enough (per-account granularity was the scope decision made during
planning).

## 2. Decision: two different share formulas, not one, depending on what's being apportioned

**Decision**:

- **Balance and withdrawal apportionment** (any account type): a flat,
  household-wide share —
  `fixed_share[account] = account.starting_balance / sum(starting balances of every account of that same type in the household, excluding inherited accounts)`.
  Zero-guarded exactly like `resolution.py`'s existing
  `_traditional_ownership_shares()`: a type with a zero pooled total
  gives every account of that type a `fixed_share` of `0.0` (never a
  `ZeroDivisionError`), safe because a zero-balance pool can never become
  positive later in the same projection (`011` research.md §2's own
  established reasoning, which applies identically here).
- **RMD apportionment** (traditional accounts only): NOT the flat share
  above — RMD is member-specific (a member's own age drives their own
  divisor), so the *exact* per-member RMD amount `011` already computes
  (§3 below) is retained, then — only when that member owns more than
  one traditional account — sub-allocated across *that member's own*
  accounts by a within-member share:
  `within_member_share[account] = account.starting_balance / sum(starting balances of accounts owned by that same member)`.
  When a member owns exactly one traditional account, this sub-allocation
  is the identity function — that account's RMD is the member's own
  exact RMD, unmodified, with no share math involved at all.

**Rationale**: These are genuinely different apportionment questions. A
household's traditional balance's *growth* is already uniform per dollar
(one market return applied to the whole pool) — so the flat household-
wide share is the *exact* consequence of that existing assumption, not a
new approximation, for balance/withdrawal apportionment. RMD is
different: `011` already computes a *real*, member-specific figure (that
member's own age against their own share-derived balance) — collapsing
it into the same flat household-wide share would throw away exactness
the engine already has, for accounts held by different members who may
be different ages with different divisors. Keeping the exact per-member
figure and sub-allocating *only within that one member's own accounts*
preserves that exactness everywhere except the genuinely-unresolvable
case (a member with more than one traditional account).

**Alternatives considered**: Using the flat household-wide `fixed_share`
for RMD too — rejected because it would silently discard exactness `011`
already established, in the common case where each member's own accounts
are already the only source of that member's own RMD.

## 3. Decision: what's exact, what's attributed — full inventory

| Figure | Status | Why |
|---|---|---|
| Inherited account balance/distribution | **Exact** | `InheritedAccountBalance` (012/013) already tracks each independently; this feature only stops discarding that state before it's overwritten each year. |
| A member's own total RMD | **Exact** | `011` already computes this correctly per member from their own age/share; this feature only stops summing it away before returning. |
| A member's own gross Social Security benefit | **Exact** | Already computed correctly per member inside `_household_gross_social_security_benefit()`'s own logic; this feature only stops discarding the per-member breakdown. |
| An account's own RMD, when its owner has exactly one traditional account | **Exact** | Identity sub-allocation of the exact member figure above (§2). |
| An account's own RMD, when its owner has more than one traditional account | **Attributed** | Sub-allocated by within-member starting-balance share (§2) — a disclosed apportionment of an otherwise-exact member total. |
| An account's own year-by-year balance (ordinary accounts) | **Attributed** | Flat household-wide share of the pooled type total (§2) — exact given the engine's own uniform-growth-per-type assumption, but not independently observed, since the engine never tracks this account's balance on its own. |
| An account's own withdrawal amount (ordinary accounts) | **Attributed** | Same flat share applied to the pooled type's withdrawal total for that year. |

Every "Attributed" row carries `attribution="fixed_share_of_pooled_total"`
in the new data model (data-model.md); every "Exact" row (inherited
accounts, and an account that's the sole holder of its owning member's
RMD) carries `attribution="independently_tracked"`.

## 4. Decision: Monte Carlo path selection defaults to path 0, is request-scoped, never computed for every path

**Decision**: A new `detail_path_index: int | None = None` request field
(BFF), defaulting to `0` when omitted. `account_detail` is computed for
exactly that one path's already-completed `PlanProjection`, never for
every path in `run.path_results`.

**Rationale**: Mirrors `reporting/export.py`'s own existing "path 0 is
the representative path" precedent (`run_to_csv_text()`'s
`has_unverified_figure` column already reads `path_results[0]` only).
Computing this for every path would scale the new work with `n_paths`
(3,000–5,000) for a view that only ever shows one path at a time —
unnecessary work that risks the performance budget (Constitution
Principle VI) for zero user-visible benefit.

**Alternatives considered**: Precomputing detail for every path so any
path can be viewed without a second request — rejected; `n_paths` scales
into the thousands, and nothing in the UI ever shows more than one path's
detail at once (spec.md Edge Cases, FR-007).

## 5. Decision: a documented, accepted limitation — Roth-conversion cross-owner attribution

**Decision**: Do not attempt to make Roth conversion destination
apportionment member-aware in this feature. Document the gap explicitly
in spec.md's Assumptions (already done) and surface it as a caption on
the new UI table (Phase 4, plan.md).

**Rationale**: `traditional_ownership_shares` (`011`) has no Roth/taxable
counterpart — there's no per-member split of the Roth or taxable pools
today, only a flat per-account share of each type's total (§2 above). If
a member's traditional account converts but that same member owns no
starting Roth account, converted dollars still apportion across whichever
Roth accounts exist by their own flat share — which may not be the
converting member's own account. A true per-account ledger (§1's rejected
alternative) doesn't escape this either, since the engine still has no
cost-basis or per-member conversion-destination rule to invent from.
This is a pre-existing characteristic of the pooled model this feature
inherits and discloses, not a new gap it introduces.

## 6. Primary sources / precedent consulted

All internal — no external primary-source lookup was needed for this
feature (it introduces no new externally-sourced regulatory figure, per
the Constitution Check's Auditability note in plan.md):

- `specs/011-per-owner-accounts/research.md` §1–§3 — the fixed-share
  precedent this feature generalizes, and the zero-guard reasoning.
- `services/bff/src/rp_bff/resolution.py`'s `_traditional_ownership_
  shares()` — the exact zero-guard implementation this feature's
  `compute_account_shares()` mirrors.
- `src/retirement_planner/reporting/export.py`'s `run_to_csv_text()` —
  the "path 0 is representative" precedent for Monte Carlo path
  selection.
- `apps/streamlit_ui/src/rp_ui/verification.py`'s
  `render_verification_indicator()` — the disclosure-idiom precedent the
  new UI table's `attribution` column reuses rather than inventing a new
  visual convention.
