"""Instructions (User Stories 1 & 2, contracts/ui-pages.md §
0_Instructions.py). Explains what financial information to gather for
each party and what every field on the Scenarios form requires
(FR-001-FR-010). Purely static content -- no widget, no session_state
entry, no HTTP call of any kind, unlike every other page in this package.

The `0` filename prefix sorts this page above 1_Scenarios.py in
Streamlit's own filename-ordered sidebar (research.md §2), since it's
meant to be read before filling out that form.
"""

import streamlit as st

from rp_ui.instructions_content import SECTIONS

st.set_page_config(page_title="Instructions -- Retirement Planner", page_icon="\U0001f4d6")
st.title("Instructions")
st.write(
    "Before creating a scenario, read the sections below for what financial "
    "information to gather for each party in the household and what each "
    "field on the Scenarios page actually requires."
)

for section in SECTIONS:
    st.header(section.title)
    st.markdown(section.body)
