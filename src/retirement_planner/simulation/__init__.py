"""Public API for the simulation engine: multi-path Monte Carlo simulation,
paired-draw comparison across states/strategies/orders/claiming-ages,
historical-bootstrap return generation, sequence-of-returns stress
scenarios, and survival-adjusted success scoring.

See specs/005-simulation-engine/contracts/simulation-api.md for the locked
contract downstream features (reporting) should code against.
"""

from .models import (
    ComparisonAxis,
    GenerationMode,
    PercentileBand,
    ReturnPath,
    SimulationComparisonResult,
    SimulationRun,
    StressScenario,
    SurvivalCurve,
)
from .compare import (
    compare_claiming_age_grid,
    compare_roth_conversion_strategies,
    compare_states,
    compare_withdrawal_sequencing_strategies,
)
from .historical_data import HISTORICAL_RETURNS
from .monte_carlo import run_simulation
from .mortality import generate_death_age_draws
from .returns import apply_stress_scenario, generate_historical_bootstrap_paths, generate_return_paths
from .spending_search import (
    SpendingSearchResult,
    SustainableSpendingRangeResult,
    find_sustainable_spending_range,
    search_spending_for_target_success_rate,
)
from .survival_data import SURVIVAL_TABLE

__all__ = [
    "SURVIVAL_TABLE",
    "ComparisonAxis",
    "GenerationMode",
    "HISTORICAL_RETURNS",
    "PercentileBand",
    "ReturnPath",
    "SimulationComparisonResult",
    "SimulationRun",
    "SpendingSearchResult",
    "StressScenario",
    "SurvivalCurve",
    "SustainableSpendingRangeResult",
    "apply_stress_scenario",
    "compare_claiming_age_grid",
    "compare_roth_conversion_strategies",
    "compare_states",
    "compare_withdrawal_sequencing_strategies",
    "find_sustainable_spending_range",
    "generate_death_age_draws",
    "generate_historical_bootstrap_paths",
    "generate_return_paths",
    "run_simulation",
    "search_spending_for_target_success_rate",
]
