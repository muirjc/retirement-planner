"""Per-account year-by-year detail table (015-per-account-projection-detail,
FR-001-FR-006). Takes 007's own account_detail response data (a list of
PlanYearAccountDetail, already to_jsonable()-shaped) -- this function
computes no statistic of its own, mirroring charts.py's "pure display
step" convention.

The `attribution` column reuses verification.py's own disclosure idiom
(never let a viewer mistake an apportioned figure for an independently
observed one, constitution Principle I) adapted to a per-row table cell
rather than a page-level banner -- every row is labeled plainly, never
silently uniform.
"""

from __future__ import annotations

import streamlit as st

from .formatting import format_currency

_ATTRIBUTION_LABELS = {
    "independently_tracked": "tracked exactly",
    "fixed_share_of_pooled_total": "apportioned (est.)",
}


def render_account_table(account_detail: list[dict]) -> None:
    """account_detail: 015's own PlanYearAccountDetail list (contracts/
    bff-api.md). Renders one row per (plan_year, account_id), plus each
    member's own Social Security benefit that year -- present even when
    zero, matching 006's "present even when empty" convention rather than
    omitting a pre-claiming member's row."""
    if not account_detail:
        st.info("No per-account detail available for this result.")
        return

    rows = []
    for year in account_detail:
        for account in year["accounts"]:
            rows.append(
                {
                    "plan_year": year["plan_year"],
                    "tax_year": year["tax_year"],
                    "account_id": account["account_id"],
                    "account_type": account["account_type"],
                    "owner": account["owner"],
                    "starting_balance": format_currency(account["starting_balance"]),
                    "ending_balance": format_currency(account["ending_balance"]),
                    "rmd_amount": format_currency(account["rmd_amount"]),
                    "withdrawal_amount": format_currency(account["withdrawal_amount"]),
                    "figure_basis": _ATTRIBUTION_LABELS.get(account["attribution"], account["attribution"]),
                }
            )
        for member, benefit in year["member_social_security_benefits"].items():
            rows.append(
                {
                    "plan_year": year["plan_year"],
                    "tax_year": year["tax_year"],
                    "account_id": f"— {member}'s Social Security",
                    "account_type": "",
                    "owner": member,
                    "starting_balance": "",
                    "ending_balance": "",
                    "rmd_amount": "",
                    "withdrawal_amount": format_currency(benefit),
                    "figure_basis": "tracked exactly",
                }
            )

    st.caption(
        "\"apportioned (est.)\" figures are a fixed share of a combined "
        "account-type total, not independently observed for that specific "
        "account -- see docs/BRD.md for how this is computed. A Roth "
        "conversion's destination account, in particular, may not always "
        "line up with which household member actually converted, when a "
        "household's Roth accounts aren't owned member-for-member the "
        "same way its converting traditional accounts are."
    )
    st.dataframe(rows)
