---

description: "Task list for Inherited IRA (Already-in-RMD-Status) Modeling"
---

# Tasks: Inherited IRA (Already-in-RMD-Status) Modeling

**Input**: Design documents from `/specs/012-inherited-ira-rmd/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/) (`scenario-api.md`, `mechanics-api.md`, `comparison-api.md`, `bff-api.md`), [quickstart.md](./quickstart.md)

**Tests**: Included — plan.md's Development Workflow gate requires unit tests for `compute_inherited_rmd()`'s divisor arithmetic against hand-calculated reference values (the constitution's "Unit test coverage for numeric primitives" gate), matching every prior engine feature's (`002`/`003`/`004`/`011`) practice.

**Organization**: Tasks are grouped by user story (spec.md priorities P1–P3) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to (US1–US3)
- File paths are exact and relative to the repository root

## Path Conventions

This feature extends the existing three-package monorepo (`src/retirement_planner`, `services/bff`) — no new package, no new dependency, no `apps/streamlit_ui` change (plan.md's Structure Decision). See [plan.md](./plan.md) Project Structure for the full file list. `retirement_planner.simulation` (`005`) is deliberately not touched — US3 instead adds an explicit rejection for that path (research.md §10 addendum).

**Story dependency shape**: US1 (annual distribution) and US2 (10-year depletion) are not independent in the usual sense — US2 is a small, additive branch on the exact same `run_plan_projection()` per-inherited-account loop US1 builds (data-model.md § Consumption's single combined step, split here into two increments: annual-only first, then the deadline override). US2's own phase therefore depends directly on US1's core implementation task (T015), not just on Foundational. US3 (reject unsupported cases) is almost entirely independent of US1/US2 in file surface (`scenario/validation.py`, `services/bff/.../resolution.py`+`routes/`) and could be built in parallel with them by a second person, but is sequenced last here to match spec.md's P1 > P2 > P3 order — except its BFF tasks (T024, T025) depend on US1's `resolution.py` work (T017) existing first.

---

## Phase 1: Setup

**Purpose**: Confirm the existing packages need no new dependency before extending them

- [X] T001 Confirm no new dependency is needed for this feature (plan.md's Technical Context — no new third-party dependency anywhere) — run `pytest tests/ services/bff/tests/` to confirm the existing suites pass as a pre-change baseline (300 passed: 253 core + 47 BFF, via `.venv/bin/python3.12 -m pytest`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The new `Account`/`InheritedIraDetails` schema fields and the new mechanics-layer data shapes must exist before any user story can be implemented or tested against real data

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Unit test `Account.account_id`/`Account.inherited` parsing in `tests/unit/scenario/test_loader.py`: an omitted `account_id` auto-fills to `f"{account_type}-{index}"` (research.md §10); a provided `account_id` passes through unchanged; an omitted `inherited` key parses to `None`; a present `inherited` block requires all five sub-fields (`death_year`, `decedent_age_at_death`, `decedent_was_taking_rmds`, `beneficiary_relationship`, `beneficiary_classification`) — missing any one raises `ScenarioParseError` (scenario-api.md) — write FIRST, ensure it FAILS before T004–T005
- [X] T003 [P] Add `InheritedRmdResult`, `InheritedAccountBalance` dataclasses and `WithdrawalPlan.inherited_distribution_drawn: float = 0.0` field to `src/retirement_planner/mechanics/models.py` (mechanics-api.md) — independent of T002, can run in parallel
- [X] T004 Add `InheritedIraDetails` dataclass and `Account.account_id: str | None = None` / `Account.inherited: InheritedIraDetails | None = None` fields to `src/retirement_planner/scenario/models.py` (data-model.md § Account, § InheritedIraDetails) (depends on T002)
- [X] T005 [P] Implement `account_id` auto-fill (`f"{account_type}-{index}"`) and `_build_inherited_ira_details()` (mirrors `_build_roth_conversion()`'s "present block, required inner fields" pattern), wired into `_build_account()`/`parse_scenario()`, in `src/retirement_planner/scenario/loader.py` (scenario-api.md, research.md §10) (depends on T002, T004)
- [X] T006 [P] Serialize `account_id` and `inherited` in `src/retirement_planner/scenario/store.py` (scenario-api.md) (depends on T004) — added `_account_to_dict()` helper plus a round-trip regression test in `tests/unit/scenario/test_store.py`, matching `011`'s owner round-trip precedent

**Checkpoint**: Foundation ready — `Account.account_id`/`.inherited` round-trip through YAML, and the new mechanics data shapes exist. US1, US2, and US3 implementation can now begin.

---

## Phase 3: User Story 1 - Correct annual distribution for an inherited account (Priority: P1) 🎯 MVP

**Goal**: An inherited traditional account's own annual required distribution is computed using the Single Life Expectancy divisor method and included in the household's projected withdrawals and taxes — independently of any account the beneficiary owns outright.

**Independent Test**: A scenario with one inherited traditional account (decedent already taking RMDs) shows a positive `inherited_distribution_drawn` in each relevant plan year's mechanics, while the pooled `AccountBalances.traditional` stays completely unaffected — testable purely at the library level via `run_plan_projection()` (quickstart.md §1), no UI or BFF required for the core check.

### Tests for User Story 1 ⚠️

> Write these tests FIRST, ensure they FAIL before implementing T012–T018

- [X] T007 [P] [US1] Unit test `compute_inherited_rmd()` divisor arithmetic in `tests/unit/mechanics/test_inherited_rmd.py`: divisor looked up at `decedent_age_at_death` for `death_year + 1`, then reduced by exactly `1.0` for each subsequent `tax_year` (never a fresh table lookup) — against hand-calculated reference values (plan.md's Development Workflow gate); `inherited_balance <= 0` → zeroed result (`required_amount=0.0`, `table_used=None`, `divisor=None`); `required_amount = inherited_balance / divisor`; `depletion_deadline_year = death_year + 10`; `is_within_ten_year_window = tax_year <= depletion_deadline_year`; unsupported divisor year raises `UnsupportedTaxYearError`
- [X] T008 [P] [US1] Unit test `compute_withdrawal_plan()`'s new `inherited_distribution_amount` parameter in `tests/unit/mechanics/test_withdrawal_sequencing.py`: reduces `remaining_need` exactly like `rmd_drawn` already does but never subtracts from `starting_balances.traditional`; returned `inherited_distribution_drawn` equals the passed amount exactly (never capped); omitting the parameter reproduces this function's exact prior behavior (mechanics-api.md)
- [X] T009 [P] [US1] Unit test `compute_plan_year_mechanics()`'s new `inherited_distribution_amount`/`inherited_rmd_figures_used` parameters in `tests/unit/mechanics/test_plan_year.py`: `ordinary_income_established` includes `withdrawal_plan.inherited_distribution_drawn`; `figures_used` unions `inherited_rmd_figures_used`; omitting both parameters reproduces this function's exact prior behavior (mechanics-api.md)
- [X] T010 [P] [US1] Integration test: quickstart.md §1's scenario (one inherited traditional account, decedent already taking RMDs) end-to-end through `run_plan_projection()`, in `tests/unit/comparison/test_projection.py` — first relevant plan year's `withdrawal_plan.inherited_distribution_drawn > 0`; `starting_balances.traditional` stays `0` throughout, unaffected by the inherited account (research.md §5)
- [X] T011 [P] [US1] Unit test the "fresh copy per candidate" property in `tests/unit/comparison/test_compare.py`: calling any of `compare_roth_conversion_strategies()`/`compare_withdrawal_sequencing_strategies()`/`compare_claiming_age_grid()` with `inherited_accounts` containing one account and 2+ candidates leaves the caller's own original `InheritedAccountBalance.balance` unmutated, and no candidate's projection is affected by another candidate's distributions (comparison-api.md's per-candidate independent-copy requirement)

### Implementation for User Story 1

- [X] T012 [US1] Implement `SINGLE_LIFE_EXPECTANCY_TABLE` (`SourcedFigure`, partial/illustrative coverage, `verified=False`, matching `rmd.py`'s existing citation shape) and `compute_inherited_rmd()` in new `src/retirement_planner/mechanics/inherited_rmd.py` (mechanics-api.md, research.md §7) (depends on T003, T007)
- [X] T013 [US1] Add `inherited_distribution_amount: float = 0.0` parameter to `compute_withdrawal_plan()`, `src/retirement_planner/mechanics/withdrawal_sequencing.py` (mechanics-api.md, research.md §10) (depends on T003, T008)
- [X] T014 [US1] Add `inherited_distribution_amount`/`inherited_rmd_figures_used` parameters to `compute_plan_year_mechanics()`, `src/retirement_planner/mechanics/plan_year.py` (mechanics-api.md, research.md §10) (depends on T013, T009)
- [X] T015 [US1] Add `inherited_accounts: list[InheritedAccountBalance] = []` parameter to `run_plan_projection()`; implement step 3a's annual-distribution branch (`min(compute_inherited_rmd(...).required_amount, balance)` for every account with `balance > 0`, summed and unioned into the new step-4 arguments); wire step 7 to apply that year's `growth_factor` to every surviving inherited account's balance — **no deadline-year override yet** (US2 adds that) — in `src/retirement_planner/comparison/projection.py` (comparison-api.md, data-model.md § Consumption) (depends on T012, T014, T010)
- [X] T016 [P] [US1] Add `inherited_accounts` parameter to `compare_roth_conversion_strategies()`, `compare_withdrawal_sequencing_strategies()`, `compare_claiming_age_grid()`, each constructing a fresh, independently-copied list before its own `run_plan_projection()` call, in `src/retirement_planner/comparison/compare.py` (comparison-api.md) (depends on T015, T011)
- [X] T017 [P] [US1] Compute `inherited_accounts` from `Scenario.accounts` (data-model.md § Derived), excluding these same accounts from `_sum_accounts()`'s and `_traditional_ownership_shares()`'s pooled totals (data-model.md § Exclusion from pooling), and add `inherited_accounts` to `ResolvedRunContext`, in `services/bff/src/rp_bff/resolution.py` (bff-api.md) (depends on T004 — independent of T012–T016, can run in parallel with them) — added 3 focused unit tests to `services/bff/tests/unit/test_resolution.py`; also fixed a pre-existing round-trip assertion in `services/bff/tests/integration/test_bff_lifecycle.py` that broke because responses now include the new `account_id`/`inherited` fields
- [X] T018 [US1] Pass `inherited_accounts` through the deterministic branch of `services/bff/src/rp_bff/routes/comparisons.py` (`compare_*_deterministic` calls) (depends on T016, T017)

**Checkpoint**: User Story 1 is independently functional — quickstart.md §1 passes end-to-end at the library level, and a deterministic BFF comparison against a scenario with an inherited account includes its annual distributions.

---

## Phase 4: User Story 2 - Mandatory full depletion within 10 years (Priority: P2)

**Goal**: An inherited account's entire remaining balance is force-distributed no later than the 10th calendar year after the original owner's death, regardless of what the annual divisor-computed amount alone would leave behind.

**Independent Test**: A plan horizon extending past an inherited account's depletion deadline shows that account's balance at exactly `$0` in the deadline year and every year after — testable via `run_plan_projection()` alone (quickstart.md §2).

### Tests for User Story 2 ⚠️

> Write this test FIRST, ensure it FAILS before implementing T020

- [X] T019 [P] [US2] Integration test in `tests/unit/comparison/test_projection.py`: an inherited account whose divisor-computed annual amount is smaller than its remaining balance in `depletion_deadline_year` has its entire remaining balance distributed that year (not just the computed annual amount); every plan year after `depletion_deadline_year` contributes `inherited_distribution_drawn == 0` for that account (quickstart.md §2)

### Implementation for User Story 2

- [X] T020 [US2] Add the deadline-year override to step 3a's per-inherited-account loop — when `tax_year == depletion_deadline_year`, distribute the account's entire remaining `balance` instead of `compute_inherited_rmd()`'s amount — in `run_plan_projection()`, `src/retirement_planner/comparison/projection.py` (comparison-api.md, research.md §8) (depends on T015, T019)

**Checkpoint**: User Stories 1 and 2 both work independently — annual distributions are accurate, and full depletion by year 10 is enforced.

---

## Phase 5: User Story 3 - Clear rejection of unsupported inherited-IRA cases (Priority: P3)

**Goal**: A scenario configuring a case this feature does not compute (pre-RBD death, eligible-designated-beneficiary, non-traditional inherited account, or a Monte Carlo simulation request) is blocked with a specific, actionable message — never silently computed or silently run with the inherited account's distributions dropped.

**Independent Test**: A scenario with an unsupported `inherited` configuration fails `validate()` with a specific blocking flag naming the case (quickstart.md §3); a `POST /simulations`/simulated `POST /comparisons` request against any scenario with an inherited account returns `422 inherited_accounts_unsupported_for_simulation` (quickstart.md §5) — both checkable independently of US1/US2's computation being correct.

### Tests for User Story 3 ⚠️

> Write these tests FIRST, ensure they FAIL before implementing T023–T025

- [X] T021 [P] [US3] Unit test the four new blocking `ValidationFlag` rules in `tests/unit/scenario/test_validation.py`: `decedent_was_taking_rmds=False` → blocking flag at `accounts[i].inherited`; `beneficiary_classification` other than `non_eligible_designated_beneficiary` → blocking flag; `account_type` other than `traditional` on an inherited account → blocking flag; an inherited account with `owner=None` still produces the existing missing-owner flag (data-model.md § Validation rules, quickstart.md §3)
- [X] T022 [P] [US3] BFF test in `services/bff/tests/`: `POST /simulations` and the simulated branch of `POST /comparisons` return `422 inherited_accounts_unsupported_for_simulation` (with `account_ids`) for a scenario with any inherited account; the deterministic `POST /comparisons` branch and `POST /scenarios/{name}/validate` are unaffected (bff-api.md, quickstart.md §5)

### Implementation for User Story 3

- [X] T022a [P] [US3] **Discovered during implementation** (missing from the original task breakdown, despite being specified in `contracts/bff-api.md` and `plan.md`'s Project Structure — an omission found while writing T022's test, which needs a way to PUT an inherited account through the API at all): add `InheritedIraDetailsRequest` and `AccountRequest.account_id: str | None = None` / `.inherited: InheritedIraDetailsRequest | None = None` to `services/bff/src/rp_bff/schemas.py` (bff-api.md) (depends on T004) — without this, Pydantic's default `extra="ignore"` behavior silently drops `account_id`/`inherited` from every `PUT /scenarios/{name}` request body, making this feature's data entirely unreachable through the BFF API
- [X] T023 [US3] Implement the four new blocking `ValidationFlag` rules in `_validate_accounts()`, `src/retirement_planner/scenario/validation.py` (scenario-api.md, data-model.md § Validation rules) (depends on T004, T021)
- [X] T024 [US3] Add `InheritedAccountsUnsupportedForSimulationError` to `services/bff/src/rp_bff/resolution.py`; check `context.inherited_accounts` and raise it from `resolve_and_run_simulation()`, translated to the `422` response, in `services/bff/src/rp_bff/routes/simulations.py` (bff-api.md) (depends on T017, T022, T022a)
- [X] T025 [US3] Add the identical check and `422` translation to the simulated-comparison resolve path in `services/bff/src/rp_bff/routes/comparisons.py` (bff-api.md) (depends on T017, T022, T022a)

**Checkpoint**: All three user stories are independently functional. Every unsupported case is rejected explicitly, at both the scenario-validation and the simulation-request layer.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Regression safety and final end-to-end validation across all three stories

- [X] T026 [P] Regression-parity test: every existing reference scenario and test fixture (no inherited accounts, `inherited_accounts` defaulting to `[]` everywhere) produces byte-for-byte identical output before and after this feature — extend `tests/unit/comparison/test_projection.py` and/or `tests/integration/` (plan.md's Constraints; mirrors `011`'s FR-009/SC-004 discipline). Confirm no existing call site (`examples/reference_scenario.py`, every existing test) needed updating, since `inherited_accounts` is a defaulted, not required, parameter (unlike `011`'s `traditional_ownership_shares`)
- [X] T027 Run quickstart.md's five scenarios end-to-end manually as a final smoke validation (all prerequisites from Phases 2–5 complete)
- [X] T028 Run the full test suite across both packages (`pytest tests/`, `pytest services/bff/tests/`) and confirm no regressions outside this feature's intended changes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational. Independent of US3 in file surface; sequenced first to match spec priority and because US2 builds directly on it.
- **User Story 2 (Phase 4)**: Depends on Foundational **and** on US1's T015 (same function, additive branch) — not independent of US1 the way most story pairs are (see Story dependency shape note above).
- **User Story 3 (Phase 5)**: Depends on Foundational (T004) for its `scenario/validation.py` work (T021, T023); its BFF work (T022, T024, T025) additionally depends on US1's `resolution.py` task (T017). Otherwise independent of US1/US2's computation logic — could be built in parallel by a second person once T004 and T017 exist.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests MUST be written and FAIL before their corresponding implementation task.
- `mechanics` layer changes (new module, new parameters) before the `comparison/projection.py` change that consumes them.
- `comparison` layer changes before the `services/bff` resolution/route changes that depend on them.
- Story complete before moving to the next priority.

### Parallel Opportunities

- T002 and T003 (Foundational: `scenario` vs `mechanics` packages, different files).
- T005 and T006 (`loader.py` vs `store.py`, both depend only on T004).
- T007, T008, T009, T010, T011 (US1 tests, five different files).
- T016 and T017 (`compare.py` vs `resolution.py` — both depend only on T015/T004 respectively, independent of each other).
- T021 and T022 (US3 tests, different files/packages).
- T024 and T025 (`routes/simulations.py` vs `routes/comparisons.py`, both depend only on T017/T022).
- Once Foundational (Phase 2) completes, User Story 3's `scenario/validation.py` work (T021, T023) can proceed in parallel with all of User Story 1 (disjoint files) if staffed by two people.

---

## Parallel Example: Foundational + User Story 1

```bash
# Launch both Foundational tests/implementation-without-tests together:
Task: "Unit test Account.account_id/.inherited parsing in tests/unit/scenario/test_loader.py"
Task: "Add InheritedRmdResult, InheritedAccountBalance to src/retirement_planner/mechanics/models.py"

# After Foundational, launch all five User Story 1 tests together:
Task: "Unit test compute_inherited_rmd() divisor arithmetic in tests/unit/mechanics/test_inherited_rmd.py"
Task: "Unit test compute_withdrawal_plan()'s inherited_distribution_amount in tests/unit/mechanics/test_withdrawal_sequencing.py"
Task: "Unit test compute_plan_year_mechanics()'s new parameters in tests/unit/mechanics/test_plan_year.py"
Task: "Integration test quickstart.md §1 in tests/unit/comparison/test_projection.py"
Task: "Unit test fresh-copy-per-candidate in tests/unit/comparison/test_compare.py"

# After T015, launch compare.py and resolution.py together:
Task: "Add inherited_accounts to src/retirement_planner/comparison/compare.py"
Task: "Compute inherited_accounts in services/bff/src/rp_bff/resolution.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: Run quickstart.md §1 and confirm the inherited account's annual distribution is computed and included.
5. This alone delivers real value — an inherited account's tax and cash-flow impact is now visible at all, even before the 10-year deadline is enforced or unsupported cases are rejected.

### Incremental Delivery

1. Setup + Foundational → the new schema fields and data shapes exist and round-trip.
2. Add User Story 1 → annual distributions are computed and reachable via a deterministic BFF comparison → validate independently.
3. Add User Story 2 → full depletion by year 10 is enforced → validate independently.
4. Add User Story 3 → every unsupported case (scenario-level and simulation-request-level) is rejected explicitly → validate independently.
5. Polish → regression-parity confirmation, full-suite validation.

---

## Notes

- [P] tasks = different files, no unmet dependencies.
- [Story] label maps task to specific user story for traceability.
- Verify each story's tests fail before implementing that story.
- Stop at any checkpoint to validate a story independently before continuing.
- `inherited_accounts` is a defaulted parameter (`= []`) everywhere it's added, unlike `011`'s required `traditional_ownership_shares` — no existing call site outside this feature's own new code needs updating, which is why this task list has no `011`-style "T016 mechanical call-site churn" task.
- `apps/streamlit_ui` is untouched by this feature (plan.md's Structure Decision) — `account_id`/`inherited` are entered directly in scenario YAML or via `PUT /scenarios/{name}`'s request body for this feature's scope.
