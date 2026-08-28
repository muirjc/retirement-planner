"""Compare candidates (User Story 3, contracts/ui-pages.md § 3_Compare.py).
FR-009-FR-012. The candidate-list editor is bounded to a fixed number of
slots (1-4, chosen via a number_input) rather than a free-form add/remove
list, mirroring 1_Scenarios.py's own household-member simplification --
quickstart.md's own worked examples never exceed 3 candidates. The
verification indicator (US4) and CSV download (US5) are added to this
same file later, as small additive edits.
"""

import streamlit as st

from rp_ui.api_client import (
    compare_deterministic,
    compare_simulated,
    export_comparison_csv,
    list_comparison_axes,
    list_conversion_strategies,
    list_scenarios,
    list_states,
    list_withdrawal_strategies,
)
from rp_ui.charts import comparison_bar_chart, comparison_overlay_chart
from rp_ui.verification import render_verification_indicator
from rp_ui.errors import (
    BackendUnreachableError,
    BlockingValidationError,
    CostBudgetExceededError,
    RpUiError,
    ScenarioNotFoundError,
    UnknownReferenceValueError,
    UnsupportedTaxYearError,
)

st.set_page_config(page_title="Compare -- Retirement Planner", page_icon="\U0001f4ca")
st.title("Compare")

DETERMINISTIC_AXES = {"roth_conversion_strategy", "withdrawal_sequencing", "claiming_age_grid"}
SIMULATED_AXES = {"state", "roth_conversion_strategy", "withdrawal_sequencing", "claiming_age_grid"}

try:
    scenario_names = list_scenarios()
    all_axes = list_comparison_axes()
    states = list_states()
    conversion_strategies = list_conversion_strategies()
    withdrawal_strategies = list_withdrawal_strategies()
except RpUiError as err:
    st.error(str(err))
    st.stop()

if not scenario_names:
    st.info("No saved scenarios yet -- create one on the Scenarios page first.")
    st.stop()

st.selectbox("Scenario", options=scenario_names, key="compare_scenario_select")
st.radio("Engine", options=["Monte Carlo", "Deterministic"], key="compare_engine")

# FR-010, Acceptance Scenario US3.2: "state" is never offered for
# Deterministic, enforced client-side before submission.
allowed_axes = DETERMINISTIC_AXES if st.session_state.get("compare_engine") == "Deterministic" else SIMULATED_AXES
axis_options = [axis for axis in all_axes if axis in allowed_axes]
st.selectbox("Axis", options=axis_options, key="compare_axis")

c1, c2, c3 = st.columns(3)
c1.number_input("Reference tax year", min_value=1900, step=1, key="compare_reference_tax_year")
c2.number_input("Start plan year", min_value=1, step=1, key="compare_start_plan_year")
c3.number_input("Start tax year", min_value=1900, step=1, key="compare_start_tax_year")

st.number_input("Number of candidates", min_value=1, max_value=4, step=1, key="compare_candidate_count")

axis = st.session_state.get("compare_axis")
count = st.session_state.get("compare_candidate_count", 1)

for i in range(count):
    st.markdown(f"**Candidate {i + 1}**")
    if axis == "state":
        options = [""] + states
        st.selectbox("State", options=options, key=f"compare_candidate_{i}_state")
    elif axis == "roth_conversion_strategy":
        cc1, cc2, cc3, cc4 = st.columns(4)
        cc1.text_input("Label", key=f"compare_candidate_{i}_label")
        cc2.selectbox("Conversion strategy", options=[""] + conversion_strategies, key=f"compare_candidate_{i}_strategy")
        cc3.number_input("Bracket ceiling/amount", key=f"compare_candidate_{i}_bracket")
        w1, w2 = cc4.columns(2)
        w1.number_input("Window start", min_value=0, step=1, key=f"compare_candidate_{i}_window_start")
        w2.number_input("Window end", min_value=0, step=1, key=f"compare_candidate_{i}_window_end")
    elif axis == "withdrawal_sequencing":
        cc1, cc2 = st.columns(2)
        cc1.text_input("Label", key=f"compare_candidate_{i}_label")
        cc2.selectbox("Withdrawal strategy", options=withdrawal_strategies, key=f"compare_candidate_{i}_strategy")
    elif axis == "claiming_age_grid":
        cc1, cc2, cc3, cc4 = st.columns(4)
        cc1.text_input("Person 1 name", key=f"compare_candidate_{i}_person1_name")
        cc2.number_input("Person 1 claim age", min_value=0, step=1, key=f"compare_candidate_{i}_person1_age")
        cc3.text_input("Person 2 name (optional)", key=f"compare_candidate_{i}_person2_name")
        cc4.number_input("Person 2 claim age", min_value=0, step=1, key=f"compare_candidate_{i}_person2_age")


def _build_candidates() -> list:
    candidates = []
    for i in range(count):
        if axis == "state":
            candidates.append(st.session_state.get(f"compare_candidate_{i}_state") or "")
        elif axis == "roth_conversion_strategy":
            strategy = st.session_state.get(f"compare_candidate_{i}_strategy") or None
            candidates.append(
                {
                    "label": st.session_state.get(f"compare_candidate_{i}_label") or f"candidate_{i + 1}",
                    "conversion_strategy": strategy,
                    "conversion_bracket_ceiling_or_amount": st.session_state.get(f"compare_candidate_{i}_bracket", 0.0),
                    "conversion_window": [
                        st.session_state.get(f"compare_candidate_{i}_window_start", 0),
                        st.session_state.get(f"compare_candidate_{i}_window_end", 0),
                    ],
                }
            )
        elif axis == "withdrawal_sequencing":
            candidates.append(
                {
                    "label": st.session_state.get(f"compare_candidate_{i}_label") or f"candidate_{i + 1}",
                    "withdrawal_strategy": st.session_state.get(f"compare_candidate_{i}_strategy"),
                }
            )
        elif axis == "claiming_age_grid":
            cell = {}
            name1 = st.session_state.get(f"compare_candidate_{i}_person1_name")
            if name1:
                cell[name1] = st.session_state.get(f"compare_candidate_{i}_person1_age", 0)
            name2 = st.session_state.get(f"compare_candidate_{i}_person2_name")
            if name2:
                cell[name2] = st.session_state.get(f"compare_candidate_{i}_person2_age", 0)
            candidates.append(cell)
    return candidates


def _build_body() -> dict:
    return {
        "scenario_name": st.session_state["compare_scenario_select"],
        "reference_tax_year": st.session_state["compare_reference_tax_year"],
        "start_plan_year": st.session_state["compare_start_plan_year"],
        "start_tax_year": st.session_state["compare_start_tax_year"],
        "axis": axis,
        "candidates": _build_candidates(),
    }


if st.button("Compare", key="compare_button"):
    with st.spinner("Comparing..."):
        engine = st.session_state.get("compare_engine")
        try:
            if engine == "Deterministic":
                result = compare_deterministic(_build_body())
            else:
                result = compare_simulated(_build_body())
        except ScenarioNotFoundError:
            st.error("This scenario no longer exists.")
        except BlockingValidationError as err:
            st.error("Fix these problems on the Scenarios page first:")
            for flag in err.flags:
                st.error(f"**{flag['field']}**: {flag['message']}")
        except UnknownReferenceValueError as err:
            st.error(f"{err.field!r} value {err.value!r} isn't currently supported -- pick from the list.")
        except UnsupportedTaxYearError as err:
            years = err.documented_years
            st.error(
                f"Tax year {err.requested_year} isn't supported for {err.figure_name!r} -- "
                f"enter a year between {min(years)} and {max(years)}." if years else
                f"Tax year {err.requested_year} isn't supported for {err.figure_name!r}."
            )
        except CostBudgetExceededError as err:
            st.error(
                f"This request is too large (estimated {err.estimated_seconds:.0f}s "
                f"against a {err.budget_seconds:.0f}s budget) -- try fewer paths or candidates."
            )
        except BackendUnreachableError as err:
            st.error(str(err))
        except RpUiError as err:
            st.error(str(err))
        else:
            st.session_state["compare_last_result"] = result
            st.session_state["compare_last_body"] = _build_body()
            st.session_state["compare_last_engine"] = engine

if "compare_last_result" in st.session_state:
    summaries = st.session_state["compare_last_result"]["summaries"]
    if summaries and summaries[0].get("percentile_bands") is not None:
        st.plotly_chart(comparison_overlay_chart(summaries))
    else:
        st.plotly_chart(comparison_bar_chart(summaries))

    st.dataframe(
        [
            {
                "candidate_label": s.get("candidate_label"),
                "success_rate": f"{s['success_rate'] * 100:.1f}%" if s.get("success_rate") is not None else "n/a",
                "ending_balance": s.get("ending_balance"),
                "median_lifetime_tax_paid": s.get("median_lifetime_tax_paid"),
                "median_depletion_age": s.get("median_depletion_age") if s.get("median_depletion_age") is not None else "n/a",
            }
            for s in summaries
        ]
    )

    # Per-candidate unverified figures shown as one union list -- no single
    # candidate is more relevant than another for this purpose
    # (contracts/ui-pages.md § 3_Compare.py).
    union_unverified = sorted({name for s in summaries for name in s.get("unverified_figure_names", [])})
    render_verification_indicator(union_unverified)

    # US5, FR-014: the same request body already used for the on-screen
    # comparison, plus the engine that produced it (data-model.md §
    # Relationships) -- same prepare-then-download pattern as
    # 2_Run_Simulation.py, since st.download_button needs its data ready
    # before render.
    engine_param = "deterministic" if st.session_state["compare_last_engine"] == "Deterministic" else "simulated"
    if st.button("Prepare CSV download", key="compare_prepare_csv_button"):
        try:
            st.session_state["compare_csv_text"] = export_comparison_csv(
                st.session_state["compare_last_body"], engine=engine_param
            )
        except RpUiError as err:
            st.error(str(err))
    if "compare_csv_text" in st.session_state:
        st.download_button(
            "Download CSV",
            data=st.session_state["compare_csv_text"],
            file_name="comparison.csv",
            mime="text/csv",
            key="compare_download_csv_button",
        )
