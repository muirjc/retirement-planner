"""Full-horizon plan projection (FR-001, FR-002, FR-004).

The per-plan-year orchestration loop: RMD -> account mechanics -> federal
and state tax -> tax-funding withdrawal -> investment growth, chained
across every plan year from the start of retirement through the household's
configured planning horizon. Every comparison this feature offers (US2-US4)
is this same loop run more than once with one input varied — see
specs/004-strategy-comparison-layer/research.md and contracts/comparison-api.md.
"""

from __future__ import annotations

from retirement_planner.mechanics import (
    AccountBalances,
    WithdrawalPlan,
    compute_plan_year_mechanics,
    compute_rmd,
    compute_withdrawal_plan,
)
from retirement_planner.scenario import Household, HouseholdMember
from retirement_planner.tax import IncomeComponents, compute_federal_tax, compute_state_tax

from .models import PlanOutcome, PlanProjection, PlanYearProjection, ReturnSchedule, StrategyConfiguration


def member_age_in_tax_year(member: HouseholdMember, tax_year: int, reference_tax_year: int) -> int:
    """Translates a member's current_age (as of reference_tax_year) into
    their age in an arbitrary tax_year (research.md §2). Renamed from
    private to public in 006-reporting-aggregation (research.md §1) so
    that feature can reuse this exact age-translation formula rather than
    re-implementing it -- behavior unchanged."""
    return member.current_age + (tax_year - reference_tax_year)


def deemed_rmd_owner(household: Household) -> HouseholdMember:
    """The older household member (or the sole member) is treated as the
    deemed owner of the household's entire traditional balance for RMD
    purposes (research.md §4). Renamed from private to public in
    006-reporting-aggregation (research.md §1) -- behavior unchanged."""
    return max(household.members, key=lambda member: member.current_age)


def _household_gross_social_security_benefit(
    household: Household, ages_this_year: dict[str, int], claiming_ages: dict[str, int]
) -> float:
    """Sums each member's ss_annual_benefit, counted only once that
    member's translated age reaches their configured claiming age
    (data-model.md § Relationships)."""
    return sum(
        member.ss_annual_benefit
        for member in household.members
        if ages_this_year[member.person_name] >= claiming_ages[member.person_name]
    )


def run_plan_projection(
    household: Household,
    accounts: AccountBalances,
    annual_spending_need: float,
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    strategy: StrategyConfiguration,
    return_assumption: ReturnSchedule,
) -> PlanProjection:
    """Runs one full-horizon projection, one plan year at a time, from
    start_plan_year through the plan year in which the deemed RMD owner
    (the older household member) reaches plan_to_age (inclusive) (FR-001,
    FR-002). See contracts/comparison-api.md for the full per-year sequence.
    """
    deemed_owner = deemed_rmd_owner(household)
    spouse = next((m for m in household.members if m is not deemed_owner), None)

    years: list[PlanYearProjection] = []
    current_balances = accounts
    plan_year = start_plan_year
    tax_year = start_tax_year

    while True:
        ages_this_year = {
            member.person_name: member_age_in_tax_year(member, tax_year, reference_tax_year)
            for member in household.members
        }
        deemed_owner_age = ages_this_year[deemed_owner.person_name]
        spouse_age = ages_this_year[spouse.person_name] if spouse is not None else None

        if deemed_owner_age > plan_to_age:
            break

        household_ss_benefit = _household_gross_social_security_benefit(
            household, ages_this_year, strategy.claiming_ages
        )

        rmd_result = compute_rmd(
            traditional_balance=current_balances.traditional,
            member_age=deemed_owner_age,
            tax_year=tax_year,
            spouse_age=spouse_age,
            spouse_is_sole_beneficiary=False,  # research.md §3
        )

        mechanics_result = compute_plan_year_mechanics(
            # conversion_window is calendar-year-based (001's Scenario.roth_conversion.window,
            # e.g. (2028, 2034)) and compute_roth_conversion() checks it against this
            # `plan_year` argument — so tax_year (the calendar year), not this loop's
            # sequential plan_year counter, must be passed here for the window check to
            # align with the scenario data it's checked against.
            plan_year=tax_year,
            tax_year=tax_year,
            spending_need=annual_spending_need,
            starting_balances=current_balances,
            rmd_amount=rmd_result.required_amount,
            social_security_gross_benefit=household_ss_benefit,
            filing_status=household.filing_status,
            conversion_window=strategy.conversion_window,
            conversion_strategy=strategy.conversion_strategy,
            conversion_bracket_ceiling_or_amount=strategy.conversion_bracket_ceiling_or_amount,
            withdrawal_strategy=strategy.withdrawal_strategy,
            rmd_figures_used=rmd_result.figures_used,
        )

        income = IncomeComponents(
            ordinary_income=mechanics_result.ordinary_income,
            social_security_gross_benefit=household_ss_benefit,
        )
        federal_tax = compute_federal_tax(income, household.filing_status, tax_year)
        filer_ages = [ages_this_year[member.person_name] for member in household.members]
        state_tax = compute_state_tax(state, income, filer_ages, household.filing_status, tax_year)

        tax_owed = federal_tax.federal_tax_owed + state_tax.state_tax_owed
        tax_funding_withdrawal: WithdrawalPlan = compute_withdrawal_plan(
            spending_need=tax_owed,
            rmd_amount=0.0,
            starting_balances=mechanics_result.ending_balances,
            strategy=strategy.withdrawal_strategy,
        )

        shortfall = mechanics_result.withdrawal_plan.shortfall + tax_funding_withdrawal.shortfall

        post_tax_balances = tax_funding_withdrawal.ending_balances
        # return_assumption may be a DeterministicReturnAssumption (004, a
        # fixed value every plan year) or a ReturnPath (005, one value per
        # plan year) -- both satisfy ReturnSchedule (research.md §1).
        growth_factor = 1.0 + return_assumption.return_for_plan_year(plan_year)
        ending_balances = AccountBalances(
            traditional=post_tax_balances.traditional * growth_factor,
            roth=post_tax_balances.roth * growth_factor,
            taxable=post_tax_balances.taxable * growth_factor,
        )

        figures_used = [*mechanics_result.figures_used, *federal_tax.figures_used, *state_tax.figures_used]

        years.append(
            PlanYearProjection(
                plan_year=plan_year,
                tax_year=tax_year,
                mechanics=mechanics_result,
                federal_tax=federal_tax,
                state_tax=state_tax,
                tax_funding_withdrawal=tax_funding_withdrawal,
                starting_balances=current_balances,
                ending_balances=ending_balances,
                shortfall=shortfall,
                figures_used=figures_used,
            )
        )

        current_balances = ending_balances
        plan_year += 1
        tax_year += 1

    outcome = _derive_outcome(years)

    return PlanProjection(
        strategy=strategy,
        return_assumption=return_assumption,
        years=years,
        outcome=outcome,
    )


def _derive_outcome(years: list[PlanYearProjection]) -> PlanOutcome:
    """Derives a PlanProjection's summary PlanOutcome from its assembled
    years list (data-model.md § PlanOutcome): the last year's total ending
    balance, the first plan year (if any) with a nonzero shortfall, and
    cumulative tax owed across every year.
    """
    last_year = years[-1]
    ending_balance = last_year.ending_balances.traditional + last_year.ending_balances.roth + last_year.ending_balances.taxable

    first_shortfall_plan_year = next((year.plan_year for year in years if year.shortfall > 0), None)

    cumulative_tax_paid = sum(
        year.federal_tax.federal_tax_owed + year.state_tax.state_tax_owed for year in years
    )

    return PlanOutcome(
        ending_balance=ending_balance,
        first_shortfall_plan_year=first_shortfall_plan_year,
        cumulative_tax_paid=cumulative_tax_paid,
    )
