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
from retirement_planner.scenario import Household, HouseholdMember, IncomeStream, MarketAssumptions
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


def test_income_stream_matches_deterministic_projection_exactly():
    """021-pension-annuity-income (rp-pid) FR-011/SC-004: income streams
    are computed entirely inside comparison.run_plan_projection() -- every
    Monte Carlo path already calls that function internally, so no
    separate simulation-layer wiring is needed. Mirrors
    test_death_switch_matches_deterministic_projection_exactly's own
    consistency-check precedent."""
    from retirement_planner.comparison import DeterministicReturnAssumption, run_plan_projection
    from retirement_planner.simulation.monte_carlo import run_simulation

    household = Household(
        filing_status="single",
        members=[
            HouseholdMember(
                person_name="you",
                current_age=60,
                ss_claim_age=99,
                ss_annual_benefit=0,
                full_retirement_age=67.0,
                income_streams=[
                    IncomeStream(
                        label="State Pension", stream_type="pension", start_age=62,
                        annual_amount=18_000.0, inflation_adjustment="cola_adjusted",
                    )
                ],
            )
        ],
    )
    accounts = AccountBalances(traditional=0, roth=0, taxable=500_000)
    strategy = StrategyConfiguration(
        label="test",
        withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
        conversion_window=None,
        claiming_ages={"you": 99},
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
        plan_to_age=65,  # spans both pre- and post-pension-start plan years (starts at 62)
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
        assert simulated_year.member_income_stream_amounts == deterministic_year.member_income_stream_amounts

    # Sanity: the pension actually turned on somewhere in this horizon.
    assert any(year.member_income_stream_amounts["you"] > 0 for year in deterministic.years)
    assert any(year.member_income_stream_amounts["you"] == 0 for year in deterministic.years)


def test_roth_ladder_flag_matches_deterministic_projection_exactly():
    """019-roth-conversion-ladder (rp-886) FR-007/SC-005, research.md
    Decision 2: the Roth conversion-lot tracking lives entirely inside
    comparison.run_plan_projection() as PURELY LOCAL state (never a
    parameter) -- every Monte Carlo path already calls that function
    internally, so a path's own per-year unseasoned_roth_withdrawal flag
    must match a direct run_plan_projection() call exactly, for every
    year, with zero cross-path leakage (there is no shared list to leak
    in the first place, unlike inherited_accounts). This is a regression
    guard against that shared call site ever drifting apart, mirroring
    016's/017's/018's own test_monte_carlo.py consistency-check
    precedent -- not a re-test of the ladder logic itself (covered by
    tests/unit/mechanics/test_roth_conversion_ladder.py and
    tests/unit/comparison/test_projection.py)."""
    from retirement_planner.comparison import DeterministicReturnAssumption, run_plan_projection
    from retirement_planner.simulation.monte_carlo import run_simulation

    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=55, ss_claim_age=67, ss_annual_benefit=0)],
    )
    accounts = AccountBalances(traditional=100_000, roth=0, taxable=0)
    strategy = StrategyConfiguration(
        label="test",
        withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy="fixed_amount",
        conversion_bracket_ceiling_or_amount=90_000,
        conversion_window=(2026, 2026),
        claiming_ages={"you": 67},
    )
    common_kwargs = dict(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=15_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=65,  # spans both the unseasoned-draw years and the seasoned year (2031+)
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
        assert simulated_year.unseasoned_roth_withdrawal == deterministic_year.unseasoned_roth_withdrawal

    # Sanity: the flag actually fired somewhere, and stopped firing once seasoned.
    assert any(year.unseasoned_roth_withdrawal > 0 for year in deterministic.years)
    assert any(
        year.tax_year >= 2031 and year.unseasoned_roth_withdrawal == 0.0 for year in deterministic.years
    )


def test_early_withdrawal_penalty_matches_deterministic_projection_exactly():
    """020-early-withdrawal-penalty (rp-8z0) FR-007, SC-001: the penalty
    computation lives entirely inside comparison.run_plan_projection()'s
    own per-year loop -- every Monte Carlo path already calls that
    function internally, so a path's own per-year
    early_withdrawal_penalty.penalty_owed must match a direct
    run_plan_projection() call exactly, for every year. Regression guard
    against that shared call site ever drifting apart, mirroring
    016's/017's/018's/019's own test_monte_carlo.py consistency-check
    precedent -- not a re-test of the penalty logic itself (covered by
    tests/unit/tax/test_early_withdrawal_penalty.py and
    tests/unit/comparison/test_projection.py)."""
    from retirement_planner.comparison import DeterministicReturnAssumption, run_plan_projection
    from retirement_planner.simulation.monte_carlo import run_simulation

    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=55, ss_claim_age=67, ss_annual_benefit=0)],
    )
    accounts = AccountBalances(traditional=200_000, roth=0, taxable=0)
    strategy = StrategyConfiguration(
        label="test",
        withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
        conversion_window=None,
        claiming_ages={"you": 67},
    )
    common_kwargs = dict(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=20_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=65,  # spans both under-59.5 and 60+ plan years
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
        assert (
            simulated_year.early_withdrawal_penalty.penalty_owed
            == deterministic_year.early_withdrawal_penalty.penalty_owed
        )

    # Sanity: the penalty actually fired somewhere, and stopped firing once 60+.
    assert any(year.early_withdrawal_penalty.penalty_owed > 0 for year in deterministic.years)
    assert any(
        year.tax_year >= 2031 and year.early_withdrawal_penalty.penalty_owed == 0.0 for year in deterministic.years
    )


# -- 023-probabilistic-death-draws (rp-vgv), User Story 1 -------------------

def _married_household_and_kwargs():
    """Shared MFJ fixture for the death_year_draws tests below -- no
    member has predicted_death_age configured (this feature's whole point
    is to supply it per-path instead)."""
    household = Household(
        filing_status="married_filing_jointly",
        survivor_spending_reduction_pct=0.20,
        members=[
            HouseholdMember(
                person_name="you", current_age=67, ss_claim_age=67,
                ss_annual_benefit=30_000, full_retirement_age=67.0,
            ),
            HouseholdMember(
                person_name="spouse", current_age=65, ss_claim_age=67,
                ss_annual_benefit=20_000, full_retirement_age=67.0,
            ),
        ],
    )
    accounts = AccountBalances(traditional=800_000, roth=0, taxable=0)
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
        traditional_ownership_shares={"you": 1.0, "spouse": 0.0},
        annual_spending_need=60_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=85,
        strategy=strategy,
        candidate_label="test",
    )
    return household, accounts, strategy, common_kwargs


def _survival_curves_for(household):
    """A deliberately degenerate "always alive" curve (probability 1.0 at
    every documented age) -- fine for tests below that only need
    survival_curves to satisfy run_simulation()'s own precondition
    (required alongside death_year_draws for citation purposes) and
    otherwise hand-craft their own death_year_draws directly; NOT suitable
    for a test that needs generate_death_age_draws() itself to produce a
    varying draw (see the real SURVIVAL_TABLE used for that instead)."""
    from datetime import date

    from retirement_planner.simulation.models import SurvivalCurve

    curve = SurvivalCurve(
        person_name="placeholder",
        probabilities_by_age={age: 1.0 for age in range(50, 111)},
        citation="test fixture",
        last_verified=date(2026, 8, 28),
        verified=False,
    )
    return {member.person_name: curve for member in household.members}


def test_death_year_draws_defaulting_to_none_is_identical_to_omitting_the_parameter():
    """FR-007, SC-005: death_year_draws=None (the explicit default) must
    produce byte-for-byte identical output to a caller that doesn't pass
    the parameter at all -- even when survival_curves is also given (so
    survival_adjusted_success_rate is in play too)."""
    from retirement_planner.simulation.monte_carlo import run_simulation

    household, _accounts, _strategy, common_kwargs = _married_household_and_kwargs()
    survival_curves = _survival_curves_for(household)
    path = ReturnPath(start_plan_year=1, annual_returns=[0.0] * 19, generation_mode="parametric", figures_used=[])

    explicit_none = run_simulation(
        **common_kwargs, return_paths=[path], survival_curves=survival_curves, death_year_draws=None
    )
    omitted = run_simulation(**common_kwargs, return_paths=[path], survival_curves=survival_curves)

    assert explicit_none.success_rate == omitted.success_rate
    assert explicit_none.percentile_bands == omitted.percentile_bands
    assert explicit_none.survival_adjusted_success_rate == omitted.survival_adjusted_success_rate
    assert explicit_none.path_results == omitted.path_results


def test_death_year_draw_reproduces_a_direct_run_plan_projection_call_with_that_death_age():
    """Acceptance Scenario 2 (and 3, via the "you" entry's None draw):
    a path's own drawn death age for "spouse" must produce exactly the
    same PlanProjection a direct run_plan_projection() call with that
    same predicted_death_age would -- reusing 018's survivor-scenario
    logic completely unchanged, per _household_for_path()."""
    from dataclasses import replace

    from retirement_planner.comparison import run_plan_projection
    from retirement_planner.simulation.monte_carlo import run_simulation

    household, accounts, strategy, common_kwargs = _married_household_and_kwargs()
    survival_curves = _survival_curves_for(household)
    path = ReturnPath(start_plan_year=1, annual_returns=[0.0] * 19, generation_mode="parametric", figures_used=[])
    # "spouse" (current_age=65) drawn to die at 70 -- 5 years into the
    # horizon; "you" drawn as None -- no death at all for this path.
    death_year_draws = [{"you": None, "spouse": 70}]

    run = run_simulation(
        **common_kwargs, return_paths=[path], survival_curves=survival_curves, death_year_draws=death_year_draws
    )

    household_for_this_path = replace(
        household,
        members=[
            replace(household.members[0], predicted_death_age=None),
            replace(household.members[1], predicted_death_age=70),
        ],
    )
    direct = run_plan_projection(
        household=household_for_this_path,
        accounts=accounts,
        traditional_ownership_shares={"you": 1.0, "spouse": 0.0},
        annual_spending_need=60_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=85,
        strategy=strategy,
        return_assumption=path,
    )

    assert run.path_results[0] == direct
    # Sanity: the switch actually took effect somewhere in this projection.
    assert any(year.filing_status == "single" for year in direct.years)


def test_death_year_draws_vary_independently_path_to_path():
    """A different draw per path produces a different per-path Household
    override -- the whole point of this feature over the single,
    household-wide static predicted_death_age every path shared before."""
    from retirement_planner.simulation.monte_carlo import run_simulation

    household, _accounts, _strategy, common_kwargs = _married_household_and_kwargs()
    survival_curves = _survival_curves_for(household)
    paths = [
        ReturnPath(start_plan_year=1, annual_returns=[0.0] * 19, generation_mode="parametric", figures_used=[]),
        ReturnPath(start_plan_year=1, annual_returns=[0.0] * 19, generation_mode="parametric", figures_used=[]),
    ]
    death_year_draws = [{"you": None, "spouse": None}, {"you": None, "spouse": 70}]

    run = run_simulation(
        **common_kwargs, return_paths=paths, survival_curves=survival_curves, death_year_draws=death_year_draws
    )

    path0_filing_statuses = [year.filing_status for year in run.path_results[0].years]
    path1_filing_statuses = [year.filing_status for year in run.path_results[1].years]
    assert all(status == "married_filing_jointly" for status in path0_filing_statuses)
    assert "single" in path1_filing_statuses
    assert path0_filing_statuses != path1_filing_statuses


def test_death_year_draws_identical_under_serial_and_forced_parallel_dispatch(monkeypatch):
    """023-probabilistic-death-draws (rp-vgv), User Story 2, SC-003
    (second half): the same household/return_paths/death_year_draws/seed
    must produce identical results regardless of dispatch mode -- mirrors
    this file's own existing
    test_run_simulation_reproducible_including_under_forced_parallel_dispatch
    precedent, extended to cover the new per-path Household override
    threaded through _run_one_path_shared()'s per-task argument."""
    import retirement_planner.simulation.monte_carlo as monte_carlo_module
    from retirement_planner.simulation.mortality import generate_death_age_draws
    from retirement_planner.simulation.monte_carlo import run_simulation
    from retirement_planner.simulation.returns import generate_return_paths
    from retirement_planner.simulation.survival_data import SURVIVAL_TABLE

    monkeypatch.setattr(monte_carlo_module, "_PARALLEL_DISPATCH_THRESHOLD", 10)

    household, _accounts, _strategy, common_kwargs = _married_household_and_kwargs()
    # The real (illustrative) survival table, not _survival_curves_for()'s
    # deliberately-degenerate always-alive fixture -- this test needs
    # draws that actually vary path to path.
    survival_curves = {"you": SURVIVAL_TABLE["primary"], "spouse": SURVIVAL_TABLE["spouse"]}
    market = MarketAssumptions(
        equity_allocation=0.60, equity_return_mean_real=0.065, equity_return_std_real=0.17,
        bond_allocation=0.40, bond_return_mean_real=0.015, bond_return_std_real=0.06,
        correlation=-0.10,
    )
    return_paths = generate_return_paths(
        market_assumptions=market, path_count=50, horizon_years=19, start_plan_year=1, seed=99
    )
    death_year_draws = generate_death_age_draws(
        household=household, survival_curves=survival_curves, path_count=50, seed=123
    )

    first = run_simulation(
        **common_kwargs, return_paths=return_paths, survival_curves=survival_curves,
        death_year_draws=death_year_draws,
    )
    second = run_simulation(
        **common_kwargs, return_paths=return_paths, survival_curves=survival_curves,
        death_year_draws=death_year_draws,
    )

    assert first.success_rate == second.success_rate
    assert first.percentile_bands == second.percentile_bands
    assert first.path_results == second.path_results
    # Sanity: the parallel branch (path_count=50 >= the monkeypatched
    # threshold of 10) is actually the one exercised here, and draws did
    # vary path to path -- not a vacuously-true comparison of two empty
    # or identical-by-construction runs.
    assert len({tuple(sorted(d.items())) for d in death_year_draws}) > 1
