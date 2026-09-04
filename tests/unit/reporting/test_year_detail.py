"""Unit tests for retirement_planner.reporting.year_detail (rp-bm8.3):
build_year_computation_detail() -- the balance waterfall, income
composition, and federal/state tax breakdown behind narrative.py's
YearStory.detail. Mirrors test_narrative.py's fixture style -- real
PlanProjection objects built via run_plan_projection(), no synthetic
dataclass construction.
"""

import pytest

from retirement_planner.comparison import DeterministicReturnAssumption, StrategyConfiguration, run_plan_projection
from retirement_planner.mechanics import AccountBalances, InheritedAccountBalance
from retirement_planner.reporting.year_detail import build_year_computation_detail
from retirement_planner.scenario import Household, HouseholdMember, IncomeStream

_RETURN_4PCT = DeterministicReturnAssumption(annual_real_return=0.04)


def _strategy(**overrides):
    base = dict(
        label="test",
        withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
        conversion_window=None,
        claiming_ages={},
    )
    base.update(overrides)
    return StrategyConfiguration(**base)


def _project(household, accounts, strategy, spending_need=40_000, plan_to_age=80, state="FL", ownership=None, inherited_accounts=None):
    owner_shares = ownership or {member.person_name: 1.0 / len(household.members) for member in household.members}
    return run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares=owner_shares,
        annual_spending_need=spending_need,
        state=state,
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=plan_to_age,
        strategy=strategy,
        return_assumption=_RETURN_4PCT,
        inherited_accounts=inherited_accounts or [],
    )


def _rmd_onset_household():
    return Household(
        filing_status="single",
        members=[HouseholdMember(person_name="Alex", current_age=72, ss_claim_age=99, ss_annual_benefit=0)],
    )


def _accounts_by_type(waterfall):
    return {"traditional": waterfall.traditional, "roth": waterfall.roth, "taxable": waterfall.taxable}


def test_balance_waterfall_reconciles_for_every_type_and_every_year():
    household = _rmd_onset_household()
    strategy = _strategy(claiming_ages={"Alex": 99})
    projection = _project(household, AccountBalances(traditional=700_000, roth=100_000, taxable=100_000), strategy)

    for year in projection.years:
        detail = build_year_computation_detail(year)
        for waterfall in _accounts_by_type(detail.balance_waterfall).values():
            reconciled = (
                waterfall.starting_balance
                - waterfall.rmd_drawn
                - waterfall.spending_withdrawal
                + waterfall.conversion_delta
                - waterfall.tax_funding_withdrawal
                + waterfall.growth
            )
            assert reconciled == waterfall.ending_balance


def test_balance_waterfall_totals_match_household_ending_balance():
    household = _rmd_onset_household()
    strategy = _strategy(claiming_ages={"Alex": 99})
    projection = _project(household, AccountBalances(traditional=700_000, roth=100_000, taxable=100_000), strategy)

    for year in projection.years:
        detail = build_year_computation_detail(year)
        wf = detail.balance_waterfall
        assert wf.total_ending_balance == year.ending_balances.traditional + year.ending_balances.roth + year.ending_balances.taxable
        assert wf.total_tax_owed == (
            year.federal_tax.federal_tax_owed
            + year.state_tax.state_tax_owed
            + year.irmaa.surcharge_owed
            + year.niit.surtax_owed
            + year.early_withdrawal_penalty.penalty_owed
            + year.fica_tax.total_fica_tax
        )


def test_rmd_only_drawn_from_traditional():
    household = _rmd_onset_household()
    strategy = _strategy(claiming_ages={"Alex": 99})
    projection = _project(household, AccountBalances(traditional=700_000, roth=100_000, taxable=100_000), strategy)

    for year in projection.years:
        detail = build_year_computation_detail(year)
        assert detail.balance_waterfall.roth.rmd_drawn == 0.0
        assert detail.balance_waterfall.taxable.rmd_drawn == 0.0


def test_income_composition_sums_to_ordinary_income_total():
    household = _rmd_onset_household()
    strategy = _strategy(claiming_ages={"Alex": 99})
    projection = _project(household, AccountBalances(traditional=700_000, roth=0, taxable=100_000), strategy)

    for year in projection.years:
        ic = build_year_computation_detail(year).income_composition
        reconstructed = (
            ic.rmd_drawn
            + ic.traditional_sequence_withdrawal
            + ic.inherited_distribution
            + ic.income_streams
            + ic.roth_conversion_added
            - ic.hsa_deduction
        )
        assert reconstructed == ic.ordinary_income_total
        assert ic.ordinary_income_total == year.mechanics.ordinary_income
        assert ic.taxable_social_security == year.federal_tax.taxable_social_security


def test_federal_tax_detail_matches_federal_tax_result():
    household = _rmd_onset_household()
    strategy = _strategy(claiming_ages={"Alex": 99})
    projection = _project(household, AccountBalances(traditional=700_000, roth=0, taxable=100_000), strategy)

    for year in projection.years:
        fed = build_year_computation_detail(year).federal_tax_detail
        assert fed.taxable_income == year.federal_tax.taxable_income
        assert fed.deduction_or_exclusion_amount == year.federal_tax.standard_deduction_used
        assert fed.deduction_or_exclusion_label == "standard deduction"
        assert fed.tax_owed == year.federal_tax.federal_tax_owed
        assert sum(row.tax_in_bracket for row in fed.bracket_breakdown) == fed.tax_owed


def test_state_tax_detail_label_per_state():
    household = _rmd_onset_household()
    strategy = _strategy(claiming_ages={"Alex": 99})
    accounts = AccountBalances(traditional=700_000, roth=0, taxable=100_000)

    for state, expected_label in (("FL", "no state income tax"), ("SC", "age-65 exclusion"), ("NC", "NC Bailey settlement exclusion")):
        projection = _project(household, accounts, strategy, state=state)
        state_detail = build_year_computation_detail(projection.years[0]).state_tax_detail
        assert state_detail.deduction_or_exclusion_label == expected_label
        assert state_detail.tax_owed == projection.years[0].state_tax.state_tax_owed


def test_inherited_accounts_empty_for_a_household_with_none_configured():
    household = _rmd_onset_household()
    strategy = _strategy(claiming_ages={"Alex": 99})
    projection = _project(household, AccountBalances(traditional=700_000, roth=0, taxable=100_000), strategy)

    for year in projection.years:
        assert build_year_computation_detail(year).inherited_accounts == []


def test_build_year_computation_detail_is_deterministic():
    household = _rmd_onset_household()
    strategy = _strategy(claiming_ages={"Alex": 99})
    projection = _project(household, AccountBalances(traditional=700_000, roth=0, taxable=100_000), strategy)

    first = build_year_computation_detail(projection.years[1])
    second = build_year_computation_detail(projection.years[1])
    assert first == second


# -- rp-bm8.4: inherited-account reasoning + earned income/FICA transparency --


def test_inherited_account_detail_includes_reason_and_deadline_for_a_forced_distribution():
    household = _rmd_onset_household()
    strategy = _strategy(claiming_ages={"Alex": 99})
    inherited = InheritedAccountBalance(
        account_id="traditional-6", balance=513_000.0, death_year=2005, decedent_age_at_death=67,
        depletion_deadline_year=2015, account_type="traditional", decedent_was_taking_rmds=True,
        beneficiary_classification="non_eligible_designated_beneficiary", beneficiary_person_name="Alex",
    )
    projection = _project(
        household, AccountBalances(traditional=700_000, roth=0, taxable=100_000), strategy, inherited_accounts=[inherited]
    )

    detail = build_year_computation_detail(projection.years[0])
    assert len(detail.inherited_accounts) == 1
    account = detail.inherited_accounts[0]
    assert account.account_id == "traditional-6"
    assert account.distribution == pytest.approx(513_000.0)
    assert account.distribution_reason == "ten_year_rule_deadline"
    assert account.rmd_divisor is None
    assert account.depletion_deadline_year == 2015


def test_inherited_account_detail_includes_divisor_for_an_annual_rmd():
    household = _rmd_onset_household()
    strategy = _strategy(claiming_ages={"Alex": 99})
    inherited = InheritedAccountBalance(
        account_id="inh-1", balance=200_000.0, death_year=2023, decedent_age_at_death=80,
        depletion_deadline_year=2033, account_type="traditional", decedent_was_taking_rmds=True,
        beneficiary_classification="non_eligible_designated_beneficiary", beneficiary_person_name="Alex",
    )
    projection = _project(
        household, AccountBalances(traditional=700_000, roth=0, taxable=100_000), strategy, inherited_accounts=[inherited]
    )

    detail = build_year_computation_detail(projection.years[0])
    account = detail.inherited_accounts[0]
    assert account.distribution_reason == "annual_rmd"
    assert account.rmd_divisor > 0.0
    assert account.distribution == pytest.approx(200_000.0 / account.rmd_divisor)


def test_income_composition_earned_income_matches_member_earned_income():
    household = Household(
        filing_status="single",
        members=[HouseholdMember(
            person_name="Alex", current_age=60, ss_claim_age=99, ss_annual_benefit=0,
            income_streams=[IncomeStream(label="Salary", stream_type="earned_income", start_age=60, end_age=None, annual_amount=90_000.0, inflation_adjustment="fixed_nominal")],
        )],
    )
    strategy = _strategy(claiming_ages={"Alex": 99})
    projection = _project(household, AccountBalances(traditional=200_000, roth=0, taxable=0), strategy, plan_to_age=61)

    year = projection.years[0]
    composition = build_year_computation_detail(year).income_composition
    assert composition.earned_income == sum(year.member_earned_income.values())
    assert composition.earned_income == pytest.approx(90_000.0)
    assert composition.earned_income <= composition.income_streams


def test_fica_tax_detail_matches_fica_tax_result():
    household = Household(
        filing_status="single",
        members=[HouseholdMember(
            person_name="Alex", current_age=60, ss_claim_age=99, ss_annual_benefit=0,
            income_streams=[IncomeStream(label="Salary", stream_type="earned_income", start_age=60, end_age=None, annual_amount=90_000.0, inflation_adjustment="fixed_nominal")],
        )],
    )
    strategy = _strategy(claiming_ages={"Alex": 99})
    projection = _project(household, AccountBalances(traditional=200_000, roth=0, taxable=0), strategy, plan_to_age=61)

    year = projection.years[0]
    fica_detail = build_year_computation_detail(year).fica_tax_detail
    assert fica_detail.member_oasdi_tax == year.fica_tax.member_oasdi_tax
    assert fica_detail.member_medicare_tax == year.fica_tax.member_medicare_tax
    assert fica_detail.additional_medicare_tax == year.fica_tax.additional_medicare_tax
    assert fica_detail.total_fica_tax == year.fica_tax.total_fica_tax
    assert fica_detail.total_fica_tax > 0.0


def test_fica_tax_detail_is_zero_for_a_household_with_no_earned_income():
    household = _rmd_onset_household()
    strategy = _strategy(claiming_ages={"Alex": 99})
    projection = _project(household, AccountBalances(traditional=700_000, roth=0, taxable=100_000), strategy)

    fica_detail = build_year_computation_detail(projection.years[0]).fica_tax_detail
    assert fica_detail.total_fica_tax == 0.0
