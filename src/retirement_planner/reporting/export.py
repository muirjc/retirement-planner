"""CSV export (FR-008-FR-010): renders a SimulationRun as one row per plan
year, and a comparison result (either kind) as one row per candidate.
Stdlib csv.DictWriter over an io.StringIO -- no new dependency (FR-012).
See specs/006-reporting-aggregation/research.md §6-7 and
contracts/reporting-api.md.
"""

from __future__ import annotations

import csv
import io

from retirement_planner.comparison import ComparisonResult
from retirement_planner.scenario import Household
from retirement_planner.simulation import SimulationComparisonResult, SimulationRun

from .aggregation import summarize_deterministic_comparison, summarize_simulation_comparison
from .models import SummaryStatistics


def _rows_to_csv_text(fieldnames: list[str], rows: list[dict]) -> str:
    """Writes rows (each a dict matching fieldnames) through
    csv.DictWriter into an io.StringIO, returning the resulting text
    (header row + one line per row) (research.md §7)."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def run_to_csv_text(run: SimulationRun) -> str:
    """One row per plan year: plan_year, one column per percentile level
    present in run.percentile_bands[*].percentiles, and
    has_unverified_figure -- derived from run.path_results[0].years[y]'s
    figures_used for plan-year index y (research.md §6), true iff any
    figure there has verified=False (FR-008, FR-010)."""
    if not run.percentile_bands:
        return _rows_to_csv_text(["plan_year", "has_unverified_figure"], [])

    percentile_levels = sorted(run.percentile_bands[0].percentiles.keys())
    percentile_columns = [f"p{int(level * 100)}" for level in percentile_levels]
    fieldnames = ["plan_year", *percentile_columns, "has_unverified_figure"]

    rows = []
    for index, band in enumerate(run.percentile_bands):
        year_figures = run.path_results[0].years[index].figures_used
        row = {"plan_year": band.plan_year}
        for level, column in zip(percentile_levels, percentile_columns):
            row[column] = band.percentiles[level]
        row["has_unverified_figure"] = any(not figure.verified for figure in year_figures)
        rows.append(row)

    return _rows_to_csv_text(fieldnames, rows)


_SUMMARY_FIELDNAMES = [
    "candidate_label",
    "success_rate",
    "ending_balance",
    "median_depletion_age",
    "median_lifetime_tax_paid",
    "median_lifetime_irmaa_paid",  # 010-advanced-tax-benefits
    "median_lifetime_niit_paid",  # 010-advanced-tax-benefits
    "has_unverified_figure",
]


def _summary_to_row(summary: SummaryStatistics) -> dict:
    """Flattens one SummaryStatistics into a CSV row dict: None fields
    (not-applicable, research.md §2) render as an empty string;
    unverified_figure_names collapses to a single has_unverified_figure
    boolean (true iff non-empty) (FR-009, FR-010)."""
    return {
        "candidate_label": summary.candidate_label,
        "success_rate": "" if summary.success_rate is None else summary.success_rate,
        "ending_balance": summary.ending_balance,
        "median_depletion_age": "" if summary.median_depletion_age is None else summary.median_depletion_age,
        "median_lifetime_tax_paid": summary.median_lifetime_tax_paid,
        "median_lifetime_irmaa_paid": summary.median_lifetime_irmaa_paid,
        "median_lifetime_niit_paid": summary.median_lifetime_niit_paid,
        "has_unverified_figure": bool(summary.unverified_figure_names),
    }


def simulation_comparison_to_csv_text(
    comparison: SimulationComparisonResult, household: Household, reference_tax_year: int
) -> str:
    """Calls summarize_simulation_comparison() and renders one row per
    resulting SummaryStatistics (FR-009, FR-010)."""
    summaries = summarize_simulation_comparison(comparison, household, reference_tax_year)
    rows = [_summary_to_row(summary) for summary in summaries]
    return _rows_to_csv_text(_SUMMARY_FIELDNAMES, rows)


def deterministic_comparison_to_csv_text(
    comparison: ComparisonResult, household: Household, reference_tax_year: int
) -> str:
    """Calls summarize_deterministic_comparison() and renders the same row
    shape as simulation_comparison_to_csv_text(), with success_rate always
    blank since every candidate in a deterministic comparison has none to
    report (FR-009, FR-010, research.md §2)."""
    summaries = summarize_deterministic_comparison(comparison, household, reference_tax_year)
    rows = [_summary_to_row(summary) for summary in summaries]
    return _rows_to_csv_text(_SUMMARY_FIELDNAMES, rows)
