# Phase 0 Research: Strategy Comparison Layer

No items in Technical Context were left as `NEEDS CLARIFICATION` — language, dependencies, storage, testing, platform, and performance posture all follow directly from `001`/`002`/`003`'s established choices. The research below resolves the feature-specific design questions this spec's Assumptions and Edge Cases raised — several of which are genuinely new ground, since this is the first feature to chain a plan year's mechanics and tax calculation together across a multi-year horizon.

## 1. How is a single deterministic annual return derived from `MarketAssumptions`?

**Decision**: `derive_deterministic_return(market_assumptions) -> float` returns the allocation-weighted blend of the two mean real returns already present in `001`'s `MarketAssumptions`: `equity_allocation * equity_return_mean_real + bond_allocation * bond_return_mean_real`. `equity_return_std_real`, `bond_return_std_real`, and `correlation` are read from the scenario but not used by this feature at all.

**Rationale**: FR-003 requires one fixed, deterministic annual return per comparison rather than a randomly drawn value, and the spec's Assumptions section commits to this explicitly as the stand-in for the future Simulation Engine feature's genuine Monte Carlo draws. Every field this formula consumes already exists in `001`'s scenario schema with exactly this meaning (mean real return per asset class, weighted by allocation) — no new scenario field or sourced legal figure is introduced, so Principle III's citation/verification requirement doesn't apply here (this is user-supplied market opinion, not a legal fact).

**Alternatives considered**: Using only the equity mean return (worst case for a bond-heavy portfolio) or only the bond mean return (overly conservative) — both rejected as arbitrary distortions of the household's actual configured allocation. Implementing real Monte Carlo return generation now — rejected; that is explicitly the future §3.5 Simulation Engine feature's job (spec.md Assumptions), and building it here would blur this feature's boundary and duplicate work once §3.5 exists.

## 2. How does a plan year's tax year map to each household member's age?

**Decision**: This feature is the first to run for more than one plan year, so it establishes the convention: every full-horizon projection takes an explicit `reference_tax_year` (the tax year `HouseholdMember.current_age`, from `001`, was accurate as of) alongside `start_plan_year`/`start_tax_year`. A member's age in `tax_year` is `current_age + (tax_year - reference_tax_year)`. Plan years and tax years advance together, one per year, starting at `start_plan_year`/`start_tax_year`.

**Rationale**: `001`'s `HouseholdMember.current_age` is a snapshot as of scenario authoring — it says nothing on its own about age in a plan year ten years later. `002` and `003` never needed this translation because they operate on a single already-known `tax_year`/age pair supplied directly by the caller (their contracts take `member_age`/`tax_year` as independent arguments — see `003`'s data-model.md § RmdResult). A multi-year projection is the first place the translation itself needs to happen, so it belongs here rather than being retrofitted into `001`.

**Alternatives considered**: Deriving `reference_tax_year` implicitly from the current system clock at run time — rejected; it would break Principle II (Reproducibility), since running the identical scenario on two different calendar dates would silently change every member's computed age and therefore every year's RMD/tax result.

## 3. Which RMD table does this feature's projection use for a two-member household?

**Decision**: Every RMD call this feature makes uses the Uniform Lifetime Table only (`compute_rmd(..., spouse_is_sole_beneficiary=False)`), never the Joint Life and Last Survivor Table, regardless of the household's ages.

**Rationale**: `003`'s `compute_rmd()` correctly leaves sole-beneficiary determination to its caller rather than inferring it (its own research.md §4) — but `001`'s `Scenario` schema has no field recording whether a spouse is the sole named beneficiary of a traditional account, only ages and balances. Guessing "sole beneficiary" from the age gap alone would be wrong (the Joint Life Table requires *both* facts, and sole-beneficiary status is an account-registration fact this tool has no source for), and Principle I forbids presenting a guessed simplification as if it were a real determination. Defaulting to the Uniform Lifetime Table is the conservative choice (it never understates a required distribution) and is recorded here as an explicit, flagged simplification rather than a silent one — extending `001`'s schema with a sole-beneficiary field is a natural follow-on, out of this feature's scope.

**Alternatives considered**: Inferring sole-beneficiary status whenever the age gap exceeds 10 years — rejected; conflates two independent facts (age gap and beneficiary designation) and would silently overstate how many households qualify for the smaller Joint Life divisor.

## 4. Which household member's age/balance drives the RMD call, given `001`'s balances are household-level, not per-owner?

**Decision**: The older household member (by `current_age` at `reference_tax_year`; the sole member for a single-filer household) is treated as the deemed owner of the household's entire traditional balance for RMD purposes, every plan year.

**Rationale**: `003`'s research.md §4 already established that `compute_rmd()` takes an explicit `(member_age, traditional_balance)` pair and deliberately leaves attribution of a household-level balance to a specific owner as a caller decision, since `001`'s `Scenario.accounts` has no per-owner split. This feature is the first caller that actually needs to make that call. Attributing the balance to the older member is the conservative choice (RMDs on a shared balance start no later than they would under a per-owner split, since the older member reaches the RMD-required starting age first) and is simplest to state and audit.

**Alternatives considered**: Splitting the traditional balance evenly across both members and computing two independent (smaller) RMDs — rejected as inventing a 50/50 ownership assumption `001`'s schema doesn't support, and it can understate the combined required distribution once only one member is past the starting age.

## 5. How does a plan year's federal/state tax liability actually reduce account balances?

**Decision**: After `compute_plan_year_mechanics()` produces the year's `ordinary_income` and post-mechanics `ending_balances`, this feature computes federal and state tax on that income (`002`'s `compute_federal_tax()`/`compute_state_tax()`), then draws the resulting tax owed from the post-mechanics balances as a **second, separate `compute_withdrawal_plan()` call** — `spending_need=federal_tax_owed + state_tax_owed`, `rmd_amount=0`, `starting_balances=` the post-mechanics balances, using the same `withdrawal_strategy` as the year's spending draws. This second draw's own `shortfall` (if any) is added to the year's total shortfall. Tax is not "grossed up" — a tax-funding withdrawal never itself triggers a further tax recalculation for the same year.

**Rationale**: `003`'s `compute_withdrawal_plan()` only ever satisfies a `spending_need` figure the caller supplies (its own scope note: "does not compute federal or state tax itself... calls it as an input"); nothing in `001`–`003` funds the tax bill itself out of the accounts it draws down, yet a lifetime-tax comparison (this feature's whole point, per US2's "cumulative tax paid" outcome) is meaningless if tax never actually reduces the balances being compared. Reusing `compute_withdrawal_plan()` for the tax draw — rather than inventing a second drawdown mechanism — keeps this feature's own account-balance arithmetic entirely delegated to `003`, with zero duplicated logic (Principle IV).

**Alternatives considered**: Grossing up the spending-need withdrawal to cover both spending and its own resulting tax, solved iteratively until convergence — rejected as materially more complex (an iterative fixed-point solve per plan year, run once per candidate per comparison) for a precision gain the deterministic-return simplification (Decision 1) already outweighs; documented here as a known simplification (Principle I) rather than silently assumed. Treating "cumulative tax paid" as a pure informational metric that never reduces account balances — rejected; it would make the ending-balance outcome financially wrong, undermining the very comparison (Roth conversion vs. no conversion) this feature exists to support.

## 6. Does investment growth apply uniformly across traditional, Roth, and taxable balances?

**Decision**: Yes — the single deterministic annual return from Decision 1 is applied identically to all three account types' post-tax-funding ending balances to produce the next plan year's starting balances.

**Rationale**: `001`'s `MarketAssumptions` models one household-level equity/bond blend, not a separate allocation per account type — there is no scenario input this feature could use to grow, say, the Roth balance differently from the taxable balance. Applying one blended rate everywhere is the only choice consistent with the data actually available, and is recorded here rather than left implicit.

**Alternatives considered**: Assuming taxable accounts hold only bonds and tax-advantaged accounts hold only equities (a common real-world "asset location" pattern) — rejected as inventing a per-account allocation `001`'s schema doesn't capture; it would be exactly the kind of unstated assumption Principle I flags.

## 7. What happens to a projection after a plan year's spending or tax draw comes up short?

**Decision**: A shortfall never drives a balance negative (per `003`'s existing guarantee) — depleted account types simply stay at `0`. The projection continues computing every subsequent plan year exactly as it would otherwise, with whatever balances remain (typically `0` across the board once fully depleted), and each year's own shortfall (if any) is recorded independently in that year's result.

**Rationale**: FR-004/Edge Cases require the projection to record a first-shortfall year and keep going rather than raising an unhandled error or silently truncating the horizon — a user needs to see the full trajectory (including a $0-balance "coasting" tail) to judge severity, not just the year money first ran out.

**Alternatives considered**: Halting the projection at the first shortfall year — rejected; it would make `PlanOutcome.ending_balance` and `cumulative_tax_paid` incomparable across candidate configurations that deplete in different years, defeating the whole comparison purpose.

## 8. Where does the second withdrawal sequencing order (needed for User Story 3) live?

**Decision**: This feature adds one additional entry — `"rmd_traditional_taxable_roth" -> (traditional, taxable, roth)`, traditional drawn before taxable — directly into `003`'s existing `retirement_planner.mechanics.withdrawal_sequencing.WITHDRAWAL_STRATEGIES` registry. No new module, no change to `003`'s shared draw-down function.

**Rationale**: `003`'s own design (data-model.md § WithdrawalSequencingStrategy, contracts/mechanics-api.md) exists precisely so that "adding a new strategy means adding one tuple + one registry entry — nothing else in this package changes" (SC-006). This feature needs a second, genuinely different order to make User Story 3's comparison meaningful at all (comparing one order against itself proves nothing), and `003`'s registry is the correct, already-designed extension point for it — inventing a parallel registry inside this feature's own package would fragment the "which withdrawal orders exist" answer across two places.

**Alternatives considered**: Defining the second order as a comparison-layer-local concept that never touches `003`'s registry — rejected; `compute_withdrawal_plan()`'s `strategy` parameter is a registry key lookup (raises `KeyError` otherwise per its contract), so any order this feature wants to run through it must be registered there regardless.
