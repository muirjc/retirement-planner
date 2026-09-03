"""Year-by-year results walkthrough (rp-bm8.1, 028-results-walkthrough
FR-009-FR-013). Reads the narrative already computed server-side and stored
in st.session_state["run_last_result"]["narrative"] by 2_Run_Simulation.py's
own run_simulation() call -- no new HTTP request from this page (FR-008,
research.md §7). Steps through the projection three plan years at a time via
Next/Previous (FR-009/FR-010, spec.md Clarifications), and scopes the
existing verification indicator (US3, FR-011) to each shown year's own
unverified_figure_names (research.md §4).
"""

import streamlit as st

from rp_ui.formatting import format_currency
from rp_ui.verification import render_verification_indicator
from rp_ui.year_detail import render_year_computation_detail

_BATCH_SIZE = 3
"""spec.md Clarifications (2026-09-03): fixed batches of 3 plan years per
screen; the final batch shows fewer if the remainder doesn't fill one."""

st.set_page_config(page_title="Walkthrough -- Retirement Planner", page_icon="\U0001f4d6")
st.title("Walkthrough")

if "run_last_result" not in st.session_state:
    st.info("Run a simulation on the **Run Simulation** page first, then come back here to step through it year by year.")
    st.stop()

result = st.session_state["run_last_result"]
narrative = result.get("narrative")
if not narrative or not narrative.get("years"):
    st.info("Run a simulation on the **Run Simulation** page first, then come back here to step through it year by year.")
    st.stop()

years = narrative["years"]
selected_path_index = narrative["selected_path_index"]
# The narrative's own selected path, not body.detail_path_index's (possibly
# different) path -- contracts/reporting-narrative-api.md's own note that
# the two selections are independent.
path_years = result["run"]["path_results"][selected_path_index]["years"]

# Reset to the first batch whenever a new run replaces run_last_result
# (identity-compared, since a fresh Run click stores a brand-new dict).
if st.session_state.get("walkthrough_last_narrative_id") != id(narrative):
    st.session_state["walkthrough_last_narrative_id"] = id(narrative)
    st.session_state["walkthrough_batch_index"] = 0

total_batches = (len(years) + _BATCH_SIZE - 1) // _BATCH_SIZE
batch_index = min(st.session_state.get("walkthrough_batch_index", 0), total_batches - 1)

st.caption(f"Path {selected_path_index} of {len(result['run']['path_results'])} -- the simulated path closest to the median outcome.")

nav_prev, nav_status, nav_next = st.columns([1, 2, 1])
with nav_prev:
    if st.button("← Previous", disabled=batch_index == 0, key="walkthrough_prev"):
        batch_index -= 1
        st.session_state["walkthrough_batch_index"] = batch_index
        st.rerun()
with nav_status:
    st.write(f"Years {batch_index * _BATCH_SIZE + 1}–{min((batch_index + 1) * _BATCH_SIZE, len(years))} of {len(years)}")
with nav_next:
    if st.button("Next →", disabled=batch_index >= total_batches - 1, key="walkthrough_next"):
        batch_index += 1
        st.session_state["walkthrough_batch_index"] = batch_index
        st.rerun()

batch_start = batch_index * _BATCH_SIZE
for offset, story in enumerate(years[batch_start : batch_start + _BATCH_SIZE]):
    year_detail = path_years[batch_start + offset]
    ages = ", ".join(f"{name} (age {age})" for name, age in story["member_ages"].items())
    st.subheader(f"Plan year {story['plan_year']} -- tax year {story['tax_year']}")
    st.caption(ages)

    for entry in story["entries"]:
        st.markdown(f"**{entry['label']}.** {entry['explanation']}")

    ending_balances = year_detail["ending_balances"]
    ending_total = ending_balances["traditional"] + ending_balances["roth"] + ending_balances["taxable"]
    metric_cols = st.columns(3)
    metric_cols[0].metric("Ending balance", format_currency(ending_total))
    metric_cols[1].metric(
        "Taxes owed",
        format_currency(year_detail["federal_tax"]["federal_tax_owed"] + year_detail["state_tax"]["state_tax_owed"]),
    )
    metric_cols[2].metric("Shortfall", format_currency(year_detail["shortfall"]) if year_detail["shortfall"] else "None")

    with st.expander("How was this year's math computed?"):
        render_year_computation_detail(story["detail"])

    render_verification_indicator(story.get("unverified_figure_names", []))
    st.divider()
