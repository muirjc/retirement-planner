# Implementation Plan: Per-Owner Account Attribution

**Branch**: `011-per-owner-accounts` | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-per-owner-accounts/spec.md`

## Summary

Extends `001`'s `Account` with a required-in-practice `owner` field (a `household.members[*].person_name` reference), replacing `004`'s documented "deem the older household member the owner of the household's entire traditional balance" RMD simplification with genuine per-member attribution — each member's own age and own share of the traditional balance drives their own RMD, summed into the household's total RMD for that plan year. The pooled, household-level arithmetic every other mechanic already uses (withdrawal sequencing, Roth conversion, tax-funding withdrawal, investment growth) is untouched; only how the year's RMD dollar amount is derived changes (research.md §1). `services/bff`'s `resolution.py` computes each member's fixed ownership share once, from the scenario's initial account data, and threads it as a new required parameter through `run_plan_projection()` (`004`), `run_simulation()`/`compare_*()` (`005`), and `comparison.compare_*()` (`004`). The Streamlit UI's account-entry form gains a per-account owner selector; a scenario saved before this feature surfaces a specific blocking validation flag rather than a silent guess, except for single-filer scenarios, which are unambiguous and require no user action at all.

## Technical Context

**Language/Version**: Python 3.11+ — same project, same interpreter floor as `001`–`010` (`pyproject.toml` still pins `>=3.11`).

**Primary Dependencies**: No new third-party runtime dependency anywhere in the stack. Standard library only in the core library; this feature's own in-repo dependencies are `retirement_planner.scenario` (`Account.owner`, `Household`, `HouseholdMember`, `validate()`), `retirement_planner.mechanics` (`compute_rmd()`, unchanged signature, called once per owning member instead of once per household), `retirement_planner.comparison` (`run_plan_projection()`, `compare_*()`), and `retirement_planner.simulation` (`run_simulation()`, `compare_*()`). `services/bff` gains no new dependency (still FastAPI/Pydantic, unchanged versions); `apps/streamlit_ui` gains no new dependency (still Streamlit, unchanged version) — the new owner control is a standard `st.selectbox`.

**Storage**: None new. Scenario YAML files remain the only persisted form (`001`'s `store.py`, unchanged) — `owner` is one more field inside an already-YAML-serialized `Account`.

**Testing**: pytest — continuing `001`–`010`'s convention for the core library and `services/bff`; `streamlit.testing.v1.AppTest` — continuing `008`'s convention for `apps/streamlit_ui`. Each package's suite still runs independently (README's existing note), unchanged by this feature.

**Target Platform**: Same as `001`–`010`: local developer/user machine, offline, BFF bound to `127.0.0.1` only, Streamlit UI talking to it over HTTP.

**Project Type**: Continues the existing four-layer monorepo (core library / BFF / UI) — no new package, no new subpackage. This feature is unusual only in breadth: it threads one new field (`Account.owner`) and one new derived value (`traditional_ownership_shares`) through all three existing layers simultaneously, rather than adding a new layer or subpackage the way `004`–`010` each did.

**Performance Goals**: `compute_rmd()` (already well under `003`'s own sub-10ms budget) is now called up to twice per plan year (once per household member with a positive traditional share) instead of once — a fixed, at-most-2x increase to a step that was never the per-year cost driver, negligible against `004`'s existing "well under 2 seconds per full single projection" / `005`'s Monte Carlo path-volume budget (Constitution Principle VI). No other per-year step changes cost.

**Constraints**: Every constraint `004`'s and `005`'s own plans already establish continues to hold (no network access; every comparison/simulation holds `traditional_ownership_shares` fixed across all its candidates, exactly like `accounts`/`household` already are, per `comparison-api.md`'s consumption note; every `FigureUsage` is retained, never dropped). New for this feature: a single-member household's computed output (RMDs, withdrawals, tax, comparisons, simulation outcomes) MUST be identical, plan-year-for-plan-year, before and after this feature ships, for every existing reference scenario (FR-009, SC-004) — the one hard regression-parity requirement this plan is built around.

**Scale/Scope**: Household size is capped at 1 or 2 members by `001`'s own schema (unchanged) — `traditional_ownership_shares` never has more than 2 entries, and the new per-year RMD step never makes more than 2 `compute_rmd()` calls. No change to the number of plan years, candidates, or Monte Carlo paths a run can request.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against all six principles plus the Technology/Architecture Constraints and Development Workflow gates, following the same evaluation `004`–`010` did:

- **I. Accuracy Over Cleverness** — ✅ PASS. This feature exists specifically to shrink a previously-documented simplification (`004` research.md §4's "deemed owner"). The simplification it introduces in place of that one — each member's share of the traditional balance held fixed at its scenario-configured initial split, rather than dynamically tracked through withdrawals/conversions — is itself explicitly documented, with its rationale and rejected alternatives, in research.md §1, and is a strictly narrower approximation than what it replaces (correct at scenario-start for every household, drifting only via the same pooled-mechanics arithmetic that already applied identically to every household before this feature). Nothing here is silently absorbed.
- **II. Reproducibility** — ✅ PASS. `traditional_ownership_shares` is a pure, deterministic function of one `Scenario`'s `accounts` (research.md §2) — no randomness, no dependency on wall-clock time or run order. Identical scenario and seed continue to produce identical output (FR-009's single-filer byte-identical requirement is the strictest form of this check this feature adds).
- **III. Auditability** — ✅ PASS. No new externally-sourced legal figure is introduced (research.md §5) — `compute_rmd()`'s existing `SourcedFigure`s are consumed exactly as before, just called once per owning member. `figures_used` is still a union, never a fresh derivation (data-model.md § Consumption).
- **IV. Extensibility Through Module Interfaces** — ✅ PASS. No withdrawal-sequencing or Roth-conversion strategy registry changes; ownership data flows through the same "caller supplies pre-resolved data, compute layer stays a pure function of it" shape `accounts`/`strategy`/`survival_curves` already established (research.md §2's explicit precedent-following). Adding this feature required zero new branching inside `run_plan_projection()`'s existing per-year step structure — the RMD step's internals changed; its position in the sequence didn't.
- **V. Offline-First, No Runtime Network Dependency** — ✅ PASS. Pure computation over caller-supplied/scenario-derived data; no I/O of any kind introduced.
- **VI. Performance Budget** — ✅ PASS. See Performance Goals above — a fixed, at-most-doubling of an already-cheap per-year step, not a scaling risk at any path/candidate count.

**Technology & Architecture Constraints:**

- *"Config as data, not code"* — `owner` is one more plain YAML field on `Account`, authored the same way every other scenario input already is; no engine code branches on a specific owner name.
- *Paired-draw comparison is the standard pattern* — Unaffected: `traditional_ownership_shares` is one more argument every `compare_*()` function holds fixed across all candidates within one call, exactly like `accounts`/`household`/`return_assumption` already are (`comparison-api.md`'s consumption note makes this explicit and checkable, not just asserted).
- *Scope boundary with the working document* — N/A, not implicated by this feature.

**Development Workflow & Quality Gates:**

- *Regression baseline* — Required and elevated to a hard functional requirement for this feature specifically (FR-009/SC-004): every existing single-filer reference scenario (`examples/reference_scenario.py` plus every single-filer test fixture across `tests/`, `services/bff/tests/`, `apps/streamlit_ui/tests/`) must produce byte-identical output before and after this feature, since a single-member household's `traditional_ownership_shares` is always `{that member: 1.0}` — mathematically a no-op multiplication against the exact `compute_rmd()` call that already ran.
- *Verified-figure gate* — N/A; no new figure is introduced (Principle III above).
- *Unit test coverage for numeric primitives* — Required: the per-member RMD summation (multiple owning members, differing ages/shares, differing crossing years) against hand-calculated reference values, replacing `004`'s now-removed "deemed-RMD-owner selection" test case with its per-member equivalent (mirrors `004`'s own Development Workflow gate item, updated for this feature's actual computation).

**Post-Phase 1 re-check**: Confirmed after generating research.md, data-model.md, contracts/{scenario-api,comparison-api,simulation-api,bff-api,ui-pages}.md, and quickstart.md — no new violations. Keeping `traditional_ownership_shares` fixed-and-precomputed (never re-derived mid-projection) keeps Principle II mechanically simple to verify; documenting the fixed-share simplification alongside its rejected dynamic-tracking alternative in research.md §1 keeps Principle I satisfied without discovering the conversion-attribution problem (the `$0`-basis ratio issue) late, during implementation.

## Project Structure

### Documentation (this feature)

```text
specs/011-per-owner-accounts/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── scenario-api.md
│   ├── comparison-api.md
│   ├── simulation-api.md
│   ├── bff-api.md
│   └── ui-pages.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── retirement_planner/
    ├── scenario/
    │   ├── models.py                    # Account.owner: str | None = None
    │   ├── loader.py                    # household built before accounts; owner
    │   │                                 # read permissively; single-member auto-fill
    │   └── validation.py                # +2 blocking ValidationFlag rules (accounts[i].owner)
    ├── mechanics/                       # unchanged -- compute_rmd()'s signature
    │   └── ...                          # and every other 003 contract is untouched
    ├── comparison/
    │   ├── projection.py                # run_plan_projection(): per-member RMD loop
    │   │                                 # replaces deemed_rmd_owner()-attributed single call
    │   │                                 # (deemed_rmd_owner()/member_age_in_tax_year() themselves
    │   │                                 # stay, still used by 006's reporting label)
    │   └── compare.py                   # +traditional_ownership_shares param, forwarded
    └── simulation/
        ├── monte_carlo.py               # +traditional_ownership_shares param, threaded through
        │                                 # _init_worker/_worker_shared_args/_run_one_path(_shared)
        └── compare.py                   # +traditional_ownership_shares param, forwarded

services/bff/src/rp_bff/
├── schemas.py                           # AccountRequest.owner: str | None = None
└── resolution.py                        # ResolvedRunContext gains traditional_ownership_shares;
                                          # computed alongside the existing accounts summation

apps/streamlit_ui/pages/
└── 1_Scenarios.py                       # accounts section: owner selector per entry,
                                          # populated from the form's own household member names

examples/
└── reference_scenario.py                # direct run_simulation() call gains an explicit
                                          # traditional_ownership_shares argument

tests/
├── unit/
│   ├── scenario/
│   │   ├── test_loader.py               # +owner parse/auto-fill cases
│   │   └── test_validation.py           # +owner blocking-flag cases
│   ├── comparison/
│   │   └── test_projection.py           # per-member RMD summation replaces the removed
│   │                                     # deemed-RMD-owner-selection cases (plan.md's
│   │                                     # Development Workflow gate)
│   └── simulation/
│       └── test_monte_carlo.py          # +traditional_ownership_shares call-site updates
└── integration/
    └── test_scenario_lifecycle.py       # +single-filer regression-parity assertion (FR-009)

services/bff/tests/                      # +AccountRequest.owner request/response round-trip,
                                          # +owner-missing blocking_validation_flags case
apps/streamlit_ui/tests/                 # +owner selector rendering/options (AppTest)
```

**Structure Decision**: Continues `001`–`010`'s existing three-package layout (`src/retirement_planner`, `services/bff`, `apps/streamlit_ui`) with no new package or subpackage — every file this feature touches already exists. The dependency graph is unchanged (`scenario` → `mechanics` → `comparison`/`simulation` → `services/bff` → `apps/streamlit_ui`, each layer a pure consumer of the ones before it, matching `004`'s already-established layer order); this feature's breadth comes from touching one field/one derived value at every layer of that existing chain simultaneously, not from adding a new layer.

## Complexity Tracking

*No constitution violations were found (see Constitution Check above) — this section is not needed.*
