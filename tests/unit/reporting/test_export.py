"""Unit tests for retirement_planner.reporting.export: CSV row shaping for
a single run (US3) and for comparisons of both kinds (US3), including the
per-row verification-status column (US3.3, US4).
"""

import copy
import csv
import io
from datetime import date

import pytest

from retirement_planner.comparison import (
    ComparisonResult,
    DeterministicReturnAssumption,
    StrategyConfiguration,
    run_plan_projection,
)
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember
from retirement_planner.simulation import PercentileBand, SimulationComparisonResult, SimulationRun
from retirement_planner.tax import FigureUsage

_HOUSEHOLD = Household(
    filing_status="single",
    members=[HouseholdMember(person_name="you", current_age=75, ss_claim_age=99, ss_annual_benefit=0)],
)
_STRATEGY = StrategyConfiguration(
    label="test",
    withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy=None,
    conversion_bracket_ceiling_or_amount=None,
    conversion_window=None,
    claiming_ages={"you": 99},
)
_COMMON_KWARGS = dict(
    household=_HOUSEHOLD,
    state="FL",
    reference_tax_year=2026,
    start_plan_year=1,
    start_tax_year=2026,
    plan_to_age=76,  # 2 plan years
    strategy=_STRATEGY,
)


def _projection(traditional, taxable, spending_need):
    accounts = AccountBalances(traditional=traditional, roth=0, taxable=taxable)
    return run_plan_projection(
        **_COMMON_KWARGS,
        accounts=accounts,
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=spending_need,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )


_PROJECTION_A = _projection(traditional=200_000, taxable=1_000_000, spending_need=20_000)
_PROJECTION_B = _projection(traditional=10_000, taxable=0, spending_need=500_000)  # depletes

_PERCENTILE_BANDS = [
    PercentileBand(plan_year=1, percentiles={0.10: 100.0, 0.50: 150.0, 0.90: 200.0}),
    PercentileBand(plan_year=2, percentiles={0.10: 90.0, 0.50: 140.0, 0.90: 190.0}),
]


def _run(path_results=None, percentile_bands=None, candidate_label="test", figures_used=None):
    path_results = path_results if path_results is not None else [_PROJECTION_A, _PROJECTION_B]
    return SimulationRun(
        candidate_label=candidate_label,
        strategy=_STRATEGY,
        state="FL",
        path_results=path_results,
        success_rate=0.5,
        percentile_bands=percentile_bands if percentile_bands is not None else _PERCENTILE_BANDS,
        survival_adjusted_success_rate=None,
        figures_used=figures_used if figures_used is not None else [],
    )


def _rows(csv_text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(csv_text)))


# --- run_to_csv_text() ---


def test_run_to_csv_text_has_one_row_per_plan_year_with_percentile_columns():
    from retirement_planner.reporting.export import run_to_csv_text

    run = _run()
    text = run_to_csv_text(run)
    rows = _rows(text)

    assert len(rows) == len(run.percentile_bands) == 2
    assert rows[0]["plan_year"] == "1"
    assert rows[1]["plan_year"] == "2"
    assert float(rows[0]["p10"]) == pytest.approx(100.0)
    assert float(rows[0]["p50"]) == pytest.approx(150.0)
    assert float(rows[0]["p90"]) == pytest.approx(200.0)


def test_run_to_csv_text_has_unverified_figure_column_reflects_path_zero():
    from retirement_planner.reporting.export import run_to_csv_text

    # This household/state (single filer, FL -- no state-tax figure, no
    # spouse -- no joint-life table) draws only on federal-tax and RMD
    # figures that 014-figure-verification has since cross-checked and
    # verified: has_unverified_figure is false for every row of a real
    # run built from it. Confirm that, then confirm the column still
    # flips to true when a path's year figures are (deliberately) made
    # to include an unverified one.
    run = _run()
    text = run_to_csv_text(run)
    rows = _rows(text)
    assert all(row["has_unverified_figure"] == "False" for row in rows)

    # Deep-copy before mutating -- run.path_results[0] is the shared,
    # module-level _PROJECTION_A fixture; mutating it in place would leak
    # into other tests.
    unverified_run = copy.deepcopy(run)
    an_unverified_figure = [
        FigureUsage(name="f", citation="c", last_verified=date(2026, 1, 1), verified=False)
    ]
    unverified_run.path_results[0].years[0].figures_used = an_unverified_figure
    unverified_run.path_results[0].years[1].figures_used = an_unverified_figure

    text = run_to_csv_text(unverified_run)
    rows = _rows(text)
    assert all(row["has_unverified_figure"] == "True" for row in rows)


# --- simulation_comparison_to_csv_text() / deterministic_comparison_to_csv_text() ---


def test_simulation_comparison_to_csv_text_has_one_row_per_candidate_clearly_labeled():
    from retirement_planner.reporting.export import simulation_comparison_to_csv_text

    run_a = _run(path_results=[_PROJECTION_A], candidate_label="candidate_a")
    run_b = _run(path_results=[_PROJECTION_B], candidate_label="candidate_b")
    comparison = SimulationComparisonResult(axis="state", return_paths=[], runs=[run_a, run_b])

    text = simulation_comparison_to_csv_text(comparison, household=_HOUSEHOLD, reference_tax_year=2026)
    rows = _rows(text)

    assert len(rows) == 2
    assert {row["candidate_label"] for row in rows} == {"candidate_a", "candidate_b"}


def test_deterministic_comparison_to_csv_text_leaves_success_rate_blank():
    from retirement_planner.reporting.export import deterministic_comparison_to_csv_text

    comparison = ComparisonResult(
        dimension="roth_conversion_strategy",
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
        projections=[_PROJECTION_A, _PROJECTION_B],
    )

    text = deterministic_comparison_to_csv_text(comparison, household=_HOUSEHOLD, reference_tax_year=2026)
    rows = _rows(text)

    assert len(rows) == 2
    assert all(row["success_rate"] == "" for row in rows)


def test_comparison_exports_include_has_unverified_figure_column():
    from retirement_planner.reporting.export import deterministic_comparison_to_csv_text, simulation_comparison_to_csv_text

    sim_comparison = SimulationComparisonResult(
        axis="state", return_paths=[], runs=[_run(path_results=[_PROJECTION_A])]
    )
    det_comparison = ComparisonResult(
        dimension="withdrawal_sequencing",
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
        projections=[_PROJECTION_A],
    )

    sim_text = simulation_comparison_to_csv_text(sim_comparison, household=_HOUSEHOLD, reference_tax_year=2026)
    det_text = deterministic_comparison_to_csv_text(det_comparison, household=_HOUSEHOLD, reference_tax_year=2026)

    assert "has_unverified_figure" in sim_text.splitlines()[0]
    assert "has_unverified_figure" in det_text.splitlines()[0]


def test_comparison_exports_include_irmaa_and_niit_columns():
    """010-advanced-tax-benefits T031: mirrors the has_unverified_figure
    column check above for the two new cumulative-figure columns."""
    from retirement_planner.reporting.export import deterministic_comparison_to_csv_text, simulation_comparison_to_csv_text

    sim_comparison = SimulationComparisonResult(
        axis="state", return_paths=[], runs=[_run(path_results=[_PROJECTION_A])]
    )
    det_comparison = ComparisonResult(
        dimension="withdrawal_sequencing",
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
        projections=[_PROJECTION_A],
    )

    sim_text = simulation_comparison_to_csv_text(sim_comparison, household=_HOUSEHOLD, reference_tax_year=2026)
    det_text = deterministic_comparison_to_csv_text(det_comparison, household=_HOUSEHOLD, reference_tax_year=2026)

    for header in sim_text.splitlines()[0], det_text.splitlines()[0]:
        assert "median_lifetime_irmaa_paid" in header
        assert "median_lifetime_niit_paid" in header

    det_rows = _rows(det_text)
    assert det_rows[0]["median_lifetime_irmaa_paid"] == str(_PROJECTION_A.outcome.cumulative_irmaa_paid)
    assert det_rows[0]["median_lifetime_niit_paid"] == str(_PROJECTION_A.outcome.cumulative_niit_paid)
