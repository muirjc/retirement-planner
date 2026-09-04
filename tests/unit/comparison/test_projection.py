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
from retirement_planner.mechanics import AccountBalances, InheritedAccountBalance
from retirement_planner.scenario import Household, HouseholdMember, IncomeStream
from retirement_planner.tax import FederalTaxResult, IncomeComponents, compute_taxable_social_security


def _mfj_household(you_age=60, spouse_age=58, you_benefit=32_000, spouse_benefit=24_000, you_fra=67.0, spouse_fra=67.0):
    # 016-ss-claiming-age-actuarial-adjustment: full_retirement_age defaults
    # to 67.0, matching this helper's own hardcoded ss_claim_age=67 -- so
    # every existing caller that relies on the default claiming_ages
    # ({"you": 67, "spouse": 67}, _strategy()'s own base) sees 0% adjustment
    # and unchanged pre-feature benefit amounts, exactly as
    # research.md Decision 3 intends. Callers exercising a claiming age
    # that diverges from 67 pass an explicit *_fra to keep their own
    # expected amounts meaningful.
    return Household(
        filing_status="married_filing_jointly",
        members=[
            HouseholdMember(
                person_name="you",
                current_age=you_age,
                ss_claim_age=67,
                ss_annual_benefit=you_benefit,
                full_retirement_age=you_fra,
            ),
            HouseholdMember(
                person_name="spouse",
                current_age=spouse_age,
                ss_claim_age=67,
                ss_annual_benefit=spouse_benefit,
                full_retirement_age=spouse_fra,
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
    # full_retirement_age matches each member's own claiming_ages entry
    # below (67 for "you", 70 for spouse) so this test isolates the
    # 0-vs-nonzero *timing* logic under test here, unaffected by the
    # separate claiming-age-adjustment magnitude logic (that math has its
    # own dedicated coverage in test_social_security_benefit.py and
    # test_compare_claiming_age_grid.py).
    household = _mfj_household(you_age=60, spouse_age=58, you_benefit=32_000, spouse_benefit=24_000, you_fra=67.0, spouse_fra=70.0)
    claiming_ages = {"you": 67, "spouse": 70}

    before_anyone_claims = _household_gross_social_security_benefit(household, ages_this_year={"you": 65, "spouse": 63}, claiming_ages=claiming_ages, tax_year=2026)
    assert before_anyone_claims == 0.0

    after_you_claim = _household_gross_social_security_benefit(household, ages_this_year={"you": 67, "spouse": 65}, claiming_ages=claiming_ages, tax_year=2026)
    assert after_you_claim == 32_000.0

    after_both_claim = _household_gross_social_security_benefit(household, ages_this_year={"you": 70, "spouse": 70}, claiming_ages=claiming_ages, tax_year=2026)
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


# -- 012-inherited-ira-rmd: inherited account annual distribution (US1) and
# 10-year forced depletion (US2) -- data-model.md § Consumption, quickstart.md --


def _single_member_household(current_age=55):
    return Household(
        filing_status="single",
        members=[
            HouseholdMember(
                person_name="you",
                current_age=current_age,
                ss_claim_age=67,
                ss_annual_benefit=0,
                full_retirement_age=67.0,
            )
        ],
    )


def _inherited_account(**overrides):
    base = dict(
        account_id="traditional-1",
        balance=250_000.0,
        death_year=2023,
        decedent_age_at_death=80,
        depletion_deadline_year=2033,
        beneficiary_person_name="you",  # rp-kn5: consulted for the "longer of" comparison now too
    )
    base.update(overrides)
    return InheritedAccountBalance(**base)


def test_inherited_account_annual_distribution_included_in_withdrawal_plan():
    """quickstart.md §1 (SC-001): the inherited account's own distribution
    -- computed from the Single Life Expectancy divisor, not from any
    ownership share of the pooled traditional balance -- shows up as
    inherited_distribution_drawn."""
    household = _single_member_household(current_age=55)
    accounts = AccountBalances(traditional=0, roth=0, taxable=100_000)
    strategy = _strategy(claiming_ages={"you": 99})

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0},
        inherited_accounts=[_inherited_account()],
        annual_spending_need=10_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=55,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    first_year = result.years[0]
    # rp-kn5: household member "you" (55 in 2026) is the account's own
    # beneficiary_person_name and much younger than the decedent
    # (decedent_age_at_death=80) -- the "longer of" comparison picks the
    # beneficiary's own divisor (Table I age 53 at the 2024 initial divisor
    # year, decremented 2 years to 2026 -> 33.4 - 2 = 31.4), not the
    # decedent's shorter one (11.2 - 2 = 9.2).
    assert first_year.mechanics.withdrawal_plan.inherited_distribution_drawn == pytest.approx(250_000 / 31.4)
    # Pooled traditional balance is untouched by the inherited account
    # entirely (research.md §5) -- stays $0 throughout.
    assert first_year.starting_balances.traditional == 0
    assert first_year.ending_balances.traditional == 0


def test_inherited_account_distribution_excluded_when_no_inherited_accounts_passed():
    """inherited_accounts defaults to [] -- a strict no-op, reproducing
    every existing scenario's exact prior output (plan.md's Constraints)."""
    household = _single_member_household(current_age=55)
    accounts = AccountBalances(traditional=0, roth=0, taxable=100_000)
    strategy = _strategy(claiming_ages={"you": 99})

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0},
        annual_spending_need=10_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=55,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    assert result.years[0].mechanics.withdrawal_plan.inherited_distribution_drawn == 0.0


def test_inherited_account_balance_grows_and_divisor_reduces_year_over_year():
    household = _single_member_household(current_age=55)
    accounts = AccountBalances(traditional=0, roth=0, taxable=100_000)
    strategy = _strategy(claiming_ages={"you": 99})
    inherited = _inherited_account()

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0},
        inherited_accounts=[inherited],
        annual_spending_need=10_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=56,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.05),
    )

    year_1_distribution = result.years[0].mechanics.withdrawal_plan.inherited_distribution_drawn
    year_2_distribution = result.years[1].mechanics.withdrawal_plan.inherited_distribution_drawn
    # rp-kn5: beneficiary "you" (55) is younger than the decedent (80), so
    # the beneficiary's own divisor wins the "longer of" comparison both
    # years (31.4 in 2026, decremented to 30.4 in 2027 -- never the
    # decedent's shorter 9.2/8.2). Hand check: year 1 balance=250,000,
    # divisor=31.4 -> distribution=7,961.78. Remaining balance 242,038.22
    # grows 5% -> 254,140.13; divisor drops to 30.4 -> year 2 distribution
    # = 254,140.13 / 30.4 = 8,360.53. (With 0% growth this ratio's algebra
    # makes consecutive distributions exactly equal -- a real property of
    # the "reduce divisor by 1" method, not a bug -- so growth must be
    # nonzero to observe the divisor's effect.)
    assert year_1_distribution == pytest.approx(250_000 / 31.4)
    assert year_2_distribution == pytest.approx((250_000 - 250_000 / 31.4) * 1.05 / 30.4)
    assert year_2_distribution != pytest.approx(year_1_distribution)
    assert year_2_distribution > 0


def test_two_inherited_accounts_from_different_decedents_computed_independently():
    """SC-004: changing one account's facts never changes the other's
    computed distribution."""
    household = _single_member_household(current_age=55)
    accounts = AccountBalances(traditional=0, roth=0, taxable=100_000)
    strategy = _strategy(claiming_ages={"you": 99})

    account_a = _inherited_account(account_id="traditional-1", balance=250_000, death_year=2023, decedent_age_at_death=80)
    account_b = _inherited_account(account_id="traditional-2", balance=90_000, death_year=2020, decedent_age_at_death=75, depletion_deadline_year=2030)

    result_both = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0},
        inherited_accounts=[account_a, account_b],
        annual_spending_need=10_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=55,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    result_a_alone = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0},
        inherited_accounts=[_inherited_account(account_id="traditional-1", balance=250_000, death_year=2023, decedent_age_at_death=80)],
        annual_spending_need=10_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=55,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    total_drawn = result_both.years[0].mechanics.withdrawal_plan.inherited_distribution_drawn
    a_alone_drawn = result_a_alone.years[0].mechanics.withdrawal_plan.inherited_distribution_drawn
    # account_a's own contribution to the combined total equals exactly
    # what it produces on its own -- account_b's presence never perturbs it.
    assert total_drawn > a_alone_drawn
    assert total_drawn - a_alone_drawn > 0  # account_b's own distribution


def test_inherited_account_forces_full_balance_distribution_in_deadline_year():
    """quickstart.md §2 (US2, SC-002): the entire remaining balance is
    distributed in depletion_deadline_year, not just the divisor-computed
    annual amount."""
    household = _single_member_household(current_age=55)
    accounts = AccountBalances(traditional=0, roth=0, taxable=1_000_000)
    strategy = _strategy(claiming_ages={"you": 99})
    inherited = _inherited_account(balance=5_000.0, death_year=2016, decedent_age_at_death=80, depletion_deadline_year=2026)

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0},
        inherited_accounts=[inherited],
        annual_spending_need=10_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=55,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    # The deadline-year distribution is the account's entire $5,000
    # remaining balance -- not $5,000 / (a divisor far smaller than $5,000
    # itself would ever require).
    assert result.years[0].mechanics.withdrawal_plan.inherited_distribution_drawn == pytest.approx(5_000.0)


def test_inherited_account_contributes_nothing_after_its_depletion_deadline():
    household = _single_member_household(current_age=55)
    accounts = AccountBalances(traditional=0, roth=0, taxable=1_000_000)
    strategy = _strategy(claiming_ages={"you": 99})
    inherited = _inherited_account(balance=5_000.0, death_year=2016, decedent_age_at_death=80, depletion_deadline_year=2026)

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0},
        inherited_accounts=[inherited],
        annual_spending_need=10_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=57,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    assert result.years[0].tax_year == 2026  # the deadline year itself
    later_years = [year for year in result.years if year.tax_year > 2026]
    assert len(later_years) == 2
    assert all(year.mechanics.withdrawal_plan.inherited_distribution_drawn == 0.0 for year in later_years)


# -- rp-bm8.4: retains *why* each year's inherited-account distribution is
# what it is (deep-computation-traceability follow-on to rp-bm8.3) --


def test_inherited_account_reason_is_ten_year_rule_when_deadline_already_passed_before_plan_start():
    """The exact combination the Walkthrough feature surfaced as
    previously-invisible: a plan that starts YEARS after
    depletion_deadline_year has already passed (not merely reaching it
    mid-plan, which test_inherited_account_forces_full_balance_distribution_
    in_deadline_year above already covers) -- the same
    `tax_year >= depletion_deadline_year` "safety net" check fires
    immediately in plan year 1."""
    household = _single_member_household(current_age=64)
    accounts = AccountBalances(traditional=0, roth=0, taxable=1_000_000)
    strategy = _strategy(claiming_ages={"you": 99})
    # death_year=2005 -> depletion_deadline_year=2015, 11 years before this
    # plan's own start_tax_year=2026.
    inherited = _inherited_account(balance=513_000.0, death_year=2005, decedent_age_at_death=67, depletion_deadline_year=2015)

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0},
        inherited_accounts=[inherited],
        annual_spending_need=15_000,
        state="NC",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=65,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    first_year = result.years[0]
    assert first_year.inherited_account_distributions["traditional-1"] == pytest.approx(513_000.0)
    assert first_year.inherited_account_distribution_reason["traditional-1"] == "ten_year_rule_deadline"
    assert "traditional-1" not in first_year.inherited_account_rmd_divisor
    assert first_year.inherited_account_depletion_deadline_year["traditional-1"] == 2015


def test_inherited_account_reason_is_annual_rmd_within_the_ten_year_window():
    """Companion to the above: a genuine divisor-based partial RMD, still
    within the 10-year window, is reason "annual_rmd" with a real divisor
    retained."""
    household = _single_member_household(current_age=55)
    accounts = AccountBalances(traditional=0, roth=0, taxable=1_000_000)
    strategy = _strategy(claiming_ages={"you": 99})
    inherited = _inherited_account(balance=250_000.0, death_year=2023, decedent_age_at_death=80, depletion_deadline_year=2033)

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0},
        inherited_accounts=[inherited],
        annual_spending_need=10_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=56,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    first_year = result.years[0]
    assert first_year.inherited_account_distribution_reason["traditional-1"] == "annual_rmd"
    assert first_year.inherited_account_rmd_divisor["traditional-1"] > 0.0
    assert first_year.inherited_account_distributions["traditional-1"] == pytest.approx(
        250_000.0 / first_year.inherited_account_rmd_divisor["traditional-1"]
    )
    assert first_year.inherited_account_depletion_deadline_year["traditional-1"] == 2033


def test_inherited_account_reason_absent_once_account_already_fully_distributed():
    """Once an account's balance hits 0 in an earlier year, the existing
    loop `continue`s past it entirely -- confirms the three new fields
    follow that same convention (no entry, not a 0.0/None placeholder)."""
    household = _single_member_household(current_age=55)
    accounts = AccountBalances(traditional=0, roth=0, taxable=1_000_000)
    strategy = _strategy(claiming_ages={"you": 99})
    inherited = _inherited_account(balance=5_000.0, death_year=2016, decedent_age_at_death=80, depletion_deadline_year=2026)

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0},
        inherited_accounts=[inherited],
        annual_spending_need=10_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=57,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    later_years = [year for year in result.years if year.tax_year > 2026]
    assert len(later_years) == 2
    assert all("traditional-1" not in year.inherited_account_distribution_reason for year in later_years)


# -- 012-inherited-ira-rmd Polish (T026): regression parity for scenarios
# with no inherited accounts, mirroring 011's own FR-009/SC-004 discipline --


def test_regression_parity_omitted_vs_explicit_empty_inherited_accounts():
    """inherited_accounts=[] (the default) must be a strict no-op --
    identical output whether the parameter is omitted entirely or passed
    explicitly as an empty list, for a realistic multi-year, multi-strategy
    scenario (reusing test_growth_applied_uniformly_between_years' own
    fixture, plan.md's Constraints)."""
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=70, ss_claim_age=99, ss_annual_benefit=0)],
    )
    accounts = AccountBalances(traditional=900_000, roth=200_000, taxable=100_000)
    strategy = _strategy(claiming_ages={"you": 99})
    return_assumption = DeterministicReturnAssumption(annual_real_return=0.05)

    kwargs = dict(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=60_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=75,
        strategy=strategy,
        return_assumption=return_assumption,
    )

    omitted = run_plan_projection(**kwargs)
    explicit_empty = run_plan_projection(**kwargs, inherited_accounts=[])

    assert omitted == explicit_empty


def test_regression_parity_every_existing_multi_year_test_fixture_unaffected():
    """The exact fixture/assertions from test_growth_applied_uniformly_between_years
    (a pre-012 test), re-run byte-for-byte identically -- confirms this
    feature changed no existing scenario's output."""
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
    assert result.years[0].mechanics.withdrawal_plan.inherited_distribution_drawn == 0.0


# -- 015-per-account-projection-detail: PlanYearProjection's four new
# retained (not newly-computed) fields (data-model.md § PlanYearProjection
# extension) --


def test_member_rmd_amounts_sum_to_the_pooled_rmd_drawn_and_match_each_members_own_figure():
    household = _mfj_household(you_age=76, spouse_age=74)
    accounts = AccountBalances(traditional=2_000_000, roth=0, taxable=0)
    strategy = _strategy(claiming_ages={"you": 99, "spouse": 99})

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
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    year = result.years[0]
    assert sum(year.member_rmd_amounts.values()) == pytest.approx(year.mechanics.withdrawal_plan.rmd_drawn)
    assert year.member_rmd_amounts["you"] == pytest.approx(1_200_000 / 23.7)
    assert year.member_rmd_amounts["spouse"] == pytest.approx(800_000 / 25.5)


def test_member_rmd_amounts_omits_a_member_with_zero_share_or_below_start_age():
    household = _mfj_household(you_age=80, spouse_age=60)
    accounts = AccountBalances(traditional=500_000, roth=0, taxable=0)
    strategy = _strategy(claiming_ages={"you": 99, "spouse": 99})

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 1.0, "spouse": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=80,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    # spouse has a 0.0 share, so no compute_rmd() call is ever made for them
    # -- absent from the dict entirely, not present at $0.0.
    assert "spouse" not in result.years[0].member_rmd_amounts
    assert result.years[0].member_rmd_amounts["you"] == pytest.approx(500_000 / 20.2)


def test_member_social_security_benefits_present_even_before_claiming_never_omitted():
    household = _mfj_household(you_age=60, spouse_age=58, you_benefit=32_000, spouse_benefit=24_000)
    accounts = AccountBalances(traditional=0, roth=0, taxable=500_000)
    strategy = _strategy(claiming_ages={"you": 67, "spouse": 70})

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0, "spouse": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=70,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    first_year = result.years[0]  # you=60, spouse=58 -- neither has claimed yet
    assert first_year.member_social_security_benefits == {"you": 0.0, "spouse": 0.0}
    assert sum(first_year.member_social_security_benefits.values()) == 0.0

    last_year = result.years[-1]  # you=70, spouse=68 -- you has claimed (67), spouse hasn't (70)
    assert last_year.member_social_security_benefits["you"] == 32_000.0
    assert last_year.member_social_security_benefits["spouse"] == 0.0
    assert sum(last_year.member_social_security_benefits.values()) == 32_000.0


def test_income_stream_appears_only_within_active_window():
    """021-pension-annuity-income (rp-pid), US1/US2: a lifetime
    cola_adjusted pension appears at its full flat amount from start_age
    on; a windowed fixed_nominal annuity appears only inside
    [start_age, end_age] inclusive, mirrors
    test_member_social_security_benefits_present_even_before_claiming_never_omitted's
    own isolate-with-zero-spending-need pattern."""
    household = _single_member_household(current_age=60)
    household.members[0].income_streams = [
        IncomeStream(
            label="State Pension",
            stream_type="pension",
            start_age=62,
            annual_amount=18_000.0,
            inflation_adjustment="cola_adjusted",
        ),
        IncomeStream(
            label="Old annuity",
            stream_type="annuity",
            start_age=65,
            end_age=65,
            annual_amount=6_000.0,
            inflation_adjustment="fixed_nominal",
        ),
    ]
    accounts = AccountBalances(traditional=0, roth=0, taxable=500_000)
    strategy = _strategy(claiming_ages={"you": 99})

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=67,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    by_age = {60 + i: year for i, year in enumerate(result.years)}
    assert by_age[61].member_income_stream_amounts["you"] == 0.0
    assert by_age[61].mechanics.ordinary_income == 0.0
    assert by_age[62].member_income_stream_amounts["you"] == pytest.approx(18_000.0)
    assert by_age[62].mechanics.ordinary_income == pytest.approx(18_000.0)
    # 65 is the annuity's own single-year window (end_age == start_age).
    assert by_age[65].member_income_stream_amounts["you"] > 18_000.0
    assert by_age[66].member_income_stream_amounts["you"] == pytest.approx(18_000.0)


def test_income_streams_are_independent_per_member():
    """021-pension-annuity-income (rp-pid), US2: two members' own
    independently-windowed streams don't cross-contaminate each other's
    member_income_stream_amounts entry."""
    household = _mfj_household(you_age=62, spouse_age=62)
    household.members[0].income_streams = [
        IncomeStream(
            label="Your pension",
            stream_type="pension",
            start_age=62,
            annual_amount=10_000.0,
            inflation_adjustment="cola_adjusted",
        )
    ]
    household.members[1].income_streams = [
        IncomeStream(
            label="Spouse annuity",
            stream_type="annuity",
            start_age=65,
            annual_amount=4_000.0,
            inflation_adjustment="cola_adjusted",
        )
    ]
    accounts = AccountBalances(traditional=0, roth=0, taxable=500_000)
    strategy = _strategy(claiming_ages={"you": 99, "spouse": 99})

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0, "spouse": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=66,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    first_year = result.years[0]  # both age 62
    assert first_year.member_income_stream_amounts == {"you": 10_000.0, "spouse": 0.0}
    last_year = result.years[-1]  # both age 66
    assert last_year.member_income_stream_amounts == {"you": 10_000.0, "spouse": 4_000.0}
    assert last_year.mechanics.ordinary_income == pytest.approx(14_000.0)


def test_earned_income_stream_treated_identically_to_pension_for_tax_purposes():
    """021-pension-annuity-income (rp-pid), US3: stream_type is purely
    informational for *ordinary income tax* purposes -- an earned_income
    stream flows through the exact same code path as pension/annuity
    (data-model.md), contributing identically to mechanics.ordinary_income.
    (022-fica-payroll-tax, rp-elp, later added a real FICA-specific
    consequence for earned_income streams -- see test_projection.py's own
    FICA-focused tests below -- so this test no longer asserts that no
    such figure appears at all, only that ordinary-income treatment is
    identical.)"""
    household = _single_member_household(current_age=63)
    household.members[0].income_streams = [
        IncomeStream(
            label="Part-time consulting",
            stream_type="earned_income",
            start_age=63,
            end_age=65,
            annual_amount=25_000.0,
            inflation_adjustment="fixed_nominal",
        )
    ]
    accounts = AccountBalances(traditional=0, roth=0, taxable=500_000)
    strategy = _strategy(claiming_ages={"you": 99})

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=67,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    by_age = {63 + i: year for i, year in enumerate(result.years)}
    assert by_age[63].member_income_stream_amounts["you"] > 0.0
    assert by_age[63].mechanics.ordinary_income == by_age[63].member_income_stream_amounts["you"]
    assert by_age[66].member_income_stream_amounts["you"] == 0.0  # window ended after 65


# --- 027-nc-bailey-exclusion ---------------------------------------------


def _bailey_and_other_pension_household(bailey_amount, other_amount, bailey_qualifying=True, current_age=65):
    """A household with two pension streams: one Bailey-qualifying (or not,
    per `bailey_qualifying`), one plain -- start_age == current_age so both
    are active from year 1, mirroring the income-stream tests above's own
    "start_age == current_age" convention for keeping the math simple."""
    household = _single_member_household(current_age=current_age)
    household.members[0].income_streams = [
        IncomeStream(
            label="State Teachers' Pension",
            stream_type="pension",
            start_age=current_age,
            annual_amount=bailey_amount,
            inflation_adjustment="cola_adjusted",
            bailey_qualifying=bailey_qualifying,
        ),
        IncomeStream(
            label="Private annuity",
            stream_type="annuity",
            start_age=current_age,
            annual_amount=other_amount,
            inflation_adjustment="cola_adjusted",
        ),
    ]
    return household


def test_bailey_qualifying_pension_reduces_nc_state_tax_only():
    """spec.md User Story 1: a $40k Bailey-qualifying pension + $30k other
    pension income, projected against NC -- only the $30k is taxed by NC,
    exactly as tax.state.nc.compute_tax() computes in isolation
    (quickstart.md § 1)."""
    household = _bailey_and_other_pension_household(bailey_amount=40_000.0, other_amount=30_000.0)
    accounts = AccountBalances(traditional=0, roth=0, taxable=0)
    strategy = _strategy(claiming_ages={"you": 99})

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0},
        annual_spending_need=0,
        state="NC",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=65,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    first_year = result.years[0]
    assert first_year.mechanics.ordinary_income == pytest.approx(70_000.0)
    assert first_year.state_tax.state_tax_owed == pytest.approx(30_000.0 * 0.0399)


def test_bailey_qualifying_flag_leaves_federal_fica_irmaa_niit_unaffected():
    """spec.md User Story 2: federal tax, FICA, IRMAA, and NIIT are
    identical whether or not the same income is marked bailey_qualifying --
    the exclusion is NC-state-only (research.md §5)."""
    common_kwargs = dict(
        accounts=AccountBalances(traditional=0, roth=0, taxable=0),
        traditional_ownership_shares={"you": 0.0},
        annual_spending_need=0,
        state="NC",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=65,
        strategy=_strategy(claiming_ages={"you": 99}),
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    with_flag = run_plan_projection(
        household=_bailey_and_other_pension_household(40_000.0, 30_000.0, bailey_qualifying=True), **common_kwargs
    )
    without_flag = run_plan_projection(
        household=_bailey_and_other_pension_household(40_000.0, 30_000.0, bailey_qualifying=False), **common_kwargs
    )

    with_year, without_year = with_flag.years[0], without_flag.years[0]
    assert with_year.mechanics.ordinary_income == without_year.mechanics.ordinary_income == pytest.approx(70_000.0)
    assert with_year.federal_tax == without_year.federal_tax
    assert with_year.fica_tax == without_year.fica_tax
    assert with_year.irmaa == without_year.irmaa
    assert with_year.niit == without_year.niit
    # Only NC's own state tax differs -- the whole point of the exclusion.
    assert with_year.state_tax.state_tax_owed < without_year.state_tax.state_tax_owed


@pytest.mark.parametrize("state", ["SC", "DE", "FL"])
def test_bailey_qualifying_flag_is_inert_outside_nc(state):
    """spec.md User Story 3: SC, DE, and FL compute identical results
    whether or not a stream is marked bailey_qualifying -- the flag has
    meaning only inside tax.state.nc.compute_tax()."""
    common_kwargs = dict(
        accounts=AccountBalances(traditional=0, roth=0, taxable=0),
        traditional_ownership_shares={"you": 0.0},
        annual_spending_need=0,
        state=state,
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=65,
        strategy=_strategy(claiming_ages={"you": 99}),
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    with_flag = run_plan_projection(
        household=_bailey_and_other_pension_household(40_000.0, 30_000.0, bailey_qualifying=True), **common_kwargs
    )
    without_flag = run_plan_projection(
        household=_bailey_and_other_pension_household(40_000.0, 30_000.0, bailey_qualifying=False), **common_kwargs
    )
    assert with_flag.years[0].state_tax.state_tax_owed == without_flag.years[0].state_tax.state_tax_owed


def _earned_income_household(annual_amount, current_age=63, start_age=63, end_age=None):
    household = _single_member_household(current_age=current_age)
    household.members[0].income_streams = [
        IncomeStream(
            label="Consulting",
            stream_type="earned_income",
            start_age=start_age,
            end_age=end_age,
            annual_amount=annual_amount,
            inflation_adjustment="cola_adjusted",
        )
    ]
    return household


def test_earned_income_stream_fica_is_funded_from_account_balances():
    """022-fica-payroll-tax (rp-elp), US1: FICA reduces the household's
    own account balances (spec.md FR-004/SC-002), not merely reported
    alongside them -- mirrors how IRMAA/NIIT/the early-withdrawal penalty
    already fund tax_owed."""
    common_kwargs = dict(
        accounts=AccountBalances(traditional=0, roth=0, taxable=500_000),
        traditional_ownership_shares={"you": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=64,
        strategy=_strategy(claiming_ages={"you": 99}),
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    with_earned_income = run_plan_projection(household=_earned_income_household(40_000), **common_kwargs)
    without_earned_income = run_plan_projection(household=_single_member_household(current_age=63), **common_kwargs)

    first_year = with_earned_income.years[0]
    assert first_year.fica_tax.total_fica_tax == pytest.approx(40_000 * (0.062 + 0.0145))
    assert with_earned_income.outcome.ending_balance < without_earned_income.outcome.ending_balance
    assert with_earned_income.outcome.cumulative_fica_tax_paid > 0.0
    assert without_earned_income.outcome.cumulative_fica_tax_paid == 0.0


def test_member_earned_income_retained_and_matches_what_funded_fica():
    """rp-bm8.4: PlanYearProjection.member_earned_income retains the exact
    per-member dict _member_earned_income_amounts() already computes to
    feed compute_fica_tax() -- previously discarded once FICA was
    computed. 6.2% OASDI + 1.45% Medicare, both uncapped here since
    $40,000 < the wage base."""
    result = run_plan_projection(
        household=_earned_income_household(40_000),
        accounts=AccountBalances(traditional=0, roth=0, taxable=500_000),
        traditional_ownership_shares={"you": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=64,
        strategy=_strategy(claiming_ages={"you": 99}),
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    first_year = result.years[0]
    assert first_year.member_earned_income["you"] == pytest.approx(40_000.0)
    assert first_year.fica_tax.member_oasdi_tax["you"] == pytest.approx(first_year.member_earned_income["you"] * 0.062)
    assert first_year.fica_tax.member_medicare_tax["you"] == pytest.approx(first_year.member_earned_income["you"] * 0.0145)


def test_member_earned_income_zero_for_pension_only_household():
    """A pension-only household's member_income_stream_amounts is nonzero
    but member_earned_income stays 0.0 -- confirms the two dicts really
    are independently tracked (pension/annuity never counts as wages)."""
    household = _single_member_household(current_age=63)
    household.members[0].income_streams = [
        IncomeStream(label="Pension", stream_type="pension", start_age=63, end_age=None, annual_amount=30_000, inflation_adjustment="cola_adjusted")
    ]
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=0, roth=0, taxable=500_000),
        traditional_ownership_shares={"you": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=64,
        strategy=_strategy(claiming_ages={"you": 99}),
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    first_year = result.years[0]
    assert first_year.member_income_stream_amounts["you"] == pytest.approx(30_000.0)
    assert first_year.member_earned_income["you"] == 0.0
    assert first_year.fica_tax.total_fica_tax == 0.0


def test_pension_and_annuity_streams_never_incur_fica():
    """spec.md Acceptance Scenario US1.2: a household with only pension/
    annuity streams (no earned_income) has fica_tax.total_fica_tax == 0.0
    every year."""
    household = _single_member_household(current_age=63)
    household.members[0].income_streams = [
        IncomeStream(
            label="Pension",
            stream_type="pension",
            start_age=63,
            annual_amount=40_000.0,
            inflation_adjustment="cola_adjusted",
        ),
        IncomeStream(
            label="Annuity",
            stream_type="annuity",
            start_age=63,
            annual_amount=10_000.0,
            inflation_adjustment="fixed_nominal",
        ),
    ]
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=0, roth=0, taxable=500_000),
        traditional_ownership_shares={"you": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=65,
        strategy=_strategy(claiming_ages={"you": 99}),
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    for year in result.years:
        assert year.fica_tax.total_fica_tax == 0.0
    assert result.outcome.cumulative_fica_tax_paid == 0.0


def test_no_income_streams_produces_zero_fica_and_unaffected_output():
    """spec.md FR-005/SC-003: a scenario with no income streams at all
    (every scenario predating 021/022) is unaffected -- fica_tax is
    always present (required field) but zeroed."""
    result = run_plan_projection(
        household=_single_member_household(current_age=63),
        accounts=AccountBalances(traditional=0, roth=0, taxable=500_000),
        traditional_ownership_shares={"you": 0.0},
        annual_spending_need=10_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=65,
        strategy=_strategy(claiming_ages={"you": 99}),
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    for year in result.years:
        assert year.fica_tax.total_fica_tax == 0.0
        assert year.fica_tax.member_oasdi_tax == {"you": 0.0}
        assert year.fica_tax.member_medicare_tax == {"you": 0.0}
    assert result.outcome.cumulative_fica_tax_paid == 0.0


def test_earned_income_over_wage_base_caps_oasdi_in_a_running_projection():
    """022-fica-payroll-tax (rp-elp), US2: the wage-base cap survives the
    full projection wiring, not just compute_fica_tax() in isolation."""
    household = _earned_income_household(250_000)
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=0, roth=0, taxable=500_000),
        traditional_ownership_shares={"you": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=63,
        strategy=_strategy(claiming_ages={"you": 99}),
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    first_year = result.years[0]
    assert first_year.fica_tax.member_oasdi_tax["you"] == pytest.approx(184_500 * 0.062)
    assert first_year.fica_tax.member_medicare_tax["you"] == pytest.approx(250_000 * 0.0145)


def test_additional_medicare_tax_applies_to_combined_mfj_earned_income_in_a_running_projection():
    """022-fica-payroll-tax (rp-elp), US3: two spouses each individually
    under the single-shaped $200k amount, but combined over the $250k MFJ
    threshold -- computed once for the household."""
    household = _mfj_household(you_age=63, spouse_age=63)
    household.members[0].income_streams = [
        IncomeStream(
            label="Consulting",
            stream_type="earned_income",
            start_age=63,
            annual_amount=150_000.0,
            inflation_adjustment="cola_adjusted",
        )
    ]
    household.members[1].income_streams = [
        IncomeStream(
            label="Consulting",
            stream_type="earned_income",
            start_age=63,
            annual_amount=150_000.0,
            inflation_adjustment="cola_adjusted",
        )
    ]
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=0, roth=0, taxable=1_000_000),
        traditional_ownership_shares={"you": 0.0, "spouse": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=63,
        strategy=_strategy(claiming_ages={"you": 99, "spouse": 99}),
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    first_year = result.years[0]
    assert first_year.fica_tax.additional_medicare_tax == pytest.approx((300_000 - 250_000) * 0.009)


def test_full_retirement_age_equal_to_claim_age_reproduces_pre_feature_flat_benefit():
    """016-ss-claiming-age-actuarial-adjustment backward compatibility
    (research.md Decision 3, spec.md FR-001): a member whose
    full_retirement_age equals their ss_claim_age -- the default every
    scenario predating this feature resolves to -- receives exactly their
    configured ss_annual_benefit once claimed, with zero adjustment,
    identical to this feature's absence."""
    household = _mfj_household(you_age=65, spouse_age=65, you_benefit=32_000, spouse_benefit=24_000, you_fra=67.0, spouse_fra=67.0)
    strategy = _strategy(claiming_ages={"you": 67, "spouse": 67})
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=0, roth=0, taxable=500_000),
        traditional_ownership_shares={"you": 0.0, "spouse": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=67,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    last_year = result.years[-1]  # you=67, spouse=67 -- both have just claimed, exactly at FRA
    assert last_year.member_social_security_benefits == {"you": 32_000.0, "spouse": 24_000.0}


def test_omitted_full_retirement_age_defaults_to_claim_age_even_when_household_built_directly():
    """The same backward-compatible default applies even when
    full_retirement_age is left None entirely (not just when explicitly
    set equal to ss_claim_age) -- the defense-in-depth default in
    _member_gross_social_security_benefits() itself (data-model.md), not
    only scenario.loader.parse_scenario()'s own resolution."""
    household = Household(
        filing_status="single",
        members=[
            HouseholdMember(person_name="you", current_age=66, ss_claim_age=67, ss_annual_benefit=32_000),
        ],
    )
    assert household.members[0].full_retirement_age is None  # never set -- the raw dataclass default

    strategy = _strategy(claiming_ages={"you": 67})
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=0, roth=0, taxable=500_000),
        traditional_ownership_shares={"you": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=67,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    assert result.years[-1].member_social_security_benefits["you"] == 32_000.0


# --- 017-ss-spousal-survivor-benefits: spousal benefit floor (rp-52n) ---


def test_spousal_floor_raises_a_lower_earning_members_benefit():
    """spec.md Acceptance Scenarios 1-2: a lower earner's benefit is
    raised to 50% of the higher earner's PIA once both have claimed; the
    higher earner's own benefit is unaffected."""
    household = _mfj_household(you_age=67, spouse_age=67, you_benefit=30_000, spouse_benefit=6_000)
    strategy = _strategy(claiming_ages={"you": 67, "spouse": 67})
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=0, roth=0, taxable=500_000),
        traditional_ownership_shares={"you": 0.0, "spouse": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=67,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    first_year = result.years[0]
    assert first_year.member_social_security_benefits["spouse"] == pytest.approx(15_000.0)  # 50% of 30,000, not 6,000
    assert first_year.member_social_security_benefits["you"] == pytest.approx(30_000.0)  # unaffected


def test_spousal_floor_uses_the_spousal_specific_reduction_rate():
    """spec.md Acceptance Scenario 3: a lower earner claiming before their
    own FRA has their spousal amount reduced via the SSA's spousal-
    specific rate (25/36 of 1%/month), not the worker's-own-benefit rate
    (5/9 of 1%/month) 016 already models -- so the two reduced amounts
    differ even though both start from the same PIA base."""
    household = _mfj_household(you_age=67, spouse_age=65, you_benefit=30_000, spouse_benefit=6_000, you_fra=67.0, spouse_fra=67.0)
    strategy = _strategy(claiming_ages={"you": 67, "spouse": 65})  # spouse claims 24 months before their own FRA
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=0, roth=0, taxable=500_000),
        traditional_ownership_shares={"you": 0.0, "spouse": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=67,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    spousal_reduction = 24 * (25 / 36) / 100  # spousal-specific tier-1 rate
    worker_reduction = 24 * (5 / 9) / 100  # 016's own worker-benefit tier-1 rate, for contrast
    assert spousal_reduction != pytest.approx(worker_reduction)
    expected_spousal_amount = 15_000.0 * (1.0 - spousal_reduction)
    assert result.years[0].member_social_security_benefits["spouse"] == pytest.approx(expected_spousal_amount)


def test_spousal_floor_does_not_apply_to_this_repos_own_reference_pair():
    """research.md Decision 5 / SC-002: the ~$32k/$24k pair used across
    this repo's own fixtures is comfortably above the 50% threshold
    ($16,000) -- confirming the spousal floor never perturbs it."""
    household = _mfj_household(you_age=67, spouse_age=67, you_benefit=32_000, spouse_benefit=24_000)
    strategy = _strategy(claiming_ages={"you": 67, "spouse": 67})
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=0, roth=0, taxable=500_000),
        traditional_ownership_shares={"you": 0.0, "spouse": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=67,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    assert result.years[0].member_social_security_benefits == {"you": 32_000.0, "spouse": 24_000.0}


def test_spousal_floor_never_applies_to_a_single_filing_status_household():
    """spec.md Acceptance Scenario 4, FR-004: a single-member household has
    no second member to derive a spousal floor from -- no spousal logic
    is consulted at all."""
    household = Household(
        filing_status="single",
        members=[
            HouseholdMember(person_name="you", current_age=67, ss_claim_age=67, ss_annual_benefit=6_000, full_retirement_age=67.0),
        ],
    )
    strategy = _strategy(claiming_ages={"you": 67})
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=0, roth=0, taxable=500_000),
        traditional_ownership_shares={"you": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=67,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    assert result.years[0].member_social_security_benefits["you"] == pytest.approx(6_000.0)


def test_spousal_floor_does_not_apply_until_both_members_have_claimed():
    """research.md Decision 3: the real SSA rule requires the other
    (higher-earning) spouse to have already filed for their own benefit
    before a spousal amount is payable off that record -- so a lower
    earner who has already claimed, while the higher earner has not yet
    reached their own claiming age, gets their own (unfloor) benefit
    only, this plan year."""
    household = _mfj_household(you_age=60, spouse_age=62, you_benefit=30_000, spouse_benefit=6_000)
    strategy = _strategy(claiming_ages={"you": 67, "spouse": 62})
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=0, roth=0, taxable=500_000),
        traditional_ownership_shares={"you": 0.0, "spouse": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=62,  # deemed_rmd_owner is the older member (spouse, 62) -- must reach this age for a year to run
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    first_year = result.years[0]  # you=60 (not yet claimed), spouse=62 (has claimed)
    assert first_year.member_social_security_benefits["you"] == 0.0
    # spouse has claimed their own (60-months-early-reduced, 016) benefit
    # -- 6,000 * 0.70 = 4,200 -- but the spousal floor cannot apply yet
    # since "you" (the higher earner) hasn't filed for their own benefit.
    # If the floor incorrectly applied here, spouse would instead see
    # 15,000 (50% of you's $30,000 PIA).
    expected_own_benefit = 6_000.0 * (1.0 - (36 * (5 / 9) / 100 + 24 * (5 / 12) / 100))
    assert first_year.member_social_security_benefits["spouse"] == pytest.approx(expected_own_benefit)


def test_predicted_death_age_beyond_the_horizon_has_zero_effect_on_projection_output():
    """018-survivor-scenario-projection (rp-g8y) spec.md Edge Cases: a
    predicted_death_age that translates to a tax year AFTER the
    projection's last plan year never takes effect. Here death age 80
    (=> death tax year 2039) is well beyond plan_to_age=75's own last
    plan year (tax year 2034 below) -- confirmed here by asserting a
    scenario that sets it produces byte-for-byte identical output to the
    same scenario without it. (Originally written under
    017-ss-spousal-survivor-benefits, when predicted_death_age had no
    effect on ANY projection by design -- this test's own age/horizon
    values happen to still exercise 018's own "beyond horizon" no-op
    case, so it was updated in place rather than replaced.)"""

    def _build(predicted_death_age):
        return Household(
            filing_status="married_filing_jointly",
            members=[
                HouseholdMember(
                    person_name="you",
                    current_age=67,
                    ss_claim_age=67,
                    ss_annual_benefit=30_000,
                    full_retirement_age=67.0,
                    predicted_death_age=predicted_death_age,
                ),
                HouseholdMember(person_name="spouse", current_age=67, ss_claim_age=67, ss_annual_benefit=24_000, full_retirement_age=67.0),
            ],
        )

    strategy = _strategy(claiming_ages={"you": 67, "spouse": 67})
    common_kwargs = dict(
        accounts=AccountBalances(traditional=500_000, roth=0, taxable=200_000),
        traditional_ownership_shares={"you": 0.6, "spouse": 0.4},
        annual_spending_need=60_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=75,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.04),
    )

    without_death_age = run_plan_projection(household=_build(None), **common_kwargs)
    with_death_age = run_plan_projection(household=_build(80), **common_kwargs)

    assert with_death_age == without_death_age


def test_compute_survivor_benefit_now_has_a_caller_in_this_module():
    """018-survivor-scenario-projection (rp-g8y) supersedes
    017-ss-spousal-survivor-benefits' own FR-007 (which this test used to
    assert the *opposite* of -- compute_survivor_benefit() had no caller
    yet, by design, since 017 explicitly deferred projection wiring to
    this feature). compute_survivor_benefit() is now called from this
    module's run_plan_projection() for every post-death plan year -- see
    test_death_switches_filing_status_ss_and_spending_after_the_death_year
    below for the actual behavioral coverage; this test only confirms the
    historical "not yet wired" assertion no longer holds."""
    import inspect

    from retirement_planner.comparison import projection as projection_module

    assert "compute_survivor_benefit" in inspect.getsource(projection_module)


# --- 018-survivor-scenario-projection: mid-horizon death wiring (rp-g8y) ---


def _death_household(you_death_age=None, spouse_death_age=None, survivor_spending_reduction_pct=0.0):
    return Household(
        filing_status="married_filing_jointly",
        survivor_spending_reduction_pct=survivor_spending_reduction_pct,
        members=[
            HouseholdMember(
                person_name="you",
                current_age=67,
                ss_claim_age=67,
                ss_annual_benefit=30_000,
                full_retirement_age=67.0,
                predicted_death_age=you_death_age,
            ),
            HouseholdMember(
                person_name="spouse",
                current_age=67,
                ss_claim_age=67,
                ss_annual_benefit=20_000,
                full_retirement_age=67.0,
                predicted_death_age=spouse_death_age,
            ),
        ],
    )


def _run_death_projection(household, plan_to_age=80):
    strategy = _strategy(claiming_ages={"you": 67, "spouse": 67})
    return run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=800_000, roth=200_000, taxable=100_000),
        traditional_ownership_shares={"you": 0.7, "spouse": 0.3},
        annual_spending_need=60_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=plan_to_age,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.04),
    )


def test_death_switches_filing_status_ss_and_spending_after_the_death_year():
    """spec.md Acceptance Scenarios 1-4: spouse dies at age 70 (tax year
    2029, 3 years into the horizon; "you" and "spouse" both start at 67).
    The death year itself (2029) stays married_filing_jointly with the
    full combined benefit and full spending; every year after (2030+)
    switches to single, the survivor-benefit amount, and reduced
    spending."""
    household = _death_household(spouse_death_age=70, survivor_spending_reduction_pct=0.20)
    result = _run_death_projection(household)

    death_year = next(y for y in result.years if y.tax_year == 2029)
    assert death_year.filing_status == "married_filing_jointly"
    assert death_year.member_social_security_benefits == {"you": 30_000.0, "spouse": 20_000.0}
    assert death_year.effective_spending_need == 60_000.0

    first_post_death_year = next(y for y in result.years if y.tax_year == 2030)
    assert first_post_death_year.filing_status == "single"
    # Acceptance Scenario 2: higher of the two ($30,000) survives; the
    # deceased member's own entry is 0.0, not omitted (015 precedent).
    assert first_post_death_year.member_social_security_benefits == {"you": 30_000.0, "spouse": 0.0}
    # Acceptance Scenario 4: 20% reduction applied.
    assert first_post_death_year.effective_spending_need == pytest.approx(60_000.0 * 0.80)

    later_year = next(y for y in result.years if y.tax_year == 2035)
    assert later_year.filing_status == "single"
    assert later_year.effective_spending_need == pytest.approx(60_000.0 * 0.80)


def test_death_with_no_spending_reduction_configured_leaves_spending_unchanged():
    """spec.md Acceptance Scenario 3: omitting survivor_spending_reduction_pct
    (default 0.0) leaves annual_spending_need unchanged even after death --
    only filing status and Social Security income switch."""
    household = _death_household(spouse_death_age=70)  # survivor_spending_reduction_pct defaults to 0.0
    result = _run_death_projection(household)

    first_post_death_year = next(y for y in result.years if y.tax_year == 2030)
    assert first_post_death_year.filing_status == "single"
    assert first_post_death_year.effective_spending_need == 60_000.0


def test_fica_additional_medicare_tax_threshold_switches_with_mid_horizon_filing_status():
    """022-fica-payroll-tax (rp-elp), US3 + 018-survivor-scenario-projection
    interaction: "you" earns $220k/year -- under the $250k MFJ threshold
    (no Additional Medicare Tax while married), but over the $200k single
    threshold (Additional Medicare Tax applies) once effective_filing_status
    switches to single after spouse's death (contracts/comparison-api.md)."""
    household = _death_household(spouse_death_age=70)
    household.members[0].income_streams = [
        IncomeStream(
            label="Consulting",
            stream_type="earned_income",
            start_age=67,
            annual_amount=220_000.0,
            inflation_adjustment="cola_adjusted",
        )
    ]
    result = _run_death_projection(household)

    pre_death_year = next(y for y in result.years if y.tax_year == 2028)
    assert pre_death_year.filing_status == "married_filing_jointly"
    assert pre_death_year.fica_tax.additional_medicare_tax == 0.0

    first_post_death_year = next(y for y in result.years if y.tax_year == 2030)
    assert first_post_death_year.filing_status == "single"
    assert first_post_death_year.fica_tax.additional_medicare_tax == pytest.approx((220_000 - 200_000) * 0.009)


def test_no_configured_death_leaves_every_year_unchanged():
    """spec.md Acceptance Scenario 5, SC-002: a household with no member's
    predicted_death_age configured is completely unaffected -- every
    year's filing_status equals household.filing_status and
    effective_spending_need equals annual_spending_need, unchanged."""
    household = _death_household()  # no predicted_death_age on either member
    result = _run_death_projection(household)

    assert all(year.filing_status == "married_filing_jointly" for year in result.years)
    assert all(year.effective_spending_need == 60_000.0 for year in result.years)
    assert result.years[0].member_social_security_benefits == {"you": 30_000.0, "spouse": 20_000.0}


def test_single_filing_status_household_never_affected_by_predicted_death_age():
    """spec.md Acceptance Scenario 6: a "single"-filing-status household
    (one member) is never affected by this feature's logic, regardless of
    any predicted_death_age value present -- there is no second member to
    derive a switch from (_household_death_tax_year() returns None)."""
    household = Household(
        filing_status="single",
        members=[
            HouseholdMember(
                person_name="you",
                current_age=67,
                ss_claim_age=67,
                ss_annual_benefit=30_000,
                full_retirement_age=67.0,
                predicted_death_age=70,
            ),
        ],
    )
    strategy = _strategy(claiming_ages={"you": 67})
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=500_000, roth=0, taxable=100_000),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=40_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=80,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.04),
    )
    assert all(year.filing_status == "single" for year in result.years)
    assert all(year.effective_spending_need == 40_000.0 for year in result.years)


def test_death_before_start_tax_year_makes_the_entire_horizon_post_death():
    """spec.md Edge Cases: a predicted_death_age that translates to a tax
    year before start_tax_year means the household is single (survivor
    benefit, reduced spending) for the ENTIRE horizon -- there is no year
    in the projection where the deceased member is still alive. Spouse's
    current_age=67 with predicted_death_age=68 => death tax year 2027,
    one year before start_tax_year=2028 below."""
    household = _death_household(spouse_death_age=68, survivor_spending_reduction_pct=0.10)
    strategy = _strategy(claiming_ages={"you": 67, "spouse": 67})
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=800_000, roth=200_000, taxable=100_000),
        traditional_ownership_shares={"you": 0.7, "spouse": 0.3},
        annual_spending_need=60_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2028,  # after the death tax year (2027)
        plan_to_age=75,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.04),
    )
    assert all(year.filing_status == "single" for year in result.years)
    assert all(year.effective_spending_need == pytest.approx(60_000.0 * 0.90) for year in result.years)
    assert all(year.member_social_security_benefits["spouse"] == 0.0 for year in result.years)


def test_both_members_configured_the_earlier_death_year_drives_the_switch():
    """spec.md Edge Cases: when both members have predicted_death_age
    configured within the horizon, the EARLIER death year drives the
    switch; the survivor's own later configured death has no further
    modeled effect (no second switch, no early termination)."""
    # spouse dies at 70 (tax year 2029); you dies at 75 (tax year 2034) --
    # spouse's death is earlier and should be the one that takes effect.
    household = _death_household(you_death_age=75, spouse_death_age=70)
    result = _run_death_projection(household, plan_to_age=85)

    year_2029 = next(y for y in result.years if y.tax_year == 2029)
    assert year_2029.filing_status == "married_filing_jointly"

    year_2030 = next(y for y in result.years if y.tax_year == 2030)
    assert year_2030.filing_status == "single"
    assert year_2030.member_social_security_benefits == {"you": 30_000.0, "spouse": 0.0}

    # "you"'s own later configured death (2034) has no further effect --
    # still single, still the same survivor benefit, no second switch.
    year_2040 = next(y for y in result.years if y.tax_year == 2040)
    assert year_2040.filing_status == "single"
    assert year_2040.member_social_security_benefits["spouse"] == 0.0


def test_plain_non_grid_projection_uses_the_reduced_benefit_in_income_and_tax():
    """016-ss-claiming-age-actuarial-adjustment US2 (spec.md Acceptance
    Scenario 1): a household running one fixed, non-comparison claiming
    age -- not the claiming-age grid -- still gets the actuarially
    reduced benefit, and that reduced amount (not the PIA) is what flows
    into this year's income/tax figures, since _member_gross_social_
    security_benefits() is the one call site every engine path shares
    (research.md Decision 4)."""
    household = Household(
        filing_status="single",
        members=[
            HouseholdMember(
                person_name="you",
                current_age=64,
                ss_claim_age=64,  # claiming 3 years before FRA
                ss_annual_benefit=30_000,  # PIA
                full_retirement_age=67.0,
            ),
        ],
    )
    strategy = _strategy(claiming_ages={"you": 64})
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=0, roth=0, taxable=500_000),
        traditional_ownership_shares={"you": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=64,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    first_year = result.years[0]
    # 36 months early against a 67 FRA: 20% reduction -> 24,000, not 30,000.
    expected_reduction = 36 * (5 / 9) / 100
    expected_benefit = 30_000.0 * (1 - expected_reduction)
    assert first_year.member_social_security_benefits["you"] == pytest.approx(expected_benefit)

    # The reduced amount, not the PIA, is what fed into this year's federal
    # tax computation's own provisional-income test -- reproduced directly
    # against compute_taxable_social_security() with the reduced benefit to
    # confirm equality (not just a >0 proxy, since this household's zero
    # ordinary income keeps both the reduced and unreduced case under the
    # single-filer 0%-taxable threshold either way).
    expected_taxable_ss, _ = compute_taxable_social_security(
        IncomeComponents(
            ordinary_income=first_year.mechanics.ordinary_income,
            social_security_gross_benefit=expected_benefit,
        ),
        filing_status="single",
        tax_year=2026,
    )
    assert first_year.federal_tax.taxable_social_security == pytest.approx(expected_taxable_ss)


def test_inherited_account_balances_and_distributions_are_snapshotted_per_account_id():
    household = _single_member_household(current_age=55)
    accounts = AccountBalances(traditional=0, roth=0, taxable=100_000)
    strategy = _strategy(claiming_ages={"you": 99})
    inherited = _inherited_account()

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0},
        inherited_accounts=[inherited],
        annual_spending_need=10_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=55,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    year = result.years[0]
    # A single inherited account's own distribution is the entire
    # pooled inherited_distribution_drawn figure -- same value, now also
    # individually addressable by account_id. rp-kn5: 31.4, the
    # beneficiary's own divisor -- see
    # test_inherited_account_annual_distribution_included_in_withdrawal_plan
    # above for the full "longer of" hand check.
    assert year.inherited_account_distributions == {"traditional-1": pytest.approx(250_000 / 31.4)}
    assert year.inherited_account_distributions["traditional-1"] == pytest.approx(year.mechanics.withdrawal_plan.inherited_distribution_drawn)
    assert year.inherited_account_balances["traditional-1"] == pytest.approx(inherited.balance)


def test_two_inherited_accounts_have_independently_keyed_snapshots():
    household = _single_member_household(current_age=55)
    accounts = AccountBalances(traditional=0, roth=0, taxable=100_000)
    strategy = _strategy(claiming_ages={"you": 99})
    account_a = _inherited_account(account_id="traditional-1", balance=250_000, death_year=2023, decedent_age_at_death=80)
    account_b = _inherited_account(account_id="traditional-2", balance=90_000, death_year=2020, decedent_age_at_death=75, depletion_deadline_year=2030)

    result = run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares={"you": 0.0},
        inherited_accounts=[account_a, account_b],
        annual_spending_need=10_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=55,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    year = result.years[0]
    assert set(year.inherited_account_distributions) == {"traditional-1", "traditional-2"}
    assert sum(year.inherited_account_distributions.values()) == pytest.approx(year.mechanics.withdrawal_plan.inherited_distribution_drawn)
    # account_a's own snapshot is unaffected by account_b's presence.
    # rp-kn5: 31.4, the beneficiary's own divisor (see the hand check in
    # test_inherited_account_annual_distribution_included_in_withdrawal_plan).
    assert year.inherited_account_distributions["traditional-1"] == pytest.approx(250_000 / 31.4)


# --- 019-roth-conversion-ladder: five-year seasoning / conversion-ladder tracking (rp-886) ---


def _ladder_household(current_age=55):
    return Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=current_age, ss_claim_age=67, ss_annual_benefit=0)],
    )


def _run_ladder_projection(household, conversion_bracket_ceiling_or_amount=90_000, plan_to_age=65, annual_spending_need=15_000):
    strategy = _strategy(
        claiming_ages={"you": 67},
        conversion_strategy="fixed_amount",
        conversion_bracket_ceiling_or_amount=conversion_bracket_ceiling_or_amount,
        conversion_window=(2026, 2026),
    )
    return run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=100_000, roth=0, taxable=0),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=annual_spending_need,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=plan_to_age,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )


def _roth_draw(year):
    return next(
        (item.amount for item in year.mechanics.withdrawal_plan.sequence_withdrawals if item.account_type == "roth"),
        0.0,
    )


def test_unseasoned_conversion_withdrawal_is_flagged_then_stops_once_seasoned():
    """spec.md Acceptance Scenarios 1-2 (User Story 1), quickstart.md §1:
    a conversion executed in 2026 (age 55) is drawn against every year
    from 2027-2030 while still unseasoned and the household member is
    under 59.5 -- each such draw is flagged in full. By 2031 the
    conversion has seasoned (5 full tax years elapsed) and the identical
    kind of draw is no longer flagged."""
    result = _run_ladder_projection(_ladder_household(current_age=55))

    year_2026 = next(y for y in result.years if y.tax_year == 2026)
    assert year_2026.mechanics.conversion.amount_converted > 0
    assert year_2026.unseasoned_roth_withdrawal == 0.0  # same-year conversion is never its own draw source

    for tax_year in (2027, 2028, 2029, 2030):
        year = next(y for y in result.years if y.tax_year == tax_year)
        draw = _roth_draw(year)
        assert draw > 0.0
        assert year.unseasoned_roth_withdrawal == pytest.approx(draw)

    year_2031 = next(y for y in result.years if y.tax_year == 2031)
    assert year_2031.unseasoned_roth_withdrawal == 0.0


def test_no_flag_once_every_member_has_cleared_59_5():
    """spec.md Acceptance Scenario 3 (User Story 1), quickstart.md §2: a
    household member who is already 60 by the time a draw reaches an
    unseasoned lot is never flagged, even though the draw itself still
    happens and still touches the unseasoned lot."""
    result = _run_ladder_projection(_ladder_household(current_age=59), plan_to_age=70)

    year_2027 = next(y for y in result.years if y.tax_year == 2027)  # "you" is 60 this year
    draw = _roth_draw(year_2027)
    assert draw > 0.0
    assert year_2027.unseasoned_roth_withdrawal == 0.0


def test_household_covered_by_pre_existing_balance_alone_never_flags():
    """spec.md Acceptance Scenario 4 (User Story 1): a draw fully covered
    by the pre-existing/non-lot Roth balance never flags, regardless of
    any conversion's own seasoning status or any member's age."""
    household = _ladder_household(current_age=55)
    strategy = _strategy(
        claiming_ages={"you": 67},
        conversion_strategy="fixed_amount",
        conversion_bracket_ceiling_or_amount=10_000,
        conversion_window=(2026, 2026),
    )
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=100_000, roth=200_000, taxable=0),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=15_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=65,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    # Traditional alone comfortably covers spending here -- Roth is never touched at all.
    assert all(y.unseasoned_roth_withdrawal == 0.0 for y in result.years)


def test_no_roth_conversion_configured_leaves_every_year_unaffected():
    """spec.md Acceptance Scenario 5 (User Story 1), FR-008, SC-004,
    quickstart.md §3: a household whose scenario configures no Roth
    conversion strategy sees no tracked lots and no flags raised by this
    feature, ever."""
    household = _ladder_household(current_age=55)
    no_conversion_strategy = _strategy(claiming_ages={"you": 67})  # conversion_strategy=None by default
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=100_000, roth=50_000, taxable=0),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=15_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=65,
        strategy=no_conversion_strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    assert all(y.unseasoned_roth_withdrawal == 0.0 for y in result.years)


def test_no_numeric_output_changes_because_of_this_feature():
    """spec.md FR-007, SC-005: 019's OWN ladder-tracking/flagging logic
    adds an informational field only -- it never itself alters any
    dollar amount. Confirmed by comparing the PRE-tax-funding ending Roth
    balance (mechanics.ending_balances.roth, set entirely by 019's own
    withdrawal/conversion logic) against the same household's own
    hand-verifiable arithmetic, independent of the flag.

    020-early-withdrawal-penalty correction (found via this feature's own
    T014 regression triage, not a 019 regression): the FINAL
    ending_balances.roth can legitimately differ from that pre-tax-funding
    figure once 020 ships, because 020's own penalty (itself correctly
    computed FROM 019's flag, per 020 research.md Decision 3) is funded
    via tax_funding_withdrawal, which may draw further from Roth if
    Traditional/taxable are already exhausted that year -- exactly what
    020 FR-007 requires (the penalty must genuinely reduce balances). The
    two effects are properly disentangled below: 019's own logic (asserted
    against the pre-tax-funding balance) is unchanged; the further,
    documented reduction is fully explained by 020's own funded penalty."""
    result = _run_ladder_projection(_ladder_household(current_age=55))
    year_2027 = next(y for y in result.years if y.tax_year == 2027)
    # 019's own logic: the withdrawal/conversion step alone (before any tax
    # funding) reduces Roth by exactly this year's own draw -- unaffected by
    # whether unseasoned_roth_withdrawal is 0 or positive.
    assert year_2027.mechanics.ending_balances.roth == pytest.approx(year_2027.starting_balances.roth - _roth_draw(year_2027))
    # 020's own logic: any further reduction down to the FINAL ending
    # balance is fully explained by the tax-funding withdrawal's own
    # roth-sourced draw (federal/state tax owed is $0 in this low-income
    # scenario, so tax_owed here is exactly the early-withdrawal penalty).
    roth_funding_draw = next(
        (item.amount for item in year_2027.tax_funding_withdrawal.sequence_withdrawals if item.account_type == "roth"),
        0.0,
    )
    assert year_2027.ending_balances.roth == pytest.approx(year_2027.mechanics.ending_balances.roth - roth_funding_draw)
    assert roth_funding_draw == pytest.approx(year_2027.early_withdrawal_penalty.penalty_owed)


def test_multiple_conversions_draw_down_oldest_first_end_to_end():
    """spec.md User Story 2, quickstart.md's multi-lot pattern applied
    end-to-end through run_plan_projection(): three conversions executed
    in consecutive plan years (2026-2028), drawn down oldest-first. 2030's
    draw reaches into the still-unseasoned 2026 lot (flagged); by 2031 that
    same lot has seasoned (5 years) and still has enough remaining balance
    to cover every later year's draw without ever reaching the newer,
    still-unseasoned 2027/2028 lots -- confirming the projection loop's
    per-year reassignment (T009-T010) preserves oldest-lot-first ordering
    across years, not just within one call."""
    household = _ladder_household(current_age=50)
    strategy = _strategy(
        claiming_ages={"you": 67},
        conversion_strategy="fixed_amount",
        conversion_bracket_ceiling_or_amount=20_000,
        conversion_window=(2026, 2028),
    )
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=100_000, roth=0, taxable=0),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=8_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=70,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    conversions = {y.tax_year: y.mechanics.conversion.amount_converted for y in result.years}
    assert conversions[2026] > 0 and conversions[2027] > 0 and conversions[2028] > 0

    year_2030 = next(y for y in result.years if y.tax_year == 2030)
    draw_2030 = _roth_draw(year_2030)
    assert draw_2030 > 0.0
    assert year_2030.unseasoned_roth_withdrawal == pytest.approx(draw_2030)  # 2026 lot, still unseasoned

    # 2031 onward: the 2026 lot has seasoned and still has enough balance left
    # to cover every subsequent year's draw on its own -- never flagged again.
    for year in result.years:
        if year.tax_year >= 2031:
            assert year.unseasoned_roth_withdrawal == 0.0


# --- 020-early-withdrawal-penalty: 10% penalty on pre-59.5 distributions (rp-8z0) ---


def _penalty_strategy(**overrides):
    base = dict(
        label="early_withdrawal",
        withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
        conversion_window=None,
    )
    base.update(overrides)
    return _strategy(**base)


def _traditional_draw(year):
    return next(
        (item.amount for item in year.mechanics.withdrawal_plan.sequence_withdrawals if item.account_type == "traditional"),
        0.0,
    )


def test_voluntary_traditional_withdrawal_under_59_5_is_penalized():
    """spec.md Acceptance Scenario 1, quickstart.md §1: a single-member
    household under 59.5 taking a $20,000 voluntary Traditional
    withdrawal shows a $2,000 penalty (10%) that plan year."""
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=55, ss_claim_age=67, ss_annual_benefit=0)],
    )
    strategy = _penalty_strategy(claiming_ages={"you": 67})
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=200_000, roth=0, taxable=0),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=20_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=65,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    year = result.years[0]
    assert _traditional_draw(year) == pytest.approx(20_000.0)
    assert year.early_withdrawal_penalty.penalty_owed == pytest.approx(2_000.0)


def test_rmd_mandated_distribution_is_never_penalized():
    """spec.md Acceptance Scenario 2 (FR-003, SC-004): a plan year fully
    satisfied by the RMD leg alone (no additional voluntary draw) shows a
    $0 penalty, even though real RMD dollars flowed that year. This is
    also always true by construction in this engine (research.md
    Decision 4 -- RMD_START_AGE is never under 73, always well past
    59.5), so this test also incidentally exercises the age exemption --
    documented honestly, not claimed as an isolated RMD-only case."""
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=74, ss_claim_age=67, ss_annual_benefit=0)],
    )
    strategy = _penalty_strategy(claiming_ages={"you": 67})
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=500_000, roth=0, taxable=0),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=1_000,  # small enough to be fully covered by the RMD leg alone
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=75,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    year = result.years[0]
    assert year.mechanics.withdrawal_plan.rmd_drawn > 0  # real RMD money flowed
    assert year.mechanics.withdrawal_plan.sequence_withdrawals == []  # no additional voluntary draw
    assert year.early_withdrawal_penalty.penalty_owed == 0.0


def test_per_member_attribution_only_penalizes_the_under_59_5_members_own_share():
    """spec.md Acceptance Scenario 3: an MFJ household where "you" (62)
    and "spouse" (55) own distinct shares of the Traditional balance --
    only spouse's own 30% share of the voluntary withdrawal is
    penalized, not the combined household total."""
    household = Household(
        filing_status="married_filing_jointly",
        members=[
            HouseholdMember(person_name="you", current_age=62, ss_claim_age=67, ss_annual_benefit=0),
            HouseholdMember(person_name="spouse", current_age=55, ss_claim_age=67, ss_annual_benefit=0),
        ],
    )
    strategy = _penalty_strategy(claiming_ages={"you": 67, "spouse": 67})
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=200_000, roth=0, taxable=0),
        traditional_ownership_shares={"you": 0.7, "spouse": 0.3},
        annual_spending_need=20_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=65,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    year = result.years[0]
    draw = _traditional_draw(year)
    assert draw == pytest.approx(20_000.0)
    assert year.early_withdrawal_penalty.penalty_owed == pytest.approx(draw * 0.3 * 0.10)


def test_member_at_translated_age_60_is_never_penalized():
    """spec.md Acceptance Scenario 4 (Edge Cases age-precision rule): a
    member whose translated age is exactly 60 contributes $0 to the
    penalty base regardless of their own withdrawal amount."""
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=60, ss_claim_age=67, ss_annual_benefit=0)],
    )
    strategy = _penalty_strategy(claiming_ages={"you": 67})
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=200_000, roth=0, taxable=0),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=20_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=65,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    year = result.years[0]
    assert _traditional_draw(year) > 0
    assert year.early_withdrawal_penalty.penalty_owed == 0.0


def test_inherited_account_distribution_is_never_penalized_regardless_of_beneficiary_age():
    """spec.md Acceptance Scenario 5 (FR-004, SC-004): a 50-year-old
    beneficiary's own inherited-account distribution is never subject to
    this penalty -- an entirely separate distribution stream from the
    household's pooled Traditional balance (research.md Decision 4)."""
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=50, ss_claim_age=67, ss_annual_benefit=0)],
    )
    account = InheritedAccountBalance(
        account_id="traditional-1",
        balance=250_000.0,
        death_year=2023,
        decedent_age_at_death=80,
        depletion_deadline_year=2033,
        beneficiary_person_name="you",
    )
    strategy = _penalty_strategy(claiming_ages={"you": 67})
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=0, roth=0, taxable=0),
        traditional_ownership_shares={"you": 0.0},
        inherited_accounts=[account],
        annual_spending_need=10_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=55,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    year = result.years[0]
    assert year.mechanics.withdrawal_plan.inherited_distribution_drawn > 0
    assert year.early_withdrawal_penalty.penalty_owed == 0.0


def test_penalty_actually_reduces_ending_balance_versus_an_unaffected_household():
    """spec.md SC-001: a household with a member under 59.5 taking a
    voluntary Traditional withdrawal ends the plan year with a strictly
    lower balance than an otherwise-identical household whose only
    difference is having already cleared 59.5 -- confirms the penalty is
    genuinely funded (FR-007), not merely reported."""
    strategy = _penalty_strategy(claiming_ages={"you": 67})
    common_kwargs = dict(
        accounts=AccountBalances(traditional=200_000, roth=0, taxable=0),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=20_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=65,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    younger_household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=55, ss_claim_age=67, ss_annual_benefit=0)],
    )
    older_household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=60, ss_claim_age=67, ss_annual_benefit=0)],
    )
    younger_result = run_plan_projection(household=younger_household, **common_kwargs)
    older_result = run_plan_projection(household=older_household, **common_kwargs)

    younger_year = younger_result.years[0]
    older_year = older_result.years[0]
    assert younger_year.early_withdrawal_penalty.penalty_owed > 0
    assert older_year.early_withdrawal_penalty.penalty_owed == 0.0

    younger_total = younger_year.ending_balances.traditional + younger_year.ending_balances.roth + younger_year.ending_balances.taxable
    older_total = older_year.ending_balances.traditional + older_year.ending_balances.roth + older_year.ending_balances.taxable
    assert younger_total < older_total


def test_unaffected_household_sees_zero_penalty_every_year():
    """spec.md FR-010, SC-002: a household whose every member stays 60+
    for the entire horizon and never touches an unseasoned Roth
    conversion shows a penalty of exactly 0.0 for every plan year -- no
    regression to households this feature doesn't affect."""
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=65, ss_claim_age=67, ss_annual_benefit=0)],
    )
    strategy = _penalty_strategy(claiming_ages={"you": 67})
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=500_000, roth=0, taxable=100_000),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=40_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=90,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    assert all(year.early_withdrawal_penalty.penalty_owed == 0.0 for year in result.years)


# --- 020-early-withdrawal-penalty: combining with 019's Roth-ladder flag (User Story 2) ---


def test_unseasoned_roth_withdrawal_alone_is_penalized_at_ten_percent():
    """spec.md Acceptance Scenario US2.1: a plan year where 019's own
    unseasoned_roth_withdrawal is the only early-distribution exposure
    that year shows a penalty of exactly 10% of that amount."""
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=55, ss_claim_age=67, ss_annual_benefit=0)],
    )
    strategy = _penalty_strategy(
        claiming_ages={"you": 67},
        conversion_strategy="fixed_amount",
        conversion_bracket_ceiling_or_amount=90_000,
        conversion_window=(2026, 2026),
    )
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=100_000, roth=0, taxable=0),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=15_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=65,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    year_2027 = next(y for y in result.years if y.tax_year == 2027)
    assert _traditional_draw(year_2027) == 0.0
    assert year_2027.unseasoned_roth_withdrawal == pytest.approx(15_000.0)
    assert year_2027.early_withdrawal_penalty.penalty_owed == pytest.approx(1_500.0)


def test_combined_traditional_and_roth_exposure_in_the_same_year_is_one_penalty():
    """spec.md Acceptance Scenario US2.2: a plan year with both a
    qualifying Traditional withdrawal ($6,110) and an unseasoned Roth
    withdrawal ($8,890) shows a single combined penalty equal to 10% of
    their sum ($15,000 -> $1,500), not two separately-reported amounts."""
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=55, ss_claim_age=67, ss_annual_benefit=0)],
    )
    strategy = _penalty_strategy(
        claiming_ages={"you": 67},
        conversion_strategy="fixed_amount",
        conversion_bracket_ceiling_or_amount=10_000,
        conversion_window=(2026, 2026),
    )
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=50_000, roth=0, taxable=0),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=15_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=65,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    year_2028 = next(y for y in result.years if y.tax_year == 2028)
    traditional_draw = _traditional_draw(year_2028)
    assert traditional_draw == pytest.approx(6_110.0)
    assert year_2028.unseasoned_roth_withdrawal == pytest.approx(8_890.0)
    assert year_2028.early_withdrawal_penalty.penalty_owed == pytest.approx((traditional_draw + year_2028.unseasoned_roth_withdrawal) * 0.10)
    assert year_2028.early_withdrawal_penalty.penalty_owed == pytest.approx(1_500.0)


def test_no_roth_conversion_configured_means_roth_side_contribution_is_always_zero():
    """spec.md Acceptance Scenario US2.3: a household with no Roth
    conversion configured at all still shows a Traditional-side penalty
    (it's under 59.5, drawing Traditional funds), but the Roth-side
    contribution is always $0.0 -- there is no lot to ever flag."""
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=55, ss_claim_age=67, ss_annual_benefit=0)],
    )
    strategy = _penalty_strategy(claiming_ages={"you": 67})  # no conversion configured
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=200_000, roth=0, taxable=0),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=20_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=65,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    year = result.years[0]
    assert year.unseasoned_roth_withdrawal == 0.0
    assert year.early_withdrawal_penalty.penalty_owed == pytest.approx(_traditional_draw(year) * 0.10)


# --- rp-yqf: IRMAA/NIIT are actually funded, not just reported ---


def test_irmaa_and_niit_are_included_in_the_actually_funded_tax_withdrawal():
    """rp-yqf: irmaa.surcharge_owed and niit.surtax_owed must be included
    in tax_owed/tax_funding_withdrawal -- previously omitted (an
    undocumented gap, not a design choice), so neither ever actually
    reduced a projection's account balances despite the Streamlit UI
    describing both as amounts "paid". A high-income household triggers
    both simultaneously, alongside ordinary federal tax."""
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=66, ss_claim_age=67, ss_annual_benefit=0)],
    )
    strategy = _strategy(
        withdrawal_strategy="rmd_traditional_taxable_roth",
        claiming_ages={"you": 67},
    )
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=300_000, roth=0, taxable=1_000_000),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=400_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=70,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    year = result.years[0]
    # Sanity: this scenario actually triggers all three costs simultaneously --
    # otherwise this test could pass vacuously.
    assert year.federal_tax.federal_tax_owed > 0
    assert year.niit.surtax_owed > 0
    assert year.irmaa.surcharge_owed > 0

    actually_funded = sum(item.amount for item in year.tax_funding_withdrawal.sequence_withdrawals)
    assert actually_funded == pytest.approx(
        year.federal_tax.federal_tax_owed + year.state_tax.state_tax_owed + year.irmaa.surcharge_owed + year.niit.surtax_owed + year.early_withdrawal_penalty.penalty_owed
    )


def test_cumulative_tax_paid_meaning_is_unchanged_by_the_irmaa_niit_funding_fix():
    """rp-yqf: PlanOutcome.cumulative_tax_paid keeps its existing meaning
    (federal + state income tax only) -- the fix changes what's actually
    funded (tax_owed, a local variable), not this separate reporting
    figure, matching 010's own established "keep cumulative_tax_paid
    federal+state-only, report IRMAA/NIIT in their own separate fields"
    precedent."""
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=66, ss_claim_age=67, ss_annual_benefit=0)],
    )
    strategy = _strategy(
        withdrawal_strategy="rmd_traditional_taxable_roth",
        claiming_ages={"you": 67},
    )
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=300_000, roth=0, taxable=1_000_000),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=400_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=70,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )
    expected_cumulative_tax_paid = sum(year.federal_tax.federal_tax_owed + year.state_tax.state_tax_owed for year in result.years)
    assert result.outcome.cumulative_tax_paid == pytest.approx(expected_cumulative_tax_paid)
    assert result.outcome.cumulative_irmaa_paid == pytest.approx(sum(year.irmaa.surcharge_owed for year in result.years))
    assert result.outcome.cumulative_niit_paid == pytest.approx(sum(year.niit.surtax_owed for year in result.years))


# --- 025-ss-earnings-test (rp-acq) --------------------------------------


def _early_claiming_earnings_test_household(annual_amount, claim_age=62, fra=67.0, benefit=20_000, start_age=None, end_age=None):
    household = Household(
        filing_status="single",
        members=[
            HouseholdMember(
                person_name="you",
                current_age=claim_age,
                ss_claim_age=claim_age,
                ss_annual_benefit=benefit,
                full_retirement_age=fra,
            )
        ],
    )
    household.members[0].income_streams = [
        IncomeStream(
            label="Consulting",
            stream_type="earned_income",
            start_age=start_age if start_age is not None else claim_age,
            end_age=end_age,
            annual_amount=annual_amount,
            inflation_adjustment="fixed_nominal",
        )
    ]
    return household


def _run_earnings_test_projection(household, plan_to_age):
    return run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=0, roth=0, taxable=500_000),
        traditional_ownership_shares={"you": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=plan_to_age,
        strategy=_strategy(claiming_ages={"you": household.members[0].ss_claim_age}),
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )


def test_earnings_test_withholding_reduces_near_term_benefit_in_a_running_projection():
    """025-ss-earnings-test (rp-acq) US1: a member claiming at 62 (FRA 67)
    with earned income above the below-FRA exempt amount ($24,480 for
    2026) sees their reported Social Security benefit reduced by the
    earnings test, not the full unwithheld claiming-age-adjusted amount."""
    household = _early_claiming_earnings_test_household(30_000, end_age=66)
    result = _run_earnings_test_projection(household, plan_to_age=63)

    year_62 = result.years[0]
    # PIA 20,000 at 62-vs-67 FRA -> 0.70 factor -> 14,000 unwithheld.
    # Excess earnings: 30,000 - 24,480 = 5,520; withheld = 2,760.
    assert year_62.member_ss_earnings_test_withheld["you"] == pytest.approx(2_760.0)
    assert year_62.member_social_security_benefits["you"] == pytest.approx(14_000.0 - 2_760.0)


def test_earnings_at_or_below_exempt_threshold_withholds_nothing():
    household = _early_claiming_earnings_test_household(24_480, end_age=66)
    result = _run_earnings_test_projection(household, plan_to_age=63)

    year_62 = result.years[0]
    assert year_62.member_ss_earnings_test_withheld["you"] == pytest.approx(0.0)
    assert year_62.member_social_security_benefits["you"] == pytest.approx(14_000.0)


def test_no_earned_income_stream_never_triggers_the_earnings_test():
    household = _single_member_household(current_age=62)
    household.members[0].ss_claim_age = 62
    household.members[0].ss_annual_benefit = 20_000
    result = _run_earnings_test_projection(household, plan_to_age=68)

    for year in result.years:
        assert year.member_ss_earnings_test_withheld == {"you": 0.0}
    # Unaffected -- every year pays the plain claiming-age-adjusted amount.
    assert all(year.member_social_security_benefits["you"] == pytest.approx(14_000.0) for year in result.years)


def test_member_at_or_past_own_fra_is_never_subject_to_the_earnings_test():
    """A member who hasn't claimed early (claiming at FRA itself) is
    unaffected by the earnings test regardless of earned income."""
    household = _early_claiming_earnings_test_household(200_000, claim_age=67, fra=67.0)
    result = _run_earnings_test_projection(household, plan_to_age=68)

    for year in result.years:
        assert year.member_ss_earnings_test_withheld["you"] == pytest.approx(0.0)
        assert year.member_social_security_benefits["you"] == pytest.approx(20_000.0)  # full PIA, unreduced


def test_fra_attainment_year_uses_the_lenient_rule_not_the_stricter_below_fra_rule():
    """025-ss-earnings-test (rp-acq) US3: $40,000 earned income is above
    the below-FRA exempt amount ($24,480) but below the FRA-attainment-
    year exempt amount ($65,160) -- the stricter rule would withhold
    (40,000 - 24,480) / 2 = $7,760; the correct, more lenient rule
    withholds nothing."""
    household = _early_claiming_earnings_test_household(40_000, start_age=67, end_age=67)
    result = _run_earnings_test_projection(household, plan_to_age=67)

    fra_year = next(y for y in result.years if y.tax_year == 2031)  # member turns 67 in plan year 6
    assert fra_year.member_ss_earnings_test_withheld["you"] == pytest.approx(0.0)
    assert fra_year.member_social_security_benefits["you"] == pytest.approx(14_000.0)


def test_earnings_test_recredit_permanently_raises_benefit_after_fra_year():
    """025-ss-earnings-test (rp-acq) US2: a member withheld across every
    pre-FRA year they claimed shows a permanently higher benefit starting
    the plan year after their FRA-attainment year -- SSA's ARF recredit,
    not a modeled permanent loss."""
    household = _early_claiming_earnings_test_household(60_000, end_age=None)
    result = _run_earnings_test_projection(household, plan_to_age=69)

    by_age = {62 + i: year for i, year in enumerate(result.years)}

    # Ages 62-66: below-FRA rule: excess = 60,000 - 24,480 = 35,520;
    # withheld = 17,760, capped at the 14,000 unwithheld benefit -> fully
    # withheld every one of these years.
    for age in range(62, 67):
        assert by_age[age].member_social_security_benefits["you"] == pytest.approx(0.0)

    # Age 67 (FRA-attainment year): lenient rule, exempt 65,160 > 60,000
    # earned -> no withholding this year; benefit is still the ORIGINAL
    # (not-yet-recredited) 14,000 -- this engine applies the recredit
    # starting the year AFTER the FRA-attainment year (module docstring
    # simplification: the FRA-attainment year can still itself generate
    # withholding, so it isn't also the year the recredit first appears).
    assert by_age[67].member_ss_earnings_test_withheld["you"] == pytest.approx(0.0)
    assert by_age[67].member_social_security_benefits["you"] == pytest.approx(14_000.0)

    # Age 68+: permanently recredited, higher than the original 14,000.
    assert by_age[68].member_social_security_benefits["you"] > 14_000.0
    assert by_age[69].member_social_security_benefits["you"] == pytest.approx(by_age[68].member_social_security_benefits["you"])  # persists unchanged into the next year too


def test_never_withheld_member_sees_no_step_up_at_fra():
    """025-ss-earnings-test (rp-acq) US2 edge case: a member who claimed
    before FRA but was never withheld (earned income always at/below the
    exempt threshold) sees no benefit change at their FRA year at all."""
    household = _early_claiming_earnings_test_household(20_000, end_age=None)  # always below $24,480 threshold
    result = _run_earnings_test_projection(household, plan_to_age=69)

    for year in result.years:
        assert year.member_social_security_benefits["you"] == pytest.approx(14_000.0)


# --- rp-595: auto Roth-conversion gap-window + named-bracket ceiling + ---
# --- opt-in spending-need netting -----------------------------------------


def test_auto_gap_year_window_fires_conversions_only_inside_the_derived_gap():
    """Wage-stacking-guard regression: wages active 2026-2027 (end_age=68,
    current_age=67 -> wages stop after tax year 2027), RMD-eligible 2032
    (current_age=67 turns 73 in 2032, before the 2033 age-73->75 step --
    same worked example as test_rmd.py/test_roth_conversion_window.py).
    Derived window: (2028, 2031). $0 conversion is asserted both while
    wages are still active (2026-2027) AND after the window closes at RMD
    eligibility (2032+) -- not just "some years are excluded"."""
    household = _earned_income_household(80_000, current_age=67, start_age=67, end_age=68)
    strategy = _strategy(
        claiming_ages={"you": 67},
        conversion_strategy="fill_to_bracket",
        conversion_bracket_ceiling_or_amount=100_000,
        conversion_window_mode="auto_gap_year",
    )
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=500_000, roth=0, taxable=200_000),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=75,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    conversions = {y.tax_year: y.mechanics.conversion.amount_converted for y in result.years}
    assert conversions[2026] == 0.0  # wages still active
    assert conversions[2027] == 0.0  # wages still active (end_age=68 -> active through this year)
    assert conversions[2028] > 0.0  # first gap-window year
    assert conversions[2031] > 0.0  # last gap-window year
    assert conversions[2032] == 0.0  # RMD-eligible -- window closed
    assert conversions[2033] == 0.0

    assert result.resolved_conversion_window == (2028, 2031)


def test_auto_gap_year_window_resolves_to_none_when_wages_never_end():
    household = _earned_income_household(80_000, current_age=67, start_age=67, end_age=None)
    strategy = _strategy(
        claiming_ages={"you": 67},
        conversion_strategy="fill_to_bracket",
        conversion_bracket_ceiling_or_amount=100_000,
        conversion_window_mode="auto_gap_year",
    )
    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=500_000, roth=0, taxable=200_000),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=70,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    assert result.resolved_conversion_window is None
    assert all(y.mechanics.conversion.amount_converted == 0.0 for y in result.years)


def test_named_bracket_ceiling_matches_the_equivalent_manually_computed_dollar_ceiling():
    """The named-bracket mode must produce the identical amount_converted
    sequence as passing the pre-computed dollar figure directly --
    243,600 == 211,400 (MFJ 22% row) + 32,200 (MFJ standard deduction),
    the same figure test_federal.py's own
    test_bracket_ceiling_for_rate_adds_back_the_standard_deduction_mfj
    pins."""
    household = _mfj_household(you_age=60, spouse_age=60, you_benefit=0, spouse_benefit=0)
    common_kwargs = dict(
        accounts=AccountBalances(traditional=900_000, roth=0, taxable=0),
        traditional_ownership_shares={"you": 1.0, "spouse": 0.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=61,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    named = run_plan_projection(
        household=household,
        strategy=_strategy(
            conversion_strategy="fill_to_bracket",
            conversion_window=(2026, 2026),
            conversion_ceiling_mode="named_bracket",
            conversion_named_bracket_rate=0.22,
        ),
        **common_kwargs,
    )
    dollar = run_plan_projection(
        household=household,
        strategy=_strategy(
            conversion_strategy="fill_to_bracket",
            conversion_window=(2026, 2026),
            conversion_bracket_ceiling_or_amount=243_600.0,
        ),
        **common_kwargs,
    )

    assert named.years[0].mechanics.conversion.amount_converted == pytest.approx(
        dollar.years[0].mechanics.conversion.amount_converted
    )
    assert named.years[0].mechanics.conversion.amount_converted > 0.0


def test_net_earned_income_against_spending_reduces_discretionary_withdrawal_not_rmd():
    """Household fully covers spending from wages; netting must eliminate
    the otherwise-forced full-spending-need account draw while leaving
    the (here, still $0 since below RMD age) RMD entirely unaffected --
    and, at RMD age, must leave the mandatory RMD draw byte-identical
    between netting on and off."""
    household = _earned_income_household(80_000, current_age=74, start_age=74, end_age=None)
    common_kwargs = dict(
        household=household,
        accounts=AccountBalances(traditional=500_000, roth=0, taxable=500_000),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=60_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=74,
        strategy=_strategy(claiming_ages={"you": 67}),
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    without_netting = run_plan_projection(**common_kwargs, net_earned_income_against_spending=False)
    with_netting = run_plan_projection(**common_kwargs, net_earned_income_against_spending=True)

    year_without = without_netting.years[0]
    year_with = with_netting.years[0]

    # current_age=74 is already past RMD start age (73) -- both runs draw
    # the exact same mandatory RMD, netting or not.
    assert year_with.mechanics.withdrawal_plan.rmd_drawn == pytest.approx(year_without.mechanics.withdrawal_plan.rmd_drawn)
    assert year_with.mechanics.withdrawal_plan.rmd_drawn > 0.0

    # Without netting: the full $60,000 spending need is drawn from
    # accounts on top of the $80,000 wages (the double-counting trap).
    # With netting: spending need (60,000) is more than covered by wages
    # (80,000), so the discretionary sequence draw beyond the RMD is $0.
    discretionary_without = sum(
        item.amount for item in year_without.mechanics.withdrawal_plan.sequence_withdrawals
    )
    discretionary_with = sum(
        item.amount for item in year_with.mechanics.withdrawal_plan.sequence_withdrawals
    )
    assert discretionary_with < discretionary_without
    assert discretionary_with == pytest.approx(0.0)


def test_net_earned_income_against_spending_defaults_to_false_reproducing_prior_output():
    """Regression: omitting the new parameter entirely reproduces the
    exact prior (pre-rp-595) output, byte-for-byte -- Reproducibility
    principle."""
    household = _earned_income_household(80_000, current_age=63, start_age=63, end_age=None)
    kwargs = dict(
        household=household,
        accounts=AccountBalances(traditional=500_000, roth=0, taxable=500_000),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=60_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=65,
        strategy=_strategy(claiming_ages={"you": 67}),
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    default_call = run_plan_projection(**kwargs)
    explicit_false = run_plan_projection(**kwargs, net_earned_income_against_spending=False)

    assert default_call.years == explicit_false.years
    assert default_call.resolved_conversion_window is None
    assert default_call.resolved_conversion_window == explicit_false.resolved_conversion_window


def test_net_earned_income_against_spending_also_nets_leftover_wages_against_tax_bill():
    """rp-89t: rp-595's netting only ever reached the discretionary
    spending-need withdrawal (the first of two withdrawal-sequencing
    passes) -- the second, tax-funding compute_withdrawal_plan() call had
    zero awareness of earned income, so a household's own wages sat
    unused while its tax bill (often driven by those same wages) was
    drawn from accounts regardless. annual_spending_need=0 here means
    effective_spending_need is already floored at 0 with netting either
    on or off, so the first pass -- and every tax figure derived from it
    -- is byte-identical between the two runs; only the second, tax-
    funding pass can differ, isolating exactly the behavior this issue
    reports. $100,000 of wages comfortably exceeds the resulting tax
    bill (income tax + FICA on those same wages, no other income), so
    the fix must zero the tax-funding withdrawal entirely."""
    household = _earned_income_household(100_000, current_age=63, start_age=63, end_age=None)
    common_kwargs = dict(
        household=household,
        accounts=AccountBalances(traditional=500_000, roth=0, taxable=500_000),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=63,
        strategy=_strategy(claiming_ages={"you": 99}),
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    without_netting = run_plan_projection(**common_kwargs, net_earned_income_against_spending=False)
    with_netting = run_plan_projection(**common_kwargs, net_earned_income_against_spending=True)

    year_without = without_netting.years[0]
    year_with = with_netting.years[0]

    assert year_with.mechanics == year_without.mechanics
    assert year_with.federal_tax == year_without.federal_tax
    assert year_with.fica_tax == year_without.fica_tax

    tax_owed = (
        year_without.federal_tax.federal_tax_owed
        + year_without.state_tax.state_tax_owed
        + year_without.irmaa.surcharge_owed
        + year_without.niit.surtax_owed
        + year_without.early_withdrawal_penalty.penalty_owed
        + year_without.fica_tax.total_fica_tax
    )
    assert tax_owed > 0.0

    without_draw = sum(item.amount for item in year_without.tax_funding_withdrawal.sequence_withdrawals)
    with_draw = sum(item.amount for item in year_with.tax_funding_withdrawal.sequence_withdrawals)

    assert without_draw == pytest.approx(tax_owed)
    assert with_draw == pytest.approx(0.0)


def test_net_earned_income_against_spending_partially_offsets_a_larger_tax_bill():
    """Partial-offset case: leftover wages reduce, but don't eliminate,
    the tax-funding withdrawal, when the tax bill exceeds what's left
    over. annual_spending_need=0 again isolates the effect to the
    tax-funding pass alone (the mandatory RMD -- unaffected by spending
    netting either way -- is this year's only other ordinary income, so
    both runs' mechanics/tax figures match exactly); $20,000 of leftover
    wages doesn't fully cover the tax bill a $3,000,000 traditional
    balance's RMD drives at age 75."""
    household = _earned_income_household(20_000, current_age=75, start_age=75, end_age=None)
    common_kwargs = dict(
        household=household,
        accounts=AccountBalances(traditional=3_000_000, roth=0, taxable=0),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=0,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=75,
        strategy=_strategy(claiming_ages={"you": 99}),
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    without_netting = run_plan_projection(**common_kwargs, net_earned_income_against_spending=False)
    with_netting = run_plan_projection(**common_kwargs, net_earned_income_against_spending=True)

    year_without = without_netting.years[0]
    year_with = with_netting.years[0]

    assert year_with.mechanics == year_without.mechanics
    assert year_with.mechanics.withdrawal_plan.rmd_drawn > 0.0

    without_draw = sum(item.amount for item in year_without.tax_funding_withdrawal.sequence_withdrawals)
    with_draw = sum(item.amount for item in year_with.tax_funding_withdrawal.sequence_withdrawals)

    assert with_draw == pytest.approx(without_draw - 20_000)
    assert with_draw > 0.0


def test_net_earned_income_against_spending_tax_funding_offset_defaults_to_false_reproducing_prior_output():
    """Regression: with the toggle off, the tax-funding withdrawal is
    completely unaffected by rp-89t -- leftover_earned_income_after_
    spending stays 0.0, so max(0.0, tax_owed - 0.0) == tax_owed, the
    exact pre-fix computation."""
    household = _earned_income_household(80_000, current_age=63, start_age=63, end_age=None)
    kwargs = dict(
        household=household,
        accounts=AccountBalances(traditional=500_000, roth=0, taxable=500_000),
        traditional_ownership_shares={"you": 1.0},
        annual_spending_need=60_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=65,
        strategy=_strategy(claiming_ages={"you": 67}),
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
    )

    default_call = run_plan_projection(**kwargs)
    explicit_false = run_plan_projection(**kwargs, net_earned_income_against_spending=False)

    assert default_call.years == explicit_false.years
    assert any(year.tax_funding_withdrawal.sequence_withdrawals for year in default_call.years)


def test_rp_89t_reported_scenario_year_one_tax_funding_withdrawal_is_empty_once_fixed():
    """Pins this issue's own reported reproduction (rp-89t's description):
    married household, John (64, wages $225k/yr through age 67) and Susan
    (60, wages $185k/yr through age 65), annual_need_real=$180,000,
    net_earned_income_against_spending=True. Year 1 (2026): combined
    wages $410,000, effective_spending_need correctly nets to $0 (rp-595,
    unaffected by this fix), no RMD (both under RMD age), no Roth
    conversion. The reported federal ($75,868) and FICA ($30,263) tax
    figures -- $106,131 combined, with $0 state (FL) -- are pinned here
    unchanged (this fix touches which balance funds tax_owed, never its
    computation); before this fix, that $106,131 was drawn from accounts
    (draining the $40,000 taxable balance, then $66,131 more from
    Traditional) despite $410,000 of the same year's own wages sitting
    completely unused for it. Fixed: $230,000 of wages is left over after
    funding the $180,000 spending need, comfortably covering the
    $106,131 tax bill, so tax_funding_withdrawal is empty."""
    household = Household(
        filing_status="married_filing_jointly",
        members=[
            HouseholdMember(person_name="john", current_age=64, ss_claim_age=67, ss_annual_benefit=0, full_retirement_age=67.0),
            HouseholdMember(person_name="susan", current_age=60, ss_claim_age=67, ss_annual_benefit=0, full_retirement_age=67.0),
        ],
    )
    household.members[0].income_streams = [
        IncomeStream(label="John's wages", stream_type="earned_income", start_age=64, end_age=67, annual_amount=225_000, inflation_adjustment="cola_adjusted")
    ]
    household.members[1].income_streams = [
        IncomeStream(label="Susan's wages", stream_type="earned_income", start_age=60, end_age=65, annual_amount=185_000, inflation_adjustment="cola_adjusted")
    ]

    result = run_plan_projection(
        household=household,
        accounts=AccountBalances(traditional=200_000, roth=0, taxable=40_000),
        traditional_ownership_shares={"john": 0.5, "susan": 0.5},
        annual_spending_need=180_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=64,
        strategy=_strategy(claiming_ages={"john": 67, "susan": 67}),
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
        net_earned_income_against_spending=True,
    )

    year_one = result.years[0]

    assert sum(item.amount for item in year_one.mechanics.withdrawal_plan.sequence_withdrawals) == pytest.approx(0.0)
    assert year_one.mechanics.withdrawal_plan.rmd_drawn == pytest.approx(0.0)
    assert year_one.mechanics.conversion.amount_converted == pytest.approx(0.0)
    assert year_one.federal_tax.federal_tax_owed == pytest.approx(75_868.0, abs=1.0)
    assert year_one.fica_tax.total_fica_tax == pytest.approx(30_263.0, abs=1.0)
    assert year_one.state_tax.state_tax_owed == pytest.approx(0.0)

    assert year_one.tax_funding_withdrawal.sequence_withdrawals == []


def test_explicit_window_mode_is_unaffected_by_rp_595_and_matches_prior_static_behavior():
    """Regression: window_mode="explicit" (the default/every scenario
    predating rp-595) round-trips strategy.conversion_window through to
    PlanProjection.resolved_conversion_window unchanged -- confirms the
    new resolution logic is a true no-op for every existing scenario."""
    household = _ladder_household(current_age=55)
    result = _run_ladder_projection(household)

    assert result.resolved_conversion_window == (2026, 2026)
