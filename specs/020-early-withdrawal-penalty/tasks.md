---

description: "Task list for 020-early-withdrawal-penalty"
---

# Tasks: Early-Withdrawal Penalty (Pre-59.5)

**Input**: Design documents from `/specs/020-early-withdrawal-penalty/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. The constitution's "Unit test coverage for numeric primitives" gate
(Development Workflow & Quality Gates) and this project's existing precedent (016-019) require new
engine behavior to have unit tests against hand-calculated/reference values before it's used in any
comparative run.

**Organization**: Tasks are grouped by user story (spec.md), but this feature is **not**
purely-additive like `017`/`018`/`019` — it is an accuracy correction expected to change real
computed output (ending balances, shortfall) for existing households with a member under 60 taking
a voluntary Traditional withdrawal, mirroring `016`'s own precedent instead. A dedicated task
(T016) runs the full four-suite quality gate immediately after User Story 1's core wiring lands and
triages every resulting failure individually — this is not deferred to Polish, since it is the
central risk this feature's own regression surface creates. User Story 2 (the Roth-ladder
combination) reuses the same combined-base computation User Story 1 already builds (research.md
Decision 3) — its own phase is almost entirely dedicated test coverage of behavior already wired in
by User Story 1, mirroring `019`'s own US1/US2 relationship.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

Single project — `src/retirement_planner/`, `tests/` at repo root, plus `apps/streamlit_ui/` for
the narration-layer polish (mirroring `010`'s own IRMAA/NIIT reporting/UI ripple — the closest prior
precedent for a new "lifetime X paid" figure). No `services/bff/` changes (confirmed during `019`'s
own investigation of the identical question) and no new scenario-configurable input.

---

## Phase 1: Setup

**Purpose**: Confirm a clean baseline before changing shared code.

- [X] T001 Run `pytest tests/` and confirm the existing suite is green before any change in this feature (baseline for regression comparison later)

**Checkpoint**: Baseline confirmed green.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The new cited figure and pure computation function both user stories consume.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Add `EarlyWithdrawalPenaltyResult` (`taxable_early_distribution_base: float`, `penalty_owed: float`, `figures_used: list[FigureUsage] = field(default_factory=list)`) dataclass to `src/retirement_planner/tax/models.py`, per data-model.md and contracts/tax-api.md
- [X] T003 Create `src/retirement_planner/tax/early_withdrawal_penalty.py`: module docstring (per plan.md's "new sibling module in `tax/`, mirroring `niit.py`" rationale, research.md Decision 1) plus `EARLY_WITHDRAWAL_PENALTY_RATE: SourcedFigure[float]` (`schedule={year: 0.10 for year in _DOCUMENTED_YEARS}`; citation "26 U.S.C. §72(t)(1) (10% additional tax); §72(t)(2)(A)(i) (age 59½ exception)"; cross-check the statute text directly before setting `verified=True`, per the constitution's verified-figure gate) (depends on T002)
- [X] T004 In the same file, implement `compute_early_withdrawal_penalty(taxable_early_distribution_base, tax_year) -> EarlyWithdrawalPenaltyResult`: `penalty_owed = taxable_early_distribution_base * EARLY_WITHDRAWAL_PENALTY_RATE.value_for_year(tax_year)`; `figures_used` always includes the rate figure's usage, even when the base is `0.0` (research.md Decision 5); raises `UnsupportedTaxYearError` per contracts/tax-api.md (depends on T003)
- [X] T005 [P] Re-export `compute_early_withdrawal_penalty`, `EarlyWithdrawalPenaltyResult`, and `EARLY_WITHDRAWAL_PENALTY_RATE` from `src/retirement_planner/tax/__init__.py` (depends on T002, T004)

**Checkpoint**: The pure penalty function exists, cited, and exported. User story implementation can now begin.

---

## Phase 3: User Story 1 - A projection shows the real cost of an early-retirement Traditional withdrawal (Priority: P1) 🎯 MVP

**Goal**: A voluntary (non-RMD) Traditional withdrawal for a household member under 59.5 is
penalized at 10% of that member's own share, and the penalty genuinely reduces projected account
balances.

**Independent Test**: Configure a household with a member under 59.5 taking a voluntary Traditional
withdrawal, run a projection, and confirm the penalty and its effect on ending balance
(quickstart.md §1).

### Implementation for User Story 1

- [X] T006 [US1] Add `early_withdrawal_penalty: EarlyWithdrawalPenaltyResult` (required, no default — mirrors `irmaa`/`niit`'s own non-defaulted precedent, per data-model.md) to `PlanYearProjection` in `src/retirement_planner/comparison/models.py` (depends on T002)
- [X] T007 [US1] Add `cumulative_early_withdrawal_penalty_paid: float` to `PlanOutcome` in the same file
- [X] T008 [US1] In `run_plan_projection()` (`src/retirement_planner/comparison/projection.py`), immediately after the existing `niit = compute_niit(...)` call: compute `traditional_sequence_draw` (the `"traditional"`-type entry's `amount` in `mechanics_result.withdrawal_plan.sequence_withdrawals`, `0.0` if none — never `rmd_drawn`, research.md Decision 4); `under_59_traditional_share = sum(traditional_ownership_shares[member.person_name] * traditional_sequence_draw for member in household.members if ages_this_year[member.person_name] <= 59)`; `taxable_early_distribution_base = under_59_traditional_share + ladder_result.unseasoned_amount_flagged` (`019`'s own already-computed result, no re-derivation, research.md Decision 3); call `compute_early_withdrawal_penalty(taxable_early_distribution_base, tax_year)` (depends on T004, T006)
- [X] T009 [US1] Immediately after T008: change `tax_owed = federal_tax.federal_tax_owed + state_tax.state_tax_owed` to also add `early_withdrawal_penalty.penalty_owed`, so the new cost is actually funded (research.md Decision 6 — deliberately does NOT replicate the separately-tracked IRMAA/NIIT funding gap, `rp-yqf`) (depends on T008)
- [X] T010 [US1] Fold `early_withdrawal_penalty.figures_used` into this year's overall `figures_used` list as an additional unioned source (depends on T008)
- [X] T011 [US1] Populate the constructed `PlanYearProjection(...)`'s new `early_withdrawal_penalty=early_withdrawal_penalty` field for every plan year (depends on T006, T008)
- [X] T012 [US1] Update `_derive_outcome()` to compute `cumulative_early_withdrawal_penalty_paid = sum(year.early_withdrawal_penalty.penalty_owed for year in years)` and include it in the returned `PlanOutcome` — `cumulative_tax_paid`'s own existing derivation is unchanged (depends on T007, T011)
- [X] T013 [US1] Update `run_plan_projection()`'s docstring to describe the new per-year penalty computation and funding, per contracts/comparison-api.md (depends on T008-T012)

### Regression triage for User Story 1

- [X] T014 [US1] Run the full four-suite quality gate (`pytest tests/`, `pytest services/bff/tests/`, `pytest apps/streamlit_ui/tests/`, `cd e2e && ../.venv/bin/python3.12 -m pytest -q`) immediately after T006-T013 land — **before** writing this feature's own new tests below. Triage every failure individually: for a household with a member under 60 drawing Traditional funds, the corrected expected value is the fixture's own pre-existing amount plus 10% of the newly-penalized portion (compute by hand or via a scratch script per fixture) — update the expected value with an inline comment explaining the correction (mirrors `016`'s own precedent for the Social Security claiming-age adjustment, research.md Decision 7). Do not weaken or delete an assertion to make it pass — every correction must be a verified, explained number.

### Tests for User Story 1

- [X] T015 [P] [US1] Unit tests for `compute_early_withdrawal_penalty()` in `tests/unit/tax/test_early_withdrawal_penalty.py`: `penalty_owed == base * 0.10` for a positive base (Acceptance Scenario US1.1); `penalty_owed == 0.0` for a `0.0` base, with `figures_used` still populated (research.md Decision 5); `figures_used[0].citation` contains `"72(t)(1)"`, `verified is True`, `last_verified` is set; `UnsupportedTaxYearError` for an undocumented tax year (depends on T004)
- [X] T016 [P] [US1] Integration tests in `tests/unit/comparison/test_projection.py`: a single-member household under 59.5 taking a $20,000 voluntary Traditional withdrawal shows a $2,000 penalty that plan year (Acceptance Scenario 1, quickstart.md §1); an RMD-satisfied withdrawal (member past RMD start age) contributes $0 to the base (Acceptance Scenario 2); an MFJ household with members at different ages and different `traditional_ownership_shares` — only the under-59.5 member's own share is penalized (Acceptance Scenario 3); a member at translated age 60+ contributes $0 regardless of their own withdrawal amount (Acceptance Scenario 4); an inherited-account distribution never contributes to the base regardless of the beneficiary's own age (Acceptance Scenario 5); the penalized household's `ending_balances` total is strictly lower than an otherwise-identical household whose only difference is every member already being 60+ (SC-001) (depends on T011)
- [X] T017 [P] [US1] Regression test in `tests/unit/comparison/test_projection.py`: a household whose every member stays 60+ for the entire horizon and never touches an unseasoned Roth conversion shows `early_withdrawal_penalty.penalty_owed == 0.0` for every plan year (FR-010, SC-002) (depends on T011)
- [X] T018 [P] [US1] Monte Carlo regression test in `tests/unit/simulation/test_monte_carlo.py`: for a household with a member under 59.5 taking a voluntary Traditional withdrawal, `run_simulation()`'s per-path `early_withdrawal_penalty.penalty_owed` values match a direct `run_plan_projection()` call for the same path's return sequence, mirroring `016`'s/`017`'s/`018`'s/`019`'s own shared-call-site consistency-check precedent (depends on T011)

**Checkpoint**: User Story 1 fully functional and independently testable — SC-001, SC-002, SC-004 satisfied; every existing test suite green again (post-T014 triage).

---

## Phase 4: User Story 2 - An unseasoned Roth conversion withdrawal is penalized the same way (Priority: P2)

**Goal**: Confirm a plan year's unseasoned Roth conversion withdrawal (`019`'s own flag) combines
with any Traditional-side amount into one single reported penalty — behavior User Story 1's own
T008 already wires in; this phase is dedicated test coverage of it.

**Independent Test**: Configure a household with a Roth conversion ladder whose withdrawal reaches
into an unseasoned lot while under 59.5, run a projection, and confirm the combined penalty
(quickstart.md §2).

### Tests for User Story 2

- [X] T019 [P] [US2] Integration tests in `tests/unit/comparison/test_projection.py`: a plan year where `019`'s own `unseasoned_roth_withdrawal` is the only early-distribution exposure that year shows a penalty of exactly 10% of that amount (Acceptance Scenario US2.1, quickstart.md §2); a plan year with both a qualifying Traditional withdrawal and an unseasoned Roth withdrawal shows a single combined penalty equal to 10% of their sum, not two separately-reported amounts (Acceptance Scenario US2.2); a household with no Roth conversion configured at all shows the Roth-side contribution is always `0.0` for every plan year (Acceptance Scenario US2.3) (depends on T008-T011, and 019's own `compute_roth_ladder_consumption()`)

**Checkpoint**: User Story 2 confirmed — SC-003 satisfied.

---

## Phase 5: User Story 3 - The penalty rule is documented and auditable, and its remaining gaps are disclosed (Priority: P3)

**Goal**: The 10% rate figure carries a citation/verification trail like every other regulated
figure in this codebase; `docs/BRD.md` describes the new modeled behavior and its disclosed gaps.

**Independent Test**: Inspect `EARLY_WITHDRAWAL_PENALTY_RATE`'s `FigureUsage` output and confirm it
carries its statutory citation and a `last_verified` date; read `docs/BRD.md`'s relevant section and
confirm it describes the new behavior and remaining gaps (quickstart.md §4).

### Implementation for User Story 3

- [X] T020 [US3] Update `docs/BRD.md` per research.md Decision 8: add a new `§6.6a Early-withdrawal penalty (pre-59.5)` subsection describing the 10% penalty (Traditional-side per-member attribution, Roth-side via `019`'s own flag, structural RMD/inherited-account exclusions) as modeled behavior, citing `26 U.S.C. §72(t)(1)`/`§72(t)(2)(A)(i)`; add a bullet to `§7 Known Limitations & Open Items` disclosing the remaining gaps — no 72(t)/SEPP alternative, no other real statutory exception beyond age 59.5, and the separately-tracked IRMAA/NIIT funding gap (`rp-yqf`, not this feature's own scope) (depends on T011, T019)
- [X] T021 [US3] Run `specs/020-early-withdrawal-penalty/quickstart.md`'s four snippets against the implemented code (interactively or as a scratch script) and confirm each prints/asserts the expected values — correct any snippet whose numbers drifted from the plan.md-time draft, same as every prior feature's own quickstart-verification step (depends on T011, T019, T020)

**Checkpoint**: All three user stories independently functional — SC-005 satisfied.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: The `010`-established reporting/UI ripple for a new "lifetime X paid" figure (the
closest prior precedent — `018`/`019` never added one) plus the final full quality-gate
confirmation.

- [X] T022 [P] Add `median_lifetime_early_withdrawal_penalty_paid: float` to `SummaryStatistics` in `src/retirement_planner/reporting/models.py`, placed immediately after `median_lifetime_niit_paid`, per contracts/reporting-api.md (depends on T007)
- [X] T023 Update `summarize_run()` and `_summarize_plan_projection()` in `src/retirement_planner/reporting/aggregation.py`: both gain the matching derivation from `PlanOutcome.cumulative_early_withdrawal_penalty_paid` (median across paths, or the single deterministic value), mirroring `median_lifetime_irmaa_paid`'s/`median_lifetime_niit_paid`'s own two call sites exactly (depends on T022)
- [X] T024 [P] Add `"median_lifetime_early_withdrawal_penalty_paid"` to `_SUMMARY_FIELDNAMES` (immediately after `"median_lifetime_niit_paid"`) and the matching entry to `_summary_to_row()` in `src/retirement_planner/reporting/export.py` (depends on T022)
- [X] T025 [P] Add a "Lifetime early-withdrawal penalty paid" entry to `apps/streamlit_ui/src/rp_ui/narration.py`, mirroring the existing "Lifetime Medicare IRMAA surcharge"/"Lifetime Net Investment Income Tax" entries exactly (same `tax_qualifier` phrasing pattern, reading `summary.get("median_lifetime_early_withdrawal_penalty_paid")`) (depends on T022)
- [X] T026 [P] Extend `tests/unit/reporting/test_aggregation.py` and `tests/unit/reporting/test_export.py` with cases for the new field/column, following each suite's existing per-field pattern (depends on T023, T024)
- [X] T027 [P] Extend `apps/streamlit_ui/tests/unit/test_narration.py` with a case for the new entry, following that suite's existing per-field pattern (depends on T025)
- [X] T028 Run the full four-suite quality gate from CLAUDE.md/README.md one final time: `pytest tests/`, `pytest services/bff/tests/`, `pytest apps/streamlit_ui/tests/`, `cd e2e && ../.venv/bin/python3.12 -m pytest -q` — confirm all green (depends on T001-T027)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user story phases.
- **User Story 1 (Phase 3)**: Depends on Foundational only. The MVP — delivers the entire
  observable behavior change (the penalty itself, funded) and absorbs this feature's whole
  regression-triage burden (T014) before any later phase adds more test surface on top of a shaky
  baseline.
- **User Story 2 (Phase 4)**: Depends on User Story 1's implementation (T008-T011) — its own
  combined-base computation already exists there; this phase is confirmation-only.
- **User Story 3 (Phase 5)**: Depends on User Story 1 (T011) and User Story 2 (T019) — it documents
  both stories' completed behavior.
- **Polish (Phase 6)**: Depends on User Story 1's T007 (the new `PlanOutcome` field) — independent
  of Phases 4-5's own completion, but pointless to demo before at least Phase 3 lands.

### Within Each Phase

- Foundational: T002 (parallel with starting T003); T003 → T004 → T005.
- User Story 1: T006/T007 in parallel (different dataclasses, same file — sequence the actual
  edit but no logical dependency between them); T008 → T009 → T010 → T011 → T012 → T013; then T014
  (regression triage, blocking); then T015/T016/T017/T018 in parallel with each other.
- User Story 2: T019 depends on User Story 1's full chain (T008-T011) and on T014's triage having
  already stabilized the baseline.
- User Story 3: T020 depends on T011 and T019; T021 depends on T011, T019, T020.
- Polish: T022 → T023; T022 → T024 (parallel with T023); T022 → T025 (parallel with T023/T024);
  T026 depends on T023/T024; T027 depends on T025; T028 last (depends on everything).

### Parallel Opportunities

- Foundational: T002 can start immediately; T005 depends on both T002 and T004.
- Within User Story 1: T015, T016, T017, and T018 in parallel with each other once T011 lands and
  T014's triage is complete.
- Within Polish: T024 and T025 in parallel with T023 once T022 lands (three different files).
- **File-contention note**: T008, T009, T010, T011, and T012 all edit the same per-year loop and
  `_derive_outcome()` inside `comparison/projection.py` — sequence these rather than attempting
  them concurrently, mirroring `018`'s/`019`'s own analogous file-contention notes.
- **Regression-triage note**: T014 is inherently sequential and cannot be parallelized with T015-T018
  — those tests must be written against a codebase whose existing suite is already green again,
  not one still carrying unexplained failures.

---

## Parallel Example: User Story 1 (tests, once T014's triage is complete)

```bash
Task: "Unit tests for compute_early_withdrawal_penalty() in tests/unit/tax/test_early_withdrawal_penalty.py (T015)"
Task: "Integration tests for the penalty in a real projection in tests/unit/comparison/test_projection.py (T016)"
Task: "No-regression test for an unaffected household in tests/unit/comparison/test_projection.py (T017)"
Task: "Monte Carlo propagation regression test in tests/unit/simulation/test_monte_carlo.py (T018)"
```

## Parallel Example: Polish

```bash
Task: "reporting/aggregation.py derivation (T023)"
Task: "reporting/export.py CSV column (T024)"
Task: "Streamlit narration.py entry (T025)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational) — the pure penalty function, cited and
   exported.
2. Complete Phase 3 (User Story 1), **including T014's regression triage** — do not consider this
   phase done until the full four-suite gate is green again with every correction explained.
3. **STOP and VALIDATE**: run `pytest tests/unit/tax/test_early_withdrawal_penalty.py
   tests/unit/comparison/test_projection.py tests/unit/simulation/test_monte_carlo.py` and confirm
   green. This alone delivers the entire observable capability (SC-001, SC-002, SC-004) rp-8z0
   exists for — the tool's own reference use case (ages 58/60) finally shows this real cost.

### Incremental Delivery

1. Setup + Foundational → the pure penalty function ready, cited.
2. User Story 1 → the penalty ships, funded, with every existing test's expected values corrected
   and explained — this is the deliverable with live projection impact, and the riskiest phase.
3. User Story 2 → confirms (mostly via already-built-in behavior) that the Roth-ladder combination
   works as designed.
4. User Story 3 → documentation/auditability catches up (`docs/BRD.md`).
5. Polish → the `010`-established reporting/UI ripple (lifetime-cost summary, CSV export,
   narration), plus the full four-suite quality gate one final time.

### Notes

- T014 is this feature's single most important task — unlike `017`/`018`/`019`, this feature was
  never expected to be non-disruptive to the existing suite (research.md Decision 7). Treat every
  triaged correction as a small, explained, reviewable change, not a bulk find-and-replace of
  expected values.
- T018 mirrors `016`'s/`017`'s/`018`'s/`019`'s own precedent (each added an explicit
  `test_monte_carlo.py` consistency check for the shared `run_plan_projection()` call site) —
  belt-and-suspenders, not because the underlying "every path already calls this function"
  reasoning is in doubt.
- Per this repo's Conservative git profile (CLAUDE.md): no task here commits, pushes, or opens a
  PR — that remains a separate, explicitly-requested step after implementation.
