"""Unit tests for retirement_planner.simulation.monte_carlo.run_simulation()
(US1): success rate, percentile bands, per-path depletion tracking,
reproducibility, and figures_used deduplication (Polish, FR-019).
"""

import pytest

from retirement_planner.comparison import StrategyConfiguration
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember, MarketAssumptions
from retirement_planner.simulation.models import ReturnPath
from retirement_planner.simulation.returns import generate_return_paths

_HOUSEHOLD = Household(
    filing_status="single",
    members=[HouseholdMember(person_name="you", current_age=90, ss_claim_age=99, ss_annual_benefit=0)],
)
_ACCOUNTS = AccountBalances(traditional=0, roth=0, taxable=100)
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
    accounts=_ACCOUNTS,
    traditional_ownership_shares={"you": 1.0},
    annual_spending_need=50,
    state="FL",
    reference_tax_year=2026,
    start_plan_year=1,
    start_tax_year=2026,
    plan_to_age=91,  # 2-year horizon: ages 90 and 91
    strategy=_STRATEGY,
)

# Two-year horizon, return-controlled shortfall (see task T010-T014 design):
# year1 draws 50 leaving 50, growth applied at year end. A 0.0 year1 return
# means year2 starts with exactly 50 (meets year2's 50 spending need, no
# shortfall). A -0.5 year1 return means year2 starts with 25 (falls short
# of the 50 spending need by 25).
_PATH_OK = ReturnPath(start_plan_year=1, annual_returns=[0.0, 0.0], generation_mode="parametric", figures_used=[])
_PATH_FAIL = ReturnPath(start_plan_year=1, annual_returns=[-0.5, 0.0], generation_mode="parametric", figures_used=[])


def test_success_rate_is_share_of_paths_without_shortfall():
    from retirement_planner.simulation.monte_carlo import run_simulation

    run = run_simulation(
        **_COMMON_KWARGS, return_paths=[_PATH_OK, _PATH_FAIL, _PATH_OK], candidate_label="test"
    )

    assert run.success_rate == pytest.approx(2 / 3)


def test_each_paths_depletion_year_retained_individually():
    from retirement_planner.simulation.monte_carlo import run_simulation

    run = run_simulation(
        **_COMMON_KWARGS, return_paths=[_PATH_OK, _PATH_FAIL], candidate_label="test"
    )

    assert len(run.path_results) == 2
    assert run.path_results[0].outcome.first_shortfall_plan_year is None
    assert run.path_results[1].outcome.first_shortfall_plan_year == 2


def test_percentile_bands_have_one_entry_per_plan_year_with_correct_ordering():
    from retirement_planner.simulation.monte_carlo import run_simulation

    run = run_simulation(
        **_COMMON_KWARGS, return_paths=[_PATH_OK, _PATH_FAIL, _PATH_OK], candidate_label="test"
    )

    assert [band.plan_year for band in run.percentile_bands] == [1, 2]
    for band in run.percentile_bands:
        values = list(band.percentiles.values())
        assert min(values) <= band.percentiles[0.50] <= max(values)
        assert band.percentiles[0.10] <= band.percentiles[0.50] <= band.percentiles[0.90]


def test_run_simulation_rejects_empty_return_paths():
    from retirement_planner.simulation.monte_carlo import run_simulation

    with pytest.raises(ValueError):
        run_simulation(**_COMMON_KWARGS, return_paths=[], candidate_label="test")


def test_run_simulation_reproducible_including_under_forced_parallel_dispatch(monkeypatch):
    import retirement_planner.simulation.monte_carlo as monte_carlo_module
    from retirement_planner.simulation.monte_carlo import run_simulation

    # The real reference-scale (3,000-5,000 path) threshold is set high
    # enough that dispatch stays serial by default (research.md §7's
    # benchmark found per-path cost cheap enough that ProcessPoolExecutor's
    # own IPC overhead dominates below that scale) -- lower it here to
    # force and correctness-test the parallel branch itself at a small,
    # fast path count.
    monkeypatch.setattr(monte_carlo_module, "_PARALLEL_DISPATCH_THRESHOLD", 10)

    market = MarketAssumptions(
        equity_allocation=0.60, equity_return_mean_real=0.065, equity_return_std_real=0.17,
        bond_allocation=0.40, bond_return_mean_real=0.015, bond_return_std_real=0.06,
        correlation=-0.10,
    )
    return_paths = generate_return_paths(
        market_assumptions=market, path_count=50, horizon_years=2, start_plan_year=1, seed=99
    )

    first = run_simulation(**_COMMON_KWARGS, return_paths=return_paths, candidate_label="test")
    second = run_simulation(**_COMMON_KWARGS, return_paths=return_paths, candidate_label="test")

    assert first.success_rate == second.success_rate
    assert first.percentile_bands == second.percentile_bands
    assert [p.outcome for p in first.path_results] == [p.outcome for p in second.path_results]


def test_figures_used_deduplicates_across_paths_and_years():
    from retirement_planner.simulation.monte_carlo import run_simulation

    # FL has no state-level SourcedFigure usage but federal tax figures
    # (brackets, SS thresholds) are used every year across every path --
    # confirm the same (name, last_verified) figure isn't repeated once
    # per path/year.
    run = run_simulation(
        **_COMMON_KWARGS, return_paths=[_PATH_OK, _PATH_FAIL, _PATH_OK], candidate_label="test"
    )

    keys = [(f.name, f.last_verified) for f in run.figures_used]
    assert len(keys) == len(set(keys))
