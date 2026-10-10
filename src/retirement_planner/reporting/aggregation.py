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
    deemed_rmd_owner,
    member_age_in_tax_year,
)
from retirement_planner.scenario import Household
from retirement_planner.simulation import SimulationComparisonResult, SimulationRun

from .models import FigureCitation, SummaryStatistics


def unverified_figure_names(figures_used) -> list[str]:
    """Deduplicates by name (not (name, last_verified)) -- see research.md
    §5: a reader wants to know *which* figures are unverified, not how
    many differently-dated citations of the same figure exist.

    Renamed from private to public in 028-results-walkthrough
    (research.md §4) so narrative.py's build_year_stories() can reuse this
    exact derivation per plan year, rather than re-implementing it --
    behavior unchanged."""
    return sorted({figure.name for figure in figures_used if not figure.verified})


def figure_citations(figures_used) -> list[FigureCitation]:
    """rp-4p3: every distinct figure in figures_used -- verified ones
    included, unlike unverified_figure_names above -- with its real
    citation string and verified/last_verified status preserved (neither
    is discarded the way unverified_figure_names discards everything but
    the name). Deduplicates by name, same rationale as
    unverified_figure_names: a reader (or an AI answering on their
    behalf) wants to know each figure's own current citation, not every
    differently-dated snapshot of the same figure across a multi-year
    projection. When the same figure name appears more than once, the
    first occurrence's citation/verified/last_verified wins -- in
    practice the same SourcedFigure's own citation is stable across any
    one plan year's computation, so this tie-break is never actually
    exercised by real data; it exists only so the function has
    deterministic behavior if that assumption is ever violated.

    Sorted by name, mirroring unverified_figure_names' own sorted-list
    convention (FR-006: deterministic, byte-identical output for
    identical input)."""
    by_name: dict[str, FigureCitation] = {}
    for figure in figures_used:
        if figure.name not in by_name:
            by_name[figure.name] = FigureCitation(
                name=figure.name,
                citation=figure.citation,
                verified=figure.verified,
                last_verified=figure.last_verified,
            )
    return [by_name[name] for name in sorted(by_name)]


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
        survival_adjusted_success_rate=run.survival_adjusted_success_rate,
        ending_balance=ending_balance,
        percentile_bands=run.percentile_bands,
        median_depletion_age=median_depletion_age,
        median_lifetime_tax_paid=median_lifetime_tax_paid,
        median_lifetime_irmaa_paid=median_lifetime_irmaa_paid,
        median_lifetime_niit_paid=median_lifetime_niit_paid,
        median_lifetime_early_withdrawal_penalty_paid=median_lifetime_early_withdrawal_penalty_paid,
        median_lifetime_fica_tax_paid=median_lifetime_fica_tax_paid,
        unverified_figure_names=unverified_figure_names(run.figures_used),
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
        survival_adjusted_success_rate=None,  # no Monte Carlo distribution to score (research.md §2)
        ending_balance=projection.outcome.ending_balance,
        percentile_bands=None,
        median_depletion_age=_depletion_age(projection, household, reference_tax_year),
        median_lifetime_tax_paid=projection.outcome.cumulative_tax_paid,
        median_lifetime_irmaa_paid=projection.outcome.cumulative_irmaa_paid,
        median_lifetime_niit_paid=projection.outcome.cumulative_niit_paid,
        median_lifetime_early_withdrawal_penalty_paid=projection.outcome.cumulative_early_withdrawal_penalty_paid,
        median_lifetime_fica_tax_paid=projection.outcome.cumulative_fica_tax_paid,
        unverified_figure_names=unverified_figure_names(figures),
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
