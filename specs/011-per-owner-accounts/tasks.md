---

description: "Task list for Per-Owner Account Attribution"
---

# Tasks: Per-Owner Account Attribution

**Input**: Design documents from `/specs/011-per-owner-accounts/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/) (`scenario-api.md`, `comparison-api.md`, `simulation-api.md`, `bff-api.md`, `ui-pages.md`), [quickstart.md](./quickstart.md)

**Tests**: Included — plan.md's Development Workflow gate requires unit tests for the per-member RMD summation against hand-calculated reference values (the constitution's "Unit test coverage for numeric primitives" gate), matching every prior engine feature's (`002`/`003`/`004`/`010`) practice.

**Organization**: Tasks are grouped by user story (spec.md priorities P1–P3) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to (US1–US3)
- File paths are exact and relative to the repository root

## Path Conventions

This feature extends the existing three-package monorepo (`src/retirement_planner`, `services/bff`, `apps/streamlit_ui`) — no new package, no new dependency. See [plan.md](./plan.md) Project Structure for the full file list.

**Story dependency shape, different from a typical independent-stories feature**: US1 (engine RMD accuracy) and US2 (UI/API data entry) both build directly on the Foundational scenario-schema phase, but touch almost entirely disjoint files from each other (US1: `comparison/`, `simulation/`, `resolution.py`, `routes/`, `examples/`; US2: `schemas.py`, `pages/1_Scenarios.py`, `instructions_content.py`) — they could be built in parallel by two people. They are sequenced **US1 → US2 → US3** here to match spec.md's P1 > P2 > P3 priority order and because it is more useful to have the engine provably correct (US1, testable purely at the library level, no UI needed — quickstart.md §1) before exposing the data-entry surface for it (US2). US3 (existing-scenario handling) is almost entirely *delivered* by the Foundational phase itself (the auto-fill and blocking-flag rules US3's acceptance scenarios describe); its own phase adds only the coverage that specifically needs US1's and US2's work already in place (a full-stack regression-parity check, and a UI-load-then-flag check) — so it is correctly sequenced last despite being small.

---

## Phase 1: Setup

**Purpose**: Confirm the existing packages need no new dependency before extending them

- [X] T001 Confirm no new dependency is needed for this feature (plan.md's Technical Context — no new third-party dependency anywhere) — run `pytest tests/ services/bff/tests/ apps/streamlit_ui/tests/` to confirm the existing suites pass as a pre-change baseline

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: `Account.owner` must exist, parse correctly (including the single-member auto-fill), and be validated before any of US1/US2/US3 can be implemented or tested against real data

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Unit test `Account.owner` parsing in `tests/unit/scenario/test_loader.py`: a single-member household auto-fills every account's `owner` from the sole member's `person_name` when the YAML omits it (research.md §3); a 2-member household with `owner` omitted parses with `owner=None` (no `ScenarioParseError`); an explicitly-provided `owner` (any household size) is passed through unchanged — write FIRST, ensure it FAILS before T004–T005
- [X] T003 [P] Unit test `validate()`'s new owner rules in `tests/unit/scenario/test_validation.py`: `owner=None` on an account in a 2-member household → one blocking `ValidationFlag` at `accounts[i].owner`; an `owner` not matching any `household.members[*].person_name` → one blocking `ValidationFlag` at `accounts[i].owner`, for any household size; a single-member household's accounts never produce either flag — write FIRST, ensure it FAILS before T006
- [X] T004 Add `owner: str | None = None` to `Account` in `src/retirement_planner/scenario/models.py` (data-model.md § Account) (depends on T002, T003)
- [X] T005 [P] Reorder `parse_scenario()` to build `household` before `accounts`; make `_build_account()` read `owner` permissively (`data.get("owner")`, never `_require()`) and auto-fill it from the sole member's `person_name` when `len(household.members) == 1` and the YAML omitted it, in `src/retirement_planner/scenario/loader.py` (scenario-api.md) (depends on T002, T004)
- [X] T006 [P] Implement the two new blocking `ValidationFlag` rules for `accounts[i].owner` (missing; not matching any current member) in `_validate_accounts()` in `src/retirement_planner/scenario/validation.py` (scenario-api.md) (depends on T003, T004)
- [X] T006a Fix `_scenario_to_dict()` in `src/retirement_planner/scenario/store.py` to include `owner` (discovered during implementation: it builds its YAML dict field-by-field, not generically, and initially dropped `owner` on every save — the same class of round-trip gap `010`'s `hdhp_coverage`/`hsa_contribution` hit; would have made this feature non-functional in practice). Added regression tests to `tests/unit/scenario/test_store.py` and updated `tests/integration/test_scenario_lifecycle.py`'s `BASE_CASE_YAML` fixture (a married-filing-jointly scenario with no `owner:` — now failing `is_usable` post-Foundational, as it should for real user data, but a checked-in test fixture needed the field added) (depends on T004, T006)

**Checkpoint**: Foundation ready — `Scenario.accounts[*].owner` round-trips and validates correctly. US1, US2, and US3 implementation can now begin.

---

## Phase 3: User Story 1 - Accurate RMDs for a married couple with unequal ages and balances (Priority: P1) 🎯 MVP

**Goal**: Each household member's RMD is computed from their own age and their own share of the traditional balance, replacing the household-wide "deemed owner" attribution.

**Independent Test**: A two-member household where each member owns a separate traditional account of a different size, with ages far enough apart that only one has reached the RMD-required starting age, shows an RMD sized to that member's own balance only — testable purely at the library level via `run_plan_projection()` (quickstart.md §1), no UI or BFF required.

### Tests for User Story 1 ⚠️

> Write these tests FIRST, ensure they FAIL before implementing T009

- [X] T007 [P] [US1] Unit test per-member RMD summation in `tests/unit/comparison/test_projection.py`: two members with differing ages/shares where only one has reached the RMD-required starting age → `rmd_amount` reflects only that member's own share-derived balance; both past the starting age → `rmd_amount` is the sum of two independently-computed `required_amount`s; a member with `traditional_ownership_shares[name] == 0.0` contributes no RMD regardless of age; missing a household member's name from `traditional_ownership_shares` raises `KeyError` before any plan year is processed — against hand-calculated reference values (plan.md's Development Workflow gate)
- [X] T008 [P] [US1] Integration test: the quickstart.md §1 scenario (unequal ages/shares, first-year RMD reflects only the older member's own $900k share, not the full $1.2M) end-to-end through `run_plan_projection()`, in `tests/integration/test_comparison_lifecycle.py`

### Implementation for User Story 1

- [X] T009 [US1] Replace the single `deemed_rmd_owner()`-attributed `compute_rmd()` call with the per-member loop (data-model.md § Consumption) in `run_plan_projection()`, `src/retirement_planner/comparison/projection.py` — add the `traditional_ownership_shares: dict[str, float]` parameter (comparison-api.md); `deemed_rmd_owner()`/`member_age_in_tax_year()` themselves are unchanged (research.md §4, still used by `006`'s reporting label) (depends on T007, T008)
- [X] T010 [P] [US1] Add `traditional_ownership_shares` parameter to `compare_roth_conversion_strategies()`, `compare_withdrawal_sequencing_strategies()`, `compare_claiming_age_grid()`, forwarded unchanged to their `run_plan_projection()` calls, in `src/retirement_planner/comparison/compare.py` (comparison-api.md) (depends on T009)
- [X] T011 [P] [US1] Add `traditional_ownership_shares` parameter to `run_simulation()`, threaded through `_init_worker`/`_worker_shared_args`/`_run_one_path()`/`_run_one_path_shared()`, in `src/retirement_planner/simulation/monte_carlo.py` (simulation-api.md) (depends on T009)
- [X] T012 [P] [US1] Add `traditional_ownership_shares` parameter to `compare_states()`, `compare_roth_conversion_strategies()`, `compare_withdrawal_sequencing_strategies()`, `compare_claiming_age_grid()`, forwarded unchanged, in `src/retirement_planner/simulation/compare.py` (simulation-api.md) (depends on T009)
- [X] T013 [P] [US1] Compute `traditional_ownership_shares` from `Scenario.accounts` (data-model.md § Derived) alongside the existing pooled-`AccountBalances` summation, and add it to `ResolvedRunContext`, in `resolve_run_context()`, `services/bff/src/rp_bff/resolution.py` (bff-api.md) (depends on T004 — independent of T009–T012, can run in parallel with them)
- [X] T014 [US1] Update every `ResolvedRunContext`-consuming call in `services/bff/src/rp_bff/routes/simulations.py` and `services/bff/src/rp_bff/routes/comparisons.py` to pass `traditional_ownership_shares` into `run_plan_projection()`/`run_simulation()`/`compare_*()` (depends on T010, T011, T012, T013)
- [X] T015 [US1] Update the direct `run_simulation()` call in `examples/reference_scenario.py` to pass an explicit `traditional_ownership_shares` argument (simulation-api.md's consumption note) (depends on T011)
- [X] T016 [US1] Update every remaining existing direct call site of `run_plan_projection()`/`run_simulation()`/`compare_*()` across `tests/unit/comparison/`, `tests/unit/simulation/`, `tests/integration/`, and `services/bff/tests/` to pass `traditional_ownership_shares` (mechanical call-site churn from the new required parameter, simulation-api.md's consumption note) (depends on T009, T010, T011, T012)

**Checkpoint**: User Story 1 is independently functional — quickstart.md §1 passes end-to-end; the full existing test suite passes again with the new parameter threaded everywhere it's needed.

---

## Phase 4: User Story 2 - Assign an owner to each account while entering scenario data (Priority: P2)

**Goal**: A user picks each account's owner from the household's actual members while entering scenario data, through both the API and the UI.

**Independent Test**: Creating a two-member household and adding an account offers exactly that household's member names as owner choices (not free text, not silently defaulted).

### Tests for User Story 2 ⚠️

> Write these tests FIRST, ensure they FAIL before implementing T020

- [X] T017 [P] [US2] BFF request/response round-trip test for `AccountRequest.owner` in `services/bff/tests/integration/test_bff_lifecycle.py`: `owner` provided → round-trips through `PUT`/`GET /scenarios/{name}`; `owner` omitted on a single-member household → response shows the auto-filled owner; `owner` omitted on a 2-member household → response's `validation_flags` includes the new blocking flag, `is_usable=False`
- [X] T018 [P] [US2] `streamlit.testing.v1.AppTest` test for the accounts section's per-member fields in `apps/streamlit_ui/tests/integration/test_app_pages.py`: a married-filing-jointly household renders `member2_traditional_balance`/`member2_roth_balance`/`member2_taxable_balance` fields (not just `member1_*`), each account submitted carries the correct structural owner, and a single-member household never renders `member2_*` account fields at all (ui-pages.md — corrected during implementation: `008`'s shipped form uses fixed per-member fields, not a free-form account list, so owner is structural, not a selectbox)

### Implementation for User Story 2

- [X] T019 [P] [US2] Add `owner: str | None = None` to `AccountRequest` in `services/bff/src/rp_bff/schemas.py` (bff-api.md) (depends on T017)
- [X] T020 [US2] Replace the accounts section's single `traditional_balance`/`roth_balance`/`taxable_balance` fields with per-member `member1_*`/`member2_*` fields (the latter only when `filing_status` is married) in `apps/streamlit_ui/pages/1_Scenarios.py` — update `DEFAULTS`, `_apply_scenario_to_form()` (match by `(account_type, owner)`, skip unmatched rather than guess), and `_build_body()` (submit each row with its structural owner) (ui-pages.md) (depends on T018, T019)
- [X] T021 [US2] Update the "Accounts" section body in `apps/streamlit_ui/src/rp_ui/instructions_content.py` — replace the "combine both partners' balances into one household total" guidance (now actively wrong) with guidance to enter each account with its own owner (depends on T020)
- [X] T022 [US2] Update the assertion in `apps/streamlit_ui/tests/unit/test_instructions_content.py` (currently asserts `"combined household total" in body`) to match T021's new Accounts section text (depends on T021). Also updated the same assertion in `apps/streamlit_ui/tests/integration/test_app_pages.py`'s quickstart-walkthrough test (a third reference to the old text, found only by running the suite).

**Checkpoint**: User Stories 1 and 2 both work independently — a user can enter per-owner account data through the UI and see it drive accurate RMDs.

---

## Phase 5: User Story 3 - Existing saved scenarios are handled explicitly, not silently guessed (Priority: P3)

**Goal**: A pre-existing scenario file surfaces a specific, actionable problem instead of a silent guess; a single-filer scenario is completely unaffected.

**Independent Test**: Loading a scenario file saved before this feature (accounts with no `owner`) surfaces a specific validation problem rather than proceeding with a guessed or empty attribution — already largely proven by the Foundational phase's own tests (T002, T003); this phase adds the remaining coverage that specifically needs US1's and US2's work in place.

### Tests for User Story 3 ⚠️

- [X] T023 [P] [US3] Unit test: an account whose `owner` references a household member who was since renamed or removed surfaces the referential-mismatch blocking flag (Edge Cases), extending `tests/unit/scenario/test_validation.py`
- [X] T024 [US3] Integration test — single-member regression parity (FR-009/SC-004): a single-filer scenario's `traditional_ownership_shares` is always `{sole_member: 1.0}`, and its RMD/withdrawal/ending-balance output via `run_plan_projection()` is identical to calling `compute_rmd()` directly against that member's full, unscaled balance and age, in `tests/integration/test_scenario_lifecycle.py` (depends on T009)
- [X] T025 [US3] `AppTest`: loading a scenario with a stale/missing-owner account leaves that balance absent (defaulted to $0) from every member row rather than guessed into one, in `apps/streamlit_ui/tests/integration/test_app_pages.py` (ui-pages.md's corrected "Modified *Load existing* behavior" — an unmatched balance is a visible "$0 where you expect a real number" cue, not a validation flag, since this form always supplies a valid owner on resubmit) (depends on T020)

**Checkpoint**: All three user stories are independently functional. No scenario is ever silently misattributed; single-filer behavior is provably unchanged.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation consistency and final end-to-end validation across all three stories

- [X] T026 [P] Update the "Accounts" bullet in `docs/instructions_page_requirements.md` to match T021's new per-owner guidance (documentation-source consistency — this file is `009`'s requirements source, not itself tested)
- [X] T027 Run quickstart.md's three code examples end-to-end manually as a final smoke validation (all prerequisites from Phases 2–5 complete)
- [X] T028 Run the full test suite across all three packages (`pytest tests/`, `pytest services/bff/tests/`, `pytest apps/streamlit_ui/tests/`) and confirm no regressions outside this feature's intended changes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational. Independent of US2/US3 in file surface (see Story dependency shape note above) — could proceed in parallel with US2 if staffed, sequenced first here to match spec priority.
- **User Story 2 (Phase 4)**: Depends on Foundational. Independent of US1 in file surface; sequenced second to match spec priority.
- **User Story 3 (Phase 5)**: Depends on Foundational (most of its behavior), plus T009 (US1, for T024's regression-parity check) and T020 (US2, for T025's UI-load-flag check) — correctly sequenced last.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests MUST be written and FAIL before their corresponding implementation task.
- `scenario` layer (models → loader/validation) before anything consuming it.
- `comparison`/`simulation` engine changes before the `services/bff` resolution/route changes that depend on them.
- Story complete before moving to the next priority (or in parallel, per the dependency shape note).

### Parallel Opportunities

- T002 and T003 (Foundational tests, different files).
- T005 and T006 (loader.py vs validation.py, both depend only on T004).
- T007 and T008 (US1 tests, different files).
- T010, T011, T012 (comparison/compare.py, simulation/monte_carlo.py, simulation/compare.py — all depend only on T009, independent of each other).
- T013 (resolution.py) — depends only on Foundational (T004), independent of T009–T012; can run any time after Phase 2.
- T017 and T018 (US2 tests, different files).
- T019 (schemas.py) — depends only on T017, independent of T018/T020.
- T023 (US3 validation edge case) — depends only on Foundational; can run any time after Phase 2.
- Once Foundational (Phase 2) completes, User Story 1 and User Story 2 implementation can proceed in parallel (disjoint files, per the Story dependency shape note) if staffed by two people.

---

## Parallel Example: Foundational + User Story 1

```bash
# Launch both Foundational tests together:
Task: "Unit test Account.owner parsing in tests/unit/scenario/test_loader.py"
Task: "Unit test validate()'s new owner rules in tests/unit/scenario/test_validation.py"

# After T004, launch loader.py and validation.py implementation together:
Task: "Implement owner parsing/auto-fill in src/retirement_planner/scenario/loader.py"
Task: "Implement owner blocking-flag rules in src/retirement_planner/scenario/validation.py"

# After T009, launch all three downstream signature updates together:
Task: "Add traditional_ownership_shares to src/retirement_planner/comparison/compare.py"
Task: "Add traditional_ownership_shares to src/retirement_planner/simulation/monte_carlo.py"
Task: "Add traditional_ownership_shares to src/retirement_planner/simulation/compare.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: Run quickstart.md §1 and confirm accurate per-member RMDs.
5. This alone fixes the accuracy gap the feature exists for, even before the UI can capture new ownership data (existing scenarios still get single-filer auto-fill or the MFJ blocking flag from Foundational).

### Incremental Delivery

1. Setup + Foundational → owner data round-trips and validates.
2. Add User Story 1 → engine computes accurate per-member RMDs → validate independently (library-level, no UI needed).
3. Add User Story 2 → users can actually enter ownership data through the UI → validate independently.
4. Add User Story 3 → pre-existing scenarios are provably never silently misattributed, single-filer parity proven → validate independently.
5. Polish → documentation consistency, full-suite regression confirmation.

---

## Notes

- [P] tasks = different files, no unmet dependencies.
- [Story] label maps task to specific user story for traceability.
- Verify each story's tests fail before implementing that story.
- Stop at any checkpoint to validate a story independently before continuing.
- T016 and T021/T022 were discovered by tracing actual call sites and UI copy during task generation (not present in plan.md's file list at that granularity) — `examples/reference_scenario.py`, every existing direct test call site, and the Instructions page's now-incorrect "combine both partners' balances" guidance all needed updating for this feature to be complete and non-misleading.
