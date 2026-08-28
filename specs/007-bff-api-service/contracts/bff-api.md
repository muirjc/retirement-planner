# Contract: `services/bff` HTTP API

This is a network service, not a library — the "contract" is the HTTP request/response shape this feature exposes for `008` (and any future second/third UI) to call. All routes are prefixed `/api/v1`. Anything not listed here is an internal implementation detail; anything listed here is what downstream UI clients should code against. See [data-model.md](../data-model.md) for field-level meaning; this contract lists the wire shape.

Every response body (except CSV exports) is JSON. Every JSON response's dataclass-derived fields are `to_jsonable()`'s rendering of the underlying `001`–`006` type (research.md §3) — `date` fields as ISO 8601 strings, `PercentileBand.percentiles` as `[{"percentile": p, "value": v}, ...]`.

## Scenarios (`routes/scenarios.py`)

```text
GET /api/v1/scenarios
  -> 200 {"scenarios": [string, ...]}                      (FR-001, US1.2)

PUT /api/v1/scenarios/{name}
  body: ScenarioRequest (data-model.md § Scenario Resource)
  -> 200 ScenarioResponse (includes validation_flags, is_usable)  (FR-001, FR-003, US1.1, US1.4)
  -> 422 on malformed request body (ScenarioParseError-equivalent, per 001's parse_scenario())

GET /api/v1/scenarios/{name}
  -> 200 ScenarioResponse                                    (FR-001, US1.1)
  -> 404 {"error": "no_such_scenario", "name": string}       (FR-005, US1.6)

DELETE /api/v1/scenarios/{name}
  -> 204 (no body)                                            (FR-004, US1.5)
  -> 404 {"error": "no_such_scenario", "name": string}       (FR-005, US1.6)

POST /api/v1/scenarios/{name}/validate
  body: ScenarioRequest (validated but not saved)
  -> 200 {"validation_flags": [{field, message, severity}], "is_usable": bool}  (FR-002, US1.3)
```

## Reference data (`routes/reference.py`)

```text
GET /api/v1/reference/states
  -> 200 {"states": [string, ...]}                           (FR-006, US2.1-US2.2)

GET /api/v1/reference/withdrawal-strategies
  -> 200 {"withdrawal_strategies": [string, ...]}             (FR-007, US2.3)

GET /api/v1/reference/conversion-strategies
  -> 200 {"conversion_strategies": [string, ...]}             (FR-007, US2.3)

GET /api/v1/reference/comparison-axes
  -> 200 {"axes": ["state", "roth_conversion_strategy", "withdrawal_sequencing", "claiming_age_grid"]}  (FR-007, US2.3)
  # Note: this is 005's full axis set. /comparisons/deterministic accepts only the
  # roth_conversion_strategy/withdrawal_sequencing/claiming_age_grid subset (004 has
  # no state-comparison function) -- see /comparisons/deterministic below.
```

## Simulations (`routes/simulations.py`)

```text
POST /api/v1/simulations
  body: {
    scenario_name: string,                                    # required
    withdrawal_strategy?: string,                              # default "rmd_taxable_traditional_roth"
    state?: string,                                            # default scenario.state
    reference_tax_year: int,                                   # REQUIRED, no default (research.md §4)
    start_plan_year: int,                                      # REQUIRED, no default
    start_tax_year: int,                                       # REQUIRED, no default
    plan_to_age?: int,                                         # default scenario.simulation_settings.plan_to_age
    n_paths?: int,                                              # default scenario.simulation_settings.n_paths
    seed?: int,                                                 # default scenario.simulation_settings.seed
  }
  -> 200 {"run": SimulationRun, "summary": SummaryStatistics}  (FR-008, FR-010, FR-011, US3.1, US3.3, US3.4)
  -> 404 {"error": "no_such_scenario", "name": string}         (FR-005)
  -> 422 {"error": "blocking_validation_flags", "flags": [ValidationFlag, ...]}  (FR-009, US3.2)
  -> 422 {"error": "unknown_reference_value", "field": string, "value": string}  (FR-014, research.md §6)
  -> 413 {"error": "estimated_cost_exceeds_budget", "estimated_seconds": float, "budget_seconds": float}  (FR-018)
```

## Comparisons (`routes/comparisons.py`)

```text
POST /api/v1/comparisons/deterministic
  body: {
    scenario_name: string,
    reference_tax_year: int, start_plan_year: int, start_tax_year: int,  # all REQUIRED
    plan_to_age?: int,                                          # default scenario.simulation_settings.plan_to_age
    state?: string,                                             # default scenario.state
    axis: "roth_conversion_strategy" | "withdrawal_sequencing" | "claiming_age_grid",  # never "state" (research.md §7)
    candidates: [ ... ],   # shape depends on axis, mirroring 004's compare_*() candidate params exactly:
                            #   roth_conversion_strategy -> [{label, conversion_strategy, conversion_bracket_ceiling_or_amount, conversion_window}, ...]
                            #   withdrawal_sequencing     -> [{label, withdrawal_strategy}, ...]
                            #   claiming_age_grid         -> [{person_name: int, ...}, ...]  (one dict per grid cell)
  }
  -> 200 {"axis": string, "summaries": [SummaryStatistics, ...]}  (FR-012, FR-013, FR-015, US4.2, US4.4)
  -> 404 / 422 / 413 -- same error shapes as POST /simulations   (FR-005, FR-009, FR-014, FR-018)

POST /api/v1/comparisons/simulated
  body: {
    scenario_name: string,
    reference_tax_year: int, start_plan_year: int, start_tax_year: int,  # all REQUIRED
    plan_to_age?: int, n_paths?: int, seed?: int,               # each default scenario-derived
    state?: string,                                             # default scenario.state; irrelevant when axis="state"
    axis: "state" | "roth_conversion_strategy" | "withdrawal_sequencing" | "claiming_age_grid",
    candidates: [ ... ],   # shape depends on axis, mirroring 005's compare_*() candidate params exactly:
                            #   state                     -> [string, ...]  (state codes)
                            #   roth_conversion_strategy / withdrawal_sequencing / claiming_age_grid -> same shapes as above
  }
  -> 200 {"axis": string, "summaries": [SummaryStatistics, ...]}  (FR-012, FR-013, FR-015, US4.1, US4.4)
  -> 404 / 422 / 413 -- same error shapes as POST /simulations
```

## Reports (`routes/reports.py`)

```text
POST /api/v1/reports/simulations.csv
  body: identical to POST /api/v1/simulations
  -> 200 text/csv (006's run_to_csv_text() output)             (FR-016, FR-017, US5.1, US5.3)
  -> 404 / 422 / 413 -- same error shapes as POST /simulations

POST /api/v1/reports/comparisons.csv?engine=deterministic|simulated
  body: identical to the corresponding POST /api/v1/comparisons/* request
  -> 200 text/csv (006's deterministic_comparison_to_csv_text()/simulation_comparison_to_csv_text() output)  (FR-016, FR-017, US5.2, US5.3)
  -> 404 / 422 / 413 -- same error shapes as the corresponding comparison endpoint
```

## Consumption expectations for downstream features

- `008` (and any future second/third UI) is expected to call this service exclusively over HTTP — never `import retirement_planner` directly — so this contract, not the underlying Python packages, is the one integration surface a UI needs (`docs/frontend_architecture.md` §7's explicit reasoning for why the first UI should exercise this boundary rather than bypass it).
- `GET /api/v1/reference/*` responses are the single source of truth for what values are currently valid in a run/comparison request's `state`/`withdrawal_strategy`/`conversion_strategy`/`axis` fields — a client should query these rather than hardcoding a list, per Extensibility (Principle IV, FR-006–FR-007).
- Every error response's `error` field is a stable, machine-matchable string (`no_such_scenario`, `blocking_validation_flags`, `unknown_reference_value`, `estimated_cost_exceeds_budget`) a client can branch on without parsing free-text messages.
- `reference_tax_year`/`start_plan_year`/`start_tax_year` are never defaulted by this service (research.md §4) — a client is expected to supply real calendar-year values itself (e.g., today's actual year) rather than expecting the service to infer "now."
- A future async-job addition to this service (deferred per FR-018/spec.md Assumptions until the documented performance trigger is hit) would wrap these same request/response bodies in a job envelope (`202 {job_id}` + `GET /jobs/{id}`) without changing any field shape listed above — a client built against this contract today should not need to change its request-building code when that lands, only how it awaits a response.
