"""Renders one plan year's YearComputationDetail (rp-bm8.3) -- the full
"how was this year's math computed" trace: the account-balance waterfall,
ordinary-income composition, and federal/state tax breakdown behind
narrative.py's own story text. Pure rendering over already-serialized JSON
(mirrors account_table.py's/verification.py's "computes no statistic of
its own" convention) -- every number here was already computed server-side
by retirement_planner.reporting.year_detail.build_year_computation_detail().
"""

from __future__ import annotations

import streamlit as st

from .formatting import format_currency

_ACCOUNT_TYPES = ("traditional", "roth", "taxable")
_ACCOUNT_LABELS = {"traditional": "Traditional", "roth": "Roth", "taxable": "Taxable"}
_WATERFALL_STEPS = (
    ("Starting balance", "starting_balance"),
    ("− RMD", "rmd_drawn"),
    ("− Withdrawal", "spending_withdrawal"),
    ("→ after RMD + withdrawal", "after_spending_withdrawal"),
    ("± Roth conversion", "conversion_delta"),
    ("→ after conversion", "after_conversion"),
    ("− Taxes paid", "tax_funding_withdrawal"),
    ("→ after taxes paid", "after_tax_withdrawal"),
    ("+ Growth", "growth"),
    ("= Ending balance", "ending_balance"),
)


def _render_balance_waterfall(waterfall: dict) -> None:
    st.markdown("**Account balance walk**")
    rows = [
        {"Step": label, **{_ACCOUNT_LABELS[account]: format_currency(waterfall[account][field]) for account in _ACCOUNT_TYPES}}
        for label, field in _WATERFALL_STEPS
    ]
    st.dataframe(rows, hide_index=True)
    st.caption(
        f"Household total: {format_currency(waterfall['total_starting_balance'])} → "
        f"{format_currency(waterfall['total_ending_balance'])} "
        f"(this year's total tax bill, paid via the withdrawal above: {format_currency(waterfall['total_tax_owed'])})"
    )


def _render_income_composition(composition: dict) -> None:
    st.markdown("**Ordinary income composition**")
    st.write(
        f"{format_currency(composition['rmd_drawn'])} RMD + "
        f"{format_currency(composition['traditional_sequence_withdrawal'])} other Traditional withdrawal + "
        f"{format_currency(composition['inherited_distribution'])} inherited distribution + "
        f"{format_currency(composition['income_streams'])} pensions/annuities/earned income + "
        f"{format_currency(composition['roth_conversion_added'])} Roth conversion − "
        f"{format_currency(composition['hsa_deduction'])} HSA deduction = "
        f"**{format_currency(composition['ordinary_income_total'])} ordinary income**"
    )
    if composition["earned_income"] > 0:
        st.caption(
            f"Of the pensions/annuities/earned income above, {format_currency(composition['earned_income'])} is "
            "earned income (wages) -- subject to FICA payroll tax, detailed below."
        )
    st.caption(
        f"Social Security received: {format_currency(composition['social_security_gross'])} gross, "
        f"{format_currency(composition['taxable_social_security'])} of it taxable -- added in separately at "
        "the federal tax step below, not part of ordinary income above."
    )


def _render_tax_detail(jurisdiction: str, detail: dict) -> None:
    st.markdown(f"**{jurisdiction} tax**")
    if not detail["bracket_breakdown"] and detail["taxable_income"] == 0 and detail["tax_owed"] == 0:
        st.caption(f"{detail['deduction_or_exclusion_label'].capitalize()} — $0 owed.")
        return
    st.write(
        f"Taxable income: {format_currency(detail['taxable_income'])} "
        f"(after a {format_currency(detail['deduction_or_exclusion_amount'])} {detail['deduction_or_exclusion_label']})"
    )
    for row in detail["bracket_breakdown"]:
        st.caption(f"{row['rate'] * 100:.2f}% on {format_currency(row['income_in_bracket'])} = {format_currency(row['tax_in_bracket'])}")
    st.write(f"**Total {jurisdiction.lower()} tax owed: {format_currency(detail['tax_owed'])}**")


_INHERITED_REASON_CAPTIONS = {
    "annual_rmd": "Annual required minimum distribution",
    "no_rmd_required_yet": "No distribution required yet",
    "ten_year_rule_deadline": "10-year rule deadline reached — entire balance distributed",
}


def _inherited_reason_caption(account: dict) -> str:
    reason = account["distribution_reason"]
    base = _INHERITED_REASON_CAPTIONS.get(reason, "No distribution this year")
    if reason == "annual_rmd" and account.get("rmd_divisor"):
        base += f" (divisor {account['rmd_divisor']:.1f})"
    deadline_year = account.get("depletion_deadline_year")
    if deadline_year is not None and reason != "ten_year_rule_deadline":
        base += f" — must be fully distributed by the end of {deadline_year}"
    return base


def _render_inherited_accounts(accounts: list[dict]) -> None:
    st.markdown("**Inherited accounts**")
    rows = [
        {
            "Account": account["account_id"],
            "Distribution": format_currency(account["distribution"]),
            "Ending balance": format_currency(account["ending_balance"]),
            "Why": _inherited_reason_caption(account),
        }
        for account in accounts
    ]
    st.dataframe(rows, hide_index=True)


def _render_fica_detail(detail: dict) -> None:
    st.markdown("**FICA payroll tax**")
    if detail["total_fica_tax"] == 0:
        st.caption("No FICA payroll tax this year (no earned income subject to it).")
        return
    for person_name in detail["member_oasdi_tax"]:
        oasdi = detail["member_oasdi_tax"][person_name]
        medicare = detail["member_medicare_tax"].get(person_name, 0.0)
        if oasdi == 0 and medicare == 0:
            continue
        st.caption(
            f"{person_name}: {format_currency(oasdi)} Social Security (OASDI, 6.2%) + "
            f"{format_currency(medicare)} Medicare (1.45%)"
        )
    if detail["additional_medicare_tax"] > 0:
        st.caption(f"Additional Medicare Tax (0.9% over the household threshold): {format_currency(detail['additional_medicare_tax'])}")
    st.write(f"**Total FICA payroll tax owed: {format_currency(detail['total_fica_tax'])}**")


def render_year_computation_detail(detail: dict) -> None:
    """detail: one YearStory["detail"] entry (already to_jsonable()-shaped)
    from POST /simulations's narrative field."""
    _render_balance_waterfall(detail["balance_waterfall"])
    _render_income_composition(detail["income_composition"])
    if detail["inherited_accounts"]:
        _render_inherited_accounts(detail["inherited_accounts"])
    _render_fica_detail(detail["fica_tax_detail"])
    _render_tax_detail("Federal", detail["federal_tax_detail"])
    _render_tax_detail("State", detail["state_tax_detail"])
