---

description: "Task list for Instructions Page"
---

# Tasks: Instructions Page

**Input**: Design documents from `/specs/009-instructions-page/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/ui-pages.md](./contracts/ui-pages.md), [quickstart.md](./quickstart.md)

**Tests**: Included — plan.md's Project Structure specifies test files as deliverables, matching the precedent set by `001`–`008`. Testing uses a plain unit test over the content module itself plus `streamlit.testing.v1.AppTest` for the page/navigation, per research.md §1's rationale for not paying `AppTest`'s overhead just to check that a list of strings contains the right seven items.

**Organization**: Tasks are grouped by user story (spec.md priorities P1–P2) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to (US1–US2)
- File paths are exact and relative to the repository root

## Path Conventions

This feature adds to the existing `apps/streamlit_ui` package `008` established — **no new package, no new dependency, no new `pyproject.toml` entry**:
- New: `apps/streamlit_ui/src/rp_ui/instructions_content.py`, `apps/streamlit_ui/pages/0_Instructions.py`, `apps/streamlit_ui/tests/unit/test_instructions_content.py`
- Modified: `apps/streamlit_ui/app.py` (nav text), `apps/streamlit_ui/tests/integration/test_app_pages.py` (new cases appended, per research.md §4), `apps/streamlit_ui/tests/integration/test_dependency_containment.py` (new assertion appended)

**Story dependency shape**: User Story 1 (the guidance content itself) depends only on the Foundational content module. User Story 2 (finding it at any time) depends on User Story 1's page existing, since it's an additive edit to `app.py`'s nav text plus a round-trip navigation check — there is no page to navigate to or from until US1 lands. This mirrors `008`'s own precedent of later-priority stories layering onto, not blocking, earlier ones.

---

## Phase 1: Setup

**Purpose**: Confirm the existing package needs no change to support this feature before adding anything to it

- [X] T001 Confirm `apps/streamlit_ui/pyproject.toml` needs no new dependency for this feature (`streamlit` alone is sufficient, per plan.md's Technical Context) — run `pytest apps/streamlit_ui/tests/` to confirm the existing 52 tests pass as a pre-change baseline

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The content model both user stories render — nothing else can be built without it

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 [P] Unit test `Section` dataclass and `SECTIONS` list in `src/rp_ui/instructions_content.py` — all 7 required sections present (data-model.md's table: household/parties, accounts, spending, state, market assumptions, simulation settings, Roth conversion); the accounts section states balances are pooled per household not per party (FR-003); the household section states the SS benefit must match the entered claiming age (FR-004); the spending section states today's dollars, pre-tax (FR-005); the state section names no specific state code (FR-006); the market-assumptions section frames any example figure as a starting point, not an authoritative value (FR-007) — write FIRST, ensure it FAILS before T003, in `apps/streamlit_ui/tests/unit/test_instructions_content.py`
- [X] T003 Implement `apps/streamlit_ui/src/rp_ui/instructions_content.py` — `Section` dataclass (`title`, `body`) and the `SECTIONS` list, content per data-model.md's table and `docs/instructions_page_requirements.md` §5 (depends on T002)

**Checkpoint**: Content model ready — User Story 1 implementation can now begin

---

## Phase 3: User Story 1 - Understand what to gather and what each field means (Priority: P1) 🎯 MVP

**Goal**: A user can open a page that explains, for every input group on the scenario entry form, what to gather and what the field requires — independent of any other page or backend service.

**Independent Test**: Open the page on its own, with no scenario created and no other part of the tool exercised, and confirm it explains every input group on the scenario entry form.

### Tests for User Story 1 ⚠️

> Write these tests FIRST, ensure they FAIL before implementing T005

- [X] T004 [US1] `AppTest`-driven test: `pages/0_Instructions.py` renders all 7 section headers and every section's required statement (data-model.md's table) appears in the rendered Markdown; the page renders with `api_client._transport` left unset (no mock installed) to prove it makes no HTTP call at all (contracts/ui-pages.md § `pages/0_Instructions.py`, Acceptance Scenario US1.1) in `apps/streamlit_ui/tests/integration/test_app_pages.py`

### Implementation for User Story 1

- [X] T005 [US1] Implement `apps/streamlit_ui/pages/0_Instructions.py` — imports `SECTIONS` from `rp_ui.instructions_content` and renders each as a header plus Markdown body, in list order, nothing else (contracts/ui-pages.md § `pages/0_Instructions.py`, data-model.md § Relationships) (depends on T003, T004)

**Checkpoint**: User Story 1 is independently functional — quickstart.md §1 (steps 2–5) passes end-to-end. Discoverability beyond Streamlit's own automatic sidebar entry is not yet addressed.

---

## Phase 4: User Story 2 - Find the guidance at any time (Priority: P2)

**Goal**: A user can reach the guidance from anywhere in the tool, before starting a scenario or mid-way through one, without losing their place or being blocked from continuing.

**Independent Test**: Starting from any other part of the tool, confirm the guidance is reachable in a small, constant number of steps, and that reaching it does not require a scenario to already exist or disturb one already in progress.

### Tests for User Story 2 ⚠️

> Write this test FIRST, ensure it FAILS before implementing T007

- [X] T006 [US2] `AppTest`-driven test: the Home page's navigation text names "Instructions"; `0_Instructions.py` sorts before `1_Scenarios.py` in the page order Streamlit reports; filling in Scenarios form fields, navigating to Instructions, then back to Scenarios, leaves the in-progress values unchanged (Acceptance Scenarios US2.1–US2.2) in `apps/streamlit_ui/tests/integration/test_app_pages.py`

### Implementation for User Story 2

- [X] T007 [US2] Edit `apps/streamlit_ui/app.py`'s navigation text to add a line naming **Instructions** alongside the existing Scenarios/Run Simulation/Compare bullets (depends on T005, T006)

**Checkpoint**: User Stories 1 and 2 are both independently functional — quickstart.md §1–2 pass end-to-end.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Verify this feature's cross-cutting requirements (dependency containment, zero network calls) and tie the quickstart walkthrough together as one acceptance run

- [X] T008 [P] Confirm `apps/streamlit_ui/src/rp_ui/instructions_content.py` and `apps/streamlit_ui/pages/0_Instructions.py` import neither `rp_ui.api_client` nor `retirement_planner`/`rp_bff` — a permanent assertion appended to `apps/streamlit_ui/tests/integration/test_dependency_containment.py` (mirroring that file's existing `pyproject.toml`-based checks, extended here to a source-level import check specific to this feature, per plan.md's Constitution Check) (depends on T003, T005)
- [X] T009 [P] Add docstrings to `instructions_content.py` (module + `Section` + `SECTIONS`) and `0_Instructions.py`, each referencing [contracts/ui-pages.md](./contracts/ui-pages.md) § `pages/0_Instructions.py` (depends on T003, T005)
- [X] T010 Run the complete [quickstart.md](./quickstart.md) walkthrough (§1–2) as one end-to-end assertion sequence in `apps/streamlit_ui/tests/integration/test_app_pages.py` (depends on T004, T006)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS both user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on User Story 1 (`T005`) — it edits `app.py`'s nav text pointing at a page that must already exist, and its round-trip navigation test needs both pages present
- **Polish (Phase 5)**: `T008`/`T009` depend on `T003`+`T005`; `T010` depends on `T004`+`T006`

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on other stories — the MVP slice
- **User Story 2 (P2)**: Depends on User Story 1 — unlike `008`'s US2/US3 (which were independent of each other), this feature's two stories are sequential by nature: there is nothing to navigate *to* until the page exists

### Within Each Phase

- Tests are written first and must fail before the corresponding implementation task
- Foundational's content module (T002 → T003) before either story, since both render `SECTIONS`

### Parallel Opportunities

- T002 (a new, isolated test file) can proceed as soon as Setup (T001) confirms the baseline
- T008 and T009 in Polish can run in parallel — different files, independent concerns

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run `pytest apps/streamlit_ui/tests/` and confirm SC-001/SC-002 hold via quickstart.md §1
5. This alone delivers the feature's entire stated value (spec.md: "this single piece of guidance content is the entire value of the feature") — Streamlit's own automatic sidebar entry already makes the page reachable even before US2's explicit nav-text edit lands

### Incremental Delivery

1. Setup + Foundational → content model ready
2. Add User Story 1 → the guidance page itself → validate independently (SC-001, SC-002) → this is the MVP
3. Add User Story 2 → explicit Home nav text + round-trip navigation guarantee → validate independently (SC-003)
4. Polish → dependency containment, docstrings, full quickstart.md walkthrough (SC-004 implicitly covered by T002's state-section assertion)
