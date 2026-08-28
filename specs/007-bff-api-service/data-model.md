# Data Model: BFF API Service

Source: [spec.md](./spec.md) Key Entities section, resolved against research.md's design decisions. Types are described conceptually (Pydantic request models, plain `to_jsonable()`-shaped response bodies, per research.md §3) — field names are illustrative, not a locked contract; the locked contract for downstream consumers (`008`, and any future second UI) is [contracts/bff-api.md](./contracts/bff-api.md).

Unlike `001`–`006`, this feature defines almost no *new* domain data — it defines the HTTP-shaped request/response wrapper around `001`–`006`'s already-locked types. Every entity below either mirrors an existing dataclass field-for-field (the request side) or is exactly that dataclass's `to_jsonable()` rendering (the response side).

## Scenario Resource

**Request** (`PUT /scenarios/{name}`, `POST /scenarios/{name}/validate`): mirrors `001`'s `Scenario` fields exactly — `household` (`filing_status`, `members: [{person_name, current_age, ss_claim_age, ss_annual_benefit}]`), `accounts: [{account_type, balance}]`, `spending: {annual_need_real}`, `state`, `market_assumptions` (`equity_allocation`, `equity_return_mean_real`, `equity_return_std_real`, `bond_allocation`, `bond_return_mean_real`, `bond_return_std_real`, `correlation`), `simulation_settings` (`n_paths`, `seed`, `plan_to_age`), `roth_conversion` (optional: `strategy`, `bracket_ceiling_or_amount`, `window`). The route handler converts this request body to YAML text and calls `001`'s own `parse_scenario()` — it never hand-constructs a `Scenario` object field-by-field (research.md §3, plan.md's "Config as data, not code" note).

**Response** (`GET /scenarios/{name}`, and the read-back after `PUT`): the `to_jsonable()` rendering of the resulting `Scenario`, including `validation_flags: [{field, message, severity}]` and `is_usable`.

**List response** (`GET /scenarios`): `{"scenarios": [name, ...]}` — `001`'s own `list_scenarios()` output, unmodified order.

## Reference Data

Four independent, read-only list responses, each a direct rendering of an existing registry or type — no new entity, just a live view:

| Response | Source | Shape |
|---|---|---|
| `GET /reference/states` | `002`'s `STATE_MODULES.keys()` | `{"states": [code, ...]}`, sorted |
| `GET /reference/withdrawal-strategies` | `003`'s `WITHDRAWAL_STRATEGIES.keys()` | `{"withdrawal_strategies": [name, ...]}`, sorted |
| `GET /reference/conversion-strategies` | `003`'s `CONVERSION_STRATEGIES.keys()` | `{"conversion_strategies": [name, ...]}`, sorted |
| `GET /reference/comparison-axes` | `005`'s `ComparisonAxis` (`typing.get_args`) | `{"axes": [axis, ...]}` — the full `005` set (`state`, `roth_conversion_strategy`, `withdrawal_sequencing`, `claiming_age_grid`); the deterministic comparison endpoint accepts only the subset `004`'s `ComparisonDimension` defines (research.md §7) |

## Run Request/Response

**Request** (`POST /simulations`): `scenario_name` (required), `withdrawal_strategy` (optional, default `"rmd_taxable_traditional_roth"`), `state` (optional, default the named scenario's own `state`), `reference_tax_year`/`start_plan_year`/`start_tax_year` (all **required**, no default — research.md §4), `plan_to_age`/`n_paths`/`seed` (each optional, defaulting from the named scenario's `simulation_settings`).

The route handler builds a `StrategyConfiguration` from the request's `withdrawal_strategy` plus the scenario's own `roth_conversion` (`conversion_strategy`/`conversion_bracket_ceiling_or_amount`/`conversion_window`, or all `None` if the scenario has none) and `claiming_ages` derived from `{member.person_name: member.ss_claim_age for member in scenario.household.members}` — every `StrategyConfiguration` field this service constructs traces back to either the request body or the scenario's own already-validated data, never a value invented by this service.

**Response**: `{"run": to_jsonable(SimulationRun), "summary": to_jsonable(SummaryStatistics)}` (Acceptance Scenario US3.1) — `005`'s `run_simulation()` result and `006`'s `summarize_run()` result on that same run, in one payload.

## Comparison Request/Response

Two request shapes (research.md §7), sharing the run request's `scenario_name`/`reference_tax_year`/`start_plan_year`/`start_tax_year`/`plan_to_age`/`state` fields (state as a single value here, held fixed, *except* when `axis="state"` on the simulated endpoint, where `candidates` supplies the varying state list instead) plus:

**`POST /comparisons/deterministic`**: `axis` ∈ `{roth_conversion_strategy, withdrawal_sequencing, claiming_age_grid}` (never `state` — `004` has no state-comparison function to dispatch to, research.md §7); `candidates` shaped per `axis`, mirroring `004`'s three `compare_*()` functions' own candidate-list parameters exactly. **Response**: `{"axis": ..., "summaries": [to_jsonable(SummaryStatistics), ...]}`, one entry per candidate in request order, each via `006`'s `summarize_deterministic_comparison()`.

**`POST /comparisons/simulated`**: `axis` ∈ `{state, roth_conversion_strategy, withdrawal_sequencing, claiming_age_grid}`; `n_paths`/`seed` (optional, scenario-derived defaults, same as the run request); `candidates` shaped per `axis`, mirroring `005`'s four `compare_*()` functions. **Response**: same shape as the deterministic response, populated via `006`'s `summarize_simulation_comparison()`.

## Export Response

Not JSON — `text/csv` (or equivalent plain-text) responses:

| Response | Mirrors | Request body |
|---|---|---|
| `POST /reports/simulations.csv` | `006`'s `run_to_csv_text()` | Identical shape to the run request above |
| `POST /reports/comparisons.csv?engine=deterministic` | `006`'s `deterministic_comparison_to_csv_text()` | Identical shape to the deterministic comparison request |
| `POST /reports/comparisons.csv?engine=simulated` | `006`'s `simulation_comparison_to_csv_text()` | Identical shape to the simulated comparison request |

Every export request is the *same body* as its corresponding JSON-returning request (Acceptance Scenarios US5.1–US5.2) — this service never introduces a separate "export parameters" shape distinct from "run/compare parameters."

## Relationships

- A Run Request is resolved to a `StrategyConfiguration` + the named `Scenario`'s own fields, then passed to `005`'s `generate_return_paths()` (parametric mode only — historical bootstrap/stress scenarios are not exposed by this feature, spec.md Assumptions) followed by `run_simulation()`, then `006`'s `summarize_run()` on the result — this service's own code is the glue between these calls, not a reimplementation of any of them.
- A Comparison Request is resolved the same way, but the built `StrategyConfiguration`/state/etc. become the *held-fixed* arguments to the relevant `004`/`005` `compare_*()` function, with `candidates` passed through structurally unchanged from the request body.
- Every Export Response is produced by first resolving the identical Run or Comparison Request, then calling the corresponding `006` export function on the resulting `SimulationRun`/`ComparisonResult`/`SimulationComparisonResult` — it is never derived from a JSON response that was already returned to a client (no "export the last thing you asked for" state).
- `FR-018`'s cost estimate is computed from the resolved `n_paths` × candidate count × horizon length (`plan_to_age` minus the deemed owner's current age) *before* any of the above calls happen — a rejected request never reaches `004`/`005` at all.

## State transitions

The only persisted state this feature touches is `001`'s scenario storage (`config/scenarios/`) — created via `PUT`, read via `GET`, removed via `DELETE`. Every run, comparison, and export response is computed fresh on every request (research.md §2) — this feature introduces no new state machine, no request history, and no cross-request memory of any kind.
