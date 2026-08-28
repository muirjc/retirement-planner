"""The Verification Indicator (data-model.md § Verification Indicator,
FR-013). Called on every Run View and Comparison View -- never omitted
either way, mirroring 006's own "present even when empty" discipline one
layer further downstream (Principle III, plan.md's Constitution Check).
"""

from __future__ import annotations

import streamlit as st


def render_verification_indicator(unverified_figure_names: list[str]) -> None:
    """unverified_figure_names is 007's own SummaryStatistics field,
    always a list, possibly empty, never None. Empty means "checked, none
    unverified" (a positive confirmation, Acceptance Scenario US4.2) --
    distinguishable from "not checked" (there is no page in this feature
    that renders neither, so that state is unreachable, not merely
    unrendered)."""
    if not unverified_figure_names:
        st.success("All figures used in this result are verified.")
    else:
        st.warning("This result relies on figure(s) not yet verified: " + ", ".join(unverified_figure_names))
