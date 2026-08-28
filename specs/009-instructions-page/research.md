# Phase 0 Research: Instructions Page

No items in Technical Context were left as `NEEDS CLARIFICATION` — this feature's scope (a static page inside an already-established package) leaves little to discover technically; the questions worth resolving here are about how to shape the one new piece of content so it stays easy to test and impossible to silently drift from `1_Scenarios.py`'s actual fields.

## 1. Where does the guidance text live — inline in the page script, or an importable module?

**Decision**: `src/rp_ui/instructions_content.py` — a plain data structure (a list of section objects, each with a title and a body), imported by `pages/0_Instructions.py`, which does nothing but iterate over it and render.

**Rationale**: `008`'s own Structure Decision already established the pattern this feature continues: `api_client.py`/`errors.py`/`charts.py`/`verification.py` hold every piece of reusable, Streamlit-agnostic logic; `pages/*.py` are thin scripts that only exist where Streamlit's own routing mechanism forces them to (`008` research.md §5). Content is no different from logic here — putting it in an importable module means `test_instructions_content.py` can assert "every field-group is covered" and "no state code is hardcoded" against the data directly, without paying `AppTest`'s overhead just to read strings back out of a rendered page tree. It also means a future second UI (data-model.md's own "Consumption expectations for a future second UI" note in `008`) could reuse this exact content, the same way it could already reuse `api_client`/`errors`/`charts`.

**Alternatives considered**: Writing the guidance directly as `st.markdown()` calls inline in `0_Instructions.py` — rejected; it would make FR-002's "every field-group is covered" claim testable only through `AppTest`'s rendered-text inspection, which is a heavier, slower way to check something that's really just "does this list of strings contain these seven items."

## 2. Why `0_Instructions.py`, not appended after `3_Compare.py`?

**Decision**: `apps/streamlit_ui/pages/0_Instructions.py`. Streamlit orders its sidebar by filename, and `0` sorts ahead of `1_Scenarios.py`.

**Rationale**: Spec.md's User Story 2 (P2) is explicitly about the guidance being easy to reach "before creating any scenario" — sorting it first in the sidebar is the direct, no-extra-code way to satisfy that, consistent with `008`'s own precedent of using Streamlit's filename-ordering mechanism rather than building custom navigation (`008` research.md §5).

**Alternatives considered**: A `4_Instructions.py` at the end — rejected; it would bury the one page meant to be read first behind three pages a user hasn't used the tool enough yet to need. Embedding the same content as an expander at the top of `1_Scenarios.py` instead of a separate page — rejected; the user explicitly asked for a dedicated instructions page (this session's own prior planning turn), and a separate page is what makes it reachable independent of the Scenarios form (User Story 2's own independent-test criterion).

## 3. How is "every field-group is covered" (SC-002) actually verified?

**Decision**: `instructions_content.py`'s section list and `1_Scenarios.py`'s own field-groups are checked against each other by name in `test_instructions_content.py` — the test enumerates the same seven group names spec.md's FR-002 lists (household, accounts, spending, state, market assumptions, simulation settings, Roth conversion) and asserts each has a corresponding section.

**Rationale**: A hardcoded list of expected section titles in the test is what actually catches the content drifting out of sync with the form — the risk this whole feature exists to prevent for the *user*, this test prevents for the *codebase*.

**Alternatives considered**: Deriving the expected section list programmatically from `1_Scenarios.py`'s own widget keys — rejected as unnecessary indirection for seven fixed, well-known groups; a plain hardcoded list is easier to read and just as effective at catching drift, and matches how `008`'s own `contracts/ui-pages.md` describes each page's inputs as prose, not as a generated list.

## 4. Test file placement

**Decision**: New AppTest cases for this page are appended to `008`'s existing `apps/streamlit_ui/tests/integration/test_app_pages.py`, not a new file.

**Rationale**: `008`'s own tasks.md sequenced User Story 4 and User Story 5 as additive edits to that same file rather than new ones, precisely so every page's integration coverage stays in one place. This feature's two or three new cases (Home page's nav link, the page rendering with zero backend calls, the state section not hardcoding codes) are a small extension of that same file, not a new concern.

**Alternatives considered**: A dedicated `test_instructions_page.py` — rejected; splitting integration coverage per-page would be a new convention this project hasn't used anywhere else in `008`.
