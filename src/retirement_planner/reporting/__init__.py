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
from .aggregation import (
    summarize_deterministic_comparison,
    summarize_run,
    summarize_simulation_comparison,
    unverified_figure_names,
)
from .export import deterministic_comparison_to_csv_text, run_to_csv_text, simulation_comparison_to_csv_text
from .models import NarrativeEntry, RunNarrative, SummaryStatistics, YearStory
from .narrative import build_narrative_for_run, build_year_stories, select_representative_path

__all__ = [
    "AccountShare",
    "AccountYearDetail",
    "NarrativeEntry",
    "PlanYearAccountDetail",
    "RunNarrative",
    "SummaryStatistics",
    "YearStory",
    "attribute_plan_projection",
    "build_narrative_for_run",
    "build_year_stories",
    "compute_account_shares",
    "deterministic_comparison_to_csv_text",
    "run_to_csv_text",
    "select_representative_path",
    "simulation_comparison_to_csv_text",
    "summarize_deterministic_comparison",
    "summarize_run",
    "summarize_simulation_comparison",
    "unverified_figure_names",
]
