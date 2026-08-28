# Quickstart: Streamlit UI

Validates the feature end-to-end: run the app against a real `007` instance for a human to try, and drive each page headlessly with `streamlit.testing.v1.AppTest` against a mocked backend for automated validation — per SC-001–SC-006.

> **All dollar figures, ages, and rates below are illustrative placeholders**, exactly as `001`–`007`'s quickstarts note for their own placeholder figures. This feature introduces no new figures of its own — it only renders whatever `007` returns.

## Prerequisites

- Python 3.11+, plus this feature's own dependencies (`pip install -e apps/streamlit_ui[dev]` or equivalent).
- For the manual walkthrough (steps 1–5 below, as a human would run them): a running `007` instance (`uvicorn rp_bff.main:app`, from `services/bff/`) reachable at `RP_BFF_BASE_URL` (default `http://127.0.0.1:8000/api/v1`).
- For the automated version (see the end of this document): no running `007` needed — `httpx.MockTransport` stands in for it.

## 1. Enter and manage a scenario (User Story 1)

Run `streamlit run apps/streamlit_ui/app.py`, open the **Scenarios** page, and:

1. Fill in a household (two members, ages 60/58, claiming ages 67/67, SS benefits $32,000/$24,000), accounts (traditional $1,500,000, Roth $400,000, taxable $200,000), spending ($110,000), state `FL` (from the live dropdown), market assumptions, and simulation settings (5,000 paths, seed 42, plan to age 95). Save it as `base_case`.
2. **Expected outcome**: the page confirms the save and shows `is_usable: true` with no blocking flags (US1.1).
3. Change the traditional account balance to `-100` and re-save. **Expected outcome**: a blocking flag is shown inline, distinct from a warning (US1.2).
4. Fix the balance, re-save, then delete `base_case`. **Expected outcome**: it no longer appears in the scenario selector anywhere on the page (US1.4).

## 2. Run a simulation and see the fan chart (User Story 2)

Re-save `base_case` (step 1), then open the **Run Simulation** page:

1. Select `base_case`, leave the withdrawal strategy at its default, enter `reference_tax_year=2026`, `start_plan_year=1`, `start_tax_year=2026`, and click **Run**.
2. **Expected outcome**: a spinner shows while the request is in flight (US2.4), then a success-rate metric and a fan chart of ending-balance percentiles over time both appear (US2.1).
3. Introduce a blocking flag (as in step 1.3) and run again. **Expected outcome**: a specific "fix these problems first" message appears, listing the flags, not a generic error (US2.2).

## 3. Compare candidates and see the overlay (User Story 3)

Open the **Compare** page:

1. Select `base_case`, engine **Monte Carlo**, axis **state**, candidates `SC`, `DE`, `FL`, and click **Compare**.
2. **Expected outcome**: a line-overlay chart with one line per state and a summary table with one row per state appear (US3.1).
3. Switch the engine to **Deterministic**. **Expected outcome**: `state` is no longer offered as an axis choice (US3.2).
4. Select axis **roth_conversion_strategy** with one candidate and compare. **Expected outcome**: the result still renders (a single-candidate comparison is valid, US3.4), and the table shows `success_rate`/percentile fields as "n/a", not blank or zero (US3.3).

## 4. Confirm unverified figures are flagged (User Story 4)

On either the Run or Compare page, using a scenario whose simulation draws on `005`'s historical-bootstrap or survival-adjusted paths would surface an unverified figure — for the reference `parametric`-mode default, confirm instead that the **verified** confirmation is shown explicitly (US4.2), and that switching to a fixture response with a non-empty `unverified_figure_names` list (see the automated tests below) renders the specific figure names (US4.1).

## 5. Download a CSV report (User Story 5)

From the completed Run page (step 2) or Compare page (step 3), click **Download CSV**.

**Expected outcome**: the downloaded file's figures match what's on screen — one row per plan year (Run) or one row per candidate (Compare), matching `006`'s export shapes exactly (US5.1–US5.2).

## Running the automated version

Once implemented, the equivalent assertions above are `apps/streamlit_ui/tests/integration/test_app_pages.py`, using `AppTest.from_file()` against each page script with `httpx.MockTransport` standing in for `007` (research.md §2's testing decision) — no real backend process needed:

```bash
pytest apps/streamlit_ui/tests/ -v
```

All steps passing (against both the mocked-backend automated suite and, at least once, the real manual walkthrough above) is the acceptance bar for this feature — see [contracts/ui-pages.md](./contracts/ui-pages.md) for the exact per-page inputs/actions/error states exercised above.
