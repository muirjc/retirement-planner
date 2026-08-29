"""Unit tests for run_plan_projection() and its per-year helpers (US1).

deemed_rmd_owner() and member_age_in_tax_year() were renamed from private
to public in 006-reporting-aggregation (research.md §1) so that feature
can reuse them rather than re-implementing the same age-translation
formula -- behavior is unchanged, confirmed by these same tests.
"""

import pytest

from retirement_planner.comparison import (
    DeterministicReturnAssumption,
    StrategyConfiguration,
    deemed_rmd_owner,
    member_age_in_tax_year,
    run_plan_projection,
)
from retirement_planner.comparison.projection import _approximate_magi, _household_gross_social_security_benefit
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember
from retirement_planner.tax import FederalTaxResult, IncomeComponents


def _mfj_household(you_age=60, spouse_age=58, you_benefit=32_000, spouse_benefit=24_000):
    return Household(
        filing_status="married_filing_jointly",
        members=[
            HouseholdMember(person_name="you", current_age=you_age, ss_claim_age=67, ss_annual_benefit=you_benefit),
            HouseholdMember(
                person_name="spouse", current_age=spouse_age, ss_claim_age=67, ss_annual_benefit=spouse_benefit
            ),
        ],
    )


def _strategy(**overrides):
    base = dict(
        label="test",
        withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
        conversion_window=None,
        claiming_ages={"you": 67, "spouse": 67},
    )
    base.update(overrides)
    return StrategyConfiguration(**base)


# --- private per-year helpers (research.md §2, §3-4, data-model.md § Relationships) ---


def testmember_age_in_tax_year_translates_from_reference_year():
    member = HouseholdMember(person_name="you", current_age=60, ss_claim_age=67, ss_annual_benefit=0)
    assert member_age_in_tax_year(member, tax_year=2030, reference_tax_year=2026) == 64
    assert member_age_in_tax_year(member, tax_year=2026, reference_tax_year=2026) == 60
    assert member_age_in_tax_year(member, tax_year=2020, reference_tax_year=2026) == 54


def testdeemed_rmd_owner_is_the_older_member():
    household = _mfj_household(you_age=60, spouse_age=58)
    assert deemed_rmd_owner(household).person_name == "you"

    reversed_household = _mfj_household(you_age=58, spouse_age=60)
    assert deemed_rmd_owner(reversed_household).person_name == "spouse"


def test_household_gross_social_security_benefit_counts_only_after_claiming_age():
    household = _mfj_household(you_age=60, spouse_age=58, you_benefit=32_000, spouse_benefit=24_000)
    claiming_ages = {"you": 67, "spouse": 70}

    before_anyone_claims = _household_gross_social_security_benefit(
        household, ages_this_year={"you": 65, "spouse": 63}, claiming_ages=claiming_ages
    )
    assert before_anyone_claims == 0.0

    after_you_claim = _household_gross_social_security_benefit(
        household, ages_this_year={"you": 67, "spouse": 65}, claiming_ages=claiming_ages
    )
    assert after_you_claim == 32_000.0

    after_both_claim = _household_gross_social_security_benefit(
        household, ages_this_year={"you": 70, "spouse": 70}, claiming_ages=claiming_ages
    )
    assert after_both_claim == 56_000.0


# --- 011-per-owner-accounts: per-member RMD summation (replaces the
# removed deemed-RMD-owner-selection assumption -- each member's RMD is now
# computed from their own age against their own traditional_ownership_shares
# -derived balance, summed into the year's total, research.md §1) ---


def test_rmd_reflects_only_the_member_whos_reached_the_starting_age():
    household = _mfj_household(you_age=74, spouse_age=60)
    accounts = AccountBalances(traditional=1_000_000, roth=0, taxable=0)
    strategy = _strategy(claiming_ages={"you": 99, "spouse": 99})
    return_assumption = DeterministicReturnAssumption(annual_real_return=0.0)

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.75, "spouse": 0.25},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=74,
        strategy=strategy,
        return_assumption=return_assumption,
    )

    assert len(result.years) == 1
    # you: $750k @ age 74 (divisor 25.5) = $29,411.76...; spouse: age 60, not
    # yet RMD-required -> $0. NOT $1,000,000/25.5 (the old deemed-owner
    # attribution of the full household balance to the older member).
    assert result.years[0].mechanics.withdrawal_plan.rmd_drawn == pytest.approx(750_000 / 25.5)


def test_rmd_sums_both_members_when_both_have_reached_the_starting_age():
    household = _mfj_household(you_age=76, spouse_age=74)
    accounts = AccountBalances(traditional=2_000_000, roth=0, taxable=0)
    strategy = _strategy(claiming_ages={"you": 99, "spouse": 99})
    return_assumption = DeterministicReturnAssumption(annual_real_return=0.0)

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.6, "spouse": 0.4},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=76,
        strategy=strategy,
        return_assumption=return_assumption,
    )

    # you: $1.2M @ 76 (divisor 23.7); spouse: $800k @ 74 (divisor 25.5) --
    # each sized to their own share, summed, not a single household figure.
    expected = 1_200_000 / 23.7 + 800_000 / 25.5
    assert result.years[0].mechanics.withdrawal_plan.rmd_drawn == pytest.approx(expected)


def test_rmd_ignores_a_member_with_zero_share_regardless_of_age():
    household = _mfj_household(you_age=80, spouse_age=90)
    accounts = AccountBalances(traditional=500_000, roth=0, taxable=0)
    strategy = _strategy(claiming_ages={"you": 99, "spouse": 99})
    return_assumption = DeterministicReturnAssumption(annual_real_return=0.0)

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 1.0, "spouse": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=90,
        strategy=strategy,
        return_assumption=return_assumption,
    )

    # spouse (90, well past the starting age) owns none of the traditional
    # balance -- their RMD is $0, not a share of you's balance.
    assert result.years[0].mechanics.withdrawal_plan.rmd_drawn == pytest.approx(500_000 / 20.2)


def test_missing_member_from_traditional_ownership_shares_raises_key_error_eagerly():
    household = _mfj_household(you_age=74, spouse_age=60)
    accounts = AccountBalances(traditional=1_000_000, roth=0, taxable=0)
    strategy = _strategy(claiming_ages={"you": 99, "spouse": 99})

    with pytest.raises(KeyError):
        run_plan_projection(
            household=household,
            accounts=accounts,
            traditional_ownership_shares={"you": 1.0},  # missing "spouse"
            annual_spending_need=0,
            state="FL",
            reference_tax_year=2026,
            start_plan_year=1,
            start_tax_year=2026,
            plan_to_age=74,
            strategy=strategy,
            return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
        )


# --- run_plan_projection() end-to-end behavior ---


def test_growth_applied_uniformly_between_years():
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=70, ss_claim_age=99, ss_annual_benefit=0)],
    )
    accounts = AccountBalances(traditional=0, roth=0, taxable=100_000)
    strategy = _strategy(claiming_ages={"you": 99})
    return_assumption = DeterministicReturnAssumption(annual_real_return=0.05)

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=72,
        strategy=strategy,
        return_assumption=return_assumption,
    )

    assert len(result.years) == 3
    assert result.years[0].starting_balances.taxable == 100_000
    assert result.years[0].ending_balances.taxable == pytest.approx(105_000)
    assert result.years[1].starting_balances.taxable == result.years[0].ending_balances.taxable
    assert result.years[2].ending_balances.taxable == pytest.approx(100_000 * 1.05**3)


def test_tax_funding_withdrawal_draws_the_years_tax_owed_from_post_mechanics_balances():
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=75, ss_claim_age=99, ss_annual_benefit=0)],
    )
    accounts = AccountBalances(traditional=1_000_000, roth=0, taxable=500_000)
    strategy = _strategy(claiming_ages={"you": 99})
    return_assumption = DeterministicReturnAssumption(annual_real_return=0.0)

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=75,
        strategy=strategy,
        return_assumption=return_assumption,
    )

    year = result.years[0]
    tax_owed = year.federal_tax.federal_tax_owed + year.state_tax.state_tax_owed
    assert tax_owed > 0
    assert year.tax_funding_withdrawal.rmd_drawn == 0
    assert len(year.tax_funding_withdrawal.sequence_withdrawals) == 1
    assert year.tax_funding_withdrawal.sequence_withdrawals[0].account_type == "taxable"
    assert year.tax_funding_withdrawal.sequence_withdrawals[0].amount == pytest.approx(tax_owed)
    assert year.shortfall == 0
    assert year.ending_balances.taxable == pytest.approx(500_000 - tax_owed)


def test_shortfall_continues_across_years_without_raising_and_never_goes_negative():
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=70, ss_claim_age=99, ss_annual_benefit=0)],
    )
    accounts = AccountBalances(traditional=0, roth=0, taxable=1_000)
    strategy = _strategy(claiming_ages={"you": 99})
    return_assumption = DeterministicReturnAssumption(annual_real_return=0.0)

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=5_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=72,
        strategy=strategy,
        return_assumption=return_assumption,
    )

    assert len(result.years) == 3
    assert result.outcome.first_shortfall_plan_year == 1
    for year in result.years:
        assert year.shortfall > 0
        assert year.ending_balances.traditional >= 0
        assert year.ending_balances.roth >= 0
        assert year.ending_balances.taxable >= 0


class _YearVaryingReturnStub:
    """A minimal ReturnSchedule (005-simulation-engine research.md §1) whose
    return varies by plan_year, used to confirm run_plan_projection() calls
    return_for_plan_year(plan_year) for its growth factor rather than
    reading a fixed .annual_real_return field."""

    def __init__(self, returns_by_plan_year: dict[int, float]):
        self._returns_by_plan_year = returns_by_plan_year

    def return_for_plan_year(self, plan_year: int) -> float:
        return self._returns_by_plan_year[plan_year]


def test_growth_factor_calls_return_for_plan_year_and_varies_by_year():
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=70, ss_claim_age=99, ss_annual_benefit=0)],
    )
    accounts = AccountBalances(traditional=0, roth=0, taxable=100_000)
    strategy = _strategy(claiming_ages={"you": 99})
    return_schedule = _YearVaryingReturnStub({1: 0.10, 2: 0.00, 3: 0.20})

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=72,
        strategy=strategy,
        return_assumption=return_schedule,
    )

    assert len(result.years) == 3
    assert result.years[0].ending_balances.taxable == pytest.approx(100_000 * 1.10)
    assert result.years[1].ending_balances.taxable == pytest.approx(100_000 * 1.10 * 1.00)
    assert result.years[2].ending_balances.taxable == pytest.approx(100_000 * 1.10 * 1.00 * 1.20)


def test_deterministic_return_assumption_return_for_plan_year_ignores_plan_year():
    return_assumption = DeterministicReturnAssumption(annual_real_return=0.045)
    assert return_assumption.return_for_plan_year(1) == 0.045
    assert return_assumption.return_for_plan_year(35) == 0.045


def test_repeated_calls_with_identical_inputs_produce_identical_results():
    household = _mfj_household()
    accounts = AccountBalances(traditional=1_500_000, roth=400_000, taxable=200_000)
    strategy = _strategy()
    return_assumption = DeterministicReturnAssumption(annual_real_return=0.045)

    kwargs = dict(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.75, "spouse": 0.25},
        annual_spending_need=110_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=70,
        strategy=strategy,
        return_assumption=return_assumption,
    )

    first_run = run_plan_projection(**kwargs)
    second_run = run_plan_projection(**kwargs)

    assert first_run == second_run


# -- 010-advanced-tax-benefits: shared MAGI-approximation helper (research.md §2) --


def test_approximate_magi_sums_ordinary_income_and_taxable_social_security():
    income = IncomeComponents(ordinary_income=150_000.0, social_security_gross_benefit=32_000.0)
    federal_tax = FederalTaxResult(federal_tax_owed=18_000.0, taxable_social_security=27_200.0, figures_used=[])

    assert _approximate_magi(income, federal_tax) == 150_000.0 + 27_200.0


def test_approximate_magi_ignores_gross_social_security_benefit_directly():
    """MAGI uses the taxable portion of Social Security (already computed
    by federal.py's own provisional-income rule), never the gross benefit
    -- research.md §2's own stated approximation."""
    income = IncomeComponents(ordinary_income=0.0, social_security_gross_benefit=50_000.0)
    federal_tax = FederalTaxResult(federal_tax_owed=0.0, taxable_social_security=0.0, figures_used=[])

    assert _approximate_magi(income, federal_tax) == 0.0
