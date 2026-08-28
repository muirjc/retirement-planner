# Contract: UI Pages

This is an application, not a library or network service — the "contract" is each page's inputs, actions, and rendered states, the level `streamlit.testing.v1.AppTest` (research.md's chosen testing tool) actually exercises. Anything not listed here is presentation detail; anything listed here is what this feature's own tests should assert against.

## `app.py` — Home

- **Renders**: a short description of the tool, navigation to the three pages below, and a live backend-status check (`GET /reference/states` — if this fails, the Home page itself shows `BackendUnreachableError`'s message immediately, rather than waiting for a user to discover it on a deeper page).

## `pages/1_Scenarios.py` — Scenario management (User Story 1)

- **Inputs**: a scenario-name field; a household section (add/remove members, each with name/age/claiming age/SS benefit); an accounts section (add/remove entries, each with type/balance); a spending field; a state selector (populated from `list_states()`, FR-003); a market-assumptions section; a simulation-settings section (`n_paths`/`seed`/`plan_to_age`); an optional Roth-conversion section (strategy selector populated from `list_conversion_strategies()`, bracket ceiling/amount, window).
- **Actions**:
  - *Save* → `put_scenario(name, body)` (FR-001, FR-005) → re-renders the form with the saved data and every `validation_flags` entry shown inline (FR-002), distinguishing `severity="blocking"` from `severity="warning"` (Acceptance Scenario US1.2).
  - *Validate* (without saving) → `validate_scenario(name, body)` → same inline flag rendering, no save side effect.
  - *Load existing* → a selector populated from `list_scenarios()`, on selection calls `get_scenario(name)` and populates the form.
  - *Delete* → `delete_scenario(name)` (FR-004) → the scenario disappears from the load selector immediately (Acceptance Scenario US1.4).
- **Error states**: `ScenarioNotFoundError` on a stale *Load*/*Delete* → "This scenario no longer exists — it may have been removed elsewhere." `InvalidScenarioError` on *Save*/*Validate* → the specific `reason` shown next to the field it names. `BackendUnreachableError` → the same Home-page-level message, shown inline instead of silently failing.

## `pages/2_Run_Simulation.py` — Run a simulation (User Story 2)

- **Inputs**: a saved-scenario selector (`list_scenarios()`); a withdrawal-strategy selector (`list_withdrawal_strategies()`, defaulting to `007`'s own default); `reference_tax_year`/`start_plan_year`/`start_tax_year` fields, pre-filled with a sensible starting value but always user-editable (research.md, spec.md Assumptions — never silently substituted); an "advanced" expander for `n_paths`/`seed`/`plan_to_age` overrides (each optional, defaulting from the scenario's own settings if left blank).
- **Action**: *Run* → wrapped in `st.spinner(...)` (FR-008) → `run_simulation(body)` → on success, renders:
  - the `summary.success_rate` as a headline metric;
  - `charts.fan_chart(summary.percentile_bands)` (Acceptance Scenario US2.1);
  - `verification.render_verification_indicator(summary.unverified_figure_names)` (FR-013);
  - a *Download CSV* button → `export_simulation_csv(body)` (the identical request body, per data-model.md § Relationships) → a file download (Acceptance Scenario US5.1).
- **Error states**: `ScenarioNotFoundError` → "This scenario no longer exists." `BlockingValidationError` → every flag's `message` listed, with a link back to `1_Scenarios.py` to fix them (Acceptance Scenario US2.2) — distinct wording from `ScenarioNotFoundError`. `UnknownReferenceValueError` → "`{field}` value `{value}` isn't currently supported — pick from the list." `UnsupportedTaxYearError` → "Tax year `{requested_year}` isn't supported for `{figure_name}` — enter a year between `{min}` and `{max}`." (added post-launch — see [data-model.md](./data-model.md) § Error types for why). `CostBudgetExceededError` → "This request is too large (estimated {estimated_seconds:.0f}s against a {budget_seconds:.0f}s budget) — try fewer paths." (Acceptance Scenario US2.3). `BackendUnreachableError`/`UnexpectedBackendError` → the shared unreachable/unexpected message (Edge Cases).

## `pages/3_Compare.py` — Compare candidates (User Story 3)

- **Inputs**: a saved-scenario selector; an engine selector (*Deterministic* / *Monte Carlo*); an axis selector, populated from `list_comparison_axes()` **filtered to exclude `"state"` when *Deterministic* is selected** (FR-010, Acceptance Scenario US3.2 — enforced client-side before submission, per Edge Cases' "resolves this without submitting an invalid combination"); a candidate-list editor whose fields depend on the chosen axis (state codes; conversion-strategy candidates; withdrawal-strategy candidates; a claiming-age grid builder) — mirroring `007`'s own axis-dependent `candidates` shape (`specs/007-bff-api-service/contracts/bff-api.md` § Comparisons) exactly, one widget group per axis.
- **Action**: *Compare* → `st.spinner(...)` → `compare_deterministic(body)` or `compare_simulated(body)` depending on the engine selected → on success:
  - if the first candidate's `percentile_bands` is not `null` → `charts.comparison_overlay_chart(summaries)`; otherwise → `charts.comparison_bar_chart(summaries)` (research.md §3);
  - a summary table, one row per candidate: `candidate_label`, `success_rate` (or "n/a" when `null`, Acceptance Scenario US3.3), `ending_balance`, `median_lifetime_tax_paid`, `median_depletion_age`;
  - `verification.render_verification_indicator()` per candidate (or once, over the union of every candidate's `unverified_figure_names`, if no single figure is more relevant than another — an implementation-level choice deferred to `tasks.md`, not scope-defining here);
  - a *Download CSV* button → `export_comparison_csv(body, engine)` (Acceptance Scenario US5.2).
- **Single-candidate requests** are supported without any special-casing in the UI (Acceptance Scenario US3.4) — the candidate-list editor allows exactly one entry, submits normally, and the summary table/chart render with one row/series.
- **Error states**: same five `007`-shaped errors as the Run page, plus `UnknownReferenceValueError` also covering an axis/candidate value invalid for the chosen engine (e.g. a state code `007` doesn't recognize).

## Consumption expectations for a future second UI

- Nothing in this contract is specific to Streamlit's own widgets — every "Inputs"/"Action"/"Error states" description maps directly onto `007`'s own request/response contract (`specs/007-bff-api-service/contracts/bff-api.md`), which is what a future second UI (a JS SPA, a desktop wrapper) would build against instead of this one. This feature's `src/rp_ui/api_client.py`/`errors.py`/`charts.py` logic is Streamlit-agnostic Python that a future non-Streamlit UI could theoretically reuse directly (they don't import any `streamlit`-specific type), though duplicating it in another language is equally expected and not a regression.
