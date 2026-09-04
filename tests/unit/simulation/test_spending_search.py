"""Unit tests for simulation.spending_search (rp-3g0): the sustainable-
spending range search's bracket-expansion + bisection algorithm.

Uses generate_return_paths() with a real, volatile market assumption (not
hand-crafted 2-path fixtures like test_monte_carlo.py's own) so
success_rate varies smoothly across many spending candidates -- what
these tests actually exercise is convergence behavior, not any single
hand-picked number.
"""

from retirement_planner.comparison import StrategyConfiguration
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember, MarketAssumptions
from retirement_planner.simulation import find_sustainable_spending_range, generate_return_paths
from retirement_planner.simulation.monte_carlo import run_simulation
from retirement_planner.simulation.spending_search import search_spending_for_target_success_rate

_MARKET = MarketAssumptions(
    equity_allocation=0.6,
    equity_return_mean_real=0.05,
    equity_return_std_real=0.18,
    bond_allocation=0.4,
    bond_return_mean_real=0.02,
    bond_return_std_real=0.06,
    correlation=0.0,
)


def _household_and_kwargs(current_age=65, plan_to_age=90, traditional_balance=1_000_000.0, path_count=80):
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=current_age, ss_claim_age=67, ss_annual_benefit=20_000)],
    )
    accounts = AccountBalances(traditional=traditional_balance, roth=0, taxable=0)
    strategy = StrategyConfiguration(
        label="test",
        withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
        conversion_window=None,
        claiming_ages={"you": 67},
    )
    horizon_years = plan_to_age - current_age + 1
    return_paths = generate_return_paths(_MARKET, path_count=path_count, horizon_years=horizon_years, start_plan_year=1, seed=42)
    common_kwargs = dict(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 1.0},
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=plan_to_age,
        strategy=strategy,
        return_paths=return_paths,
    )
    return common_kwargs


def test_search_converges_within_tolerance_of_an_achievable_target():
    kwargs = _household_and_kwargs()
    result = search_spending_for_target_success_rate(
        **kwargs, anchor_spending=50_000.0, target_success_rate=0.90,
    )
    assert result.bracket_exhausted is False
    assert abs(result.achieved_success_rate - 0.90) <= 0.05  # loose bound: discrete path_count=200 success_rate granularity


def test_higher_success_rate_target_requires_lower_spending():
    """The core invariant a 'range' depends on: a stricter (higher)
    success-rate target must resolve to spending at or below a looser
    (lower) target's own resolved spending, against the same paths."""
    kwargs = _household_and_kwargs()
    conservative = search_spending_for_target_success_rate(**kwargs, anchor_spending=50_000.0, target_success_rate=0.95)
    flexible = search_spending_for_target_success_rate(**kwargs, anchor_spending=50_000.0, target_success_rate=0.75)
    assert conservative.spending <= flexible.spending


def test_find_sustainable_spending_range_returns_the_same_ordering():
    kwargs = _household_and_kwargs()
    result = find_sustainable_spending_range(**kwargs, anchor_spending=50_000.0)
    assert result.conservative.spending <= result.flexible.spending
    assert result.path_count_used == len(kwargs["return_paths"])
    assert result.conservative.target_success_rate == 0.95
    assert result.flexible.target_success_rate == 0.75


def test_success_rate_is_monotonically_non_increasing_in_spending():
    """The structural property bisection depends on: against the SAME
    return_paths, more spending can only reduce or hold success_rate --
    never raise it. Spot-checked across a real, varied path set rather
    than asserted a priori."""
    kwargs = _household_and_kwargs()
    spending_levels = [10_000.0, 30_000.0, 50_000.0, 70_000.0, 90_000.0, 120_000.0]
    rates = [
        run_simulation(
            household=kwargs["household"],
            accounts=kwargs["accounts"],
            traditional_ownership_shares=kwargs["traditional_ownership_shares"],
            annual_spending_need=spending,
            state=kwargs["state"],
            reference_tax_year=kwargs["reference_tax_year"],
            start_plan_year=kwargs["start_plan_year"],
            start_tax_year=kwargs["start_tax_year"],
            plan_to_age=kwargs["plan_to_age"],
            strategy=kwargs["strategy"],
            return_paths=kwargs["return_paths"],
            candidate_label="test",
        ).success_rate
        for spending in spending_levels
    ]
    assert rates == sorted(rates, reverse=True)


def test_bracket_exhausted_when_target_is_unreachable_within_the_expansion_cap():
    """A near-$0 target success rate on a well-funded household never
    drops below target even after doubling repeatedly -- capped by a
    deliberately tiny max_bracket_expansions so the search terminates
    instead of doubling indefinitely."""
    kwargs = _household_and_kwargs(traditional_balance=10_000_000.0)
    result = search_spending_for_target_success_rate(
        **kwargs, anchor_spending=10_000.0, target_success_rate=0.01, max_bracket_expansions=2,
    )
    assert result.bracket_exhausted is True
    assert result.achieved_success_rate >= 0.01


def test_max_bisection_iterations_bounds_total_iterations_used():
    kwargs = _household_and_kwargs()
    result = search_spending_for_target_success_rate(
        **kwargs, anchor_spending=50_000.0, target_success_rate=0.90,
        max_bracket_expansions=10, max_bisection_iterations=3,
    )
    # 1 initial rate_at() call + up to 10 expansions + up to 3 bisection steps.
    assert result.iterations_used <= 1 + 10 + 3


def test_tight_tolerance_uses_more_iterations_than_loose_tolerance():
    kwargs = _household_and_kwargs()
    loose = search_spending_for_target_success_rate(**kwargs, anchor_spending=50_000.0, target_success_rate=0.90, tolerance=0.20)
    tight = search_spending_for_target_success_rate(**kwargs, anchor_spending=50_000.0, target_success_rate=0.90, tolerance=0.01)
    assert tight.iterations_used >= loose.iterations_used
