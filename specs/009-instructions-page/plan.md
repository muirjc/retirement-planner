# Implementation Plan: Instructions Page

**Branch**: `009-instructions-page` | **Date**: 2026-08-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-instructions-page/spec.md`

## Summary

A new static-content page in the existing `apps/streamlit_ui` package, reachable from anywhere in the tool, that explains what financial information to gather for each party in the household and what every field on the scenario entry form (`pages/1_Scenarios.py`) actually requires. It computes nothing, stores nothing, and calls no backend — the first page in this project with zero network dependency of any kind, not even to `007`.

## Technical Context

**Language/Version**: Python 3.11+ — same as the rest of `apps/streamlit_ui`.

**Primary Dependencies**: `streamlit` only, already declared in `apps/streamlit_ui/pyproject.toml` — this feature adds **no new dependency**, not even `httpx` or `plotly` (both already present for other pages but unused by this one).

**Storage**: None. The guidance text is hardcoded content shipped with the code, not user data — spec.md's own Assumptions rule out a content-management capability.

**Testing**: `streamlit.testing.v1.AppTest`, continuing `008`'s convention, plus a plain unit test over the content module itself (no `AppTest` overhead needed just to check that all 7 sections exist with the right key statements).

**Target Platform**: Same as the rest of `apps/streamlit_ui` — local browser via `streamlit run`, offline-capable.

**Project Type**: An addition to the existing `apps/streamlit_ui` package — no new package, no new `pyproject.toml`.

**Performance Goals**: N/A — a static render with no computation.

**Constraints**: No dependency on `retirement_planner` or `rp_bff` (already true for the whole package). No network call of any kind — stronger than every other page in `008`, which all call `007`; this page must render correctly even with `007` completely unreachable, and must never regress into calling it.

**Scale/Scope**: One new page, one new content module, a two-line edit to `app.py`'s navigation text. No new API surface, no new error type, no new chart.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Accuracy Over Cleverness** — ✅ PASS. Every example figure or rule of thumb the guidance gives (e.g., an illustrative allocation) is explicitly framed as an example, never as an authoritative value the tool computed (FR-007) — the content module's own docstring must say this outright so it's enforced by convention at the point future edits are made, not just by this plan.
- **II. Reproducibility** — N/A. No computation, no seed, no run to reproduce.
- **III. Auditability** — N/A directly (no externally-sourced tax figure is introduced or restated on this page); the same "never presented as authoritative" discipline from Principle I covers the adjacent risk of this page drifting into asserting a tax fact.
- **IV. Extensibility Through Module Interfaces** — ✅ PASS, concretely reinforced one layer further than `007`/`008` already established: FR-006 requires the guidance to point at the Scenarios page's own live state selector rather than hardcode state codes, so adding a 4th state module never requires touching this page.
- **V. Offline-First, No Runtime Network Dependency** — ✅ PASS, and stronger than any existing page: this page makes **zero** network calls, where every other page in `008` calls `007`. A dependency-containment test should assert this page's module never imports `rp_ui.api_client`.
- **VI. Performance Budget** — N/A. Trivial static render.

**Technology & Architecture Constraints:**
- *"Config as data, not code"* — N/A directly; this page owns no scenario/tax data. Its own content is deliberately hardcoded prose, not user-editable config — spec.md's Assumptions rule out a content-management capability, so this is a considered exception rather than a silent gap.
- *Paired-draw comparison* — N/A, no comparison run here.
- *Scope boundary with the working document* — N/A, purely explanatory text about fields the tool already has; no qualitative/financial modeling of its own.

**Development Workflow & Quality Gates**: Regression baseline / Verified-figure gate / Unit test coverage for numeric primitives — all N/A, same posture as `008`'s own Constitution Check for its non-numeric pieces (no engine change, no new externally-sourced figure, no numeric primitive).

**Post-Phase 1 re-check**: Confirmed after Phase 1 design below — no new violations; the dependency-containment claim (no `api_client` import) becomes a concrete test, not just an assertion in this document.

## Project Structure

### Documentation (this feature)

```text
specs/009-instructions-page/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── contracts/
│   └── ui-pages.md       # Phase 1 output -- addendum to 008's own contracts/ui-pages.md
└── quickstart.md         # Phase 1 output
```

### Source Code (repository root)

```text
apps/streamlit_ui/
├── app.py                        # MODIFIED -- one more navigation line pointing to Instructions
├── pages/
│   └── 0_Instructions.py         # NEW -- sorts above 1_Scenarios.py in the sidebar
└── src/rp_ui/
    └── instructions_content.py   # NEW -- the guidance text itself, as importable data,
                                   # so it's testable without spinning up AppTest and so a
                                   # future second UI could reuse it (008's own precedent:
                                   # api_client/errors/charts/verification are all Streamlit-
                                   # agnostic Python for the same reason)

apps/streamlit_ui/tests/
├── unit/
│   └── test_instructions_content.py   # NEW -- every field-group present, no hardcoded
│                                        # state codes, example figures framed as examples
└── integration/
    └── test_app_pages.py              # MODIFIED -- a few more AppTest cases appended to
                                         # the existing US1-US5 file (Home nav link works,
                                         # page renders with zero backend calls)
```

**Structure Decision**: No new package — this is an addition to the existing `apps/streamlit_ui` package `008` already established, keeping that feature's own convention (`api_client.py`/`errors.py`/`charts.py`/`verification.py` in `src/rp_ui/`, thin page scripts in `pages/`) intact for the one new piece of content this feature adds. Reusing `008`'s existing `tests/integration/test_app_pages.py` rather than starting a second integration test file keeps every page's AppTest coverage in one place, matching how `US4`/`US5` were added to that same file as later phases rather than new files.

## Complexity Tracking

*No Constitution Check violations — table intentionally omitted.*
