"""Unit tests for src/rp_ui/narration.py (rp-r07).

narrate_metrics() is pure (formatting.py's own pattern) and tested
directly; render_results_explanation() calls st.expander/st.markdown, so
it needs a running Streamlit script context, driven here via
AppTest.from_string() -- verification.py's own precedent
(test_verification.py).
"""

from streamlit.testing.v1 import AppTest

from rp_ui.narration import narrate_metrics

_MONTE_CARLO_SUMMARY = {
    "candidate_label": "base_case",
    "success_rate": 0.82,
    "ending_balance": 1_250_000.0,
    "percentile_bands": [{"plan_year": 1, "percentiles": {"0.5": 1_000_000.0}}],
    "median_depletion_age": None,
    "median_lifetime_tax_paid": 250_000.0,
    "median_lifetime_irmaa_paid": 4_600.0,
    "median_lifetime_niit_paid": 0.0,
    "median_lifetime_early_withdrawal_penalty_paid": 0.0,
    "median_lifetime_fica_tax_paid": 0.0,
    "unverified_figure_names": [],
}

_MONTE_CARLO_SUMMARY_WITH_DEPLETION = {**_MONTE_CARLO_SUMMARY, "success_rate": 0.4, "median_depletion_age": 84.0}

_DETERMINISTIC_SUMMARY = {
    "candidate_label": "no_conversion",
    "success_rate": None,
    "ending_balance": 900_000.0,
    "percentile_bands": None,
    "median_depletion_age": None,
    "median_lifetime_tax_paid": 300_000.0,
    "median_lifetime_irmaa_paid": 0.0,
    "median_lifetime_niit_paid": 1_200.0,
    "median_lifetime_early_withdrawal_penalty_paid": 800.0,
    "median_lifetime_fica_tax_paid": 3_060.0,
    "unverified_figure_names": [],
}


# --- narrate_metrics() (pure) ---


def test_monte_carlo_success_rate_reads_n_of_m_when_path_count_given():
    entries = narrate_metrics(_MONTE_CARLO_SUMMARY, path_count=200)
    success = next(e for e in entries if e["label"] == "Success rate")
    assert "82.0%" in success["value"]
    assert "164 of 200 simulated paths" in success["value"]


def test_monte_carlo_success_rate_falls_back_to_percentage_only_without_path_count():
    entries = narrate_metrics(_MONTE_CARLO_SUMMARY, path_count=None)
    success = next(e for e in entries if e["label"] == "Success rate")
    assert "82.0%" in success["value"]
    assert "of simulated paths" in success["value"]
    assert "of 200" not in success["value"]  # never fabricates a count


def test_monte_carlo_summary_never_shows_a_bare_deterministic_ending_balance_label():
    entries = narrate_metrics(_MONTE_CARLO_SUMMARY)
    labels = [e["label"] for e in entries]
    assert "Ending balance (median)" in labels
    assert "Ending balance" not in labels  # the deterministic-only label


def test_deterministic_summary_has_no_success_rate_or_percentile_entries():
    entries = narrate_metrics(_DETERMINISTIC_SUMMARY)
    labels = [e["label"] for e in entries]
    assert "Success rate" not in labels
    assert "Percentile bands (chart above)" not in labels
    assert "Ending balance" in labels


def test_deterministic_ending_balance_value_matches_currency_format():
    entries = narrate_metrics(_DETERMINISTIC_SUMMARY)
    ending_balance = next(e for e in entries if e["label"] == "Ending balance")
    assert ending_balance["value"] == "$900,000.00"


def test_median_depletion_age_omitted_when_none():
    entries = narrate_metrics(_MONTE_CARLO_SUMMARY)  # median_depletion_age is None
    labels = [e["label"] for e in entries]
    assert "Median depletion age" not in labels


def test_median_depletion_age_shown_when_present_for_monte_carlo():
    entries = narrate_metrics(_MONTE_CARLO_SUMMARY_WITH_DEPLETION)
    depletion = next(e for e in entries if e["label"] == "Median depletion age")
    assert depletion["value"] == "84"


def test_tax_irmaa_niit_entries_always_present_and_currency_formatted():
    entries = narrate_metrics(_DETERMINISTIC_SUMMARY)
    by_label = {e["label"]: e for e in entries}
    assert by_label["Lifetime tax paid"]["value"] == "$300,000.00"
    assert by_label["Lifetime Medicare IRMAA surcharge"]["value"] == "$0.00"
    assert by_label["Lifetime Net Investment Income Tax"]["value"] == "$1,200.00"
    assert by_label["Lifetime early-withdrawal penalty paid"]["value"] == "$800.00"  # 020-early-withdrawal-penalty
    assert by_label["Lifetime FICA payroll tax paid"]["value"] == "$3,060.00"  # 022-fica-payroll-tax


# --- render_results_explanation() (Streamlit rendering) ---

_SCRIPT = """
import streamlit as st
from rp_ui.narration import render_results_explanation
render_results_explanation({summary!r}, path_count={path_count!r}, title={title!r})
"""


def test_render_results_explanation_renders_an_expander_with_every_entry():
    at = AppTest.from_string(
        _SCRIPT.format(summary=_MONTE_CARLO_SUMMARY, path_count=200, title=None)
    ).run()
    assert not at.exception
    assert len(at.expander) == 1
    assert at.expander[0].label == "How were these numbers computed?"
    markdown_text = " ".join(m.value for m in at.expander[0].markdown)
    assert "Success rate" in markdown_text
    assert "164 of 200 simulated paths" in markdown_text


def test_render_results_explanation_title_distinguishes_candidates():
    at = AppTest.from_string(
        _SCRIPT.format(summary=_DETERMINISTIC_SUMMARY, path_count=None, title="no_conversion")
    ).run()
    assert not at.exception
    assert "no_conversion" in at.expander[0].label
