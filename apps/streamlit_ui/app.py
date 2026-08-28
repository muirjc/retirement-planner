"""Streamlit entry point -- Home page (contracts/ui-pages.md § app.py).

Run with: streamlit run apps/streamlit_ui/app.py

Renders a short description, navigation to the three pages under pages/
(Streamlit's own multi-page convention builds the sidebar automatically
from that directory -- research.md §5), and a live backend-status check:
if GET /reference/states fails, the Home page shows the error immediately
rather than waiting for a user to discover it on a deeper page.
"""

import streamlit as st

from rp_ui.api_client import list_states
from rp_ui.errors import RpUiError

st.set_page_config(page_title="Retirement Planner", page_icon="\U0001f4c8")

st.title("Retirement Planner")
st.write(
    "A single-user retirement planning tool: build a scenario, run a "
    "Monte Carlo or deterministic simulation, compare candidates on an "
    "axis, and download the results as CSV."
)
st.markdown(
    "Use the sidebar to navigate: **Scenarios** to create, edit, or "
    "delete a scenario; **Run Simulation** to run one and see a fan "
    "chart; **Compare** to compare candidates on an axis."
)

st.divider()

try:
    states = list_states()
except RpUiError as err:
    st.error(str(err))
else:
    st.success(f"Connected to the backend. {len(states)} state(s) currently supported.")
