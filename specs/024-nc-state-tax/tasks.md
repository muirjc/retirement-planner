---

description: "Task list for 024-nc-state-tax"
---

# Tasks: North Carolina State Income Tax Module

**Input**: Design documents from `/specs/024-nc-state-tax/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — constitution's "Unit test coverage for numeric primitives" gate requires unit tests against reference values for each state's tax module before it's used in any comparative run; spec.md's acceptance criteria explicitly names `tax/state/test_nc.py`.

**Organization**: As with `022`, Phase 2 (Foundational) carries the actual `tax/state/nc.py` module, since all three user stories exercise the same `compute_tax()` with different inputs (a documented tax year's rate, Social Security excluded, a second documented tax year's rate) rather than needing separate implementations or separate modules.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [x] T001 Confirm `pytest tests/` passes on `024-nc-state-tax` before any change (baseline for SC-003)

---

## Phase 2: Foundational (blocks every user story)

- [x] T002 [US-shared] Create `src/retirement_planner/tax/state/nc.py`: module docstring (mirrors `sc.py`'s, explaining the flat-rate structure and the deliberate absence of a Bailey-settlement exclusion — data-model.md, research.md §1/§3), `_DOCUMENTED_YEARS = range(2020, 2075)`, `_2025_BRACKETS`/`_2026_BRACKETS` (each a one-row `BracketTable`, `income_up_to=None`), `_NC_FLAT_RATE: SourcedFigure[BracketTable]` (`verified=True`, citation to N.C. Gen. Stat. §105-153.7 as amended by S.L. 2023-134 — data-model.md § `_NC_FLAT_RATE`), and `compute_tax(income, filer_ages, filing_status, tax_year) -> StateTaxResult` (data-model.md § `compute_tax()`)
- [x] T003 [US-shared] Register `"NC": nc.compute_tax` in `STATE_MODULES` and add the `nc` import in `src/retirement_planner/tax/state/__init__.py` (contracts/tax-api.md) — depends on T002
- [x] T004 [P] [US-shared] Unit tests in `src/retirement_planner/tax/state/test_nc.py`: zero-income floor (US1), tax year 2026 at 3.99% (US1), tax year 2025 at 4.25% (US1/US3), Social Security excluded from the taxable base (US2), no bracket cliff at a very high income (edge case), `UnsupportedTaxYearError` for a year outside `_DOCUMENTED_YEARS` (edge case), `figures_used` always carries the one `_NC_FLAT_RATE` usage — depends on T002

**Checkpoint**: `nc.compute_tax()` fully correct and registered in isolation.

---

## Phase 3: User Story 1 - Evaluate North Carolina as a candidate retirement state (Priority: P1) 🎯 MVP

**Goal**: Selecting `"NC"` as a household's state via `compute_state_tax()` returns a real, cited flat-rate tax result for a documented tax year, with the zero-income floor holding.

**Independent Test**: quickstart.md §1 — `compute_state_tax("NC", ...)` for tax year 2026 returns `ordinary_income * 0.0399`; for $0 income, returns $0.00.

### Implementation for User Story 1

- [x] T005 [US1] Confirm (no code change expected) `compute_state_tax("NC", income, filer_ages, filing_status, tax_year)` dispatches correctly through the existing `STATE_MODULES` lookup in `src/retirement_planner/tax/state/__init__.py` — depends on T003
- [x] T006 [P] [US1] Run quickstart.md §1 scenarios (2026 flat 3.99%, 2025 flat 4.25%, zero-income floor) as part of `tax/state/test_nc.py` (already covered by T004) — confirm and cross-reference in test docstrings/comments — depends on T004

**Checkpoint**: User Story 1 fully functional — this is the MVP; a household can evaluate NC as a candidate state.

---

## Phase 4: User Story 2 - Social Security income stays untaxed when comparing against NC (Priority: P2)

**Goal**: `IncomeComponents.social_security_gross_benefit` never enters NC's taxable base, matching SC's/DE's existing treatment.

**Independent Test**: quickstart.md §2 — a household with a $30,000 Social Security benefit and $50,000 ordinary income is taxed only on the $50,000.

- [x] T007 [US2] Confirm the Social-Security-excluded unit test in `tax/state/test_nc.py` (from T004) matches quickstart.md §2's worked example exactly — depends on T004

**Checkpoint**: NC held to the same Social Security treatment SC/DE already model, confirmed end to end.

---

## Phase 5: User Story 3 - Multi-decade projections see NC's legislated rate step-down (Priority: P3)

**Goal**: A projection spanning tax years 2025 and 2026 sees 4.25% in 2025 and 3.99% from 2026 onward for the same income.

**Independent Test**: quickstart.md §3 — the same fixed income taxed at both years shows the 2025 result strictly higher than the 2026 result.

- [x] T008 [US3] Confirm the two-tax-year comparison unit test in `tax/state/test_nc.py` (from T004) matches quickstart.md §3's worked example exactly (2025 result > 2026 result for identical income) — depends on T004

**Checkpoint**: All three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T009 [P] Unit test in `services/bff/tests/` confirming `GET /reference/states` now includes `"NC"` (data-model.md § Relationships, contracts/tax-api.md § Consumption expectations) — depends on T003
- [x] T010 [P] Check any `STATE_MODULES`-parametrized existing test (e.g. a `dependency_containment` test) passes with `"NC"` included and no special-casing added (SC-003) — depends on T003
- [x] T011 Update `docs/BRD.md` §2.3: remove North Carolina from the not-yet-implemented parenthetical candidate list — depends on Phase 3
- [x] T012 Update `docs/BRD.md` §5.4: rename the section heading to include North Carolina, add NC's table row (structure: "Flat rate, no age-based exclusion"; verification status: verified — cites N.C. Gen. Stat. §105-153.7), and adjust the SC/DE-only framing sentence below the table so it doesn't also describe NC — depends on Phase 3
- [x] T013 [P] Check `docs/SOLUTION_ARCHITECTURE.md` for whether the `tax.state` subpackage's component description needs a one-line mention (no new package/route — likely small, confirm) — depends on T003
- [x] T014 [P] Check `README.md` for whether test counts need updating — depends on Phases 2-6
- [x] T015 Run full quickstart.md validation end-to-end
- [x] T016 Run all affected test suites (`pytest tests/`, `pytest services/bff/tests/`) and confirm green
- [x] T017 `bd close rp-5dn` with a summary; if research (T002/data-model.md §3) leaves any open follow-on (e.g., a future Bailey-settlement-capable `IncomeComponents` extension, or confirming the historical G.S. §105-134.6(b)(6) deduction's repeal against actual statutory text rather than the current Schedule S's silence), file it as a new bead rather than leaving it implicit

---

## Dependencies & Execution Order

- **Setup (T001)**: no dependencies.
- **Foundational (T002-T004)**: blocks every user story — `nc.compute_tax()` itself and its registration.
- **User Story 1 (T005-T006)**: depends on Foundational; the MVP — NC is selectable and produces a correct flat-rate result.
- **User Story 2 (T007)**: depends on T004 — confirmation only, Social Security exclusion is already correct from T002 (it's simply never read).
- **User Story 3 (T008)**: depends on T004 — confirmation only, the two-year step is already correct from T002's schedule.
- **Polish (T009-T017)**: BFF/docs/test-suite/session-close — can start once Phase 2 lands, but T011-T012/T017 should follow Phase 3 so the docs describe a confirmed-working module.

## Implementation Strategy

### MVP First

Phases 1-3 (through T006) deliver the core ask: North Carolina becomes a selectable, correctly-taxed candidate state. Phases 4-5 are confirmation-only, since `nc.compute_tax()`'s single implementation (T002) already gets Social Security exclusion and the two-year step-down right by construction — there is no separate code path per user story, matching `022`'s own precedent for a feature where one small function serves every story. Phase 6 completes the docs/BRD.md and cross-suite verification vertical this project's convention requires before a feature is considered done (see this file's own project `CLAUDE.md` "Living documentation" note).
