# Implementation Plan: Inherited IRA (Already-in-RMD-Status) Modeling

**Branch**: `012-inherited-ira-rmd` | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-inherited-ira-rmd/spec.md`

## Summary

Extends `001`'s `Account` with two new optional fields — `account_id` (a stable per-account handle) and `inherited: InheritedIraDetails | None` (decedent/beneficiary facts) — so a scenario can record a traditional IRA the beneficiary inherited from an original owner who had already begun their own RMDs before dying. A new sibling module, `mechanics/inherited_rmd.py`, computes each such account's annual required distribution using the IRS Single Life Expectancy Table divisor method (initial divisor at the decedent's age at death, reduced by 1.0 each subsequent year) — never through `003`'s locked `compute_rmd()`, which stays untouched. Because an inherited account can never be commingled with the beneficiary's own accounts (IRS rule, research.md §5), it is excluded entirely from `011`'s pooled `traditional_ownership_shares` mechanism and instead gets its own independently-tracked balance, threaded through `run_plan_projection()` and every `comparison.compare_*()` function (`004`) as a new `inherited_accounts` parameter, forced to fully deplete no later than the 10th calendar year after the owner's death. Every case this feature does not compute — the owner died before their RBD, the beneficiary is an eligible designated beneficiary, the inherited account is Roth/taxable rather than traditional, or the request is a Monte Carlo simulation/simulated comparison (`005`, explicit follow-on) — is caught by a blocking `ValidationFlag` or a specific rejection response rather than silently mis-computed (research.md §2, §3, §10). `services/bff`'s `resolution.py` builds the new per-account runtime state once per resolved run, the same seam that already builds `traditional_ownership_shares`, and its deterministic-comparison/single-projection endpoints support inherited accounts fully; its simulation endpoints reject them explicitly.

## Technical Context

**Language/Version**: Python 3.11+ — same project, same interpreter floor as `001`–`011` (`pyproject.toml` still pins `>=3.11`).

**Primary Dependencies**: No new third-party runtime dependency anywhere in the stack. This feature's in-repo dependencies are `retirement_planner.scenario` (`Account.account_id`/`Account.inherited`, new `InheritedIraDetails`, `validate()`), `retirement_planner.mechanics` (new `inherited_rmd.py` module; `withdrawal_sequencing.py`/`plan_year.py` gain new optional parameters; `rmd.py`'s own `compute_rmd()` is untouched), and `retirement_planner.comparison` (`run_plan_projection()` and every `compare.py` function gain a new optional parameter). `retirement_planner.simulation` (`005`) is not touched (research.md §10 addendum, Monte Carlo scope decision). `services/bff` gains no new dependency (still FastAPI/Pydantic, unchanged versions).

**Storage**: None new. Scenario YAML files remain the only persisted form (`001`'s `store.py`) — `account_id` and `inherited` are two more fields inside an already-YAML-serialized `Account`.

**Testing**: pytest, continuing `001`–`011`'s convention for the core library and `services/bff`.

**Target Platform**: Same as `001`–`011`: local developer/user machine, offline, BFF bound to `127.0.0.1` only.

**Project Type**: Continues the existing three-layer monorepo (core library / BFF / UI) — no new package, no new subpackage. UI (`apps/streamlit_ui`) is not touched by this feature (spec.md Assumptions; research.md §9.9) — a scenario author enters `account_id`/`inherited` fields directly in YAML, consistent with the constitution's "config as data, not code" rule not requiring a dedicated UI control for every field.

**Performance Goals**: `compute_inherited_rmd()` (a single dict lookup and one subtraction, no heavier than `compute_rmd()`'s own already-cheap divisor lookup) is called at most once per inherited account per plan year. Household scenarios are expected to hold a small number of inherited accounts (typically 0–2); this adds a bounded, small constant number of extra calls per plan year, negligible against `005`'s Monte Carlo path-volume budget (Constitution Principle VI) — the same reasoning `011`'s plan.md used for its own "at most 2x more `compute_rmd()` calls" change.

**Constraints**: Every constraint `004`'s/`005`'s/`011`'s own plans already establish continues to hold (no network access; every comparison/simulation holds `inherited_accounts` fixed in composition across all its candidates within one call, exactly like `traditional_ownership_shares` already is). New for this feature: an inherited account's balance is never read from, or written into, `AccountBalances.traditional` at any point (research.md §5) — the one hard non-negotiable modeling constraint this plan is built around. A scenario with no inherited accounts (`inherited_accounts=[]`, the default) MUST produce output byte-for-byte identical to today's, for every existing reference scenario and test fixture (the regression-parity requirement, mirroring `011`'s own FR-009/SC-004).

**Scale/Scope**: A `Scenario`'s `accounts` list is already unbounded (`001`); this feature adds no new cap — a beneficiary may hold any number of inherited accounts, each independently tracked (research.md §7's "no basis for a one-inherited-account-per-beneficiary limit" reasoning). Each additional inherited account contributes at most one extra `compute_inherited_rmd()` call and one extra forced-full-depletion check per plan year.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against all six principles plus the Technology/Architecture Constraints and Development Workflow gates, following the same evaluation `004`–`011` did:

- **I. Accuracy Over Cleverness** — ✅ PASS. Every case this feature does not correctly compute (pre-RBD death, EDB beneficiary, Roth/taxable inherited account) is caught by an explicit blocking `ValidationFlag` naming exactly which case is unsupported (data-model.md § Validation rules) — never silently computed with the wrong rule. A Monte Carlo simulation/simulated-comparison request against a scenario with an inherited account is likewise explicitly rejected (`422 inherited_accounts_unsupported_for_simulation`, bff-api.md), not silently run with the inherited account's distributions dropped (research.md §10). The new `SINGLE_LIFE_EXPECTANCY_TABLE` figure ships with partial, illustrative coverage, `verified=False`, following `JOINT_LIFE_TABLE`'s own "partial coverage, explicitly flagged" precedent (research.md §7). The household's single return assumption being reused for an inherited account's growth, rather than a separate per-account assumption this codebase has no concept of, is itself documented as an explicit simplification (research.md §10), not silently absorbed.
- **II. Reproducibility** — ✅ PASS. `compute_inherited_rmd()` is a pure, deterministic function of its arguments (balance, tax year, death year, decedent's age at death) — no randomness. `Account.account_id`'s auto-generated fallback is a deterministic function of parse order (`f"{account_type}-{index}"`), not a random UUID (research.md §10) — `parse_scenario()` remains a pure function of its YAML input.
- **III. Auditability** — ✅ PASS. The new `SINGLE_LIFE_EXPECTANCY_TABLE` `SourcedFigure` carries a citation, `last_verified` date, and `verified=False`, in the identical shape `rmd.py`'s three existing figures already use (research.md §7). `InheritedRmdResult.figures_used` threads through `compute_plan_year_mechanics()`'s existing `figures_used` union exactly like `RmdResult.figures_used` already does.
- **IV. Extensibility Through Module Interfaces** — ✅ PASS. `compute_inherited_rmd()` lives in a new sibling module (`mechanics/inherited_rmd.py`), not a branch inside `compute_rmd()`'s locked contract (`003`'s `mechanics-api.md`) — the same "new, documented extension point, not a widened core function" principle `011` already followed for its own RMD-attribution change (research.md §7).
- **V. Offline-First, No Runtime Network Dependency** — ✅ PASS. Pure computation over caller-supplied/scenario-derived data; no I/O of any kind introduced.
- **VI. Performance Budget** — ✅ PASS. See Performance Goals above — a small, bounded number of additional cheap calls per plan year, not a scaling risk at any path/candidate count.

**Technology & Architecture Constraints:**

- *"Config as data, not code"* — `account_id`/`inherited` are plain YAML fields on `Account`, authored the same way every other scenario input already is; no engine code branches on a specific account name or beneficiary name.
- *Paired-draw comparison is the standard pattern* — Unaffected: `inherited_accounts` is one more argument every `compare_*()` function will hold fixed in composition across all candidates within one call, exactly like `accounts`/`traditional_ownership_shares` already are — though each candidate's own independent projection still mutates its own copy of each `InheritedAccountBalance`'s `balance` year-to-year (the same way each candidate already carries its own independent `current_balances`).
- *Scope boundary with the working document* — N/A, not implicated by this feature.

**Development Workflow & Quality Gates:**

- *Regression baseline* — Required: every existing reference scenario and test fixture (none of which has an inherited account) must produce byte-for-byte identical output before and after this feature, since `inherited_accounts=[]` is a strict no-op through every new code path this feature adds.
- *Verified-figure gate* — `SINGLE_LIFE_EXPECTANCY_TABLE` ships unverified and is documented as such (Principle III above); it must not be marked "verified" until cross-checked against a primary source — consistent with, not a violation of, this gate.
- *Unit test coverage for numeric primitives* — Required: `compute_inherited_rmd()`'s divisor arithmetic (the "subtract 1 per year" rule) and the depletion-deadline enforcement, against hand-calculated reference values — mirrors `003`'s own gate for `compute_rmd()`.

**Post-Phase 1 re-check**: Confirmed after generating research.md's §10 addendum, data-model.md, contracts/{scenario-api,mechanics-api,comparison-api,bff-api}.md, and quickstart.md — no new violations. Keeping the inherited-account balance out of `AccountBalances` entirely (rather than finding some pooled-arithmetic compromise) is what keeps Principle I satisfied without inventing a commingling rule IRS law doesn't allow; documenting the reused-return-assumption and hardcoded-two-literal-arguments simplifications explicitly in research.md §10 keeps Principle I satisfied there too, the same way `011`'s plan.md handled its own fixed-share simplification.

## Project Structure

### Documentation (this feature)

```text
specs/012-inherited-ira-rmd/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (rp-2cs) + §10 addendum (/speckit-plan)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/             # Phase 1 output (/speckit-plan command)
│   ├── scenario-api.md
│   ├── mechanics-api.md
│   ├── comparison-api.md
│   └── bff-api.md
├── checklists/
│   └── requirements.md  # /speckit-specify output
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── retirement_planner/
    ├── scenario/
    │   ├── models.py                    # Account.account_id, Account.inherited: InheritedIraDetails | None;
    │   │                                 # new InheritedIraDetails dataclass
    │   ├── loader.py                    # _build_account(): +index param, account_id auto-fill,
    │   │                                 # +_build_inherited_ira_details() (mirrors _build_roth_conversion())
    │   ├── validation.py                # +4 blocking ValidationFlag rules (accounts[i].inherited / .owner)
    │   └── store.py                     # serialize account_id + inherited
    ├── mechanics/
    │   ├── inherited_rmd.py             # NEW — SINGLE_LIFE_EXPECTANCY_TABLE, compute_inherited_rmd()
    │   ├── models.py                    # +InheritedRmdResult, +InheritedAccountBalance,
    │   │                                 # +WithdrawalPlan.inherited_distribution_drawn
    │   ├── withdrawal_sequencing.py     # compute_withdrawal_plan(): +inherited_distribution_amount param
    │   ├── plan_year.py                 # compute_plan_year_mechanics(): +inherited_distribution_amount,
    │   │                                 # +inherited_rmd_figures_used params
    │   └── rmd.py                       # unchanged -- 003's locked compute_rmd() contract untouched
    └── comparison/
        ├── projection.py                # run_plan_projection(): +inherited_accounts param;
        │                                 # per-plan-year loop over inherited_accounts alongside
        │                                 # the existing per-member compute_rmd() loop
        └── compare.py                   # +inherited_accounts param on all 3 functions;
                                          # fresh per-candidate copy before each run_plan_projection() call

services/bff/src/rp_bff/
├── schemas.py                           # +InheritedIraDetailsRequest; AccountRequest.account_id,
│                                         # .inherited: InheritedIraDetailsRequest | None
├── resolution.py                        # _sum_accounts()/_traditional_ownership_shares(): exclude
│                                         # inherited accounts; +_inherited_accounts(); ResolvedRunContext
│                                         # gains inherited_accounts; +InheritedAccountsUnsupportedForSimulationError
└── routes/
    ├── simulations.py                   # resolve_and_run_simulation(): +check, +422 translation
    └── comparisons.py                   # simulated-comparison resolve path: +check, +422 translation
                                          # (deterministic branch unaffected -- passes inherited_accounts through)

tests/
├── unit/
│   ├── scenario/
│   │   ├── test_loader.py               # +inherited/account_id parse cases
│   │   └── test_validation.py           # +4 new blocking-flag cases
│   ├── mechanics/
│   │   ├── test_inherited_rmd.py        # NEW — divisor arithmetic, deadline, hand-calculated references
│   │   ├── test_withdrawal_sequencing.py  # +inherited_distribution_amount cases
│   │   └── test_plan_year.py            # +inherited_distribution_amount/figures_used cases
│   └── comparison/
│       ├── test_projection.py           # +inherited-account balance/deadline/depletion cases,
│       │                                  # +regression-parity case (inherited_accounts=[])
│       └── test_compare.py              # +per-candidate independent-copy case (no cross-candidate leakage)
services/bff/tests/                      # +AccountRequest.account_id/.inherited round-trip,
                                          # +new blocking_validation_flags cases,
                                          # +422 inherited_accounts_unsupported_for_simulation cases
```

**Structure Decision**: Continues `001`–`011`'s existing three-package layout (`src/retirement_planner`, `services/bff`, `apps/streamlit_ui`) with no new package or subpackage — every source file this feature touches already exists except one new sibling module (`mechanics/inherited_rmd.py`). `apps/streamlit_ui` is intentionally not touched (spec.md Assumptions) — every other feature that added a scenario field also added a matching UI control, but this feature's fields are read/write only through YAML for its first slice, consistent with the constitution's "config as data" principle not mandating a UI control for every field, and with research.md §9.9's explicit deferral of UI/BFF surfacing.

## Complexity Tracking

*No constitution violations were found (see Constitution Check above) — this section is not needed.*
