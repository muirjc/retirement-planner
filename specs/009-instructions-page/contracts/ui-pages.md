# Contract: UI Pages (addendum to `008`)

Extends `specs/008-streamlit-ui/contracts/ui-pages.md`'s per-page Inputs/Actions/Error-states format with the one new page this feature adds. Everything else in that file is unchanged.

## `pages/0_Instructions.py` — Instructions (User Stories 1 & 2)

- **Renders**: seven sections (household/parties, accounts, spending, state, market assumptions, simulation settings, Roth conversion), each a header plus Markdown body, sourced from `src/rp_ui/instructions_content.py`'s `SECTIONS` list, in that list's order.
- **Inputs**: none. This page reads no widget state and writes no `st.session_state` entry.
- **Actions**: none beyond Streamlit's own built-in navigation (the sidebar link `app.py`'s Home page and every other page already provide).
- **Error states**: none — this page calls no `rp_ui.api_client` function, so none of `007`'s error shapes (or `BackendUnreachableError`/`UnexpectedBackendError`) are reachable from it. It renders identically whether `007` is running or not.

## Consumption expectations for a future second UI

Same note `008`'s own contract already makes: `instructions_content.py`'s `SECTIONS` list is Streamlit-agnostic Python (a list of `Section(title, body)` values) — a future non-Streamlit UI could render the same content directly rather than re-authoring it.
