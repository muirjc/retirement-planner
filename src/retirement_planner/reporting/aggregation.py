"""Summary-statistics aggregation (FR-001-FR-007): turns a completed
SimulationRun, SimulationComparisonResult, or ComparisonResult into
decision-ready SummaryStatistics. Pure functions over already-computed
004/005 output -- no new tax, mechanics, comparison, or simulation
computation (FR-014). See specs/006-reporting-aggregation/research.md and
contracts/reporting-api.md.
"""

from __future__ import annotations

import statistics

from retirement_planner.comparison import (
    ComparisonResult,
    PlanProjection,
    StrategyConfiguration,
    deemed_rmd_owner,
    member_age_in_tax_year,
)
from retirement_planner.scenario import Household
from retirement_planner.simulation import SimulationComparisonResult, SimulationRun

from .models import SummaryStatistics


def _unverified_figure_names(figures_used) -> list[str]:
    """Deduplicates by name (not (name, last_verified)) -- see research.md
    §5: a reader wants to know *which* figures are unverified, not how
    many differently-dated citations of the same figure exist."""
    return sorted({figure.name for figure in figures_used if not figure.verified})


def _depletion_age(projection: PlanProjection, household: Household, reference_tax_year: int) -> float | None:
    """The deemed owner's age at the plan year a projection's outcome
    first fell short, or None if it never did (research.md §1)."""
    first_shortfall_plan_year = projection.outcome.first_shortfall_plan_year
    if first_shortfall_plan_year is None:
        return None
    shortfall_year = next(year for year in projection.years if year.plan_year == first_shortfall_plan_year)
    owner = deemed_rmd_owner(household)
    return float(member_age_in_tax_year(owner, shortfall_year.tax_year, reference_tax_year))


def summarize_run(run: SimulationRun, household: Household, reference_tax_year: int) -> SummaryStatistics:
    """Summarizes one completed SimulationRun (FR-001-FR-004). See
    contracts/reporting-api.md for the exact field-by-field derivation."""
    depletion_ages = [
        age
        for age in (_depletion_age(path, household, reference_tax_year) for path in run.path_results)
        if age is not None
    ]
    median_depletion_age = statistics.median(depletion_ages) if depletion_ages else None

    median_lifetime_tax_paid = statistics.median(
        path.outcome.cumulative_tax_paid for path in run.path_results
    )
    median_lifetime_irmaa_paid = statistics.median(
        path.outcome.cumulative_irmaa_paid for path in run.path_results
    )
    median_lifetime_niit_paid = statistics.median(
        path.outcome.cumulative_niit_paid for path in run.path_results
    )
    median_lifetime_early_withdrawal_penalty_paid = statistics.median(
        path.outcome.cumulative_early_withdrawal_penalty_paid for path in run.path_results
    )
    median_lifetime_fica_tax_paid = statistics.median(
        path.outcome.cumulative_fica_tax_paid for path in run.path_results
    )

    ending_balance = run.percentile_bands[-1].percentiles[0.50]

    return SummaryStatistics(
        candidate_label=None,
        success_rate=run.success_rate,
        ending_balance=ending_balance,
        percentile_bands=run.percentile_bands,
        median_depletion_age=median_depletion_age,
        median_lifetime_tax_paid=median_lifetime_tax_paid,
        median_lifetime_irmaa_paid=median_lifetime_irmaa_paid,
        median_lifetime_niit_paid=median_lifetime_niit_paid,
        median_lifetime_early_withdrawal_penalty_paid=median_lifetime_early_withdrawal_penalty_paid,
        median_lifetime_fica_tax_paid=median_lifetime_fica_tax_paid,
        unverified_figure_names=_unverified_figure_names(run.figures_used),
    )


def summarize_simulation_comparison(
    comparison: SimulationComparisonResult, household: Household, reference_tax_year: int
) -> list[SummaryStatistics]:
    """One summary per candidate, in comparison.runs' order, each set from
    summarize_run() with candidate_label overwritten (FR-005, research.md
    §4)."""
    summaries = []
    for run in comparison.runs:
        summary = summarize_run(run, household, reference_tax_year)
        summary.candidate_label = run.candidate_label
        summaries.append(summary)
    return summaries


def _summarize_plan_projection(
    projection: PlanProjection, household: Household, reference_tax_year: int
) -> SummaryStatistics:
    """A deterministic (004) candidate's summary: success_rate and
    percentile_bands are None (research.md §2) -- a single fixed-return
    path has no distribution to report either over."""
    figures = [figure for year in projection.years for figure in year.figures_used]
    return SummaryStatistics(
        candidate_label=projection.strategy.label,
        success_rate=None,
        ending_balance=projection.outcome.ending_balance,
        percentile_bands=None,
        median_depletion_age=_depletion_age(projection, household, reference_tax_year),
        median_lifetime_tax_paid=projection.outcome.cumulative_tax_paid,
        median_lifetime_irmaa_paid=projection.outcome.cumulative_irmaa_paid,
        median_lifetime_niit_paid=projection.outcome.cumulative_niit_paid,
        median_lifetime_early_withdrawal_penalty_paid=projection.outcome.cumulative_early_withdrawal_penalty_paid,
        median_lifetime_fica_tax_paid=projection.outcome.cumulative_fica_tax_paid,
        unverified_figure_names=_unverified_figure_names(figures),
    )


def summarize_deterministic_comparison(
    comparison: ComparisonResult, household: Household, reference_tax_year: int
) -> list[SummaryStatistics]:
    """One summary per candidate, in comparison.projections' order
    (FR-006, research.md §2, §4)."""
    return [
        _summarize_plan_projection(projection, household, reference_tax_year)
        for projection in comparison.projections
    ]
