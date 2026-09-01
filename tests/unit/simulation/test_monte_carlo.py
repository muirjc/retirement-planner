"""Unit tests for retirement_planner.simulation.monte_carlo.run_simulation()
(US1): success rate, percentile bands, per-path depletion tracking,
reproducibility, and figures_used deduplication (Polish, FR-019).

inherited_accounts tests (012-inherited-ira-rmd rp-mt7) cover the "fresh
copy per path" property monte_carlo.py's own module docstring requires --
including under forced parallel dispatch, where one worker process runs
many paths in sequence and must not let one path's mutated balance leak
into the next.
"""

import pytest

from retirement_planner.comparison import StrategyConfiguration
from retirement_planner.mechanics import AccountBalances, InheritedAccountBalance
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


def test_callers_own_inherited_account_balance_is_never_mutated():
    from retirement_planner.simulation.monte_carlo import run_simulation

    inherited_accounts = [
        InheritedAccountBalance(
            account_id="traditional-1",
            balance=250_000.0,
            death_year=2023,
            decedent_age_at_death=80,
            depletion_deadline_year=2033,
            beneficiary_person_name="you",
        )
    ]

    run_simulation(
        **_COMMON_KWARGS,
        return_paths=[_PATH_OK, _PATH_FAIL, _PATH_OK],
        candidate_label="test",
        inherited_accounts=inherited_accounts,
    )

    # run_plan_projection() ran once per path and mutates balance in
    # place -- the caller's own original instance must still read its
    # untouched starting balance.
    assert inherited_accounts[0].balance == 250_000.0


def test_no_cross_path_leakage_in_inherited_distributions_serial():
    from retirement_planner.simulation.monte_carlo import run_simulation

    inherited_accounts = [
        InheritedAccountBalance(
            account_id="traditional-1",
            balance=250_000.0,
            death_year=2023,
            decedent_age_at_death=80,
            depletion_deadline_year=2033,
            beneficiary_person_name="you",
        )
    ]

    run = run_simulation(
        **_COMMON_KWARGS,
        return_paths=[_PATH_OK, _PATH_FAIL, _PATH_OK],
        candidate_label="test",
        inherited_accounts=inherited_accounts,
    )

    # Every path started from the identical, unmutated inherited balance
    # -- their first-year inherited distributions must therefore be
    # identical to each other (no path saw another path's already-
    # decremented balance).
    first_year_distributions = {
        projection.years[0].mechanics.withdrawal_plan.inherited_distribution_drawn
        for projection in run.path_results
    }
    assert len(first_year_distributions) == 1
    assert first_year_distributions.pop() > 0


def test_no_cross_path_leakage_in_inherited_distributions_forced_parallel(monkeypatch):
    import retirement_planner.simulation.monte_carlo as monte_carlo_module
    from retirement_planner.simulation.monte_carlo import run_simulation

    # Force the parallel branch (module docstring / test above) with more
    # paths than workers, so at least one worker process runs multiple
    # paths in sequence -- exactly the scenario _run_one_path_shared()
    # must take a fresh inherited_accounts copy for on every call.
    monkeypatch.setattr(monte_carlo_module, "_PARALLEL_DISPATCH_THRESHOLD", 10)

    inherited_accounts = [
        InheritedAccountBalance(
            account_id="traditional-1",
            balance=250_000.0,
            death_year=2023,
            decedent_age_at_death=80,
            depletion_deadline_year=2033,
            beneficiary_person_name="you",
        )
    ]
    return_paths = [_PATH_OK] * 20

    run = run_simulation(
        **_COMMON_KWARGS,
        return_paths=return_paths,
        candidate_label="test",
        inherited_accounts=inherited_accounts,
    )

    first_year_distributions = {
        projection.years[0].mechanics.withdrawal_plan.inherited_distribution_drawn
        for projection in run.path_results
    }
    assert len(first_year_distributions) == 1
    assert first_year_distributions.pop() > 0
    assert inherited_accounts[0].balance == 250_000.0


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


def test_claiming_age_adjusted_benefit_matches_deterministic_projection_exactly():
    """016-ss-claiming-age-actuarial-adjustment US2 (spec.md Acceptance
    Scenario 2, Principle II Reproducibility): run_simulation() derives
    the identical claiming-age-adjusted benefit run_plan_projection()
    would for the same inputs -- both funnel through the same shared call
    site (research.md Decision 4), so this is a regression guard against
    that ever drifting apart, not a re-test of the formula itself
    (covered by tests/unit/mechanics/test_social_security_benefit.py)."""
    from retirement_planner.comparison import DeterministicReturnAssumption, run_plan_projection
    from retirement_planner.simulation.monte_carlo import run_simulation

    household = Household(
        filing_status="single",
        members=[
            HouseholdMember(
                person_name="you",
                current_age=63,
                ss_claim_age=64,
                ss_annual_benefit=30_000,
                full_retirement_age=67.0,
            ),
        ],
    )
    accounts = AccountBalances(traditional=0, roth=0, taxable=500_000)
    strategy = StrategyConfiguration(
        label="test",
        withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
        conversion_window=None,
        claiming_ages={"you": 64},
    )
    common_kwargs = dict(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=64,
        strategy=strategy,
    )

    deterministic = run_plan_projection(
        **common_kwargs, return_assumption=DeterministicReturnAssumption(annual_real_return=0.0)
    )
    simulated = run_simulation(
        **common_kwargs,
        return_paths=[
            ReturnPath(start_plan_year=1, annual_returns=[0.0, 0.0], generation_mode="parametric", figures_used=[])
        ],
        candidate_label="test",
    )

    assert (
        simulated.path_results[0].years[0].member_social_security_benefits["you"]
        == deterministic.years[0].member_social_security_benefits["you"]
    )
    # Sanity: this is actually the reduced amount, not the flat PIA.
    assert deterministic.years[0].member_social_security_benefits["you"] < 30_000.0


def test_spousal_floor_matches_deterministic_projection_exactly():
    """017-ss-spousal-survivor-benefits (rp-52n), /speckit-analyze finding
    C1: the spousal benefit floor -- like 016's own claiming-age
    adjustment above -- is applied inside the one shared call site
    (_member_gross_social_security_benefits(), research.md Decision 7)
    every engine path funnels through. This is a regression guard against
    that ever drifting apart, not a re-test of the formula itself
    (covered by tests/unit/mechanics/test_social_security_benefit.py and
    tests/unit/comparison/test_projection.py)."""
    from retirement_planner.comparison import DeterministicReturnAssumption, run_plan_projection
    from retirement_planner.simulation.monte_carlo import run_simulation

    household = Household(
        filing_status="married_filing_jointly",
        members=[
            HouseholdMember(
                person_name="you", current_age=67, ss_claim_age=67, ss_annual_benefit=30_000, full_retirement_age=67.0
            ),
            HouseholdMember(
                person_name="spouse",
                current_age=67,
                ss_claim_age=67,
                ss_annual_benefit=6_000,  # well under 50% of "you"'s PIA -- the floor must trigger
                full_retirement_age=67.0,
            ),
        ],
    )
    accounts = AccountBalances(traditional=0, roth=0, taxable=500_000)
    strategy = StrategyConfiguration(
        label="test",
        withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
        conversion_window=None,
        claiming_ages={"you": 67, "spouse": 67},
    )
    common_kwargs = dict(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0, "spouse": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=67,
        strategy=strategy,
    )

    deterministic = run_plan_projection(
        **common_kwargs, return_assumption=DeterministicReturnAssumption(annual_real_return=0.0)
    )
    simulated = run_simulation(
        **common_kwargs,
        return_paths=[
            ReturnPath(start_plan_year=1, annual_returns=[0.0, 0.0], generation_mode="parametric", figures_used=[])
        ],
        candidate_label="test",
    )

    assert (
        simulated.path_results[0].years[0].member_social_security_benefits["spouse"]
        == deterministic.years[0].member_social_security_benefits["spouse"]
    )
    # Sanity: this is actually the spousal-floor amount (50% of 30,000), not spouse's own $6,000 PIA.
    assert deterministic.years[0].member_social_security_benefits["spouse"] == pytest.approx(15_000.0)


def test_death_switch_matches_deterministic_projection_exactly():
    """018-survivor-scenario-projection (rp-g8y) FR-007, SC-005: the
    mid-horizon death switch (filing status, survivor Social Security
    income, spending reduction) lives entirely inside
    comparison.run_plan_projection() -- every Monte Carlo path already
    calls that function internally, so a path's own per-year results must
    match a direct run_plan_projection() call exactly, for every year,
    with no per-path probabilistic death draw of any kind (every path
    uses the identical, deterministic, household-configured death year).
    This is a regression guard against that shared call site ever
    drifting apart, mirroring 016's and 017's own test_monte_carlo.py
    consistency-check precedent -- not a re-test of the switch itself
    (covered by tests/unit/comparison/test_projection.py)."""
    from retirement_planner.comparison import DeterministicReturnAssumption, run_plan_projection
    from retirement_planner.simulation.monte_carlo import run_simulation

    household = Household(
        filing_status="married_filing_jointly",
        survivor_spending_reduction_pct=0.20,
        members=[
            HouseholdMember(
                person_name="you", current_age=67, ss_claim_age=67, ss_annual_benefit=30_000, full_retirement_age=67.0
            ),
            HouseholdMember(
                person_name="spouse",
                current_age=67,
                ss_claim_age=67,
                ss_annual_benefit=20_000,
                full_retirement_age=67.0,
                predicted_death_age=70,  # death tax year 2029, mid-horizon below
            ),
        ],
    )
    accounts = AccountBalances(traditional=0, roth=0, taxable=500_000)
    strategy = StrategyConfiguration(
        label="test",
        withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
        conversion_window=None,
        claiming_ages={"you": 67, "spouse": 67},
    )
    common_kwargs = dict(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0, "spouse": 0.0},
        annual_spending_need=60_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=72,  # spans both pre- and post-death plan years (death at 70)
        strategy=strategy,
    )

    deterministic = run_plan_projection(
        **common_kwargs, return_assumption=DeterministicReturnAssumption(annual_real_return=0.0)
    )
    simulated = run_simulation(
        **common_kwargs,
        return_paths=[
            ReturnPath(
                start_plan_year=1,
                annual_returns=[0.0] * len(deterministic.years),
                generation_mode="parametric",
                figures_used=[],
            )
        ],
        candidate_label="test",
    )

    simulated_years = simulated.path_results[0].years
    assert len(simulated_years) == len(deterministic.years)
    for simulated_year, deterministic_year in zip(simulated_years, deterministic.years):
        assert simulated_year.filing_status == deterministic_year.filing_status
        assert simulated_year.effective_spending_need == deterministic_year.effective_spending_need
        assert simulated_year.member_social_security_benefits == deterministic_year.member_social_security_benefits

    # Sanity: the switch actually occurred somewhere in this horizon.
    assert any(year.filing_status == "single" for year in deterministic.years)
    assert any(year.filing_status == "married_filing_jointly" for year in deterministic.years)
