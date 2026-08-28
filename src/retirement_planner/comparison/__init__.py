"""Public API for the strategy comparison layer: full-horizon plan
projection, plus Roth conversion strategy, withdrawal sequencing, and
Social Security claiming-age comparisons.

See specs/004-strategy-comparison-layer/contracts/comparison-api.md for the
locked contract downstream features (simulation engine, reporting) should
code against.
"""

from .compare import (
    compare_claiming_age_grid,
    compare_roth_conversion_strategies,
    compare_withdrawal_sequencing_strategies,
)
from .models import (
    ComparisonDimension,
    ComparisonResult,
    DeterministicReturnAssumption,
    PlanOutcome,
    PlanProjection,
    PlanYearProjection,
    StrategyConfiguration,
)
from .projection import deemed_rmd_owner, member_age_in_tax_year, run_plan_projection
from .returns import derive_deterministic_return

__all__ = [
    "ComparisonDimension",
    "ComparisonResult",
    "DeterministicReturnAssumption",
    "PlanOutcome",
    "PlanProjection",
    "PlanYearProjection",
    "StrategyConfiguration",
    "compare_claiming_age_grid",
    "compare_roth_conversion_strategies",
    "compare_withdrawal_sequencing_strategies",
    "deemed_rmd_owner",
    "derive_deterministic_return",
    "member_age_in_tax_year",
    "run_plan_projection",
]
