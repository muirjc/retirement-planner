# Implementation Plan: Advanced Tax & Benefits Modeling (IRMAA, NIIT, HSA)

**Branch**: `010-advanced-tax-benefits` | **Date**: 2026-08-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-advanced-tax-benefits/spec.md`

## Summary

Adds three financial mechanisms this project's tax and account-mechanics engines have deferred since `002`/`003`: IRMAA (Medicare premium surcharge), NIIT (Net Investment Income Tax), and HSA contribution/eligibility timing. All three plug into the single per-plan-year loop `004-strategy-comparison-layer` built (`comparison/projection.py::run_plan_projection()`), which `005-simulation-engine` already reuses unchanged for every Monte Carlo path — so extending that one loop is what makes the new mechanisms visible to every downstream consumer (deterministic comparison, simulation, and — additively — reporting) without duplicating logic anywhere. This is a pure engine/data-model extension: no new package, no new third-party dependency, no UI feature of its own.

## Technical Context

**Language/Version**: Python 3.11+ — unchanged, same as `001`–`009`.

**Primary Dependencies**: None new. Extends `retirement_planner.tax`, `retirement_planner.mechanics`, and `retirement_planner.comparison` — the same core library `001`–`006` already are, plus a small additive `services/bff` schema change (see Project Structure).

**Storage**: None new — `001`'s existing scenario YAML storage gains two new optional fields; no new persisted state.

**Testing**: `pytest`, continuing every prior feature's convention — unit tests for each new numeric primitive (IRMAA tier lookup, NIIT threshold/rate application, HSA contribution-limit lookup) against hand-calculated reference values, per the constitution's own "Unit test coverage for numeric primitives" gate, plus integration tests through `run_plan_projection()` and the paired-draw comparison/simulation entry points.

**Target Platform**: Unchanged — offline-first, local execution, same as every prior feature.

**Project Type**: An extension to the existing core library (`src/retirement_planner/`) — no new package. One small, additive touch to `services/bff`'s request schema (see below); no touch to `apps/streamlit_ui`.

**Performance Goals**: Each new computation is a bounded dictionary/threshold lookup per plan year (the same shape as the RMD divisor and tax-bracket lookups this engine already does per year) — no new Monte Carlo path generation, no new per-path branching cost. The existing reference-scale budget (`005`'s own measured ~3.77s for 5,000 paths × 3 states) MUST NOT regress materially; this is flagged here as a watch item per the constitution's Performance Budget principle, to be confirmed empirically during implementation rather than assumed.

**Measured (T033, Polish)**: 5,000 paths × 36-year horizon, single configuration, with IRMAA/NIIT/HSA computed every plan year: **5.24s** (was ~3.77s pre-feature — a real but small ~1.5s increase, ~9% of the 60s budget). 5,000 paths × 3-state comparison (1-year horizon, the existing benchmark's own pre-existing constraint per `SC`/`DE`'s bracket-table year coverage, unrelated to this feature): **0.89s**. Both comfortably within budget — the watch item is resolved, not merely asserted away.

**Constraints**: Every new externally-sourced figure (IRMAA tier thresholds/surcharge amounts, the NIIT threshold, HSA contribution limits) MUST use the existing `SourcedFigure`/`FigureUsage` schedule-by-year pattern (`tax/models.py`) — no new figure-provenance mechanism, no new "trust this number" exception. No new UI display is built by this feature (see Project Structure's scope note) — the new figures must be visible in the tool's existing structured output (CSV export, JSON API responses) without requiring a new presentation layer to exist first.

**Scale/Scope**: Three new compute modules (one per mechanism), a small number of new optional fields on already-existing dataclasses (`Scenario`/`HouseholdMember`, `PlanYearProjection`, `PlanOutcome`), one new integration point in one existing loop (`run_plan_projection()`), and additive CSV columns in `006`'s export functions. No new module category, no new package.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Accuracy Over Cleverness** — ✅ PASS, with one simplification this plan must document explicitly (not silently absorb), per the principle's own requirement: this engine has never tracked investment-income character (interest/dividends/realized gains) separately from principal in a taxable account, so NIIT's "net investment income" figure needs a documented approximation rather than a true cost-basis model. Phase 0 research.md resolves and documents this decision by name, in code comments and in this plan, exactly as `federal.py`'s own "real-terms brackets" simplification is already documented — not hidden behind a number that looks more precise than it is.
- **II. Reproducibility** — ✅ PASS. Every new computation is a deterministic function of already-deterministic per-plan-year inputs (income figures, ages, tax year) — no new randomness, no new seed-dependent behavior.
- **III. Auditability** — ✅ PASS, directly reinforced: every new externally-sourced figure (IRMAA tiers, NIIT threshold, HSA limits) gets its own `SourcedFigure` with citation/last-verified/verified metadata, `verified=False` until cross-checked against a primary source (matching every existing tax figure's honest starting state), and flows into the same `figures_used`/`unverified_figure_names` propagation path `002`–`009` already built and tested end-to-end.
- **IV. Extensibility Through Module Interfaces** — ✅ PASS, concretely reinforced: IRMAA/NIIT become new modules in `retirement_planner.tax` following the exact shape `federal.py`/`social_security.py` already establish (a `SourcedFigure`-backed schedule plus a pure `compute_*()` function); HSA becomes a new module in `retirement_planner.mechanics` following `rmd.py`'s own shape. Neither requires modifying `bracket_math.py`, `federal.py`, `rmd.py`, or any other existing compute module — only `run_plan_projection()` (the intended, documented extension point every comparison and simulation feature already runs through) calls the new functions.
- **V. Offline-First, No Runtime Network Dependency** — ✅ PASS. No new network call of any kind — the new figures are schedule-by-year data shipped with the code, identical in kind to every existing tax figure.
- **VI. Performance Budget** — ✅ PASS as a watch item (see Technical Context's Performance Goals) — the new per-year computations are bounded lookups, not new simulation cost, but this plan does not assert the budget holds without measuring it once implemented, per `005`'s own precedent of catching a cost-estimation error by measuring rather than assuming.

**Technology & Architecture Constraints:**
- *"Config as data, not code"* — Directly relevant and reinforced: the two new scenario inputs this feature needs (per-member HDHP coverage, an optional HSA contribution election) become new optional fields on `001`'s existing `HouseholdMember`/`Scenario` types, loaded from YAML exactly like every other scenario input — never a hardcoded assumption in engine code.
- *Paired-draw comparison is the standard pattern* — N/A directly; this feature adds new per-plan-year mechanics, not a new comparison axis or pairing logic. Every existing paired-draw comparison (state, Roth strategy, withdrawal order, claiming-age grid) automatically reflects the new mechanisms once `run_plan_projection()` is extended, without this feature reimplementing pairing.
- *Scope boundary with the working document* — N/A directly; this feature computes financial effects only, consistent with every prior feature's own respect for that boundary (spec.md's own scope note already states this explicitly).

**Development Workflow & Quality Gates:**
- *Regression baseline* — N/A; no engine refactor, only new, additive mechanics gated behind new optional scenario inputs that default to "not modeled" for every existing scenario (backward compatible by construction — see data-model.md).
- *Verified-figure gate* — Directly relevant: every new IRMAA/NIIT/HSA figure starts `verified=False`, per the same honest-by-default posture every existing tax figure already has; none may be marked verified until cross-checked against a primary source (IRS Rev. Proc. for IRMAA/HSA limits, IRC §1411 for NIIT), matching the constitution's own requirement.
- *Unit test coverage for numeric primitives* — Directly relevant: IRMAA tier lookup, NIIT threshold/rate application, and HSA contribution-limit lookup each need unit tests against hand-calculated reference values before being used in any comparative run, mirroring the discipline `002`/`003` already established for bracket math and RMD divisors.

**Post-Phase 1 re-check**: Confirmed after Phase 1 design below — no new violations; the NIIT investment-income simplification is the one deliberate approximation this feature introduces, documented by name in research.md §1 and carried into code comments at implementation, exactly as Principle I requires.

## Project Structure

### Documentation (this feature)

```text
specs/010-advanced-tax-benefits/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── contracts/            # Phase 1 output -- additive amendments to 3 existing contract docs
│   ├── tax-api.md         # extends 002's own contracts/tax-api.md
│   ├── mechanics-api.md   # extends 003's own contracts/mechanics-api.md
│   └── scenario-api.md    # extends 001's own contracts/scenario-api.md
└── quickstart.md         # Phase 1 output
```

### Source Code (repository root)

```text
src/retirement_planner/
├── scenario/
│   └── models.py                  # MODIFIED -- HouseholdMember gains an optional
│                                   # hdhp_coverage field; Scenario gains an optional
│                                   # hsa_contribution field (mirrors roth_conversion's
│                                   # own optional-block shape) -- both default to
│                                   # "not modeled," backward compatible with every
│                                   # existing saved scenario and test fixture
├── tax/
│   ├── irmaa.py                   # NEW -- SourcedFigure-backed IRMAA tier table +
│   │                               # compute_irmaa_surcharge()
│   ├── niit.py                    # NEW -- SourcedFigure-backed NIIT threshold/rate +
│   │                               # compute_niit()
│   ├── models.py                  # MODIFIED -- IrmaaResult, NiitResult dataclasses,
│   │                               # alongside the existing FederalTaxResult/StateTaxResult
│   └── __init__.py                # MODIFIED -- exports the two new modules' public API
├── mechanics/
│   ├── hsa.py                     # NEW -- SourcedFigure-backed HSA contribution-limit
│   │                               # table + compute_hsa_eligibility()/compute_hsa_contribution()
│   ├── models.py                  # MODIFIED -- HsaEligibility, HsaContributionResult
│   ├── plan_year.py               # MODIFIED -- compute_plan_year_mechanics() gains the HSA
│   │                               # contribution step (income-reducing, alongside the
│   │                               # existing Roth conversion step)
│   └── __init__.py                # MODIFIED -- exports hsa.py's public API
├── comparison/
│   ├── projection.py              # MODIFIED -- run_plan_projection() calls the new IRMAA/NIIT
│   │                               # functions immediately after federal/state tax (the point
│   │                               # that year's income figures are already assembled);
│   │                               # 005-simulation-engine's _run_one_path() reuses this exact
│   │                               # function unchanged, so this is the one integration point
│   │                               # that reaches both the deterministic and Monte Carlo engines
│   ├── models.py                  # MODIFIED -- StrategyConfiguration gains an optional
│   │                               # hsa_contribution field (contracts/comparison-api.md's
│   │                               # correction: rides through every existing signature this
│   │                               # way, instead of a new run_plan_projection() parameter);
│   │                               # PlanYearProjection gains irmaa/niit/hsa result fields;
│   │                               # PlanOutcome gains cumulative_irmaa_paid and
│   │                               # cumulative_niit_paid (additive -- cumulative_tax_paid's
│   │                               # existing meaning, income tax only, is unchanged)
│   └── compare.py                 # MODIFIED -- each of the 3 compare_*() functions gets one
│                                   # small internal addition: force hsa_contribution onto every
│                                   # candidate, alongside the fields each already forces
│                                   # (contracts/comparison-api.md) -- no signature change
└── reporting/
    └── export.py                  # MODIFIED -- CSV export functions gain additive columns for
                                    # the new per-outcome cumulative figures

src/retirement_planner/simulation/
└── compare.py                     # MODIFIED -- 005's own 4 compare_*() functions get the same
                                    # small internal addition as 004's -- no signature change;
                                    # run_simulation() itself needs no change at all

services/bff/src/rp_bff/
├── schemas.py                     # MODIFIED -- ScenarioRequest gains the two new optional
│                                   # fields, mirroring scenario/models.py exactly (research.md's
│                                   # own "config as data" note) -- response bodies need no change
│                                   # at all, since to_jsonable() is fully generic over dataclass
│                                   # fields (confirmed by reading serialization.py during planning)
└── resolution.py                  # MODIFIED -- resolve_run_context() resolves
                                    # Scenario.hsa_contribution into the StrategyConfiguration it
                                    # already builds there, the same way it already resolves
                                    # Scenario.roth_conversion into that object's conversion fields
```

**Structure Decision**: No new package. This feature extends the core library's existing `tax`, `mechanics`, `comparison`, and `reporting` subpackages, following each one's own established module-per-mechanism shape (`irmaa.py`/`niit.py` beside `federal.py`/`social_security.py`; `hsa.py` beside `rmd.py`/`roth_conversion.py`). **No function signature changes in `004` or `005-simulation-engine`** — `hsa_contribution` rides through every existing call chain as a new `StrategyConfiguration` field (contracts/comparison-api.md's own correction note, found during `/speckit-tasks`: an earlier draft would have threaded a new parameter through 8 signatures across both features before this simpler fit was found). Each feature's `compare_*()` functions need one small internal line apiece (forcing the new field onto every candidate, exactly how each already forces several others) — an implementation-body change, not a contract change. `007-bff-api-service`'s JSON responses need no code change at all (`to_jsonable()` is fully generic); its *request* schema and `resolve_run_context()` need small additive changes to accept and apply the two new scenario inputs. **`apps/streamlit_ui` (`008`) is explicitly out of scope for this feature** — the new figures become visible through the existing CSV export and JSON API responses; a dedicated UI display (a new table column, a new chart) is a natural, small follow-on feature, not something spec.md's own functional requirements require this feature to build.

## Complexity Tracking

*No Constitution Check violations — table intentionally omitted. The NIIT investment-income simplification is a documented approximation (Principle I's own explicit mechanism for handling this), not a violation requiring justification against a rejected alternative.*
