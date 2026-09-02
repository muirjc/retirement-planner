# Research: Pension, Annuity & Phased-Retirement Income Streams

## 1. What "COLA-adjusted vs. fixed-nominal" means in an all-real-dollar engine

**Decision**: `cola_adjusted` streams pay their configured `annual_amount` flat, every active year, with no computation at all. `fixed_nominal` streams erode against a new `SourcedFigure[float]` inflation-rate figure, compounded from the scenario's reference (start) tax year.

**Rationale**: Every existing figure in this engine — federal/state bracket edges, `ss_annual_benefit`/PIA, `MarketAssumptions.equity_return_mean_real`, `SpendingProfile.annual_need_real` — is stated and held in today's real (inflation-adjusted) dollars, with "no further indexing engine" as `tax/federal.py`'s own docstring puts it (and `docs/BRD.md` §5.2 restates for the whole tool). A COLA-adjusted income source, translated into that convention, is a no-op: real dollars that already track inflation don't move. A *non*-COLA'd (fixed-nominal) source is the opposite — its purchasing power genuinely declines every year, and this engine has no existing nominal-dollar inflation schedule to derive that decline from, because nothing before this feature needed one.

**Alternatives considered**:
- *Ignore the distinction; treat both modes as flat.* Rejected — this drops exactly the property `fixed_nominal` exists to express (Acceptance Scenario US1.2) and would make the field misleading rather than merely simplified.
- *Add a full nominal-dollar re-platforming of the engine (track both nominal and real dollars throughout).* Rejected — enormous, unjustified scope increase touching every existing module; the constitution's Principle VI/IV (performance budget, extensibility through narrow interfaces) argue against it, and nothing else in the spec needs it.
- *Let the user configure their own inflation-rate assumption.* Considered reasonable future work, but out of scope: no existing `Scenario` field is analogous (equity/bond returns are configurable **because** the engine already re-samples them every plan year in `005-simulation-engine`; a single flat erosion rate has no comparable existing knob). Deferred — the hardcoded `SourcedFigure` below already carries a documented, cited value and can gain a scenario override later without a breaking change (an optional parameter, following this codebase's own established additive-parameter pattern, e.g. `010`'s `hsa_contribution`).

**Figure chosen**: the 2025 OASDI Trustees Report's own intermediate-assumption ultimate CPI rate — 2.40%/year — used by SSA itself to project future Social Security COLAs. Source: *The 2025 Annual Report of the Boards of Trustees of the OASI and DI Trust Funds*, "Long-Range Economic Assumptions" (intermediate assumption), https://www.ssa.gov/oact/TR/2025/2025_Long-Range_Economic_Assumptions.pdf — confirmed against that primary source on 2026-09-02, so shipped `verified=True` (unlike the Joint Life RMD table precedent, which ships `verified=False` because it has *not yet* been cross-checked). This is a defensible choice specifically *because* it's the same inflation index the Social Security Administration itself uses to decide whether a pension even needs a COLA in the first place — using any other index would be an arbitrary, less-defensible pairing.

## 2. Does an income stream reduce the amount withdrawn from accounts?

**Decision**: No — mirrors `ss_annual_benefit` exactly. `run_plan_projection()` passes the household's full `effective_spending_need` into `compute_withdrawal_plan()` unchanged; Social Security's gross benefit is never subtracted from that spending need before withdrawal sequencing runs, it is only added afterward as additional taxable income. Income streams get byte-for-byte the same treatment.

**Rationale**: `spec.md`'s own requirement is "feed into the same tax and cash-flow pipeline as Social Security benefits" — that pipeline, as already built (`003-retirement-account-mechanics`, `004-strategy-comparison-layer`), never treats SS as spending-need-reducing; `annual_need_real` is not documented anywhere as "need net of Social Security," and no existing feature (`016`, `017`, `018`) changed that. Introducing a different (spending-reducing) treatment for income streams would make two similarly-described income sources (SS vs. pension) behave inconsistently for no reason the spec asks for, and would be a much larger, unrequested change to `compute_withdrawal_plan()`'s locked signature.

**Alternatives considered**: *Net income streams against spending_need before withdrawal sequencing.* Rejected as inconsistent with the existing SS precedent and out of this feature's requested scope; if the existing SS treatment is later judged to be a modeling gap, that is pre-existing behavior this feature should not silently change as a side effect.

## 3. Where the income-stream total enters `compute_plan_year_mechanics()`

**Decision**: Two new optional, trailing parameters — `income_stream_total: float = 0.0` and `income_stream_figures_used: list[FigureUsage] | None = None` — added into `ordinary_income_established` (alongside `rmd_drawn`, `traditional_draws`, `inherited_distribution_drawn`) **before** `compute_roth_conversion()` is called, and unioned into the returned `figures_used`.

**Rationale**: `ordinary_income_established` is exactly the figure `compute_roth_conversion()`'s bracket-fill strategies consume to size remaining bracket headroom (`roth_conversion.py`). Pension/annuity/earned income is fully taxable ordinary income (unlike SS, which keeps its own separate, partially-excluded `IncomeComponents.social_security_gross_benefit` field) — if it were added only *after* `compute_plan_year_mechanics()` returns (the way SS is layered on in `projection.py`), a `fill_to_bracket_ceiling` Roth conversion strategy would over-convert, unaware that a pension already occupies part of that year's bracket. Adding the parameter here, exactly where `hsa_contribution` (`010`) and `inherited_distribution_amount` (`012`) were each added before it, keeps every downstream consumer (federal/state tax, IRMAA/NIIT MAGI, early-withdrawal-penalty base) automatically correct with no separate wiring, since they all already consume `mechanics_result.ordinary_income`/`figures_used`.

**Alternatives considered**: *Add it in `projection.py` only, after `compute_plan_year_mechanics()` returns (SS's own pattern).* Rejected — SS is intentionally partially tax-excluded and is not itself bracket-fill-relevant income headroom in the same way (its own taxability is *derived from* `ordinary_income`, not a plain additive component of it) — mirroring its wiring exactly would propagate that special-case handling somewhere it doesn't belong, and would leave Roth-conversion bracket sizing wrong.

## 4. Per-member vs. household-level configuration

**Decision**: Per household member (`HouseholdMember.income_streams: list[IncomeStream]`), matching `ss_annual_benefit`/`ss_claim_age`.

**Rationale**: A pension or job is intrinsically tied to one person, exactly like Social Security; a household-level pooled list would need its own `owner` field re-deriving the same per-member association `HouseholdMember` already provides for free, mirroring the account-level `owner` precedent (`011-per-owner-accounts`) in the wrong direction.

## 5. Reporting surface

**Decision**: `PlanYearProjection.member_income_stream_amounts: dict[str, float]` (comparison layer) and `PlanYearAccountDetail.member_income_stream_amounts: dict[str, float]` (reporting layer), both keyed by `person_name`, mirroring `member_social_security_benefits` exactly (`015-per-account-projection-detail`'s own precedent).

**Rationale**: Consistency with the existing per-member reporting fields already shipped for RMDs and Social Security; a caller/BFF/UI that already knows how to read `member_social_security_benefits` needs no new mental model to read this field.

## 6. BFF and Streamlit UI scope

**Decision**: BFF `schemas.py` gains a mirrored `IncomeStreamRequest`/`HouseholdMemberRequest.income_streams` — free, since `routes/scenarios.py` converts every `ScenarioRequest` to YAML generically via `body.model_dump(mode="json")` before calling `parse_scenario()`; no `resolution.py` changes needed (confirmed by reading that route). Streamlit's `1_Scenarios.py` gets a **non-lossy pass-through only** (load into `session_state`, resubmit unchanged) — not new editing widgets. See plan.md's "Scope Boundaries."

**Rationale**: The BFF change is nearly free and keeps the API layer at full parity with the core library, unlike a UI editing surface, which is a real, separately-scoped design decision (the form's own docstring states its fixed-shape, no-free-form-list philosophy explicitly) that risks silently constraining a "how many streams can a user actually enter" UX question this issue's acceptance bar doesn't require answering. The pass-through prevents the concrete regression risk of silent data loss on save (this form already has one precedent gap of this shape — `hdhp_coverage` is not round-tripped at all today — so the bar this feature holds itself to, preservation rather than silent loss, is stricter than existing precedent, not looser).
