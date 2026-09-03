# Contract: BFF API (addendum to `007-bff-api-service`)

Extends `specs/007-bff-api-service/contracts/bff-api.md`'s Simulations/Comparisons sections. Every
existing field, response shape, and error case keeps its exact existing meaning; this addendum lists
only what's new.

## `POST /api/v1/simulations` — new request fields

```text
POST /api/v1/simulations
  body: {
    ... (all existing fields unchanged) ...
    generation_mode?: "parametric" | "historical_bootstrap",   # default "parametric"
    historical_block_length?: int,                              # default 10 (rp-741)
    stress_scenario?: {                                         # default None -- no overlay (rp-2bn)
      magnitude: float,
      duration_years: int,
      start_plan_year: int,
    },
  }
  -> 200 {"run": SimulationRun, "summary": SummaryStatistics}   # unchanged response shape;
       # historical_bootstrap mode's own figures_used (HISTORICAL_RETURNS, verified=False) flows
       # into summary.unverified_figure_names via the existing pipeline, no new response field
  -> 422 {"error": "invalid_simulation_options", "detail": string}   # NEW (rp-741, rp-2bn):
       # ValueError from generate_historical_bootstrap_paths() (bad historical_block_length) or
       # apply_stress_scenario() (stress window past the run's own horizon)
  -> 404 / 422 (existing shapes) / 413 -- unchanged
```

## `POST /api/v1/comparisons/simulated` — new request fields

Identical three fields, identical defaults, identical new 422 shape — added to `ComparisonRequest`.
`POST /api/v1/comparisons/deterministic` is completely unaffected: it never reads these fields at all
(FR-007, both options are Monte-Carlo-only).

## New (private): `rp_bff.resolution.generate_configured_return_paths()`

```python
# rp_bff.resolution:

def generate_configured_return_paths(
    context: ResolvedRunContext,
    horizon_years: int,
    start_plan_year: int,
    generation_mode: GenerationMode,
    historical_block_length: int,
    stress_scenario: StressScenario | None,
) -> list[ReturnPath]:
    """Builds this run's return paths per generation_mode (research.md
    Decision 1) -- generate_return_paths() for "parametric" (default),
    generate_historical_bootstrap_paths() for "historical_bootstrap" (using
    historical_block_length) -- then applies apply_stress_scenario() on top
    when stress_scenario is not None (rp-2bn). Shared by
    resolve_and_run_simulation() and resolve_and_compare_simulated() so both
    endpoints dispatch identically (mirrors build_survival_curves()'s own
    integration shape). Raises ValueError, propagated unchanged from
    whichever engine call raised it -- callers translate via
    invalid_simulation_options_error()."""


def invalid_simulation_options_error(exc: ValueError) -> HTTPException:
    """Translates a ValueError raised by generate_configured_return_paths()
    into a 422 response (research.md Decision 5) -- mirrors
    survival_curve_age_out_of_range_error()'s own "dedicated translator per
    resolution-layer exception" shape."""
```

## Consumption expectations for downstream features

- `resolve_and_run_simulation()` (`routes/simulations.py`) and `resolve_and_compare_simulated()`
  (`routes/comparisons.py`) each replace their existing direct `generate_return_paths()` call with a
  call to `generate_configured_return_paths()`, passing `body.generation_mode`,
  `body.historical_block_length`, and (converted from `body.stress_scenario` when not `None`) a core
  `StressScenario`, wrapped in `try/except ValueError: raise invalid_simulation_options_error(exc)`.
- `resolve_and_compare_deterministic()` requires **no change** — it has no return-path generation
  step at all (FR-007).
- `retirement_planner.simulation`'s own public API (`generate_return_paths()`,
  `generate_historical_bootstrap_paths()`, `apply_stress_scenario()`, `GenerationMode`,
  `StressScenario`, `ReturnPath`) keeps its exact existing, already-locked shape — this feature adds
  no new core-library operation.
