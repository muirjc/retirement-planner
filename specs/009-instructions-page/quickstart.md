# Quickstart: Instructions Page

Validates the feature end-to-end: read the page as a human would, and drive it headlessly with `streamlit.testing.v1.AppTest` for automated validation — per SC-001 through SC-004.

## Prerequisites

- Python 3.11+, `apps/streamlit_ui` installed editable (`pip install -e apps/streamlit_ui[dev]` or equivalent) — same environment `008`'s own quickstart uses.
- No running `007` instance needed for this feature specifically (this page makes no HTTP calls) — but `streamlit run apps/streamlit_ui/app.py` still needs `007` reachable for the *other* pages to work normally in the same session, per `008`'s own quickstart.

## 1. Find and read the guidance before creating a scenario (User Stories 1 & 2)

Run `streamlit run apps/streamlit_ui/app.py`.

1. On the Home page, before creating any scenario, confirm the sidebar shows **Instructions** above **Scenarios** (User Story 2, Acceptance Scenario 1).
2. Open **Instructions**. **Expected outcome**: all seven sections render — household/parties, accounts, spending, state, market assumptions, simulation settings, Roth conversion (Acceptance Scenario 1, SC-002).
3. Read the Accounts section. **Expected outcome**: it states balances are entered as one combined household total per account type, not per party (Acceptance Scenario 2, FR-003).
4. Read the Household section. **Expected outcome**: it states the SS benefit figure must match the specific claiming age entered, not the full-retirement-age amount (Acceptance Scenario 3, FR-004).
5. Read the State section. **Expected outcome**: it points to the Scenarios page's own state dropdown for the current list, without naming specific state codes itself (FR-006, SC-004).

## 2. Reach it mid-form and return without losing your place (User Story 2)

1. Open **Scenarios** and start filling in a scenario (do not save).
2. Navigate to **Instructions**, then back to **Scenarios**. **Expected outcome**: the in-progress form's values are unaffected — visiting Instructions has no bearing on the Scenarios page's own state (Acceptance Scenario 2).

## Running the automated version

```bash
pytest apps/streamlit_ui/tests/unit/test_instructions_content.py -v   # all 7 sections present, no hardcoded state codes
pytest apps/streamlit_ui/tests/integration/test_app_pages.py -v       # -k instructions for this feature's own cases
```

Both passing (plus the manual walkthrough above at least once) is the acceptance bar for this feature — see [contracts/ui-pages.md](./contracts/ui-pages.md) for the exact contract exercised above.
