# Data Model: Advanced Simulation Options

No core `retirement_planner` package change — `GenerationMode`, `StressScenario`, and `ReturnPath`
(`retirement_planner.simulation.models`) already exist, unchanged, from `005-simulation-engine`. This
feature's only new types live in the BFF layer.

## New: `StressScenarioRequest` (`rp_bff.schemas`)

```python
class StressScenarioRequest(BaseModel):
    """Mirrors 005-simulation-engine's StressScenario fields exactly (rp-2bn).
    None (the field's default on SimulationRequest/ComparisonRequest) means
    no stress overlay -- every existing request's exact current behavior."""

    magnitude: float
    """The fixed annual return every path is overridden to for the
    configured window -- e.g. -0.30 for a 30% single-year decline."""
    duration_years: int
    """How many consecutive plan years the shock lasts."""
    start_plan_year: int
    """The first plan year the shock applies to."""
```

## Modified: `SimulationRequest` (`rp_bff.routes.simulations`)

```python
class SimulationRequest(BaseModel):
    # ... existing fields unchanged (scenario_name, withdrawal_strategy, state,
    #     reference_tax_year, start_plan_year, start_tax_year, plan_to_age,
    #     n_paths, seed, detail_path_index, survival_adjusted) ...
    generation_mode: GenerationMode = "parametric"
    """rp-741: "parametric" (default, unchanged existing behavior) or
    "historical_bootstrap" (opt-in, moving-block resampling from
    HISTORICAL_RETURNS -- synthetic placeholder data, docs/BRD.md §6.9)."""
    historical_block_length: int = 10
    """rp-741: consulted only when generation_mode == "historical_bootstrap"
    -- research.md Decision 4's default, matching 005's own quickstart.md
    worked example. Ignored (harmlessly present) in parametric mode."""
    stress_scenario: StressScenarioRequest | None = None
    """rp-2bn: None (default) means no stress overlay -- every existing
    request's exact current behavior. Applied on top of whichever
    generation_mode produced the underlying paths."""
```

## Modified: `ComparisonRequest` (`rp_bff.routes.comparisons`)

Identical three fields added, same defaults, same meaning — this class already independently
duplicates `SimulationRequest`'s overlapping fields (existing convention; both classes are used by
`resolve_and_compare_simulated()`/`resolve_and_run_simulation()` respectively, never shared). Applies
only when the comparison actually calls `resolve_and_compare_simulated()` (the Monte Carlo path) —
`resolve_and_compare_deterministic()` never reads these three fields at all (FR-007).

## New (private, `rp_bff.resolution`): `generate_configured_return_paths()`

Not a new *type* — a new function. See contracts/bff-api.md's addendum to
`specs/007-bff-api-service/contracts/bff-api.md` for its exact shape and the two routes' new
request-body fields.
