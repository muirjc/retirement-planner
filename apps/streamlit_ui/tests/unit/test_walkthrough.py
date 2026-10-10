"""Unit tests for apps/streamlit_ui/pages/4_Walkthrough.py (028-results-
walkthrough, rp-bm8.1). Driven via AppTest.from_file() with a pre-seeded
st.session_state["run_last_result"] -- the per-year display tests below
make no HTTP call of their own (FR-008), so no httpx mock is needed for
them, unlike 2_Run_Simulation.py/3_Compare.py's own integration tests.

rp-4p3 adds one HTTP call to this page (the AI Q&A widget's POST
/walkthrough/ask) -- the tests covering it, at the bottom of this file,
install an httpx.MockTransport on rp_ui.api_client first, mirroring
apps/streamlit_ui/tests/integration/test_app_pages.py's own pattern.
"""

import json
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from rp_ui import api_client

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
WALKTHROUGH_PAGE = PACKAGE_ROOT / "pages" / "4_Walkthrough.py"


@pytest.fixture(autouse=True)
def _reset_transport():
    yield
    api_client._transport = None


def _install(handler) -> None:
    api_client._transport = httpx.MockTransport(handler)


def _year_detail(plan_year: int, tax_year: int) -> dict:
    return {
        "plan_year": plan_year,
        "tax_year": tax_year,
        "ending_balances": {"traditional": 100_000.0, "roth": 0.0, "taxable": 0.0},
        "federal_tax": {"federal_tax_owed": 100.0},
        "state_tax": {"state_tax_owed": 50.0},
        "shortfall": 0.0,
    }


def _account_waterfall(starting: float, ending: float) -> dict:
    """A trivially reconciling single-step waterfall (no RMD/withdrawal/
    conversion/tax activity) -- rp-bm8.3's own field-shape, real values
    aren't the point of these page-rendering tests."""
    growth = ending - starting
    return {
        "account_type": "traditional",
        "starting_balance": starting,
        "rmd_drawn": 0.0,
        "spending_withdrawal": 0.0,
        "after_spending_withdrawal": starting,
        "conversion_delta": 0.0,
        "after_conversion": starting,
        "tax_funding_withdrawal": 0.0,
        "after_tax_withdrawal": starting,
        "growth": growth,
        "growth_rate_pct": (growth / starting * 100.0) if starting else None,
        "ending_balance": ending,
    }


def _detail() -> dict:
    """rp-bm8.3: a minimal but internally-consistent YearComputationDetail
    fixture."""
    return {
        "balance_waterfall": {
            "traditional": _account_waterfall(100_000.0, 105_000.0),
            "roth": _account_waterfall(0.0, 0.0),
            "taxable": _account_waterfall(0.0, 0.0),
            "total_starting_balance": 100_000.0,
            "total_ending_balance": 105_000.0,
            "total_tax_owed": 100.0,
        },
        "income_composition": {
            "rmd_drawn": 0.0,
            "traditional_sequence_withdrawal": 0.0,
            "inherited_distribution": 0.0,
            "income_streams": 0.0,
            "earned_income": 0.0,
            "roth_conversion_added": 0.0,
            "hsa_deduction": 0.0,
            "ordinary_income_total": 0.0,
            "social_security_gross": 0.0,
            "taxable_social_security": 0.0,
        },
        "federal_tax_detail": {
            "taxable_income": 0.0,
            "deduction_or_exclusion_label": "standard deduction",
            "deduction_or_exclusion_amount": 32_200.0,
            "bracket_breakdown": [],
            "tax_owed": 100.0,
        },
        "state_tax_detail": {
            "taxable_income": 0.0,
            "deduction_or_exclusion_label": "no state income tax",
            "deduction_or_exclusion_amount": 0.0,
            "bracket_breakdown": [],
            "tax_owed": 0.0,  # FL-shaped: no state income tax at all
        },
        "fica_tax_detail": {
            "member_oasdi_tax": {},
            "member_medicare_tax": {},
            "additional_medicare_tax": 0.0,
            "total_fica_tax": 0.0,
        },
        "inherited_accounts": [],
    }


def _story(
    plan_year: int,
    tax_year: int,
    unverified_figure_names: list[str] | None = None,
    detail_overrides: dict | None = None,
    account_breakdown: list[dict] | None = None,
) -> dict:
    detail = _detail()
    if detail_overrides:
        detail.update(detail_overrides)
    return {
        "plan_year": plan_year,
        "tax_year": tax_year,
        "member_ages": {"you": 69 + plan_year},
        "detail": detail,
        "entries": [
            {
                "driver_key": "baseline",
                "label": "No notable change",
                "explanation": "No notable change from the prior year.",
                "amounts": {},
            }
        ],
        "unverified_figure_names": unverified_figure_names or [],
        "account_breakdown": account_breakdown
        if account_breakdown is not None
        else [
            {
                "account_id": "traditional-0", "account_type": "traditional", "owner": "you",
                "starting_balance": 100_000.0, "ending_balance": 95_000.0,
                "rmd_amount": 5_000.0, "withdrawal_amount": 5_000.0,
                "attribution": "independently_tracked",
            }
        ],
    }


def _run_last_result(
    n_years: int,
    unverified_by_plan_year: dict[int, list[str]] | None = None,
    detail_overrides: dict | None = None,
) -> dict:
    unverified_by_plan_year = unverified_by_plan_year or {}
    stories = [_story(year, 2025 + year, unverified_by_plan_year.get(year), detail_overrides) for year in range(1, n_years + 1)]
    path_years = [_year_detail(year, 2025 + year) for year in range(1, n_years + 1)]
    return {
        "run": {"path_results": [{"years": path_years}]},
        "narrative": {"selected_path_index": 0, "years": stories},
    }


def test_no_run_yet_shows_guidance_instead_of_erroring():
    """FR-013: no run_last_result in session_state -> guidance, not a
    blank page or exception."""
    at = AppTest.from_file(str(WALKTHROUGH_PAGE)).run()
    assert not at.exception
    assert any("run a simulation" in info.value.lower() for info in at.info)


def test_first_batch_shows_up_to_three_years_with_previous_disabled():
    """FR-009/FR-010, spec.md Clarifications: batches of 3 plan years;
    Previous unavailable on the first batch."""
    at = AppTest.from_file(str(WALKTHROUGH_PAGE))
    at.session_state["run_last_result"] = _run_last_result(5)
    at.run()

    assert not at.exception
    assert len(at.subheader) == 4  # 3 plan years + the "Ask about these years" Q&A section (rp-4p3)
    assert [s.value for s in at.subheader] == [
        "Plan year 1 -- tax year 2026",
        "Plan year 2 -- tax year 2027",
        "Plan year 3 -- tax year 2028",
        "Ask about these years",
    ]
    assert at.button(key="walkthrough_prev").disabled is True
    assert at.button(key="walkthrough_next").disabled is False


def test_next_advances_to_the_remainder_batch_and_disables_next():
    """FR-009/FR-010: a 5-year projection's second batch shows the
    remaining 2 years, and Next is unavailable there (the last batch)."""
    at = AppTest.from_file(str(WALKTHROUGH_PAGE))
    at.session_state["run_last_result"] = _run_last_result(5)
    at.run()

    at.button(key="walkthrough_next").click().run()

    assert not at.exception
    assert len(at.subheader) == 3  # 2 plan years + the "Ask about these years" Q&A section (rp-4p3)
    assert [s.value for s in at.subheader] == [
        "Plan year 4 -- tax year 2029",
        "Plan year 5 -- tax year 2030",
        "Ask about these years",
    ]
    assert at.button(key="walkthrough_next").disabled is True
    assert at.button(key="walkthrough_prev").disabled is False


def test_previous_returns_to_the_first_batch():
    at = AppTest.from_file(str(WALKTHROUGH_PAGE))
    at.session_state["run_last_result"] = _run_last_result(5)
    at.run()
    at.button(key="walkthrough_next").click().run()

    at.button(key="walkthrough_prev").click().run()

    assert not at.exception
    assert [s.value for s in at.subheader] == [
        "Plan year 1 -- tax year 2026",
        "Plan year 2 -- tax year 2027",
        "Plan year 3 -- tax year 2028",
        "Ask about these years",
    ]


def test_verification_indicator_scoped_per_shown_year():
    """US3/FR-011: a year whose unverified_figure_names is nonempty shows
    the warning naming it; a year with none shows the positive
    confirmation -- same as render_verification_indicator() everywhere
    else, just scoped per shown year rather than once for the whole page."""
    at = AppTest.from_file(str(WALKTHROUGH_PAGE))
    at.session_state["run_last_result"] = _run_last_result(3, unverified_by_plan_year={2: ["nc_bailey_exclusion"]})
    at.run()

    assert not at.exception
    assert len(at.warning) == 1
    assert "nc_bailey_exclusion" in at.warning[0].value
    assert len(at.success) == 2  # plan years 1 and 3, both fully verified


def test_computation_detail_expander_renders_the_balance_waterfall_and_tax_breakdown():
    """rp-bm8.3: each shown year gets a 'How was this year's math
    computed?' expander with the balance waterfall table and the federal/
    state tax breakdown."""
    at = AppTest.from_file(str(WALKTHROUGH_PAGE))
    at.session_state["run_last_result"] = _run_last_result(1)
    at.run()

    assert not at.exception
    assert len(at.expander) == 3  # computation-detail + account-breakdown-by-member (rp-kmu) + the Q&A "About this AI assistant" one (rp-4p3)
    assert at.expander[0].label == "How was this year's math computed?"
    assert len(at.dataframe) == 2  # the balance-waterfall table + one account-breakdown table (owner "you")
    markdown_text = " ".join(m.value for m in at.markdown)
    assert "Account balance walk" in markdown_text
    assert "Ordinary income composition" in markdown_text
    assert "Federal tax" in markdown_text
    assert "State tax" in markdown_text


def test_computation_detail_expander_shows_no_state_income_tax_when_bracket_breakdown_is_empty():
    at = AppTest.from_file(str(WALKTHROUGH_PAGE))
    at.session_state["run_last_result"] = _run_last_result(1)
    at.run()

    assert not at.exception
    caption_text = " ".join(c.value for c in at.caption)
    assert "No state income tax" in caption_text


def test_inherited_account_ten_year_rule_deadline_shows_the_reason():
    """rp-bm8.4: an inherited account force-distributed by the 10-year
    rule renders both the account itself and why its distribution is the
    full balance."""
    at = AppTest.from_file(str(WALKTHROUGH_PAGE))
    at.session_state["run_last_result"] = _run_last_result(
        1,
        detail_overrides={
            "inherited_accounts": [
                {
                    "account_id": "traditional-6",
                    "distribution": 513_000.0,
                    "ending_balance": 0.0,
                    "distribution_reason": "ten_year_rule_deadline",
                    "rmd_divisor": None,
                    "depletion_deadline_year": 2015,
                }
            ]
        },
    )
    at.run()

    assert not at.exception
    markdown_text = " ".join(m.value for m in at.markdown)
    assert "Inherited accounts" in markdown_text
    assert len(at.dataframe) == 3  # balance waterfall + inherited accounts + one account-breakdown table (owner "you")
    rows = at.dataframe[1].value
    assert rows.iloc[0]["Account"] == "traditional-6"
    assert "10-year rule" in rows.iloc[0]["Why"]


def test_fica_section_shows_per_member_and_total_when_present():
    """rp-bm8.4: earned income subject to FICA gets its own explained
    section, separate from federal/state income tax."""
    at = AppTest.from_file(str(WALKTHROUGH_PAGE))
    at.session_state["run_last_result"] = _run_last_result(
        1,
        detail_overrides={
            "income_composition": {
                "rmd_drawn": 0.0,
                "traditional_sequence_withdrawal": 0.0,
                "inherited_distribution": 0.0,
                "income_streams": 90_000.0,
                "earned_income": 90_000.0,
                "roth_conversion_added": 0.0,
                "hsa_deduction": 0.0,
                "ordinary_income_total": 90_000.0,
                "social_security_gross": 0.0,
                "taxable_social_security": 0.0,
            },
            "fica_tax_detail": {
                "member_oasdi_tax": {"you": 5_580.0},
                "member_medicare_tax": {"you": 1_305.0},
                "additional_medicare_tax": 0.0,
                "total_fica_tax": 6_885.0,
            },
        },
    )
    at.run()

    assert not at.exception
    markdown_text = " ".join(m.value for m in at.markdown)
    assert "FICA payroll tax" in markdown_text
    caption_text = " ".join(c.value for c in at.caption)
    assert "earned income" in caption_text.lower()
    assert "$5,580.00" in caption_text
    assert "$1,305.00" in caption_text
    assert "$6,885.00" in markdown_text


def test_fica_section_shows_placeholder_when_no_earned_income():
    at = AppTest.from_file(str(WALKTHROUGH_PAGE))
    at.session_state["run_last_result"] = _run_last_result(1)  # default fixture: 0 FICA
    at.run()

    assert not at.exception
    caption_text = " ".join(c.value for c in at.caption)
    assert "No FICA payroll tax" in caption_text


# -- AI Q&A widget (rp-4p3) ---------------------------------------------------


def test_asking_a_question_sends_the_current_batchs_own_stories_and_renders_the_answer():
    captured = {}

    def handler(request):
        assert request.url.path == "/api/v1/walkthrough/ask"
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"answer": "Yes, that figure is verified."})

    _install(handler)
    at = AppTest.from_file(str(WALKTHROUGH_PAGE))
    at.session_state["run_last_result"] = _run_last_result(5)
    at.run()

    at.text_input(key="walkthrough_question_0").set_value("Is the RMD figure verified?")
    at.button(key="walkthrough_ask_0").click().run()

    assert not at.exception
    assert captured["body"]["question"] == "Is the RMD figure verified?"
    # Scoped to the current (first) batch's own 3 stories, not all 5 years.
    assert [story["plan_year"] for story in captured["body"]["plan_years"]] == [1, 2, 3]
    markdown_text = " ".join(m.value for m in at.markdown)
    assert "Yes, that figure is verified." in markdown_text
    caption_text = " ".join(c.value for c in at.caption)
    assert "not authoritative" in caption_text.lower()


def test_asking_nothing_does_not_call_the_backend():
    def handler(request):
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    _install(handler)
    at = AppTest.from_file(str(WALKTHROUGH_PAGE))
    at.session_state["run_last_result"] = _run_last_result(1)
    at.run()

    at.button(key="walkthrough_ask_0").click().run()

    assert not at.exception


def test_asking_a_question_when_ollama_is_unavailable_shows_the_error():
    def handler(request):
        return httpx.Response(
            503,
            json={"error": "ollama_unavailable", "message": "Local AI model unavailable -- is Ollama running with a model pulled?"},
        )

    _install(handler)
    at = AppTest.from_file(str(WALKTHROUGH_PAGE))
    at.session_state["run_last_result"] = _run_last_result(1)
    at.run()

    at.text_input(key="walkthrough_question_0").set_value("anything")
    at.button(key="walkthrough_ask_0").click().run()

    assert not at.exception
    assert any("ollama" in e.value.lower() for e in at.error)


def test_about_this_ai_assistant_disclosure_is_present():
    at = AppTest.from_file(str(WALKTHROUGH_PAGE))
    at.session_state["run_last_result"] = _run_last_result(1)
    at.run()

    assert any(e.label == "About this AI assistant" for e in at.expander)


# --- Account breakdown by household member (rp-kmu) ---


def test_account_breakdown_expander_present_per_shown_year():
    at = AppTest.from_file(str(WALKTHROUGH_PAGE))
    at.session_state["run_last_result"] = _run_last_result(2)
    at.run()

    assert not at.exception
    breakdown_expanders = [e for e in at.expander if e.label == "Where withdrawals came from, by household member"]
    assert len(breakdown_expanders) == 2  # one per shown plan year


def test_account_breakdown_groups_rows_by_member_and_shows_each_owner():
    story = _story(
        1,
        2026,
        account_breakdown=[
            {
                "account_id": "traditional-0", "account_type": "traditional", "owner": "you",
                "starting_balance": 500_000.0, "ending_balance": 480_000.0,
                "rmd_amount": 20_000.0, "withdrawal_amount": 20_000.0,
                "attribution": "independently_tracked",
            },
            {
                "account_id": "taxable-1", "account_type": "taxable", "owner": "spouse",
                "starting_balance": 100_000.0, "ending_balance": 90_000.0,
                "rmd_amount": 0.0, "withdrawal_amount": 10_000.0,
                "attribution": "fixed_share_of_pooled_total",
            },
        ],
    )
    at = AppTest.from_file(str(WALKTHROUGH_PAGE))
    at.session_state["run_last_result"] = {
        "run": {"path_results": [{"years": [_year_detail(1, 2026)]}]},
        "narrative": {"selected_path_index": 0, "years": [story]},
    }
    at.run()

    assert not at.exception
    markdown_text = " ".join(m.value for m in at.markdown)
    assert "you" in markdown_text and "$20,000.00" in markdown_text
    assert "spouse" in markdown_text and "$10,000.00" in markdown_text
    assert len(at.dataframe) == 3  # the balance-waterfall table + one account-breakdown table per owner (2)


def test_account_breakdown_shows_explicit_message_when_empty():
    at = AppTest.from_file(str(WALKTHROUGH_PAGE))
    at.session_state["run_last_result"] = {
        "run": {"path_results": [{"years": [_year_detail(1, 2026)]}]},
        "narrative": {"selected_path_index": 0, "years": [_story(1, 2026, account_breakdown=[])]},
    }
    at.run()

    assert not at.exception
    assert any("No per-account breakdown available" in i.value for i in at.info)
