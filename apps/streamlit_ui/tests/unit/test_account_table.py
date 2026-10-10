"""Unit tests for src/rp_ui/account_table.py (015-per-account-projection-detail).

render_account_table() calls st.dataframe/st.caption/st.info directly, so
it needs a running Streamlit script context -- driven via
AppTest.from_string(), mirroring test_verification.py's own pattern.
"""

from streamlit.testing.v1 import AppTest

_SCRIPT = """
import streamlit as st
from rp_ui.account_table import render_account_table
render_account_table({account_detail!r})
"""

_ACCOUNT_DETAIL = [
    {
        "plan_year": 1,
        "tax_year": 2026,
        "accounts": [
            {
                "account_id": "traditional-0", "account_type": "traditional", "owner": "you",
                "starting_balance": 1_200_000.0, "ending_balance": 1_150_000.0,
                "rmd_amount": 50_000.0, "withdrawal_amount": 50_000.0,
                "attribution": "independently_tracked",
            },
            {
                "account_id": "traditional-6", "account_type": "traditional", "owner": "spouse",
                "starting_balance": 250_000.0, "ending_balance": 230_000.0,
                "rmd_amount": 20_000.0, "withdrawal_amount": 20_000.0,
                "attribution": "independently_tracked",
            },
        ],
        "member_social_security_benefits": {"you": 32_000.0, "spouse": 0.0},
    },
]


def test_renders_one_row_per_account_plus_one_per_member_social_security():
    at = AppTest.from_string(_SCRIPT.format(account_detail=_ACCOUNT_DETAIL)).run()

    assert not at.exception
    assert len(at.dataframe) == 1
    rows = at.dataframe[0].value
    # 2 accounts + 2 household members' own SS rows for the one plan year.
    assert len(rows) == 4


def test_caption_discloses_what_apportioned_means():
    at = AppTest.from_string(_SCRIPT.format(account_detail=_ACCOUNT_DETAIL)).run()

    assert not at.exception
    assert len(at.caption) == 1
    assert "apportioned" in at.caption[0].value.lower()


def test_empty_account_detail_shows_an_explicit_message_not_a_blank_table():
    at = AppTest.from_string(_SCRIPT.format(account_detail=[])).run()

    assert not at.exception
    assert len(at.info) == 1
    assert len(at.dataframe) == 0


def test_attribution_labels_are_human_readable_not_the_raw_enum_value():
    at = AppTest.from_string(_SCRIPT.format(account_detail=_ACCOUNT_DETAIL)).run()

    rows = at.dataframe[0].value
    figure_basis_values = set(rows["figure_basis"]) if hasattr(rows, "__getitem__") else {r["figure_basis"] for r in rows}
    assert "independently_tracked" not in figure_basis_values
    assert any("tracked exactly" in v for v in figure_basis_values)


# --- render_account_breakdown_by_member() (rp-kmu) ---

_BREAKDOWN_SCRIPT = """
import streamlit as st
from rp_ui.account_table import render_account_breakdown_by_member
render_account_breakdown_by_member({account_breakdown!r}, {member_order!r})
"""

_ONE_YEAR_BREAKDOWN = [
    {
        "account_id": "traditional-0", "account_type": "traditional", "owner": "you",
        "starting_balance": 1_200_000.0, "ending_balance": 1_150_000.0,
        "rmd_amount": 50_000.0, "withdrawal_amount": 50_000.0,
        "attribution": "independently_tracked",
    },
    {
        "account_id": "roth-1", "account_type": "roth", "owner": "you",
        "starting_balance": 400_000.0, "ending_balance": 410_000.0,
        "rmd_amount": 0.0, "withdrawal_amount": 0.0,
        "attribution": "fixed_share_of_pooled_total",
    },
    {
        "account_id": "taxable-2", "account_type": "taxable", "owner": "spouse",
        "starting_balance": 200_000.0, "ending_balance": 180_000.0,
        "rmd_amount": 0.0, "withdrawal_amount": 20_000.0,
        "attribution": "fixed_share_of_pooled_total",
    },
]


def test_breakdown_groups_rows_by_owner_one_table_per_member():
    at = AppTest.from_string(_BREAKDOWN_SCRIPT.format(account_breakdown=_ONE_YEAR_BREAKDOWN, member_order=["you", "spouse"])).run()

    assert not at.exception
    assert len(at.dataframe) == 2  # "you" has 2 accounts, "spouse" has 1 -- one table per owner
    assert len(at.dataframe[0].value) == 2
    assert len(at.dataframe[1].value) == 1


def test_breakdown_shows_total_withdrawn_per_member():
    at = AppTest.from_string(_BREAKDOWN_SCRIPT.format(account_breakdown=_ONE_YEAR_BREAKDOWN, member_order=["you", "spouse"])).run()

    markdown_text = " ".join(m.value for m in at.markdown)
    assert "you" in markdown_text and "$50,000.00" in markdown_text  # you: 50k + 0
    assert "spouse" in markdown_text and "$20,000.00" in markdown_text


def test_breakdown_respects_member_order():
    at = AppTest.from_string(_BREAKDOWN_SCRIPT.format(account_breakdown=_ONE_YEAR_BREAKDOWN, member_order=["spouse", "you"])).run()

    markdown_text = [m.value for m in at.markdown]
    owners_in_order = [line.split("**")[1] for line in markdown_text if line.startswith("**")]
    assert owners_in_order == ["spouse", "you"]


def test_breakdown_empty_shows_an_explicit_message_not_a_blank_section():
    at = AppTest.from_string(_BREAKDOWN_SCRIPT.format(account_breakdown=[], member_order=["you", "spouse"])).run()

    assert not at.exception
    assert len(at.info) == 1
    assert len(at.dataframe) == 0
