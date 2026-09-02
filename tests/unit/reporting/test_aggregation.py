"""Unit tests for retirement_planner.reporting.aggregation: summarize_run()
(US1), summarize_simulation_comparison()/summarize_deterministic_comparison()
(US2), unverified-figure surfacing (US4), and deduplication (Polish).

Fixtures build real PlanProjection objects via 004's already-tested
run_plan_projection() (varying traditional balance to get genuinely
different cumulative_tax_paid, and varying taxable balance/spending to get
a genuine shortfall), then assemble them into SimulationRun/
SimulationComparisonResult/ComparisonResult objects directly -- this tests
006's own aggregation logic in isolation, without depending on 005's Monte
Carlo internals (already tested in 005's own suite).
"""

import statistics
from dataclasses import replace
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
    plan_to_age=76,  # 2 plan years: ages 75 and 76
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


# Three real projections: A and B have ample taxable balances (no shortfall)
# but different traditional balances (so genuinely different RMD-driven
# cumulative_tax_paid); C has a tiny balance against large spending (a real
# shortfall, at plan_year=1 -> tax_year=2026 -> age 75). A and B's traditional
# balances are large enough that RMD-driven ordinary income clears the
# household's federal standard deduction (rp-7me; single filer, one member
# age 75+ so base + age-65 addition applies) -- otherwise both would owe
# $0 and this fixture could no longer demonstrate "genuinely different".
_PROJECTION_A = _projection(traditional=700_000, taxable=1_000_000, spending_need=20_000)
_PROJECTION_B = _projection(traditional=1_100_000, taxable=1_000_000, spending_need=20_000)
_PROJECTION_C = _projection(traditional=10_000, taxable=0, spending_need=500_000)


def _percentile_bands_from_projections(projections):
    """A minimal, test-only stand-in for 005's own percentile aggregation:
    one band per plan year, with a single 0.50 (median) entry -- enough for
    summarize_run()'s ending_balance derivation, without needing 005's
    full multi-percentile machinery for these isolated aggregation tests.
    """
    if not projections:
        return []
    horizon = len(projections[0].years)
    bands = []
    for index in range(horizon):
        plan_year = projections[0].years[index].plan_year
        balances = [
            p.years[index].ending_balances.traditional
            + p.years[index].ending_balances.roth
            + p.years[index].ending_balances.taxable
            for p in projections
        ]
        bands.append(PercentileBand(plan_year=plan_year, percentiles={0.50: statistics.median(balances)}))
    return bands


def _run_from_projections(path_results, success_rate, percentile_bands=None, candidate_label="test"):
    return SimulationRun(
        candidate_label=candidate_label,
        strategy=_STRATEGY,
        state="FL",
        path_results=path_results,
        success_rate=success_rate,
        percentile_bands=percentile_bands if percentile_bands is not None else _percentile_bands_from_projections(path_results),
        survival_adjusted_success_rate=None,
        figures_used=[fig for p in path_results for year in p.years for fig in year.figures_used],
    )


# --- summarize_run() (US1) ---


def test_success_rate_and_percentile_bands_pass_through_unchanged():
    from retirement_planner.reporting.aggregation import summarize_run

    bands = [PercentileBand(plan_year=1, percentiles={0.5: 100.0}), PercentileBand(plan_year=2, percentiles={0.5: 90.0})]
    run = _run_from_projections([_PROJECTION_A, _PROJECTION_B], success_rate=1.0, percentile_bands=bands)

    summary = summarize_run(run, household=_HOUSEHOLD, reference_tax_year=2026)

    assert summary.success_rate == run.success_rate
    assert summary.percentile_bands == run.percentile_bands
    assert summary.candidate_label is None


def test_median_depletion_age_computed_only_from_depleted_paths():
    from retirement_planner.reporting.aggregation import summarize_run

    run = _run_from_projections([_PROJECTION_A, _PROJECTION_B, _PROJECTION_C], success_rate=2 / 3)

    summary = summarize_run(run, household=_HOUSEHOLD, reference_tax_year=2026)

    # Only C depletes, at plan_year=1 -> tax_year=2026 -> age 75 (current_age
    # unchanged since reference_tax_year == tax_year).
    assert summary.median_depletion_age == pytest.approx(75.0)


def test_median_depletion_age_is_none_when_nothing_depletes():
    from retirement_planner.reporting.aggregation import summarize_run

    run = _run_from_projections([_PROJECTION_A, _PROJECTION_B], success_rate=1.0)

    summary = summarize_run(run, household=_HOUSEHOLD, reference_tax_year=2026)

    assert summary.median_depletion_age is None


def test_median_lifetime_tax_paid_includes_depleted_paths():
    from retirement_planner.reporting.aggregation import summarize_run

    projections = [_PROJECTION_A, _PROJECTION_B, _PROJECTION_C]
    run = _run_from_projections(projections, success_rate=2 / 3)

    summary = summarize_run(run, household=_HOUSEHOLD, reference_tax_year=2026)

    expected = statistics.median(p.outcome.cumulative_tax_paid for p in projections)
    assert summary.median_lifetime_tax_paid == pytest.approx(expected)
    # Sanity: the three projections' tax figures are not all identical, so
    # this assertion would fail if depleted-path C were silently excluded.
    tax_values = {p.outcome.cumulative_tax_paid for p in projections}
    assert len(tax_values) > 1


def test_median_lifetime_early_withdrawal_penalty_paid_derived_from_plan_outcome():
    """020-early-withdrawal-penalty: median_lifetime_early_withdrawal_penalty_paid
    is derived the same way median_lifetime_irmaa_paid/median_lifetime_niit_paid
    already are -- the median across paths' own
    PlanOutcome.cumulative_early_withdrawal_penalty_paid."""
    from retirement_planner.reporting.aggregation import summarize_run

    projections = [_PROJECTION_A, _PROJECTION_B, _PROJECTION_C]
    run = _run_from_projections(projections, success_rate=2 / 3)

    summary = summarize_run(run, household=_HOUSEHOLD, reference_tax_year=2026)

    expected = statistics.median(p.outcome.cumulative_early_withdrawal_penalty_paid for p in projections)
    assert summary.median_lifetime_early_withdrawal_penalty_paid == pytest.approx(expected)


def test_median_lifetime_fica_tax_paid_derived_from_plan_outcome():
    """022-fica-payroll-tax (rp-elp): median_lifetime_fica_tax_paid is
    derived the same way median_lifetime_early_withdrawal_penalty_paid
    already is -- the median across paths' own
    PlanOutcome.cumulative_fica_tax_paid."""
    from retirement_planner.reporting.aggregation import summarize_run

    projections = [_PROJECTION_A, _PROJECTION_B, _PROJECTION_C]
    run = _run_from_projections(projections, success_rate=2 / 3)

    summary = summarize_run(run, household=_HOUSEHOLD, reference_tax_year=2026)

    expected = statistics.median(p.outcome.cumulative_fica_tax_paid for p in projections)
    assert summary.median_lifetime_fica_tax_paid == pytest.approx(expected)


def test_summarize_deterministic_comparison_includes_fica_tax():
    """022-fica-payroll-tax (rp-elp): the deterministic path
    (_summarize_plan_projection()) surfaces cumulative_fica_tax_paid
    directly, the same "single value, no median needed" convention every
    other median_lifetime_X_paid field already follows for one candidate."""
    from retirement_planner.reporting.aggregation import summarize_deterministic_comparison

    comparison = ComparisonResult(
        dimension="withdrawal_sequencing",
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.03),
        projections=[_PROJECTION_A],
    )
    summaries = summarize_deterministic_comparison(comparison, household=_HOUSEHOLD, reference_tax_year=2026)
    assert summaries[0].median_lifetime_fica_tax_paid == _PROJECTION_A.outcome.cumulative_fica_tax_paid


def test_summarize_run_is_repeatable():
    from retirement_planner.reporting.aggregation import summarize_run

    run = _run_from_projections([_PROJECTION_A, _PROJECTION_C], success_rate=0.5)

    first = summarize_run(run, household=_HOUSEHOLD, reference_tax_year=2026)
    second = summarize_run(run, household=_HOUSEHOLD, reference_tax_year=2026)

    assert first == second


# --- summarize_simulation_comparison() / summarize_deterministic_comparison() (US2) ---


def test_summarize_simulation_comparison_matches_summarize_run_per_candidate():
    from retirement_planner.reporting.aggregation import summarize_run, summarize_simulation_comparison

    run_a = _run_from_projections([_PROJECTION_A], success_rate=1.0, candidate_label="A")
    run_b = _run_from_projections([_PROJECTION_B, _PROJECTION_C], success_rate=0.5, candidate_label="B")
    comparison = SimulationComparisonResult(axis="state", return_paths=[], runs=[run_a, run_b])

    summaries = summarize_simulation_comparison(comparison, household=_HOUSEHOLD, reference_tax_year=2026)

    assert len(summaries) == 2
    assert summaries[0].candidate_label == "A"
    assert summaries[1].candidate_label == "B"
    # Every field matches summarize_run() on that candidate directly, aside
    # from candidate_label (None for a standalone run, set here from the
    # comparison's own run.candidate_label per research.md §4).
    assert replace(summaries[0], candidate_label=None) == summarize_run(run_a, household=_HOUSEHOLD, reference_tax_year=2026)
    assert replace(summaries[1], candidate_label=None) == summarize_run(run_b, household=_HOUSEHOLD, reference_tax_year=2026)


def test_summarize_deterministic_comparison_marks_monte_carlo_fields_not_applicable():
    from retirement_planner.reporting.aggregation import summarize_deterministic_comparison

    comparison = ComparisonResult(
        dimension="roth_conversion_strategy",
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
        projections=[_PROJECTION_A, _PROJECTION_C],
    )

    summaries = summarize_deterministic_comparison(comparison, household=_HOUSEHOLD, reference_tax_year=2026)

    assert len(summaries) == 2
    for summary in summaries:
        assert summary.success_rate is None
        assert summary.percentile_bands is None
        assert isinstance(summary.ending_balance, float)
    # Candidate labels come from StrategyConfiguration.label -- both share
    # the fixture's "test" label here, which is fine; this asserts they're
    # present, not that they're distinct.
    assert summaries[0].candidate_label == "test"


def test_both_comparison_summarizers_accept_a_single_candidate():
    from retirement_planner.reporting.aggregation import summarize_deterministic_comparison, summarize_simulation_comparison

    sim_comparison = SimulationComparisonResult(
        axis="state", return_paths=[], runs=[_run_from_projections([_PROJECTION_A], success_rate=1.0)]
    )
    det_comparison = ComparisonResult(
        dimension="withdrawal_sequencing",
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
        projections=[_PROJECTION_A],
    )

    assert len(summarize_simulation_comparison(sim_comparison, household=_HOUSEHOLD, reference_tax_year=2026)) == 1
    assert len(summarize_deterministic_comparison(det_comparison, household=_HOUSEHOLD, reference_tax_year=2026)) == 1


# --- unverified-figure surfacing (US4) ---


def _figure(name, verified):
    return FigureUsage(name=name, citation="test", last_verified=date(2026, 1, 1), verified=verified)


def test_unverified_figure_names_includes_only_unverified_distinct_names():
    from retirement_planner.reporting.aggregation import summarize_run

    run = _run_from_projections([_PROJECTION_A], success_rate=1.0)
    run.figures_used = [_figure("verified_one", True), _figure("unverified_one", False), _figure("unverified_two", False)]

    summary = summarize_run(run, household=_HOUSEHOLD, reference_tax_year=2026)

    assert set(summary.unverified_figure_names) == {"unverified_one", "unverified_two"}


def test_unverified_figure_names_present_and_empty_when_nothing_unverified():
    from retirement_planner.reporting.aggregation import summarize_run

    run = _run_from_projections([_PROJECTION_A], success_rate=1.0)
    run.figures_used = [_figure("verified_one", True)]

    summary = summarize_run(run, household=_HOUSEHOLD, reference_tax_year=2026)

    assert summary.unverified_figure_names == []


def test_unverified_figure_names_deduplicates_by_name_across_different_last_verified_dates():
    from retirement_planner.reporting.aggregation import summarize_run

    run = _run_from_projections([_PROJECTION_A], success_rate=1.0)
    run.figures_used = [
        FigureUsage(name="dupe", citation="c1", last_verified=date(2026, 1, 1), verified=False),
        FigureUsage(name="dupe", citation="c2", last_verified=date(2026, 6, 1), verified=False),
    ]

    summary = summarize_run(run, household=_HOUSEHOLD, reference_tax_year=2026)

    assert summary.unverified_figure_names == ["dupe"]
