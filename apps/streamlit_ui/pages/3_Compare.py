"""Compare candidates (User Story 3, contracts/ui-pages.md § 3_Compare.py).
FR-009-FR-012. The candidate-list editor is bounded to a fixed number of
slots (1-4, chosen via a number_input) rather than a free-form add/remove
list, mirroring 1_Scenarios.py's own household-member simplification --
quickstart.md's own worked examples never exceed 3 candidates. The
verification indicator (US4) and CSV download (US5) are added to this
same file later, as small additive edits.
"""

import streamlit as st

from rp_ui.account_table import render_account_table
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
from rp_ui.formatting import format_currency
from rp_ui.narration import render_results_explanation
from rp_ui.verification import render_verification_indicator
from rp_ui.errors import (
    BackendUnreachableError,
    BlockingValidationError,
    CostBudgetExceededError,
    InvalidSimulationOptionsError,
    RpUiError,
    ScenarioNotFoundError,
    SurvivalCurveAgeOutOfRangeError,
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

st.selectbox("Scenario", options=scenario_names, key="compare_scenario_select", help="Which saved scenario to compare candidates against.")
st.radio(
    "Engine",
    options=["Monte Carlo", "Deterministic"],
    key="compare_engine",
    help=(
        "Monte Carlo -- full randomized simulation per candidate; results include a success "
        "rate and percentile fan chart. Deterministic -- one fixed-return projection per "
        "candidate (no randomness); faster, shows a single ending balance and tax total "
        "instead of a success rate."
    ),
)

# FR-010, Acceptance Scenario US3.2: "state" is never offered for
# Deterministic, enforced client-side before submission.
allowed_axes = DETERMINISTIC_AXES if st.session_state.get("compare_engine") == "Deterministic" else SIMULATED_AXES
axis_options = [axis for axis in all_axes if axis in allowed_axes]
st.selectbox(
    "Axis",
    options=axis_options,
    key="compare_axis",
    help=(
        "What varies between candidates. `state` -- different states of residence (Monte Carlo "
        "only). `roth_conversion_strategy` -- different Roth conversion setups. "
        "`withdrawal_sequencing` -- different withdrawal-order strategies. `claiming_age_grid` "
        "-- different Social Security claiming ages. See the Instructions page's Compare "
        "section for the full explanation."
    ),
)

if st.session_state.get("compare_engine") != "Deterministic":
    st.checkbox(
        "Score success using survival-adjusted probability",
        key="compare_survival_adjusted",
        help=(
            "Monte Carlo only. Also reports each candidate's share of paths that never ran out "
            "of money while at least one household member is presumed alive, using an "
            "illustrative, not-yet-verified survival curve (rp-9vl) -- see the verification "
            "notice below when shown."
        ),
    )

    with st.expander("Advanced overrides"):
        g1, g2 = st.columns(2)
        g1.selectbox(
            "Return generation mode",
            options=["parametric", "historical_bootstrap"],
            key="compare_generation_mode",
            help=(
                "`parametric` (default) -- correlated-normal draws from this scenario's own market "
                "assumptions. `historical_bootstrap` -- resamples contiguous blocks from a "
                "documented historical annual-return series instead, to capture fat tails and real "
                "historical clustering. That series is currently SYNTHETIC PLACEHOLDER DATA, not "
                "real market history (docs/BRD.md §6.9) -- flagged below as relying on an "
                "unverified figure, the same way every other unverified figure in this tool already is."
            ),
        )
        g2.number_input(
            "Historical block length (years)",
            min_value=1,
            step=1,
            value=10,
            key="compare_historical_block_length",
            help="Only used in `historical_bootstrap` mode -- how many consecutive years are resampled together each time.",
        )

        st.checkbox(
            "Apply a sequence-of-returns stress overlay",
            key="compare_apply_stress",
            help=(
                "A bad early sequence of returns is a materially different risk than the same "
                "average return spread evenly across the whole horizon -- this overrides every "
                "candidate's simulated paths to the fixed return below for the configured window, "
                "identically across every candidate (this tool's paired-draw methodology). Off by "
                "default (rp-2bn)."
            ),
        )
        s1, s2, s3 = st.columns(3)
        s1.number_input(
            "Shock magnitude",
            step=0.01,
            format="%.2f",
            key="compare_stress_magnitude",
            help="The fixed annual return every path is overridden to for the window below -- e.g. -0.30 for a 30% single-year decline.",
        )
        s2.number_input(
            "Duration (years)",
            min_value=1,
            step=1,
            key="compare_stress_duration_years",
            help="How many consecutive plan years the shock lasts.",
        )
        s3.number_input(
            "Starting plan year",
            min_value=1,
            step=1,
            key="compare_stress_start_plan_year",
            help="The first plan year the shock applies to -- must fit within this run's own horizon.",
        )

c1, c2, c3 = st.columns(3)
c1.number_input(
    "Reference tax year",
    min_value=1900,
    step=1,
    key="compare_reference_tax_year",
    help="The real calendar year each member's Current age is measured as of -- e.g. if today is 2026, enter 2026. Always replace the placeholder before comparing.",
)
c2.number_input(
    "Start plan year",
    min_value=1,
    step=1,
    key="compare_start_plan_year",
    help="Which plan year this comparison starts counting from -- 1 for a fresh run starting today.",
)
c3.number_input(
    "Start tax year",
    min_value=1900,
    step=1,
    key="compare_start_tax_year",
    help="The calendar tax year the first plan year corresponds to -- normally the same as Reference tax year.",
)

st.number_input(
    "Number of candidates",
    min_value=1,
    max_value=4,
    step=1,
    key="compare_candidate_count",
    help="How many candidates to compare side by side, 1 to 4 -- each gets its own row of fields below.",
)

axis = st.session_state.get("compare_axis")
count = st.session_state.get("compare_candidate_count", 1)

for i in range(count):
    st.markdown(f"**Candidate {i + 1}**")
    if axis == "state":
        options = [""] + states
        st.selectbox(
            "State",
            options=options,
            key=f"compare_candidate_{i}_state",
            help="See the Instructions page's State section for what differs between states.",
        )
    elif axis == "roth_conversion_strategy":
        cc1, cc2, cc3, cc4 = st.columns(4)
        cc1.text_input("Label", key=f"compare_candidate_{i}_label", help="A short name for this candidate, shown in the chart and table.")
        cc2.selectbox(
            "Conversion strategy",
            options=[""] + conversion_strategies,
            key=f"compare_candidate_{i}_strategy",
            help=("`fill_to_bracket` -- fills up to the ceiling below. `fixed_amount` -- converts that flat amount every year. See the Instructions page's Roth Conversion section."),
        )
        cc3.number_input(
            "Bracket ceiling/amount ($)",
            key=f"compare_candidate_{i}_bracket",
            help="For `fill_to_bracket`: the income ceiling to fill up to. For `fixed_amount`: the flat dollar amount to convert each year.",
        )
        w1, w2 = cc4.columns(2)
        _CANDIDATE_WINDOW_HELP = "The plan years this candidate's conversion strategy is active -- outside this window, no conversions happen."
        w1.number_input("Window start", min_value=0, step=1, key=f"compare_candidate_{i}_window_start", help=_CANDIDATE_WINDOW_HELP)
        w2.number_input("Window end", min_value=0, step=1, key=f"compare_candidate_{i}_window_end", help=_CANDIDATE_WINDOW_HELP)
    elif axis == "withdrawal_sequencing":
        cc1, cc2 = st.columns(2)
        cc1.text_input("Label", key=f"compare_candidate_{i}_label", help="A short name for this candidate, shown in the chart and table.")
        cc2.selectbox(
            "Withdrawal strategy",
            options=withdrawal_strategies,
            key=f"compare_candidate_{i}_strategy",
            help="See the Instructions page's Run Simulation section for what each option draws down first.",
        )
    elif axis == "claiming_age_grid":
        cc1, cc2, cc3, cc4 = st.columns(4)
        cc1.text_input(
            "Person 1 name",
            key=f"compare_candidate_{i}_person1_name",
            help="Must exactly match a household member's Name from the Scenarios page.",
        )
        cc2.number_input(
            "Person 1 claim age",
            min_value=0,
            step=1,
            key=f"compare_candidate_{i}_person1_age",
            help="The Social Security claiming age to test for this candidate, 62 to 70.",
        )
        cc3.text_input(
            "Person 2 name (optional)",
            key=f"compare_candidate_{i}_person2_name",
            help="Leave blank for a single-filer scenario. Must exactly match the second household member's Name otherwise.",
        )
        cc4.number_input(
            "Person 2 claim age",
            min_value=0,
            step=1,
            key=f"compare_candidate_{i}_person2_age",
            help="The Social Security claiming age to test for this candidate, 62 to 70.",
        )


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


def _build_stress_scenario() -> dict:
    # rp-2bn: same Deterministic-safe .get() pattern as survival_adjusted
    # below -- the expander only renders for Monte Carlo, and only sent
    # when the checkbox is on (mirrors 2_Run_Simulation.py's own
    # conditional-inclusion precedent).
    if not st.session_state.get("compare_apply_stress"):
        return {}
    return {
        "stress_scenario": {
            "magnitude": st.session_state["compare_stress_magnitude"],
            "duration_years": st.session_state["compare_stress_duration_years"],
            "start_plan_year": st.session_state["compare_stress_start_plan_year"],
        }
    }


def _build_body() -> dict:
    return {
        "scenario_name": st.session_state["compare_scenario_select"],
        "reference_tax_year": st.session_state["compare_reference_tax_year"],
        "start_plan_year": st.session_state["compare_start_plan_year"],
        "start_tax_year": st.session_state["compare_start_tax_year"],
        "axis": axis,
        "candidates": _build_candidates(),
        # rp-9vl: the checkbox above only renders for Monte Carlo (the
        # deterministic route ignores this field regardless) -- `.get`
        # covers a Deterministic-engine submission, where the widget was
        # never drawn and so has no session_state entry at all.
        "survival_adjusted": st.session_state.get("compare_survival_adjusted", False),
        # rp-741: same Deterministic-safe .get() pattern -- the expander
        # (and these two widgets) only render for Monte Carlo.
        "generation_mode": st.session_state.get("compare_generation_mode", "parametric"),
        "historical_block_length": st.session_state.get("compare_historical_block_length", 10),
        **_build_stress_scenario(),
    }


if st.button("Compare", key="compare_button", help="Runs the selected engine once per candidate above and charts the results together."):
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
                f"Tax year {err.requested_year} isn't supported for {err.figure_name!r} -- enter a year between {min(years)} and {max(years)}."
                if years
                else f"Tax year {err.requested_year} isn't supported for {err.figure_name!r}."
            )
        except SurvivalCurveAgeOutOfRangeError as err:
            st.error(
                f"Survival-adjusted scoring isn't available for {err.person_name!r} at age {err.age} -- "
                "the illustrative survival curve this feature uses only covers ages 50-110. Uncheck "
                "'Score success using survival-adjusted probability' above, or adjust this household's "
                "ages/Plan to age so every age reached during the run stays in that range."
            )
        except CostBudgetExceededError as err:
            st.error(f"This request is too large (estimated {err.estimated_seconds:.0f}s against a {err.budget_seconds:.0f}s budget) -- try fewer paths or candidates.")
        except InvalidSimulationOptionsError as err:
            st.error(err.detail)
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
                "survival_adjusted_success_rate": (f"{s['survival_adjusted_success_rate'] * 100:.1f}%" if s.get("survival_adjusted_success_rate") is not None else "n/a"),
                "ending_balance": format_currency(s.get("ending_balance")),
                "median_lifetime_tax_paid": format_currency(s.get("median_lifetime_tax_paid")),
                "median_lifetime_irmaa_paid": format_currency(s.get("median_lifetime_irmaa_paid")),
                "median_lifetime_niit_paid": format_currency(s.get("median_lifetime_niit_paid")),
                "median_depletion_age": s.get("median_depletion_age") if s.get("median_depletion_age") is not None else "n/a",
            }
            for s in summaries
        ]
    )

    # rp-r07: one plain-language explanation per candidate, right under
    # the table above -- Compare's simulated engine doesn't expose a path
    # count in its response (unlike Run Simulation's `run`), so no
    # path_count is passed here; narrate_metrics() falls back to
    # percentage-only for success rate rather than guessing a count.
    for s in summaries:
        render_results_explanation(s, title=s.get("candidate_label"))

    # Per-candidate unverified figures shown as one union list -- no single
    # candidate is more relevant than another for this purpose
    # (contracts/ui-pages.md § 3_Compare.py).
    union_unverified = sorted({name for s in summaries for name in s.get("unverified_figure_names", [])})
    render_verification_indicator(union_unverified)

    # 015-per-account-projection-detail (US2): one expander per candidate
    # -- keeps every candidate simultaneously visible (Compare's whole
    # reason for existing: side-by-side comparison), rather than a
    # selector that would hide all but one at a time.
    account_detail_by_candidate = st.session_state["compare_last_result"].get("account_detail", [])
    for s, candidate_detail in zip(summaries, account_detail_by_candidate):
        with st.expander(f"Year-by-year detail: {s.get('candidate_label')}"):
            render_account_table(candidate_detail)

    # US5, FR-014: the same request body already used for the on-screen
    # comparison, plus the engine that produced it (data-model.md §
    # Relationships) -- same prepare-then-download pattern as
    # 2_Run_Simulation.py, since st.download_button needs its data ready
    # before render.
    engine_param = "deterministic" if st.session_state["compare_last_engine"] == "Deterministic" else "simulated"
    if st.button(
        "Prepare CSV download",
        key="compare_prepare_csv_button",
        help="Fetches this comparison's full results as CSV, ready to download below.",
    ):
        try:
            st.session_state["compare_csv_text"] = export_comparison_csv(st.session_state["compare_last_body"], engine=engine_param)
        except RpUiError as err:
            st.error(str(err))
    if "compare_csv_text" in st.session_state:
        st.download_button(
            "Download CSV",
            data=st.session_state["compare_csv_text"],
            file_name="comparison.csv",
            mime="text/csv",
            key="compare_download_csv_button",
            help="Saves this comparison's full per-candidate results to a CSV file.",
        )
