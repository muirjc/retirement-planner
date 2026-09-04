"""Run a simulation (User Story 2, contracts/ui-pages.md §
2_Run_Simulation.py). FR-006, FR-008, FR-010, FR-011. The verification
indicator (US4) and CSV download (US5) are added to this same file later,
as small additive edits -- this page is fully functional and
independently testable without either (tasks.md's own sequencing note).
"""

import streamlit as st

from rp_ui.account_table import render_account_table
from rp_ui.api_client import export_simulation_csv, list_scenarios, list_withdrawal_strategies, run_simulation, search_sustainable_spending_range
from rp_ui.charts import fan_chart
from rp_ui.narration import render_results_explanation
from rp_ui.verification import render_verification_indicator
from rp_ui.errors import (
    BackendUnreachableError,
    BlockingValidationError,
    CostBudgetExceededError,
    InvalidSimulationOptionsError,
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
    a1.number_input("Paths", min_value=1, step=100, key="run_n_paths_override", help="Overrides the scenario's saved Paths for this run only.")
    a2.number_input("Seed", min_value=0, step=1, key="run_seed_override", help="Overrides the scenario's saved Seed for this run only.")
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

    g1, g2 = st.columns(2)
    g1.selectbox(
        "Return generation mode",
        options=["parametric", "historical_bootstrap"],
        key="run_generation_mode",
        help=(
            "`parametric` (default) -- correlated-normal draws from this scenario's own market "
            "assumptions. `historical_bootstrap` -- resamples contiguous blocks from a documented "
            "historical annual-return series instead, to capture fat tails and real historical "
            "clustering. That series is currently SYNTHETIC PLACEHOLDER DATA, not real market "
            "history (docs/BRD.md §6.9) -- a run using it is flagged below as relying on an "
            "unverified figure, the same way every other unverified figure in this tool already is."
        ),
    )
    g2.number_input(
        "Historical block length (years)",
        min_value=1,
        step=1,
        value=10,
        key="run_historical_block_length",
        help="Only used in `historical_bootstrap` mode -- how many consecutive years are resampled together each time.",
    )

    st.checkbox(
        "Apply a sequence-of-returns stress overlay",
        key="run_apply_stress",
        help=(
            "A bad early sequence of returns is a materially different risk than the same average "
            "return spread evenly across the whole horizon -- this overrides every simulated "
            "path's return to the fixed value below for the configured window, on top of whichever "
            "return-generation mode is selected. Off by default (rp-2bn)."
        ),
    )
    s1, s2, s3 = st.columns(3)
    s1.number_input(
        "Shock magnitude",
        step=0.01,
        format="%.2f",
        key="run_stress_magnitude",
        help="The fixed annual return every path is overridden to for the window below -- e.g. -0.30 for a 30% single-year decline.",
    )
    s2.number_input(
        "Duration (years)",
        min_value=1,
        step=1,
        key="run_stress_duration_years",
        help="How many consecutive plan years the shock lasts.",
    )
    s3.number_input(
        "Starting plan year",
        min_value=1,
        step=1,
        key="run_stress_start_plan_year",
        help="The first plan year the shock applies to -- must fit within this run's own horizon.",
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
        # rp-741: always sent -- both have a meaningful default
        # ("parametric"/10) rather than needing a separate override gate.
        "generation_mode": st.session_state["run_generation_mode"],
        "historical_block_length": st.session_state["run_historical_block_length"],
    }
    if st.session_state.get("run_override_advanced"):
        body["n_paths"] = st.session_state["run_n_paths_override"]
        body["seed"] = st.session_state["run_seed_override"]
        body["plan_to_age"] = st.session_state["run_plan_to_age_override"]
    # rp-2bn: only sent when the checkbox is on -- otherwise stress_scenario
    # stays omitted, reproducing every existing request's exact prior body.
    if st.session_state.get("run_apply_stress"):
        body["stress_scenario"] = {
            "magnitude": st.session_state["run_stress_magnitude"],
            "duration_years": st.session_state["run_stress_duration_years"],
            "start_plan_year": st.session_state["run_stress_start_plan_year"],
        }
    return body


def _build_spending_search_body() -> dict:
    """rp-430: the sustainable-spending-range endpoint's own request shape
    -- a subset of _build_run_body()'s fields (no detail_path_index/
    survival_adjusted, out of scope for a search; no n_paths/seed
    override, since the search always uses its own fixed, reduced path
    count independent of whatever the scenario or the override above
    configures -- see docs/BRD.md §6.10)."""
    body = {
        "scenario_name": st.session_state["run_scenario_select"],
        "withdrawal_strategy": st.session_state["run_withdrawal_strategy"],
        "reference_tax_year": st.session_state["run_reference_tax_year"],
        "start_plan_year": st.session_state["run_start_plan_year"],
        "start_tax_year": st.session_state["run_start_tax_year"],
        "generation_mode": st.session_state["run_generation_mode"],
        "historical_block_length": st.session_state["run_historical_block_length"],
    }
    if st.session_state.get("run_override_advanced"):
        body["plan_to_age"] = st.session_state["run_plan_to_age_override"]
    if st.session_state.get("run_apply_stress"):
        body["stress_scenario"] = {
            "magnitude": st.session_state["run_stress_magnitude"],
            "duration_years": st.session_state["run_stress_duration_years"],
            "start_plan_year": st.session_state["run_stress_start_plan_year"],
        }
    return body


run_col, search_col = st.columns(2)

with run_col:
    run_clicked = st.button("Run", key="run_button", help="Runs a Monte Carlo simulation for the selected scenario with the settings above.")
with search_col:
    search_clicked = st.button(
        "Suggest a sustainable spending range",
        key="spending_search_button",
        help=(
            "A real, simulation-backed estimate (not a formula) of what this scenario's household can "
            "afford to spend -- searches for the spending levels that hit a 95% ('conservative') and a "
            "75% ('flexible') success rate. Runs a reduced-precision search (fewer Monte Carlo paths than "
            "a full Run) for speed, roughly 10-20 seconds -- treat the result as an estimate, and confirm "
            "by running the full simulation above at whichever figure you land on."
        ),
    )

if search_clicked:
    with st.spinner("Searching for a sustainable spending range (reduced-precision estimate, ~10-20s)..."):
        try:
            st.session_state["spending_search_result"] = search_sustainable_spending_range(_build_spending_search_body())
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
                f"Tax year {err.requested_year} isn't supported for {err.figure_name!r} -- enter a year between {min(years)} and {max(years)}."
                if years
                else f"Tax year {err.requested_year} isn't supported for {err.figure_name!r}."
            )
        except CostBudgetExceededError as err:
            st.error(f"This search is too large (estimated {err.estimated_seconds:.0f}s against a {err.budget_seconds:.0f}s budget) -- try a shorter horizon.")
        except InvalidSimulationOptionsError as err:
            st.error(err.detail)
        except BackendUnreachableError as err:
            st.error(str(err))
        except RpUiError as err:
            st.error(str(err))
        # No `else:` needed -- the assignment inside `try` already stored
        # the result in session_state on success; nothing further to do.

if "spending_search_result" in st.session_state:
    result = st.session_state["spending_search_result"]
    conservative, flexible = result["conservative"], result["flexible"]
    st.info(
        f"**Estimated sustainable spending: ${conservative['spending']:,.0f} - ${flexible['spending']:,.0f}/yr** "
        f"({conservative['target_success_rate']:.0%} conservative to {flexible['target_success_rate']:.0%} flexible "
        f"success rate) -- a fast, reduced-precision estimate ({result['path_count_used']} paths), not a full-"
        "precision answer. Confirm by running the full simulation above at a spending figure in this range."
    )
    if conservative["bracket_exhausted"]:
        st.caption(
            f"The conservative ({conservative['target_success_rate']:.0%}) end didn't fully converge -- this "
            f"household stays above that success rate even at ${conservative['spending']:,.0f}/yr, so the true "
            "conservative ceiling is higher than shown."
        )
    if flexible["bracket_exhausted"]:
        st.caption(
            f"The flexible ({flexible['target_success_rate']:.0%}) end didn't fully converge -- this household "
            f"stays above that success rate even at ${flexible['spending']:,.0f}/yr, so the true flexible ceiling "
            "is higher than shown."
        )

if run_clicked:
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
                f"Tax year {err.requested_year} isn't supported for {err.figure_name!r} -- enter a year between {min(years)} and {max(years)}."
                if years
                else f"Tax year {err.requested_year} isn't supported for {err.figure_name!r}."
            )
        except PathIndexOutOfRangeError as err:
            st.error(f"Detail path index {err.requested} is out of range -- this run only has {err.path_count} path(s). Enter a value from 0 to {err.path_count - 1}.")
        except SurvivalCurveAgeOutOfRangeError as err:
            st.error(
                f"Survival-adjusted scoring isn't available for {err.person_name!r} at age {err.age} -- "
                "the illustrative survival curve this feature uses only covers ages 50-110. Uncheck "
                "'Score success using survival-adjusted probability' above, or adjust this household's "
                "ages/Plan to age so every age reached during the run stays in that range."
            )
        except CostBudgetExceededError as err:
            st.error(f"This request is too large (estimated {err.estimated_seconds:.0f}s against a {err.budget_seconds:.0f}s budget) -- try fewer paths.")
        except InvalidSimulationOptionsError as err:
            st.error(err.detail)
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
