# Data Model: Streamlit UI

Source: [spec.md](./spec.md) Key Entities section, resolved against research.md's design decisions and `007`'s actual, implemented response shapes (`specs/007-bff-api-service/contracts/bff-api.md`). Types are described conceptually (Python functions/dataclasses/exceptions) — the locked contract for this feature's own internal modules is [contracts/ui-pages.md](./contracts/ui-pages.md); the upstream contract this feature consumes is `007`'s, unchanged.

Unlike `001`–`007`, this feature defines no new domain data at all — every entity below is either (a) a thin wrapper over one of `007`'s existing request/response shapes, or (b) purely presentational (a chart, a rendered indicator) derived from one.

## API Client (`src/rp_ui/api_client.py`)

One function per `007` endpoint (research.md §2), each returning the parsed JSON body (a plain `dict`/`list`, matching `007`'s own `to_jsonable()`-shaped responses — this feature does not re-wrap them in its own dataclasses) or raising one of the exceptions below:

| Function | Calls | Returns |
|---|---|---|
| `list_scenarios()` | `GET /scenarios` | `list[str]` |
| `get_scenario(name)` | `GET /scenarios/{name}` | `dict` (Scenario, incl. `validation_flags`, `is_usable`) |
| `put_scenario(name, body)` | `PUT /scenarios/{name}` | `dict` (same shape as `get_scenario`) |
| `delete_scenario(name)` | `DELETE /scenarios/{name}` | `None` |
| `validate_scenario(name, body)` | `POST /scenarios/{name}/validate` | `dict` (`validation_flags`, `is_usable`) |
| `list_states()` | `GET /reference/states` | `list[str]` |
| `list_withdrawal_strategies()` | `GET /reference/withdrawal-strategies` | `list[str]` |
| `list_conversion_strategies()` | `GET /reference/conversion-strategies` | `list[str]` |
| `list_comparison_axes()` | `GET /reference/comparison-axes` | `list[str]` |
| `run_simulation(body)` | `POST /simulations` | `dict` (`{"run": ..., "summary": ...}`) |
| `compare_deterministic(body)` | `POST /comparisons/deterministic` | `dict` (`{"axis": ..., "summaries": [...]}`) |
| `compare_simulated(body)` | `POST /comparisons/simulated` | `dict` (same shape) |
| `export_simulation_csv(body)` | `POST /reports/simulations.csv` | `str` (CSV text) |
| `export_comparison_csv(body, engine)` | `POST /reports/comparisons.csv?engine=...` | `str` (CSV text) |

## Error types (`src/rp_ui/errors.py`)

| Type | Raised when `007` returns | Carries |
|---|---|---|
| `ScenarioNotFoundError` | 404 `no_such_scenario` | `name` |
| `InvalidScenarioError` | 422 `invalid_scenario` | `reason` |
| `BlockingValidationError` | 422 `blocking_validation_flags` | `flags: list[dict]` (each `{field, message, severity}`) |
| `UnknownReferenceValueError` | 422 `unknown_reference_value` | `field`, `value` |
| `UnsupportedTaxYearError` | 422 `unsupported_tax_year` | `figure_name`, `requested_year`, `documented_years` |
| `CostBudgetExceededError` | 413 `estimated_cost_exceeds_budget` | `estimated_seconds`, `budget_seconds` |
| `BackendUnreachableError` | a connection/timeout failure reaching `007` at all | the underlying `httpx` exception |
| `UnexpectedBackendError` | any other non-2xx response | `status_code`, raw body |

Every page script catches these (never a bare `except Exception`) and renders the message FR-007/FR-015 require — see [contracts/ui-pages.md](./contracts/ui-pages.md) for the exact per-type message each page shows.

`UnsupportedTaxYearError` was added post-launch (not part of the original `008` implementation): a real run against the Run Simulation page's unedited `reference_tax_year` placeholder (`1900`, from `min_value=1900` with no explicit default -- research.md §2's reasoning against reading the system clock) reached `002`'s figure schedules outside their documented range and surfaced as a bare, unexplained `HTTP 500` instead of a specific message. Fixed at both layers: `007`'s `routes/simulations.py`/`routes/comparisons.py` now catch the underlying `UnsupportedTaxYearError` (`retirement_planner.tax`) around the `run_simulation()`/`compare_*()` calls and translate it via `resolution.py::unsupported_tax_year_error()`, and this feature's `api_client.py`/`errors.py`/both pages render it distinctly, per this table.

## Verification Indicator (`src/rp_ui/verification.py`)

Not a data type — a rendering function, `render_verification_indicator(unverified_figure_names: list[str])`, called on every Run View and Comparison View (FR-013). Reads `summary["unverified_figure_names"]` (present, possibly empty, on every `007` `SummaryStatistics`-shaped response — `006`'s own "present even when empty" guarantee, carried through unchanged) and renders either a positive "all figures verified" confirmation or a named list of what's still unverified — never omits the indicator either way (Acceptance Scenarios US4.1–US4.2).

## Charts (`src/rp_ui/charts.py`)

| Function | Input | Chart |
|---|---|---|
| `fan_chart(percentile_bands)` | one run's `percentile_bands: [{plan_year, percentiles: [{percentile, value}, ...]}, ...]` | percentile bands over plan year (User Story 2) |
| `comparison_overlay_chart(summaries)` | a Monte Carlo comparison's `summaries` (every entry has non-`null` `percentile_bands`) | one line per candidate, each candidate's own median (50th percentile) ending balance across plan years (research.md §3) |
| `comparison_bar_chart(summaries)` | a deterministic comparison's `summaries` (every entry has `percentile_bands: null`) | one bar group per candidate, `ending_balance` and `median_lifetime_tax_paid` (research.md §3) |

`3_Compare.py` (the Compare page) selects between `comparison_overlay_chart()` and `comparison_bar_chart()` by checking whether the response's first candidate's `percentile_bands` is `null` — not by trusting the `engine` selector the user chose, since that's exactly the check research.md §3 identified as the honest signal.

## Relationships

- Every page's data ultimately traces back to exactly one `007` HTTP response — no page combines data from two separate requests into a single rendered number (e.g., the Run View's success rate is `response["summary"]["success_rate"]`, not something this feature recomputes from `response["run"]["path_results"]`).
- The Scenario Form (User Story 1) is the only entity with client-side-only state before it's saved — `st.session_state` holds the in-progress form values; nothing else in this feature persists anything client-side across a page reload.
- The Report Download (User Story 5) is not a separate request shape — it is the *same* request body already used to produce the on-screen Run View/Comparison View, sent again to the corresponding `/reports/*.csv` endpoint (mirroring `007`'s own "same request shape as the trigger endpoint" design, contracts/bff-api.md § Reports) — this feature never invents a distinct "export parameters" form.

## State transitions

None beyond what `007` already owns. This feature's own "state" is either a page's in-progress form inputs (ephemeral, lost on reload, by design) or the result of the most recent request to `007` (also not persisted — reloading a page re-fetches, never replays a cached response). No new state machine, no local file, no browser storage beyond Streamlit's own built-in session mechanism.
