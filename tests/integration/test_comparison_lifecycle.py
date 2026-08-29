"""Integration test: the full quickstart.md walkthrough for
004-strategy-comparison-layer (full-horizon projection, Roth conversion
strategy comparison, withdrawal sequencing comparison, and Social Security
claiming-age grid comparison).

See specs/004-strategy-comparison-layer/quickstart.md — this test exercises
the same four sections, using "FL" as the state (a zero-income-tax state
already implemented by 002-tax-calculation-engine's STATE_MODULES; "GA",
used as an example in quickstart.md's prose, is not yet an implemented
state module).
"""

import itertools

import pytest

from retirement_planner.comparison import (
    StrategyConfiguration,
    compare_claiming_age_grid,
    compare_roth_conversion_strategies,
    compare_withdrawal_sequencing_strategies,
    derive_deterministic_return,
    run_plan_projection,
)
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember, MarketAssumptions

_HOUSEHOLD = Household(
    filing_status="married_filing_jointly",
    members=[
        HouseholdMember(person_name="you", current_age=60, ss_claim_age=67, ss_annual_benefit=32_000),
        HouseholdMember(person_name="spouse", current_age=58, ss_claim_age=67, ss_annual_benefit=24_000),
    ],
)
_ACCOUNTS = AccountBalances(traditional=1_500_000, roth=400_000, taxable=200_000)
# 011-per-owner-accounts: arbitrary but fixed split -- this household's plan
# horizon (60-70) never reaches the RMD-required starting age, so no test
# below actually exercises RMD sizing; test_step0 (below) is the one that
# does, using quickstart.md §1's own literal figures.
_SHARES = {"you": 0.6, "spouse": 0.4}
_MARKET = MarketAssumptions(
    equity_allocation=0.60,
    equity_return_mean_real=0.065,
    equity_return_std_real=0.17,
    bond_allocation=0.40,
    bond_return_mean_real=0.015,
    bond_return_std_real=0.06,
    correlation=-0.10,
)
_STATE = "FL"
_COMMON_KWARGS = dict(
    annual_spending_need=110_000,
    state=_STATE,
    reference_tax_year=2026,
    start_plan_year=1,
    start_tax_year=2026,
    plan_to_age=70,
)


def test_step0_per_member_rmd_reflects_actual_ownership_not_deemed_owner():
    """011-per-owner-accounts quickstart.md §1: "you" (74, past the RMD-
    required starting age) owns $900k of the household's $1.2M traditional
    total; "spouse" (60, well below it) owns the remaining $300k. The
    first plan year's RMD-driven traditional draw must reflect only "you"'s
    own $900k share -- never the deemed-owner attribution of the full
    $1.2M this feature replaces (specs/004 research.md §4)."""
    household = Household(
        filing_status="married_filing_jointly",
        members=[
            HouseholdMember(person_name="you", current_age=74, ss_claim_age=67, ss_annual_benefit=32_000),
            HouseholdMember(person_name="spouse", current_age=60, ss_claim_age=67, ss_annual_benefit=24_000),
        ],
    )
    accounts = AccountBalances(traditional=1_200_000, roth=400_000, taxable=300_000)
    shares = {"you": 900_000 / 1_200_000, "spouse": 300_000 / 1_200_000}
    strategy = StrategyConfiguration(
        label="base_case", withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
        claiming_ages={"you": 67, "spouse": 67},
    )
    return_assumption = derive_deterministic_return(_MARKET)

    projection = run_plan_projection(
        household=household, accounts=accounts, traditional_ownership_shares=shares,
        annual_spending_need=90_000, state=_STATE, reference_tax_year=2026, start_plan_year=1,
        start_tax_year=2026, plan_to_age=95, strategy=strategy, return_assumption=return_assumption,
    )

    first_year = projection.years[0]
    assert first_year.mechanics.withdrawal_plan.rmd_drawn == pytest.approx(900_000 / 25.5)
    # Sanity check against the pre-fix behavior this replaces: the deemed-
    # owner figure would have been $1.2M / 25.5, strictly larger.
    assert first_year.mechanics.withdrawal_plan.rmd_drawn < 1_200_000 / 25.5


def test_step1_run_one_full_horizon_projection():
    return_assumption = derive_deterministic_return(_MARKET)
    assert return_assumption.annual_real_return == pytest.approx(0.045)

    strategy = StrategyConfiguration(
        label="fill_to_22_pct_bracket",
        withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy="fill_to_bracket",
        conversion_bracket_ceiling_or_amount=206_000,
        conversion_window=(2028, 2034),
        claiming_ages={"you": 67, "spouse": 67},
    )

    projection = run_plan_projection(
        household=_HOUSEHOLD, accounts=_ACCOUNTS, traditional_ownership_shares=_SHARES,
        strategy=strategy, return_assumption=return_assumption,
        **_COMMON_KWARGS,
    )

    assert len(projection.years) == 70 - 60 + 1
    assert projection.years[0].starting_balances == _ACCOUNTS
    assert projection.years[1].starting_balances == projection.years[0].ending_balances

    repeat = run_plan_projection(
        household=_HOUSEHOLD, accounts=_ACCOUNTS, traditional_ownership_shares=_SHARES,
        strategy=strategy, return_assumption=return_assumption,
        **_COMMON_KWARGS,
    )
    assert repeat == projection


def test_step2_compare_roth_conversion_strategies():
    return_assumption = derive_deterministic_return(_MARKET)
    candidates = [
        StrategyConfiguration(
            label="fill_to_10_pct_bracket", withdrawal_strategy="ignored", conversion_strategy="fill_to_bracket",
            conversion_bracket_ceiling_or_amount=94_300, conversion_window=(2028, 2034), claiming_ages={},
        ),
        StrategyConfiguration(
            label="fill_to_22_pct_bracket", withdrawal_strategy="ignored", conversion_strategy="fill_to_bracket",
            conversion_bracket_ceiling_or_amount=206_000, conversion_window=(2028, 2034), claiming_ages={},
        ),
        StrategyConfiguration(
            label="fixed_50k", withdrawal_strategy="ignored", conversion_strategy="fixed_amount",
            conversion_bracket_ceiling_or_amount=50_000, conversion_window=(2028, 2034), claiming_ages={},
        ),
        StrategyConfiguration(
            label="no_conversion", withdrawal_strategy="ignored", conversion_strategy=None,
            conversion_bracket_ceiling_or_amount=None, conversion_window=None, claiming_ages={},
        ),
    ]

    comparison = compare_roth_conversion_strategies(
        household=_HOUSEHOLD, accounts=_ACCOUNTS, traditional_ownership_shares=_SHARES,
        withdrawal_strategy="rmd_taxable_traditional_roth", claiming_ages={"you": 67, "spouse": 67},
        return_assumption=return_assumption, candidates=candidates,
        **_COMMON_KWARGS,
    )

    assert comparison.dimension == "roth_conversion_strategy"
    assert len(comparison.projections) == 4
    assert all(p.return_assumption == return_assumption for p in comparison.projections)

    no_conv = next(p for p in comparison.projections if p.strategy.label == "no_conversion")
    fill_22 = next(p for p in comparison.projections if p.strategy.label == "fill_to_22_pct_bracket")
    assert no_conv.outcome.cumulative_tax_paid != fill_22.outcome.cumulative_tax_paid


def test_step3_compare_withdrawal_sequencing_orders():
    return_assumption = derive_deterministic_return(_MARKET)
    order_candidates = [
        StrategyConfiguration(
            label="taxable_first", withdrawal_strategy="rmd_taxable_traditional_roth", conversion_strategy=None,
            conversion_bracket_ceiling_or_amount=None, conversion_window=None, claiming_ages={},
        ),
        StrategyConfiguration(
            label="traditional_first", withdrawal_strategy="rmd_traditional_taxable_roth", conversion_strategy=None,
            conversion_bracket_ceiling_or_amount=None, conversion_window=None, claiming_ages={},
        ),
    ]

    comparison = compare_withdrawal_sequencing_strategies(
        household=_HOUSEHOLD, accounts=_ACCOUNTS, traditional_ownership_shares=_SHARES,
        conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
        claiming_ages={"you": 67, "spouse": 67}, return_assumption=return_assumption, candidates=order_candidates,
        **_COMMON_KWARGS,
    )

    assert comparison.dimension == "withdrawal_sequencing"
    assert len(comparison.projections) == 2


def test_step4_compare_social_security_claiming_ages():
    return_assumption = derive_deterministic_return(_MARKET)
    grid = [
        {"you": you_age, "spouse": spouse_age}
        for you_age, spouse_age in itertools.product(range(62, 71), range(62, 71))
    ]

    comparison = compare_claiming_age_grid(
        household=_HOUSEHOLD, accounts=_ACCOUNTS, traditional_ownership_shares=_SHARES,
        withdrawal_strategy="rmd_taxable_traditional_roth", conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None, conversion_window=None,
        return_assumption=return_assumption, claiming_age_grid=grid,
        **_COMMON_KWARGS,
    )

    assert comparison.dimension == "claiming_age_grid"
    assert len(comparison.projections) == 9 * 9

    matching_original = next(
        p for p in comparison.projections if p.strategy.claiming_ages == {"you": 67, "spouse": 67}
    )

    strategy = StrategyConfiguration(
        label="standalone", withdrawal_strategy="rmd_taxable_traditional_roth", conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None, conversion_window=None, claiming_ages={"you": 67, "spouse": 67},
    )
    standalone = run_plan_projection(
        household=_HOUSEHOLD, accounts=_ACCOUNTS, traditional_ownership_shares=_SHARES,
        strategy=strategy, return_assumption=return_assumption,
        **_COMMON_KWARGS,
    )
    assert matching_original.outcome == standalone.outcome
