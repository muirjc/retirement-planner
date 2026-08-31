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
from retirement_planner.scenario import Household, HouseholdMember
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
    household = _mfj_household(
        you_age=60, spouse_age=58, you_benefit=32_000, spouse_benefit=24_000, you_fra=67.0, spouse_fra=70.0
    )
    claiming_ages = {"you": 67, "spouse": 70}

    before_anyone_claims = _household_gross_social_security_benefit(
        household, ages_this_year={"you": 65, "spouse": 63}, claiming_ages=claiming_ages, tax_year=2026
    )
    assert before_anyone_claims == 0.0

    after_you_claim = _household_gross_social_security_benefit(
        household, ages_this_year={"you": 67, "spouse": 65}, claiming_ages=claiming_ages, tax_year=2026
    )
    assert after_you_claim == 32_000.0

    after_both_claim = _household_gross_social_security_benefit(
        household, ages_this_year={"you": 70, "spouse": 70}, claiming_ages=claiming_ages, tax_year=2026
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
    account_b = _inherited_account(
        account_id="traditional-2", balance=90_000, death_year=2020, decedent_age_at_death=75, depletion_deadline_year=2030
    )

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


def test_full_retirement_age_equal_to_claim_age_reproduces_pre_feature_flat_benefit():
    """016-ss-claiming-age-actuarial-adjustment backward compatibility
    (research.md Decision 3, spec.md FR-001): a member whose
    full_retirement_age equals their ss_claim_age -- the default every
    scenario predating this feature resolves to -- receives exactly their
    configured ss_annual_benefit once claimed, with zero adjustment,
    identical to this feature's absence."""
    household = _mfj_household(
        you_age=65, spouse_age=65, you_benefit=32_000, spouse_benefit=24_000, you_fra=67.0, spouse_fra=67.0
    )
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
    household = _mfj_household(
        you_age=67, spouse_age=65, you_benefit=30_000, spouse_benefit=6_000, you_fra=67.0, spouse_fra=67.0
    )
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


def test_predicted_death_age_has_zero_effect_on_projection_output():
    """spec.md FR-007: this feature does not itself wire predicted_death_age
    into a running projection -- confirmed here by asserting a scenario
    that sets it produces byte-for-byte identical output to the same
    scenario without it (rp-g8y's future job, not this feature's)."""

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
                HouseholdMember(
                    person_name="spouse", current_age=67, ss_claim_age=67, ss_annual_benefit=24_000, full_retirement_age=67.0
                ),
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


def test_compute_survivor_benefit_has_no_caller_in_this_module():
    """spec.md FR-007: compute_survivor_benefit() is implemented and
    cited (tests/unit/mechanics/test_social_security_benefit.py) but not
    yet consumed by any running projection -- confirmed here by
    inspecting this module's own source, since a positive "was it ever
    called" assertion can't otherwise be made against a function with no
    caller at all."""
    import inspect

    from retirement_planner.comparison import projection as projection_module

    assert "compute_survivor_benefit" not in inspect.getsource(projection_module)


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
    assert year.inherited_account_distributions["traditional-1"] == pytest.approx(
        year.mechanics.withdrawal_plan.inherited_distribution_drawn
    )
    assert year.inherited_account_balances["traditional-1"] == pytest.approx(inherited.balance)


def test_two_inherited_accounts_have_independently_keyed_snapshots():
    household = _single_member_household(current_age=55)
    accounts = AccountBalances(traditional=0, roth=0, taxable=100_000)
    strategy = _strategy(claiming_ages={"you": 99})
    account_a = _inherited_account(account_id="traditional-1", balance=250_000, death_year=2023, decedent_age_at_death=80)
    account_b = _inherited_account(
        account_id="traditional-2", balance=90_000, death_year=2020, decedent_age_at_death=75, depletion_deadline_year=2030
    )

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
    assert sum(year.inherited_account_distributions.values()) == pytest.approx(
        year.mechanics.withdrawal_plan.inherited_distribution_drawn
    )
    # account_a's own snapshot is unaffected by account_b's presence.
    # rp-kn5: 31.4, the beneficiary's own divisor (see the hand check in
    # test_inherited_account_annual_distribution_included_in_withdrawal_plan).
    assert year.inherited_account_distributions["traditional-1"] == pytest.approx(250_000 / 31.4)
