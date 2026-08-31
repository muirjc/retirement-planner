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
    InheritedAccountBalance,
    WithdrawalPlan,
    compute_hsa_contribution,
    compute_hsa_eligibility,
    compute_inherited_rmd,
    compute_plan_year_mechanics,
    compute_rmd,
    compute_social_security_benefit,
    compute_withdrawal_plan,
)
from retirement_planner.scenario import Household, HouseholdMember
from retirement_planner.tax import (
    FederalTaxResult,
    FigureUsage,
    IncomeComponents,
    compute_federal_tax,
    compute_irmaa_surcharge,
    compute_niit,
    compute_state_tax,
)

from .models import PlanOutcome, PlanProjection, PlanYearProjection, ReturnSchedule, StrategyConfiguration

_MEDICARE_ENROLLMENT_AGE = 65
"""Standard Medicare enrollment age -- 010-advanced-tax-benefits spec.md
Assumptions: early enrollment due to disability is out of scope for v1."""


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


def _approximate_magi(income: IncomeComponents, federal_tax: FederalTaxResult) -> float:
    """MAGI approximation shared by IRMAA and NIIT determinations
    (010-advanced-tax-benefits research.md §2): ordinary_income plus the
    *taxable* portion of Social Security (federal_tax.taxable_social_security,
    already computed by compute_federal_tax()'s own provisional-income
    rule) -- never the gross benefit. This engine tracks no tax-exempt
    interest or above-the-line deductions, so this is this engine's own
    AGI proxy, not real MAGI -- a documented simplification (Principle I),
    not silently presented as the IRS's own figure."""
    return income.ordinary_income + federal_tax.taxable_social_security


def _member_gross_social_security_benefits(
    household: Household, ages_this_year: dict[str, int], claiming_ages: dict[str, int], tax_year: int
) -> tuple[dict[str, float], list[FigureUsage]]:
    """Each member's own actual annual Social Security benefit received
    this year, counted only once that member's translated age reaches
    their configured claiming age (data-model.md § Relationships) -- 0.0
    before then, never omitted (015-per-account-projection-detail
    data-model.md § PlanYearProjection extension). Summing the dict's
    values reproduces _household_gross_social_security_benefit()'s own
    total exactly.

    016-ss-claiming-age-actuarial-adjustment: the amount for a member who
    has reached their claiming age is no longer member.ss_annual_benefit
    taken flat -- it's derived via compute_social_security_benefit() from
    that field (now the member's PIA), member.full_retirement_age, and
    this comparison's own claiming_ages[member.person_name], so claiming
    earlier or later actually changes the amount, not just when it starts
    (rp-n44). Each such call's figures_used is collected into the second
    return value, threaded by the caller into this plan year's overall
    figures_used list (research.md Decision 2).

    member.full_retirement_age is defaulted here too (to that member's own
    ss_claim_age, i.e. no adjustment) whenever it's still None -- not just
    relied on from scenario.loader.parse_scenario()'s own resolution
    (data-model.md) -- so a Household built directly, bypassing the loader
    entirely (as most of this codebase's own test fixtures, and any
    future direct-API caller, do), gets the identical backward-compatible
    default a parsed scenario already gets, mirroring
    scenario.validation.validate()'s own "not just relied on from
    parse_scenario()'s own auto-fill" precedent for Account.owner."""
    benefits: dict[str, float] = {}
    figures_used: list[FigureUsage] = []
    for member in household.members:
        if ages_this_year[member.person_name] >= claiming_ages[member.person_name]:
            full_retirement_age = (
                member.full_retirement_age if member.full_retirement_age is not None else float(member.ss_claim_age)
            )
            result = compute_social_security_benefit(
                primary_insurance_amount=member.ss_annual_benefit,
                full_retirement_age=full_retirement_age,
                claiming_age=claiming_ages[member.person_name],
                tax_year=tax_year,
            )
            benefits[member.person_name] = result.annual_benefit
            figures_used.extend(result.figures_used)
        else:
            benefits[member.person_name] = 0.0
    return benefits, figures_used


def _household_gross_social_security_benefit(
    household: Household, ages_this_year: dict[str, int], claiming_ages: dict[str, int], tax_year: int
) -> float:
    """Sums each member's actual annual Social Security benefit (see
    _member_gross_social_security_benefits()), counted only once that
    member's translated age reaches their configured claiming age
    (data-model.md § Relationships). Discards figures_used -- callers
    that need the audit trail use _member_gross_social_security_benefits()
    directly, as run_plan_projection() does below."""
    benefits, _ = _member_gross_social_security_benefits(household, ages_this_year, claiming_ages, tax_year)
    return sum(benefits.values())


def run_plan_projection(
    household: Household,
    accounts: AccountBalances,
    traditional_ownership_shares: dict[str, float],
    annual_spending_need: float,
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    strategy: StrategyConfiguration,
    return_assumption: ReturnSchedule,
    inherited_accounts: list[InheritedAccountBalance] = [],  # noqa: B006 -- see docstring: never mutated as a list
) -> PlanProjection:
    """Runs one full-horizon projection, one plan year at a time, from
    start_plan_year through the plan year in which the deemed RMD owner
    (the older household member) reaches plan_to_age (inclusive) (FR-001,
    FR-002). See contracts/comparison-api.md for the full per-year sequence.

    traditional_ownership_shares (011-per-owner-accounts, comparison-api.md):
    each household member's fixed share (0-1) of the household's traditional
    balance, used to compute that member's own RMD from their own age and
    own share-derived balance every plan year (data-model.md § Consumption)
    -- replaces the prior single deemed-owner-attributed compute_rmd() call.
    deemed_rmd_owner() itself is unchanged and still drives this function's
    own loop-termination condition below (an unrelated use, research.md §4).
    Raises KeyError immediately, before processing any plan year, if this
    dict omits any of household.members[*].person_name (mirrors 005's
    survival_curves precedent).

    inherited_accounts (012-inherited-ira-rmd, comparison-api.md): each
    already-in-RMD-status inherited traditional account this household's
    beneficiary holds, tracked entirely independently of accounts/
    traditional_ownership_shares (never pooled -- research.md §5). Each
    instance's balance is mutated in place, year by year, as this
    function runs (distribution subtracted, then growth applied) -- a
    caller comparing multiple candidates (compare.py) must pass a fresh,
    independently-copied list per call, never the same instances reused
    across candidates (comparison-api.md's per-candidate independent-copy
    requirement). This default parameter is itself never mutated as a
    list (no account is ever appended/removed) -- only elements already
    inside a caller-supplied list are mutated -- so sharing the default
    empty list across calls is safe (data-model.md § Consumption).
    Defaults to [], reproducing every existing caller's exact prior
    output unchanged.
    """
    for member in household.members:
        traditional_ownership_shares[member.person_name]  # noqa: B018 -- eager KeyError check

    deemed_owner = deemed_rmd_owner(household)

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

        if deemed_owner_age > plan_to_age:
            break

        # 015-per-account-projection-detail: the per-member breakdown is
        # retained (below, threaded into PlanYearProjection), not just the
        # household sum -- household_ss_benefit stays the same value
        # _household_gross_social_security_benefit() would have returned.
        # 016-ss-claiming-age-actuarial-adjustment: each member's own
        # amount is now claiming-age-adjusted (rp-n44), and this call's
        # figures_used feeds into this year's overall figures_used below.
        member_ss_benefits, ss_benefit_figures_used = _member_gross_social_security_benefits(
            household, ages_this_year, strategy.claiming_ages, tax_year
        )
        household_ss_benefit = sum(member_ss_benefits.values())

        # 011-per-owner-accounts: one compute_rmd() call per member with a
        # positive traditional share, replacing the single deemed-owner-
        # attributed call (research.md §1). spouse_is_sole_beneficiary is
        # still always False (004 research.md §3, unaffected by this
        # feature); spouse_age is still each member's actual co-member's
        # age, for a household of at most 2 (001's own household-size cap).
        # 015-per-account-projection-detail: keyed by person_name (a dict,
        # not a list) so each member's own exact required_amount can be
        # retained (below) instead of only surviving as the summed total.
        member_rmd_results = {
            member.person_name: compute_rmd(
                traditional_balance=traditional_ownership_shares[member.person_name] * current_balances.traditional,
                member_age=ages_this_year[member.person_name],
                tax_year=tax_year,
                spouse_age=next(
                    (ages_this_year[other.person_name] for other in household.members if other is not member),
                    None,
                ),
                spouse_is_sole_beneficiary=False,  # research.md §3 (004)
            )
            for member in household.members
            if traditional_ownership_shares[member.person_name] > 0
        }
        rmd_amount = sum(result.required_amount for result in member_rmd_results.values())
        rmd_figures_used = [figure for result in member_rmd_results.values() for figure in result.figures_used]
        member_rmd_amounts = {name: result.required_amount for name, result in member_rmd_results.items()}

        # 012-inherited-ira-rmd (research.md §7, §8, §10), extended by
        # 013-inherited-ira-edge-cases (research.md § Handoff): one
        # compute_inherited_rmd() call per inherited account still holding
        # a positive balance, forwarding each account's own real
        # decedent_was_taking_rmds/beneficiary_classification/account_type
        # -- no longer hardcoded to 012's own single originally-supported
        # combination, now that scenario.validation allows more (013
        # research.md §8). beneficiary_current_age is this year's own
        # translated age for the account's beneficiary -- consulted for
        # every account whenever an annual divisor is actually computed,
        # not just an EDB's (rp-kn5's "longer of" fix extended this to the
        # non-EDB post-RBD case too -- inherited_rmd.py's own docstring).
        # In the account's depletion_deadline_year (and,
        # as a safety net, any later year a positive balance somehow
        # still remains), the ENTIRE remaining balance is force-
        # distributed instead of the divisor-computed amount (US2,
        # FR-003) -- the 10-year deadline and the annual divisor
        # arithmetic are two independent IRS rules that happen to
        # interact, so this deadline check is never folded into
        # compute_inherited_rmd()'s own divisor math (research.md §8).
        # This year's distribution is subtracted from each account's own
        # balance immediately; step 7 below (investment growth) applies
        # the household's growth_factor to whatever balance remains.
        inherited_distribution_total = 0.0
        inherited_rmd_figures_used: list = []
        # 015-per-account-projection-detail: each inherited account's own
        # distribution is snapshotted here, at the same point it's already
        # computed -- inherited_account_balances is filled in below, after
        # this year's growth (step 7) has been applied, since that's this
        # year's true ending balance.
        inherited_account_distributions: dict[str, float] = {}
        for inherited_account in inherited_accounts:
            if inherited_account.balance <= 0:
                continue
            if tax_year >= inherited_account.depletion_deadline_year:
                distribution = inherited_account.balance
            else:
                inherited_result = compute_inherited_rmd(
                    inherited_balance=inherited_account.balance,
                    tax_year=tax_year,
                    death_year=inherited_account.death_year,
                    decedent_age_at_death=inherited_account.decedent_age_at_death,
                    decedent_was_taking_rmds=inherited_account.decedent_was_taking_rmds,
                    beneficiary_classification=inherited_account.beneficiary_classification,
                    account_type=inherited_account.account_type,
                    beneficiary_current_age=ages_this_year.get(inherited_account.beneficiary_person_name),
                    depletion_deadline_year=inherited_account.depletion_deadline_year,
                )
                distribution = min(inherited_result.required_amount, inherited_account.balance)
                inherited_rmd_figures_used.extend(inherited_result.figures_used)
            inherited_account.balance -= distribution
            inherited_distribution_total += distribution
            inherited_account_distributions[inherited_account.account_id] = distribution

        # HSA (010-advanced-tax-benefits FR-008-FR-012): eligibility is
        # always computed (informative even when no contribution is
        # configured -- the same "always present" auditability discipline
        # irmaa/niit follow), using this year's own ages/coverage/Medicare-
        # enrollment status -- never the prior or a future year's.
        hsa_eligibility = compute_hsa_eligibility(
            members=[
                (member.person_name, ages_this_year[member.person_name], member.hdhp_coverage)
                for member in household.members
            ],
            medicare_enrolled={
                member.person_name: ages_this_year[member.person_name] >= _MEDICARE_ENROLLMENT_AGE
                for member in household.members
            },
        )
        hsa_contribution = compute_hsa_contribution(
            hsa_eligibility,
            configured_annual_amount=(
                strategy.hsa_contribution.annual_amount if strategy.hsa_contribution is not None else 0.0
            ),
            tax_year=tax_year,
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
            rmd_amount=rmd_amount,
            social_security_gross_benefit=household_ss_benefit,
            filing_status=household.filing_status,
            conversion_window=strategy.conversion_window,
            conversion_strategy=strategy.conversion_strategy,
            conversion_bracket_ceiling_or_amount=strategy.conversion_bracket_ceiling_or_amount,
            withdrawal_strategy=strategy.withdrawal_strategy,
            rmd_figures_used=rmd_figures_used,
            hsa_contribution=hsa_contribution,
            inherited_distribution_amount=inherited_distribution_total,
            inherited_rmd_figures_used=inherited_rmd_figures_used,
        )

        income = IncomeComponents(
            ordinary_income=mechanics_result.ordinary_income,
            social_security_gross_benefit=household_ss_benefit,
        )
        filer_ages = [ages_this_year[member.person_name] for member in household.members]
        federal_tax = compute_federal_tax(income, filer_ages, household.filing_status, tax_year)
        state_tax = compute_state_tax(state, income, filer_ages, household.filing_status, tax_year)

        # IRMAA (010-advanced-tax-benefits FR-001-FR-004, research.md §§2-3):
        # a true two-year look-back when this projection has already computed
        # that far back, else this year's own MAGI as an explicitly flagged
        # proxy -- never fabricated pre-scenario history.
        if len(years) >= 2:
            lookback_year = years[-2]
            irmaa_magi = lookback_year.mechanics.ordinary_income + lookback_year.federal_tax.taxable_social_security
            income_basis = "two_year_lookback"
        else:
            irmaa_magi = _approximate_magi(income, federal_tax)
            income_basis = "current_year_proxy"
        enrolled_member_count = sum(
            1 for member in household.members if ages_this_year[member.person_name] >= _MEDICARE_ENROLLMENT_AGE
        )
        irmaa = compute_irmaa_surcharge(
            magi=irmaa_magi,
            income_basis=income_basis,
            filing_status=household.filing_status,
            tax_year=tax_year,
            enrolled_member_count=enrolled_member_count,
        )

        # NIIT (010-advanced-tax-benefits FR-005-FR-007, research.md §1):
        # investment_income is approximated as this year's taxable-account
        # withdrawal amount in full -- the same income-establishing
        # withdrawal that already fed into `income` above, never the
        # tax-funding withdrawal computed below (which happens only after
        # tax is already determined and isn't itself part of this year's
        # taxable income).
        investment_income = sum(
            item.amount
            for item in mechanics_result.withdrawal_plan.sequence_withdrawals
            if item.account_type == "taxable"
        )
        niit = compute_niit(
            magi=_approximate_magi(income, federal_tax),
            investment_income=investment_income,
            filing_status=household.filing_status,
            tax_year=tax_year,
        )

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

        # 012-inherited-ira-rmd (research.md §10): each inherited account
        # grows using the same household growth_factor -- no separate
        # per-account return assumption exists in this codebase (an
        # explicitly documented simplification). A depleted account's
        # balance is already 0.0 here and growing it is a no-op either way.
        for inherited_account in inherited_accounts:
            inherited_account.balance *= growth_factor

        # 015-per-account-projection-detail: snapshotted after growth, so
        # this reflects this year's true ending balance -- every inherited
        # account still on the books this year, including one that fully
        # depleted this year (balance 0.0, still present so a consumer can
        # see it reached zero rather than silently disappearing).
        inherited_account_balances = {
            inherited_account.account_id: inherited_account.balance for inherited_account in inherited_accounts
        }

        # mechanics_result.figures_used already includes hsa_contribution's
        # own figures_used (compute_plan_year_mechanics() folds it in), so
        # it is not repeated here.
        figures_used = [
            *ss_benefit_figures_used,
            *mechanics_result.figures_used,
            *federal_tax.figures_used,
            *state_tax.figures_used,
            *irmaa.figures_used,
            *niit.figures_used,
        ]

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
                irmaa=irmaa,
                niit=niit,
                hsa_contribution=hsa_contribution,
                figures_used=figures_used,
                member_rmd_amounts=member_rmd_amounts,
                member_social_security_benefits=member_ss_benefits,
                inherited_account_balances=inherited_account_balances,
                inherited_account_distributions=inherited_account_distributions,
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
    cumulative_irmaa_paid = sum(year.irmaa.surcharge_owed for year in years)
    cumulative_niit_paid = sum(year.niit.surtax_owed for year in years)

    return PlanOutcome(
        ending_balance=ending_balance,
        first_shortfall_plan_year=first_shortfall_plan_year,
        cumulative_tax_paid=cumulative_tax_paid,
        cumulative_irmaa_paid=cumulative_irmaa_paid,
        cumulative_niit_paid=cumulative_niit_paid,
    )
