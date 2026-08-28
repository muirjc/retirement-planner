# Phase 0 Research: Retirement Account Mechanics

No items in Technical Context were left as `NEEDS CLARIFICATION` — this feature's language, dependencies, storage, testing, platform, and performance posture all follow directly from `001-scenario-config-management` and `002-tax-calculation-engine`'s established choices. The research below resolves the feature-specific design questions the spec's Assumptions and Edge Cases raised, so Phase 1 design has a settled foundation.

## 1. Do RMD divisor tables belong in `SourcedFigure`, or a new figure type?

**Decision**: Reuse `002`'s `SourcedFigure[T]` generic exactly as-is — `SourcedFigure[dict[int, float]]` for the Uniform Lifetime Table (schedule: tax year → `{age: divisor}`), `SourcedFigure[dict[tuple[int, int], float]]` for the Joint Life and Last Survivor Table (schedule: tax year → `{(owner_age, spouse_age): divisor}`), and `SourcedFigure[int]` for the RMD-required starting age (schedule: tax year → age, since SECURE 2.0 already changed this once and has another scheduled change on the books).

**Rationale**: FR-019 explicitly requires reusing `002`'s Sourced Figure convention rather than inventing a parallel one. `SourcedFigure` is already generic over its value type (`002` uses it for both a flat exclusion amount and a whole `BracketTable`), so a divisor table or a plain age fits without modification — no new abstraction is needed, and a single `verified`/`citation`/`last_verified` mental model applies across both features.

**Alternatives considered**: A dedicated `RmdTable` type with its own citation fields — rejected as needless duplication of `SourcedFigure`'s exact shape, and it would fragment the "how do I check if a figure is trustworthy" pattern downstream reporting (§3.6) will eventually need to render uniformly across every feature's figures.

## 2. Where does the RMD-required starting age live, and does it change over time?

**Decision**: Model it as `SourcedFigure[int]` keyed by tax year, exactly like a tax bracket figure, rather than a single hardcoded constant.

**Rationale**: The RMD starting age is legislated and has already changed twice in recent years (72 → 73 under SECURE 2.0, scheduled to become 75 in 2033) — this is precisely the "figure whose value is scheduled to change by tax year" pattern FR-012 (in `002`) and this feature's own reliance on year-scoped figures already handle. Treating it as a plain Python constant would silently break for any plan year after the next scheduled change, which Principle I (Accuracy Over Cleverness) and this feature's FR-019 both rule out.

**Alternatives considered**: Hardcoding `73` — rejected; matches the exact kind of "fixed real-terms" simplification the source document calls out as unacceptable once a schedule is known.

## 3. How does bracket-ceiling Roth conversion logic get Social Security taxability without duplicating `002`'s formula?

**Decision**: `fill_to_bracket_ceiling` (in `mechanics/roth_conversion.py`) calls `retirement_planner.tax.social_security.compute_taxable_social_security(...)` directly, passing the household's already-established ordinary income (RMD + traditional withdrawals for the year) and gross Social Security benefit, and folds the returned taxable-Social-Security amount into the taxable-income figure it fills toward the ceiling. The `FigureUsage` entries that call returns are threaded into this feature's own result (`ConversionResult.figures_used`) rather than being dropped.

**Rationale**: FR-015 requires exactly this — obtaining ordinary income and Social Security taxability figures from `002` rather than recomputing tax logic. It also means a future change to `002`'s provisional-income formula (e.g., a threshold update) automatically flows through to conversion planning without this feature needing an update.

**Alternatives considered**: Re-deriving a simplified taxability estimate locally (e.g., a flat percentage) — rejected outright; this is the exact "flat-85%-shortcut" mistake `002` was built to eliminate, and reintroducing it one layer up would defeat the point.

## 4. How does RMD's inherently per-owner computation relate to `Scenario`'s household-level account balances?

**Decision**: `compute_rmd()` takes an explicit `traditional_balance` and `member_age` (plus optional spouse info) as direct arguments — it does not read a `Scenario` or attempt to split a household-level traditional balance across owners itself. Withdrawal sequencing and Roth conversion, by contrast, operate on `AccountBalances` (traditional/roth/taxable totals) that map one-to-one onto `Scenario.accounts`' shape with no translation needed.

**Rationale**: `001`'s `Scenario.accounts` is a household-level aggregate (`traditional_ira: 1500000`, not per-member sub-balances) — it does not track which spouse owns which dollar of a traditional balance, and the source document's own reference use case doesn't require it to (RMD figures in the reference profile are illustrative at the household level). Forcing `compute_rmd()` to consume a `Scenario` directly would mean inventing an ownership-attribution rule (e.g., "split evenly," "attribute to the older spouse") that isn't specified anywhere and would be a silent assumption exactly of the kind Principle I forbids. Keeping `compute_rmd()` a pure calculator over explicit `(member_age, traditional_balance)` pairs — the same "pure calculator" posture `002` took for `IncomeComponents` — leaves that attribution decision to whichever caller has the information to make it correctly (a future integration feature, or a scenario author who supplies a per-member breakdown directly).

**Alternatives considered**: Adding per-owner sub-accounts to `Scenario` now — rejected as out of this feature's scope (that's a `001` data-model change, not a `003` mechanics change) and unnecessary for this feature's own acceptance scenarios, which specify member age/balance/spouse info directly as inputs (spec.md US1 Independent Test).

## 5. Should withdrawal-sequencing strategies be callables (like state tax modules) or data (orderings)?

**Decision**: Data — `WITHDRAWAL_STRATEGIES: dict[str, tuple[AccountType, ...]]`, consumed by one shared draw-down function, rather than one callable per strategy.

**Rationale**: See plan.md's Constitution Check note. Every withdrawal-sequencing strategy performs the *identical* arithmetic (draw from an account type up to its balance, roll any remainder to the next account type in order, report an unmet shortfall) — only the order of account types differs. A callable-per-strategy design (mirroring `002`'s `STATE_MODULES`) would require that identical arithmetic to be copy-pasted into every strategy implementation, which is itself a Principle IV risk (a fix to the shared logic could be applied to one strategy and missed in another). Roth-conversion strategies don't share this property — fill-to-bracket-ceiling and fixed-dollar-amount compute genuinely different things — so those remain callables, directly mirroring `STATE_MODULES`.

**Alternatives considered**: One callable per sequencing strategy, each internally calling a shared helper — considered viable, but rejected as strictly more indirection than a plain ordering tuple for zero behavioral benefit; FR-005/FR-006/SC-006's actual requirement ("add a strategy without touching other files") is satisfied either way.

## 6. Do RMD dollars ever get double-counted as available for Roth conversion?

**Decision**: No — `plan_year.py`'s orchestrator computes the withdrawal plan (which treats the RMD amount as an already-mandatory traditional draw, per FR-004) before computing the Roth conversion, and passes the *post-withdrawal* traditional balance into `compute_roth_conversion()`. Since the RMD amount has already been subtracted from the traditional balance by the time conversion logic runs, it is structurally impossible for the same dollars to be both "withdrawn to satisfy RMD" and "converted."

**Rationale**: This directly encodes FR-013 and the Edge Cases entry about RMD/conversion interaction, using ordering rather than a separate exclusion check — simpler to verify correct (there's no dollar-amount bookkeeping to get wrong) than tracking "already-RMD'd" dollars as a separate flag.

**Alternatives considered**: Computing conversion and withdrawal independently and reconciling afterward — rejected as more complex and more error-prone than simply sequencing the two calls correctly.
