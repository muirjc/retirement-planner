"""Unit tests for account_attribution.py (015-per-account-projection-detail).

Invariant-based, per plan.md's Development Workflow gate and spec.md's own
testing approach: what's under test is that the apportionment arithmetic
is internally consistent with the pooled totals it's derived from (and
exact where the underlying figure already is), never a hand-picked dollar
figure asserted with no derivation.
"""

import pytest

from retirement_planner.comparison import DeterministicReturnAssumption, StrategyConfiguration, run_plan_projection
from retirement_planner.mechanics import AccountBalances, InheritedAccountBalance
from retirement_planner.reporting import attribute_plan_projection, compute_account_shares
from retirement_planner.scenario import Account, Household, HouseholdMember, IncomeStream


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


def _run(household, accounts, traditional_ownership_shares, plan_to_age, inherited_accounts=None, **overrides):
    strategy = _strategy(**overrides.pop("strategy_overrides", {}))
    return run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares=traditional_ownership_shares,
        inherited_accounts=inherited_accounts or [],
        annual_spending_need=overrides.pop("annual_spending_need", 40_000),
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=plan_to_age,
        strategy=strategy,
        return_assumption=DeterministicReturnAssumption(annual_real_return=0.04),
        **overrides,
    )


# -- compute_account_shares() --


def test_per_type_shares_sum_to_one():
    scenario_accounts = [
        Account(account_type="traditional", balance=600_000, owner="you", account_id="traditional-0"),
        Account(account_type="traditional", balance=400_000, owner="spouse", account_id="traditional-1"),
        Account(account_type="roth", balance=100_000, owner="you", account_id="roth-2"),
        Account(account_type="taxable", balance=50_000, owner="you", account_id="taxable-3"),
    ]
    shares = compute_account_shares(scenario_accounts)

    for account_type in ("traditional", "roth", "taxable"):
        type_shares = [s for s in shares if s.account_type == account_type]
        assert sum(s.fixed_share for s in type_shares) == pytest.approx(1.0)


def test_zero_balance_account_never_divides_by_zero():
    scenario_accounts = [Account(account_type="roth", balance=0.0, owner="you", account_id="roth-0")]
    shares = compute_account_shares(scenario_accounts)
    assert shares[0].fixed_share == 0.0


def test_inherited_account_always_has_fixed_share_one_and_is_flagged():
    scenario_accounts = [
        Account(
            account_type="traditional", balance=250_000, owner="spouse", account_id="traditional-6",
            inherited=object(),  # any non-None sentinel -- only identity (is not None) matters here
        ),
    ]
    shares = compute_account_shares(scenario_accounts)
    assert shares[0].inherited is True
    assert shares[0].fixed_share == 1.0


# -- attribute_plan_projection(): ordinary accounts --


def test_per_account_balances_of_a_type_sum_to_the_pooled_balance():
    household = Household(
        filing_status="married_filing_jointly",
        members=[
            HouseholdMember(person_name="you", current_age=76, ss_claim_age=67, ss_annual_benefit=32_000),
            HouseholdMember(person_name="spouse", current_age=74, ss_claim_age=67, ss_annual_benefit=24_000),
        ],
    )
    scenario_accounts = [
        Account(account_type="traditional", balance=1_200_000, owner="you", account_id="traditional-0"),
        Account(account_type="traditional", balance=800_000, owner="spouse", account_id="traditional-1"),
        Account(account_type="taxable", balance=100_000, owner="you", account_id="taxable-2"),
    ]
    accounts = AccountBalances(traditional=2_000_000, roth=0, taxable=100_000)
    projection = _run(household, accounts, {"you": 0.6, "spouse": 0.4}, plan_to_age=77)
    shares = compute_account_shares(scenario_accounts)

    detail = attribute_plan_projection(projection, shares)

    for year_detail, year in zip(detail, projection.years):
        for account_type in ("traditional", "roth", "taxable"):
            pooled_start = getattr(year.starting_balances, account_type)
            pooled_end = getattr(year.ending_balances, account_type)
            # (no inherited accounts in this fixture, so every row of a
            # given type is ordinary)
            ordinary_rows = [r for r in year_detail.accounts if r.account_type == account_type]
            assert sum(r.starting_balance for r in ordinary_rows) == pytest.approx(pooled_start)
            assert sum(r.ending_balance for r in ordinary_rows) == pytest.approx(pooled_end)


def test_per_account_withdrawals_of_a_type_sum_to_the_pooled_total():
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=75, ss_claim_age=99, ss_annual_benefit=0)],
    )
    scenario_accounts = [
        Account(account_type="taxable", balance=300_000, owner="you", account_id="taxable-0"),
        Account(account_type="taxable", balance=200_000, owner="you", account_id="taxable-1"),
        Account(account_type="traditional", balance=500_000, owner="you", account_id="traditional-2"),
    ]
    accounts = AccountBalances(traditional=500_000, roth=0, taxable=500_000)
    projection = _run(
        household, accounts, {"you": 1.0}, plan_to_age=76,
        strategy_overrides={"claiming_ages": {"you": 99}}, annual_spending_need=60_000,
    )
    shares = compute_account_shares(scenario_accounts)

    detail = attribute_plan_projection(projection, shares)

    for year_detail, year in zip(detail, projection.years):
        totals = {"traditional": year.mechanics.withdrawal_plan.rmd_drawn, "roth": 0.0, "taxable": 0.0}
        for item in (*year.mechanics.withdrawal_plan.sequence_withdrawals, *year.tax_funding_withdrawal.sequence_withdrawals):
            totals[item.account_type] += item.amount
        for account_type, pooled_total in totals.items():
            rows = [r for r in year_detail.accounts if r.account_type == account_type]
            assert sum(r.withdrawal_amount for r in rows) == pytest.approx(pooled_total)


def test_sole_traditional_account_gets_the_members_exact_rmd_independently_tracked():
    household = Household(
        filing_status="married_filing_jointly",
        members=[
            HouseholdMember(person_name="you", current_age=76, ss_claim_age=67, ss_annual_benefit=32_000),
            HouseholdMember(person_name="spouse", current_age=74, ss_claim_age=67, ss_annual_benefit=24_000),
        ],
    )
    scenario_accounts = [
        Account(account_type="traditional", balance=1_200_000, owner="you", account_id="traditional-0"),
        Account(account_type="traditional", balance=800_000, owner="spouse", account_id="traditional-1"),
    ]
    accounts = AccountBalances(traditional=2_000_000, roth=0, taxable=0)
    projection = _run(household, accounts, {"you": 0.6, "spouse": 0.4}, plan_to_age=76)
    shares = compute_account_shares(scenario_accounts)

    detail = attribute_plan_projection(projection, shares)

    year_detail, year = detail[0], projection.years[0]
    you_row = next(r for r in year_detail.accounts if r.account_id == "traditional-0")
    spouse_row = next(r for r in year_detail.accounts if r.account_id == "traditional-1")
    assert you_row.rmd_amount == pytest.approx(year.member_rmd_amounts["you"])
    assert you_row.attribution == "independently_tracked"
    assert spouse_row.rmd_amount == pytest.approx(year.member_rmd_amounts["spouse"])
    assert spouse_row.attribution == "independently_tracked"


def test_member_with_two_traditional_accounts_rmd_sub_allocated_and_sums_exactly():
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=76, ss_claim_age=99, ss_annual_benefit=0)],
    )
    scenario_accounts = [
        Account(account_type="traditional", balance=750_000, owner="you", account_id="traditional-0"),
        Account(account_type="traditional", balance=250_000, owner="you", account_id="traditional-1"),
    ]
    accounts = AccountBalances(traditional=1_000_000, roth=0, taxable=0)
    projection = _run(
        household, accounts, {"you": 1.0}, plan_to_age=76, strategy_overrides={"claiming_ages": {"you": 99}},
    )
    shares = compute_account_shares(scenario_accounts)

    detail = attribute_plan_projection(projection, shares)

    year_detail, year = detail[0], projection.years[0]
    rows = [r for r in year_detail.accounts if r.account_type == "traditional"]
    assert len(rows) == 2
    assert all(r.attribution == "fixed_share_of_pooled_total" for r in rows)
    assert sum(r.rmd_amount for r in rows) == pytest.approx(year.member_rmd_amounts["you"])
    # 750k/250k split -> 75%/25% of the member's own total RMD.
    by_id = {r.account_id: r.rmd_amount for r in rows}
    assert by_id["traditional-0"] == pytest.approx(year.member_rmd_amounts["you"] * 0.75)
    assert by_id["traditional-1"] == pytest.approx(year.member_rmd_amounts["you"] * 0.25)


# -- attribute_plan_projection(): inherited accounts --


def test_inherited_account_row_is_exact_and_independent_of_ordinary_account_shares():
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=55, ss_claim_age=99, ss_annual_benefit=0)],
    )
    scenario_accounts = [
        Account(account_type="taxable", balance=100_000, owner="you", account_id="taxable-0"),
        Account(
            account_type="traditional", balance=250_000, owner="you", account_id="traditional-1",
            inherited=object(),
        ),
    ]
    accounts = AccountBalances(traditional=0, roth=0, taxable=100_000)
    inherited = InheritedAccountBalance(
        account_id="traditional-1", balance=250_000.0, death_year=2023, decedent_age_at_death=80,
        depletion_deadline_year=2033, beneficiary_person_name="you",
    )
    projection = _run(
        household, accounts, {"you": 0.0}, plan_to_age=55,
        inherited_accounts=[inherited], strategy_overrides={"claiming_ages": {"you": 99}}, annual_spending_need=10_000,
    )
    shares = compute_account_shares(scenario_accounts)

    detail = attribute_plan_projection(projection, shares)

    year_detail, year = detail[0], projection.years[0]
    inherited_row = next(r for r in year_detail.accounts if r.account_id == "traditional-1")
    assert inherited_row.attribution == "independently_tracked"
    assert inherited_row.owner == "you"
    assert inherited_row.account_type == "traditional"
    assert inherited_row.ending_balance == pytest.approx(year.inherited_account_balances["traditional-1"])
    assert inherited_row.withdrawal_amount == pytest.approx(year.inherited_account_distributions["traditional-1"])
    assert inherited_row.rmd_amount == pytest.approx(year.inherited_account_distributions["traditional-1"])


def test_member_social_security_benefits_pass_through_unchanged():
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=67, ss_claim_age=67, ss_annual_benefit=30_000)],
    )
    scenario_accounts = [Account(account_type="taxable", balance=100_000, owner="you", account_id="taxable-0")]
    accounts = AccountBalances(traditional=0, roth=0, taxable=100_000)
    projection = _run(household, accounts, {"you": 0.0}, plan_to_age=67, strategy_overrides={"claiming_ages": {"you": 67}})
    shares = compute_account_shares(scenario_accounts)

    detail = attribute_plan_projection(projection, shares)

    assert detail[0].member_social_security_benefits == projection.years[0].member_social_security_benefits == {"you": 30_000.0}


def test_member_income_stream_amounts_pass_through_unchanged():
    """021-pension-annuity-income (rp-pid), mirrors
    test_member_social_security_benefits_pass_through_unchanged."""
    household = Household(
        filing_status="single",
        members=[
            HouseholdMember(
                person_name="you",
                current_age=67,
                ss_claim_age=99,
                ss_annual_benefit=0,
                income_streams=[
                    IncomeStream(
                        label="State Pension", stream_type="pension", start_age=67,
                        annual_amount=18_000.0, inflation_adjustment="cola_adjusted",
                    )
                ],
            )
        ],
    )
    scenario_accounts = [Account(account_type="taxable", balance=100_000, owner="you", account_id="taxable-0")]
    accounts = AccountBalances(traditional=0, roth=0, taxable=100_000)
    projection = _run(household, accounts, {"you": 0.0}, plan_to_age=67, strategy_overrides={"claiming_ages": {"you": 99}})
    shares = compute_account_shares(scenario_accounts)

    detail = attribute_plan_projection(projection, shares)

    assert detail[0].member_income_stream_amounts == projection.years[0].member_income_stream_amounts == {"you": 18_000.0}
