"""Run a simulation (User Story 2, contracts/ui-pages.md §
2_Run_Simulation.py). FR-006, FR-008, FR-010, FR-011. The verification
indicator (US4) and CSV download (US5) are added to this same file later,
as small additive edits -- this page is fully functional and
independently testable without either (tasks.md's own sequencing note).
"""

import streamlit as st

from rp_ui.account_table import render_account_table
from rp_ui.api_client import export_simulation_csv, list_scenarios, list_withdrawal_strategies, run_simulation
from rp_ui.charts import fan_chart
from rp_ui.narration import render_results_explanation
from rp_ui.verification import render_verification_indicator
from rp_ui.errors import (
    BackendUnreachableError,
    BlockingValidationError,
    CostBudgetExceededError,
    PathIndexOutOfRangeError,
    RpUiError,
    ScenarioNotFoundError,
    SurvivalCurveAgeOutOfRangeError,
    UnknownReferenceValueError,
    UnsupportedTaxYearError,
)

st.set_page_config(page_title="Run Simulation -- Retirement Planner", page_icon="\U0001f3b2")
st.title("Run Simulation")

try:
    scenario_names = list_scenarios()
    withdrawal_strategies = list_withdrawal_strategies()
except RpUiError as err:
    st.error(str(err))
    st.stop()

if not scenario_names:
    st.info("No saved scenarios yet -- create one on the Scenarios page first.")
    st.stop()

st.selectbox("Scenario", options=scenario_names, key="run_scenario_select", help="Which saved scenario to run.")
st.selectbox(
    "Withdrawal strategy",
    options=withdrawal_strategies,
    key="run_withdrawal_strategy",
    help=(
        "Draw order for spending *after* the RMD (always drawn from traditional first). "
        "`rmd_taxable_traditional_roth` -- taxable, then traditional, then Roth last (keeps "
        "Roth growing longest). `rmd_traditional_taxable_roth` -- traditional, then taxable, "
        "then Roth last (draws down pre-tax money sooner). See the Instructions page's Run "
        "Simulation section for more."
    ),
)

c1, c2, c3 = st.columns(3)
c1.number_input(
    "Reference tax year",
    min_value=1900,
    step=1,
    key="run_reference_tax_year",
    help="The real calendar year each member's Current age is measured as of -- e.g. if today is 2026, enter 2026. Always replace the placeholder before running.",
)
c2.number_input(
    "Start plan year",
    min_value=1,
    step=1,
    key="run_start_plan_year",
    help="Which plan year this run starts counting from -- 1 for a fresh run starting today.",
)
c3.number_input(
    "Start tax year",
    min_value=1900,
    step=1,
    key="run_start_tax_year",
    help="The calendar tax year the first plan year corresponds to -- normally the same as Reference tax year.",
)

st.checkbox(
    "Score success using survival-adjusted probability",
    key="run_survival_adjusted",
    help=(
        "Also reports the share of simulated paths that never ran out of money while at least "
        "one household member is presumed alive -- a shortfall after every member is more "
        "likely dead than alive counts as a success here, unlike Success rate below. Uses an "
        "illustrative, not-yet-verified survival curve (rp-9vl) -- see the verification notice "
        "below when shown. Requires every household member's age to stay within roughly 50-110 "
        "for this run's full horizon, or the run is rejected with an error naming the member/age."
    ),
)

with st.expander("Advanced overrides"):
    st.checkbox(
        "Override scenario defaults",
        key="run_override_advanced",
        help="When checked, the Paths/Seed/Plan to age fields below replace this scenario's own saved Simulation Settings for this run only -- otherwise they're ignored even if changed.",
    )
    a1, a2, a3 = st.columns(3)
    a1.number_input(
        "Paths", min_value=1, step=100, key="run_n_paths_override", help="Overrides the scenario's saved Paths for this run only."
    )
    a2.number_input(
        "Seed", min_value=0, step=1, key="run_seed_override", help="Overrides the scenario's saved Seed for this run only."
    )
    a3.number_input(
        "Plan to age",
        min_value=1,
        step=1,
        key="run_plan_to_age_override",
        help="Overrides the scenario's saved Plan to age for this run only.",
    )
    st.number_input(
        "Detail path index",
        min_value=0,
        step=1,
        key="run_detail_path_index",
        help=(
            "Which one Monte Carlo path's year-by-year account detail table (below) to show -- "
            "0 is the first path. This only changes which single example path's detail is "
            "displayed, never the success rate or fan chart, which always reflect every path."
        ),
    )


def _build_run_body() -> dict:
    body = {
        "scenario_name": st.session_state["run_scenario_select"],
        "withdrawal_strategy": st.session_state["run_withdrawal_strategy"],
        "reference_tax_year": st.session_state["run_reference_tax_year"],
        "start_plan_year": st.session_state["run_start_plan_year"],
        "start_tax_year": st.session_state["run_start_tax_year"],
        # 015-per-account-projection-detail: unlike Paths/Seed/Plan to
        # age, this isn't gated by "Override scenario defaults" -- it
        # only selects which single path's detail table to display, not
        # a scenario-level setting with its own saved default to override.
        "detail_path_index": st.session_state["run_detail_path_index"],
        "survival_adjusted": st.session_state["run_survival_adjusted"],
    }
    if st.session_state.get("run_override_advanced"):
        body["n_paths"] = st.session_state["run_n_paths_override"]
        body["seed"] = st.session_state["run_seed_override"]
        body["plan_to_age"] = st.session_state["run_plan_to_age_override"]
    return body


if st.button("Run", key="run_button", help="Runs a Monte Carlo simulation for the selected scenario with the settings above."):
    with st.spinner("Running simulation..."):
        try:
            result = run_simulation(_build_run_body())
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
        except PathIndexOutOfRangeError as err:
            st.error(
                f"Detail path index {err.requested} is out of range -- this run only has "
                f"{err.path_count} path(s). Enter a value from 0 to {err.path_count - 1}."
            )
        except SurvivalCurveAgeOutOfRangeError as err:
            st.error(
                f"Survival-adjusted scoring isn't available for {err.person_name!r} at age {err.age} -- "
                "the illustrative survival curve this feature uses only covers ages 50-110. Uncheck "
                "'Score success using survival-adjusted probability' above, or adjust this household's "
                "ages/Plan to age so every age reached during the run stays in that range."
            )
        except CostBudgetExceededError as err:
            st.error(
                f"This request is too large (estimated {err.estimated_seconds:.0f}s "
                f"against a {err.budget_seconds:.0f}s budget) -- try fewer paths."
            )
        except BackendUnreachableError as err:
            st.error(str(err))
        except RpUiError as err:
            st.error(str(err))
        else:
            st.session_state["run_last_result"] = result
            st.session_state["run_last_body"] = _build_run_body()

if "run_last_result" in st.session_state:
    run = st.session_state["run_last_result"]["run"]
    summary = st.session_state["run_last_result"]["summary"]
    if summary.get("survival_adjusted_success_rate") is not None:
        m1, m2 = st.columns(2)
        m1.metric("Success rate", f"{summary['success_rate'] * 100:.1f}%")
        m2.metric(
            "Survival-adjusted success rate",
            f"{summary['survival_adjusted_success_rate'] * 100:.1f}%",
            help="Uses an illustrative, not-yet-verified survival curve -- see the notice below.",
        )
    else:
        st.metric("Success rate", f"{summary['success_rate'] * 100:.1f}%" if summary["success_rate"] is not None else "n/a")
    st.plotly_chart(fan_chart(summary["percentile_bands"] or []))
    # rp-r07: the numbers behind the chart above, in plain language --
    # path_count comes from this same response (every path's own result
    # is already in `run`), so "success rate" can read "N of M paths"
    # rather than just a percentage.
    render_results_explanation(summary, path_count=len(run["path_results"]))
    render_verification_indicator(summary.get("unverified_figure_names", []))
    render_account_table(st.session_state["run_last_result"].get("account_detail", []))

    # US5, FR-014: the *same* request body already used for the on-screen
    # run, sent again to the CSV export endpoint (data-model.md §
    # Relationships) -- st.download_button needs its data ready before
    # render, so a plain button first fetches it into session_state.
    if st.button(
        "Prepare CSV download",
        key="run_prepare_csv_button",
        help="Fetches this run's full results as CSV, ready to download below.",
    ):
        try:
            st.session_state["run_csv_text"] = export_simulation_csv(st.session_state["run_last_body"])
        except RpUiError as err:
            st.error(str(err))
    if "run_csv_text" in st.session_state:
        st.download_button(
            "Download CSV",
            data=st.session_state["run_csv_text"],
            file_name="simulation_run.csv",
            mime="text/csv",
            key="run_download_csv_button",
            help="Saves this run's full per-path results to a CSV file.",
        )
