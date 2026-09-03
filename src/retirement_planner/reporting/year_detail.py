"""Per-plan-year computation traceability (rp-bm8.3): the full "how was
this year's math computed" trace behind narrative.py's own year-by-year
story -- an account-balance waterfall (starting -> RMD -> spending
withdrawal -> Roth conversion -> tax-funding withdrawal -> growth ->
ending, per account type), an ordinary-income composition breakdown, and a
federal/state tax breakdown (taxable income, the standard deduction/
exclusion applied, bracket-by-bracket tax).

Mirrors narrative.py's/aggregation.py's pure/testable style: every value
below is either a direct PlanYearProjection sub-field read or arithmetic
over two already-computed checkpoints -- no new tax, mechanics, or
simulation computation (same FR-004/FR-014-shaped discipline
028-results-walkthrough already established). See
/home/jmuir/.claude/plans/the-detail-on-the-drifting-wave.md for the full
design and the checkpoint chain this relies on:

    year.starting_balances
      -> year.mechanics.withdrawal_plan.ending_balances   (post RMD + spending-need withdrawal)
      -> year.mechanics.ending_balances                    (post Roth conversion)
      -> year.tax_funding_withdrawal.ending_balances        (post the tax-bill withdrawal)
      -> year.ending_balances                               (post growth, final)
"""

from __future__ import annotations

from retirement_planner.comparison import PlanYearProjection
from retirement_planner.mechanics import AccountType, WithdrawalLineItem

from .models import (
    AccountTypeWaterfall,
    BalanceWaterfall,
    IncomeComposition,
    InheritedAccountDetail,
    TaxComputationDetail,
    YearComputationDetail,
)

_ACCOUNT_TYPES: tuple[AccountType, ...] = ("traditional", "roth", "taxable")

_STATE_EXCLUSION_LABELS: dict[str, str] = {
    "SC": "age-65 exclusion",
    "DE": "age-60 exclusion",
    "NC": "NC Bailey settlement exclusion",
    "FL": "no state income tax",
}
"""Reporting-layer-only human labels (year_detail.py's own concern, not
the tax module's) -- keyed off StateTaxResult.state. A state not in this
map (none exist today) falls back to a generic label rather than raising."""


def _sequence_amount(items: list[WithdrawalLineItem], account_type: AccountType) -> float:
    """This account type's own total across a WithdrawalPlan's
    sequence_withdrawals (0.0 if that type wasn't drawn on)."""
    return sum(item.amount for item in items if item.account_type == account_type)


def _waterfall_for_type(year: PlanYearProjection, account_type: AccountType) -> AccountTypeWaterfall:
    starting_balance = getattr(year.starting_balances, account_type)
    after_spending_withdrawal = getattr(year.mechanics.withdrawal_plan.ending_balances, account_type)
    after_conversion = getattr(year.mechanics.ending_balances, account_type)
    after_tax_withdrawal = getattr(year.tax_funding_withdrawal.ending_balances, account_type)
    ending_balance = getattr(year.ending_balances, account_type)

    rmd_drawn = year.mechanics.withdrawal_plan.rmd_drawn if account_type == "traditional" else 0.0
    spending_withdrawal = _sequence_amount(year.mechanics.withdrawal_plan.sequence_withdrawals, account_type)

    amount_converted = year.mechanics.conversion.amount_converted
    if account_type == "traditional":
        conversion_delta = -amount_converted
    elif account_type == "roth":
        conversion_delta = amount_converted
    else:
        conversion_delta = 0.0  # Roth conversions never touch the taxable account.

    tax_funding_withdrawal = _sequence_amount(year.tax_funding_withdrawal.sequence_withdrawals, account_type)

    growth = ending_balance - after_tax_withdrawal
    growth_rate_pct = (growth / after_tax_withdrawal * 100.0) if after_tax_withdrawal != 0.0 else None

    return AccountTypeWaterfall(
        account_type=account_type,
        starting_balance=starting_balance,
        rmd_drawn=rmd_drawn,
        spending_withdrawal=spending_withdrawal,
        after_spending_withdrawal=after_spending_withdrawal,
        conversion_delta=conversion_delta,
        after_conversion=after_conversion,
        tax_funding_withdrawal=tax_funding_withdrawal,
        after_tax_withdrawal=after_tax_withdrawal,
        growth=growth,
        growth_rate_pct=growth_rate_pct,
        ending_balance=ending_balance,
    )


def _build_balance_waterfall(year: PlanYearProjection) -> BalanceWaterfall:
    traditional = _waterfall_for_type(year, "traditional")
    roth = _waterfall_for_type(year, "roth")
    taxable = _waterfall_for_type(year, "taxable")
    # Matches comparison/projection.py's own tax_owed local exactly --
    # the amount tax_funding_withdrawal was sized to cover -- reconstructed
    # from six already-stored fields, never itself a stored field.
    total_tax_owed = (
        year.federal_tax.federal_tax_owed
        + year.state_tax.state_tax_owed
        + year.irmaa.surcharge_owed
        + year.niit.surtax_owed
        + year.early_withdrawal_penalty.penalty_owed
        + year.fica_tax.total_fica_tax
    )
    return BalanceWaterfall(
        traditional=traditional,
        roth=roth,
        taxable=taxable,
        total_starting_balance=traditional.starting_balance + roth.starting_balance + taxable.starting_balance,
        total_ending_balance=traditional.ending_balance + roth.ending_balance + taxable.ending_balance,
        total_tax_owed=total_tax_owed,
    )


def _build_income_composition(year: PlanYearProjection) -> IncomeComposition:
    traditional_sequence_withdrawal = _sequence_amount(year.mechanics.withdrawal_plan.sequence_withdrawals, "traditional")
    return IncomeComposition(
        rmd_drawn=year.mechanics.withdrawal_plan.rmd_drawn,
        traditional_sequence_withdrawal=traditional_sequence_withdrawal,
        inherited_distribution=year.mechanics.withdrawal_plan.inherited_distribution_drawn,
        income_streams=sum(year.member_income_stream_amounts.values()),
        roth_conversion_added=year.mechanics.conversion.ordinary_income_added,
        hsa_deduction=year.hsa_contribution.amount_contributed,
        ordinary_income_total=year.mechanics.ordinary_income,
        social_security_gross=sum(year.member_social_security_benefits.values()),
        taxable_social_security=year.federal_tax.taxable_social_security,
    )


def _build_federal_tax_detail(year: PlanYearProjection) -> TaxComputationDetail:
    return TaxComputationDetail(
        taxable_income=year.federal_tax.taxable_income,
        deduction_or_exclusion_label="standard deduction",
        deduction_or_exclusion_amount=year.federal_tax.standard_deduction_used,
        bracket_breakdown=year.federal_tax.bracket_breakdown,
        tax_owed=year.federal_tax.federal_tax_owed,
    )


def _build_state_tax_detail(year: PlanYearProjection) -> TaxComputationDetail:
    label = _STATE_EXCLUSION_LABELS.get(year.state_tax.state, "state exclusion")
    return TaxComputationDetail(
        taxable_income=year.state_tax.taxable_income,
        deduction_or_exclusion_label=label,
        deduction_or_exclusion_amount=year.state_tax.exclusion_applied,
        bracket_breakdown=year.state_tax.bracket_breakdown,
        tax_owed=year.state_tax.state_tax_owed,
    )


def _build_inherited_account_details(year: PlanYearProjection) -> list[InheritedAccountDetail]:
    """Naturally empty for a household with no inherited accounts --
    "present even when empty" convention, never omitted or None."""
    return [
        InheritedAccountDetail(
            account_id=account_id,
            distribution=year.inherited_account_distributions.get(account_id, 0.0),
            ending_balance=ending_balance,
        )
        for account_id, ending_balance in year.inherited_account_balances.items()
    ]


def build_year_computation_detail(year: PlanYearProjection) -> YearComputationDetail:
    """The one function this module exports (narrative.py's own
    build_year_stories() calls this once per plan year)."""
    return YearComputationDetail(
        balance_waterfall=_build_balance_waterfall(year),
        income_composition=_build_income_composition(year),
        federal_tax_detail=_build_federal_tax_detail(year),
        state_tax_detail=_build_state_tax_detail(year),
        inherited_accounts=_build_inherited_account_details(year),
    )
