"""Unit tests for src/rp_ui/verification.py -- T026.

render_verification_indicator() calls st.success/st.warning, so it needs
a running Streamlit script context -- driven here via AppTest.from_string()
rather than called directly, per Acceptance Scenarios US4.1-US4.2.
"""

from streamlit.testing.v1 import AppTest

_SCRIPT = """
import streamlit as st
from rp_ui.verification import render_verification_indicator
render_verification_indicator({figures!r})
"""


def test_empty_list_renders_positive_confirmation():
    """Acceptance Scenario US4.2: a fully-verified result shows an
    explicit positive confirmation, not just the absence of a warning."""
    at = AppTest.from_string(_SCRIPT.format(figures=[])).run()
    assert not at.exception
    assert len(at.success) == 1
    assert "verified" in at.success[0].value.lower()
    assert len(at.warning) == 0


def test_nonempty_list_names_each_unverified_figure():
    """Acceptance Scenario US4.1: every unverified figure name is shown,
    not just a generic "some figures unverified" notice."""
    at = AppTest.from_string(_SCRIPT.format(figures=["historical_bootstrap_returns", "stress_scenario_2008"])).run()
    assert not at.exception
    assert len(at.warning) == 1
    assert "historical_bootstrap_returns" in at.warning[0].value
    assert "stress_scenario_2008" in at.warning[0].value
    assert len(at.success) == 0
