"""Public API for reporting & aggregation: turning 004's ComparisonResult
and 005's SimulationRun/SimulationComparisonResult into decision-ready
summary statistics and spreadsheet-ready CSV exports.

See specs/006-reporting-aggregation/contracts/reporting-api.md for the
locked contract downstream features (007 BFF API Service) should code
against.
"""

from .account_attribution import (
    AccountShare,
    AccountYearDetail,
    PlanYearAccountDetail,
    attribute_plan_projection,
    compute_account_shares,
)
from .aggregation import summarize_deterministic_comparison, summarize_run, summarize_simulation_comparison
from .export import deterministic_comparison_to_csv_text, run_to_csv_text, simulation_comparison_to_csv_text
from .models import SummaryStatistics

__all__ = [
    "AccountShare",
    "AccountYearDetail",
    "PlanYearAccountDetail",
    "SummaryStatistics",
    "attribute_plan_projection",
    "compute_account_shares",
    "deterministic_comparison_to_csv_text",
    "run_to_csv_text",
    "simulation_comparison_to_csv_text",
    "summarize_deterministic_comparison",
    "summarize_run",
    "summarize_simulation_comparison",
]
