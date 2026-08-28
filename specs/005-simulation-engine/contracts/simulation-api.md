# Contract: `retirement_planner.simulation` public API

This is a library, not a network service — the "contract" is the public Python interface this feature exposes for later features (§3.6 Reporting) to import and build on, plus the one additive change to `retirement_planner.comparison`'s existing contract. Anything not listed here is an internal implementation detail; anything listed here is what downstream features should code against.

Module: `retirement_planner.simulation` (re-exports from `models`, `returns`, `historical_data`, `survival_data`, `monte_carlo`, `compare` — see [plan.md](../plan.md) Project Structure).

## Additive change to `retirement_planner.comparison` (research.md §1)

```python
# comparison/models.py — DeterministicReturnAssumption gains one method;
# its existing field is unchanged, so every 004 caller is unaffected.
@dataclass
class DeterministicReturnAssumption:
    annual_real_return: float

    def return_for_plan_year(self, plan_year: int) -> float:
        """Returns annual_real_return unconditionally — ignores plan_year."""

# comparison/projection.py — run_plan_projection()'s return_assumption
# parameter's type hint widens from DeterministicReturnAssumption to
# simulation.models.ReturnSchedule (a Protocol both DeterministicReturnAssumption
# and ReturnPath satisfy); its one growth-factor line now calls
# return_assumption.return_for_plan_year(plan_year) instead of reading
# .annual_real_return directly. No other behavior changes.
```

## Data types (`models`)

```python
class ReturnSchedule(Protocol):
    def return_for_plan_year(self, plan_year: int) -> float: ...

GenerationMode = Literal["parametric", "historical_bootstrap"]

@dataclass
class ReturnPath:
    start_plan_year: int
    annual_returns: list[float]          # index i = plan year start_plan_year + i
    generation_mode: GenerationMode
    figures_used: list[FigureUsage]      # empty for parametric mode

    def return_for_plan_year(self, plan_year: int) -> float: ...  # satisfies ReturnSchedule

@dataclass
class StressScenario:
    magnitude: float
    duration_years: int
    start_plan_year: int

@dataclass
class SurvivalCurve:
    person_name: str
    probabilities_by_age: dict[int, float]
    citation: str
    last_verified: date
    verified: bool

    def survival_probability(self, age: int) -> float: ...  # raises KeyError if age missing
    def usage(self) -> FigureUsage: ...

@dataclass
class PercentileBand:
    plan_year: int
    percentiles: dict[float, float]      # percentile level -> total ending balance

@dataclass
class SimulationRun:
    candidate_label: str
    strategy: StrategyConfiguration       # from retirement_planner.comparison
    state: str
    path_results: list[PlanProjection]    # from retirement_planner.comparison, one per ReturnPath
    success_rate: float
    percentile_bands: list[PercentileBand]
    survival_adjusted_success_rate: float | None
    figures_used: list[FigureUsage]

ComparisonAxis = Literal["state", "roth_conversion_strategy", "withdrawal_sequencing", "claiming_age_grid"]

@dataclass
class SimulationComparisonResult:
    axis: ComparisonAxis
    return_paths: list[ReturnPath]
    runs: list[SimulationRun]
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## Operations (`returns`)

```python
def generate_return_paths(
    market_assumptions: MarketAssumptions,  # from retirement_planner.scenario
    path_count: int,
    horizon_years: int,
    start_plan_year: int,
    seed: int,
) -> list[ReturnPath]:
    """Generates path_count independent ReturnPaths, each horizon_years long
    starting at start_plan_year, via the correlated-normal transform
    (research.md §3), consuming random.Random(seed) in a fixed order: path
    0's years in order, then path 1's, etc. -- two .gauss() calls per
    plan year, z1 before z2 (FR-001). Raises ValueError if path_count <= 0
    (FR-006). generation_mode="parametric"; figures_used=[] for every path."""


def generate_historical_bootstrap_paths(
    market_assumptions: MarketAssumptions,  # from retirement_planner.scenario -- allocation weights
                                             # only (equity_allocation/bond_allocation); the mean/std
                                             # fields are not used in this mode (research.md §4)
    path_count: int,
    horizon_years: int,
    start_plan_year: int,
    seed: int,
    block_length: int,
) -> list[ReturnPath]:
    """Generates path_count independent ReturnPaths via moving-block
    bootstrap resampling from HISTORICAL_RETURNS (research.md §4):
    repeatedly picks a random contiguous block_length-year window from the
    documented historical years, concatenates blocks until horizon_years
    is reached, truncates to exactly horizon_years. Each drawn year's
    (equity_return, bond_return) pair is blended into one value using
    market_assumptions.equity_allocation/bond_allocation, the same
    allocation-weighting formula generate_return_paths() uses (research.md
    §3) -- market_assumptions.*_mean_real and *_std_real are not used in
    this mode, since the resampled historical figures stand in for them.
    Raises ValueError if block_length exceeds the number of documented
    historical years, or if block_length <= 0 (FR-013).
    generation_mode="historical_bootstrap"; figures_used includes
    HISTORICAL_RETURNS.usage_for_year() for every historical year drawn
    into each path."""


def apply_stress_scenario(
    paths: list[ReturnPath],
    stress: StressScenario,
    horizon_last_plan_year: int,
) -> list[ReturnPath]:
    """Returns a new list[ReturnPath] (paths is not mutated) with every
    path's annual_returns overridden to stress.magnitude for plan years in
    [stress.start_plan_year, stress.start_plan_year + stress.duration_years),
    every other year unchanged, generation_mode and figures_used carried
    through unchanged (FR-014, FR-016). Raises ValueError if
    stress.start_plan_year + stress.duration_years - 1 > horizon_last_plan_year
    (FR-015)."""
```

## Operations (`monte_carlo`)

```python
def run_simulation(
    household: Household,                    # from retirement_planner.scenario
    accounts: AccountBalances,                # from retirement_planner.mechanics
    annual_spending_need: float,
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    strategy: StrategyConfiguration,          # from retirement_planner.comparison
    return_paths: list[ReturnPath],
    candidate_label: str,
    survival_curves: dict[str, SurvivalCurve] | None = None,  # person_name -> curve; None = not requested
) -> SimulationRun:
    """Calls run_plan_projection() once per entry in return_paths, each with
    that path substituted as the strategy's return_assumption (research.md
    §1), holding every other input fixed (FR-002). Aggregates the resulting
    PlanProjections into success_rate (share with outcome.first_shortfall_plan_year
    is None, FR-003), percentile_bands (FR-003), and, if survival_curves is
    given, survival_adjusted_success_rate (FR-017, research.md §5) --
    otherwise that field is None. Raises ValueError if return_paths is
    empty (FR-006). Raises KeyError if survival_curves is given but omits
    a household member's person_name (FR-018), or if a path's
    return_for_plan_year() is called for a plan_year outside its covered
    range (a caller precondition: return_paths must cover at least as many
    plan years as the horizon requires). Dispatches path-level work across
    worker processes once path_count exceeds an implementation-chosen
    threshold (research.md §7); identical inputs always produce identical
    output regardless of dispatch (Principle II)."""
```

## Operations (`compare`)

```python
def compare_states(
    household: Household,
    accounts: AccountBalances,
    annual_spending_need: float,
    states: list[str],                        # candidates -- e.g. 9 state codes
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    strategy: StrategyConfiguration,
    return_paths: list[ReturnPath],
    survival_curves: dict[str, SurvivalCurve] | None = None,
) -> SimulationComparisonResult:
    """Calls run_simulation() once per entry in states, holding strategy,
    return_paths, and every other argument fixed -- only state differs
    (FR-007, FR-009). Returns a SimulationComparisonResult with
    axis="state" (research.md §2). Requires every state in states to be a
    key of retirement_planner.tax.STATE_MODULES -- raises KeyError
    otherwise, per 002's compute_state_tax() contract."""


def compare_roth_conversion_strategies(
    household: Household, accounts: AccountBalances, annual_spending_need: float,
    state: str, reference_tax_year: int, start_plan_year: int, start_tax_year: int,
    plan_to_age: int, withdrawal_strategy: str, claiming_ages: dict[str, int],
    return_paths: list[ReturnPath], candidates: list[StrategyConfiguration],
    survival_curves: dict[str, SurvivalCurve] | None = None,
) -> SimulationComparisonResult:
    """Calls run_simulation() once per entry in candidates, forcing this
    call's shared withdrawal_strategy/claiming_ages onto every candidate
    (mirrors 004's compare_roth_conversion_strategies() exactly, plus
    return_paths in place of return_assumption). Returns a
    SimulationComparisonResult with axis="roth_conversion_strategy"."""


def compare_withdrawal_sequencing_strategies(
    household: Household, accounts: AccountBalances, annual_spending_need: float,
    state: str, reference_tax_year: int, start_plan_year: int, start_tax_year: int,
    plan_to_age: int, conversion_strategy: str | None,
    conversion_bracket_ceiling_or_amount: float | None, conversion_window: tuple[int, int] | None,
    claiming_ages: dict[str, int], return_paths: list[ReturnPath],
    candidates: list[StrategyConfiguration],
    survival_curves: dict[str, SurvivalCurve] | None = None,
) -> SimulationComparisonResult:
    """Mirrors 004's compare_withdrawal_sequencing_strategies() exactly,
    plus return_paths in place of return_assumption. Returns a
    SimulationComparisonResult with axis="withdrawal_sequencing"."""


def compare_claiming_age_grid(
    household: Household, accounts: AccountBalances, annual_spending_need: float,
    state: str, reference_tax_year: int, start_plan_year: int, start_tax_year: int,
    plan_to_age: int, withdrawal_strategy: str, conversion_strategy: str | None,
    conversion_bracket_ceiling_or_amount: float | None, conversion_window: tuple[int, int] | None,
    return_paths: list[ReturnPath], claiming_age_grid: list[dict[str, int]],
    survival_curves: dict[str, SurvivalCurve] | None = None,
) -> SimulationComparisonResult:
    """Mirrors 004's compare_claiming_age_grid() exactly, plus return_paths
    in place of return_assumption. Raises ValueError if any claiming age
    falls outside 62-70 inclusive (FR-010's bounds, same as 004's own
    FR-010). Returns a SimulationComparisonResult with axis="claiming_age_grid"."""
```

Every `compare_*()` function raises `ValueError` if the `return_paths` its candidates would each receive don't all share the same `generation_mode` (they can't — the same `list[ReturnPath]` object is passed to every candidate, so this is structurally guaranteed rather than checked per call, per research.md §2) and requires `len(candidates)` (or `len(states)`/`len(claiming_age_grid)`) to be at least 1 (FR-010, matching `004`'s FR-011 precedent) rather than requiring at least two.

## Consumption expectations for downstream features

- `run_simulation()` is the finest-grained entry point a future Reporting feature (§3.6) needs for a single configuration's fan chart and success-rate figure; `compare_*()` is what it needs for an overlay chart across a comparison axis (source document §3.6 "should generalize to any comparison axis").
- `SimulationComparisonResult.runs` preserves the order candidates were supplied in, mirroring `004`'s `ComparisonResult.projections` convention.
- `SimulationRun.figures_used` is the single place a downstream reporting feature should look to render "needs verification" flags for a simulation run, exactly as `004`'s `PlanYearProjection.figures_used` already establishes for a single year — this feature's union is across paths and years, not a fresh derivation, so it never drops a flag any of `002`, `003`, `004`, or this feature's own historical/survival figures already raised.
- A caller wanting a stress-tested simulation calls `apply_stress_scenario()` on an already-generated Paired-Draw Set before calling `run_simulation()`/`compare_*()` — this module does not accept a `StressScenario` argument directly on those entry points, keeping the "paths are pre-generated, then consumed" separation of concerns clean (research.md §2, §7).
- A caller wanting the reference-scale state comparison (source document's 9 candidate states) is limited to whichever states `002-tax-calculation-engine` has registered in `STATE_MODULES` at the time (currently `SC`, `DE`, `FL` — research.md notes this is `002`'s scope to extend, not this feature's).
