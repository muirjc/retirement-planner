"""Unit tests for apps/streamlit_ui/pages/4_Walkthrough.py (028-results-
walkthrough, rp-bm8.1). Driven via AppTest.from_file() with a pre-seeded
st.session_state["run_last_result"] -- this page makes no HTTP call of its
own (FR-008), so no httpx mock is needed, unlike 2_Run_Simulation.py/
3_Compare.py's own integration tests.
"""

from pathlib import Path

from streamlit.testing.v1 import AppTest

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
WALKTHROUGH_PAGE = PACKAGE_ROOT / "pages" / "4_Walkthrough.py"


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
        "inherited_accounts": [],
    }


def _story(plan_year: int, tax_year: int, unverified_figure_names: list[str] | None = None) -> dict:
    return {
        "plan_year": plan_year,
        "tax_year": tax_year,
        "member_ages": {"you": 69 + plan_year},
        "detail": _detail(),
        "entries": [
            {
                "driver_key": "baseline",
                "label": "No notable change",
                "explanation": "No notable change from the prior year.",
                "amounts": {},
            }
        ],
        "unverified_figure_names": unverified_figure_names or [],
    }


def _run_last_result(n_years: int, unverified_by_plan_year: dict[int, list[str]] | None = None) -> dict:
    unverified_by_plan_year = unverified_by_plan_year or {}
    stories = [_story(year, 2025 + year, unverified_by_plan_year.get(year)) for year in range(1, n_years + 1)]
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
    assert len(at.subheader) == 3
    assert [s.value for s in at.subheader] == [
        "Plan year 1 -- tax year 2026",
        "Plan year 2 -- tax year 2027",
        "Plan year 3 -- tax year 2028",
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
    assert len(at.subheader) == 2
    assert [s.value for s in at.subheader] == [
        "Plan year 4 -- tax year 2029",
        "Plan year 5 -- tax year 2030",
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
    assert len(at.expander) == 1
    assert at.expander[0].label == "How was this year's math computed?"
    assert len(at.dataframe) == 1  # the balance-waterfall table
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
