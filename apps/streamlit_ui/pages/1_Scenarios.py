"""Scenario management (User Story 1, contracts/ui-pages.md §
1_Scenarios.py). Create/view/edit/save/delete a named scenario, with
inline validation feedback and backend-driven selection options
(FR-001-FR-005).

Household member count is fixed to 1 (single) or 2 (married_filing_jointly)
by 001's own Scenario.household rule (FR-013 of 001), so this form shows a
second member's fields only when filing_status is married -- there is no
free-form add/remove list to build here. Accounts are fixed to exactly one
balance per account type per household member (traditional/roth/taxable),
mirroring that same fixed-shape convention -- a scenario with two
"traditional" accounts *for the same person* is not a case this form needs
to support (011-per-owner-accounts). Each account's owner is therefore
structural, not a free-text or dropdown field: a balance entered in
member 1's row is always submitted with member 1's person_name as its
owner, and likewise for member 2 -- an invalid owner is impossible to
enter, not merely disallowed by a validator (contracts/ui-pages.md).
"""

import streamlit as st

from rp_ui.api_client import (
    delete_scenario,
    get_scenario,
    list_conversion_strategies,
    list_scenarios,
    list_states,
    put_scenario,
    validate_scenario,
)
from rp_ui.errors import BackendUnreachableError, InvalidScenarioError, RpUiError, ScenarioNotFoundError

st.set_page_config(page_title="Scenarios -- Retirement Planner", page_icon="\U0001f4dd")
st.title("Scenarios")

DEFAULTS = {
    "scenario_name": "",
    "filing_status": "single",
    "member1_person_name": "",
    "member1_current_age": 60,
    "member1_ss_claim_age": 67,
    "member1_ss_annual_benefit": 0.0,
    "member2_person_name": "",
    "member2_current_age": 60,
    "member2_ss_claim_age": 67,
    "member2_ss_annual_benefit": 0.0,
    "member1_traditional_balance": 0.0,
    "member1_roth_balance": 0.0,
    "member1_taxable_balance": 0.0,
    "member2_traditional_balance": 0.0,
    "member2_roth_balance": 0.0,
    "member2_taxable_balance": 0.0,
    "annual_need_real": 0.0,
    "state": None,
    "equity_allocation": 0.6,
    "equity_return_mean_real": 0.05,
    "equity_return_std_real": 0.18,
    "bond_allocation": 0.4,
    "bond_return_mean_real": 0.02,
    "bond_return_std_real": 0.06,
    "correlation": 0.0,
    "n_paths": 1000,
    "seed": 42,
    "plan_to_age": 95,
    "include_roth_conversion": False,
    "conversion_strategy": None,
    "conversion_bracket_ceiling_or_amount": 0.0,
    "conversion_window_start": 0,
    "conversion_window_end": 0,
}


def _apply_scenario_to_form(scenario: dict) -> None:
    """Populates every widget key's session_state entry from a
    get_scenario()-shaped response, BEFORE any widget with that key is
    instantiated this run (must happen at the top of the script -- see
    module docstring)."""
    st.session_state["scenario_name"] = scenario["name"]
    st.session_state["filing_status"] = scenario["household"]["filing_status"]
    members = scenario["household"]["members"]
    m1 = members[0]
    st.session_state["member1_person_name"] = m1["person_name"]
    st.session_state["member1_current_age"] = m1["current_age"]
    st.session_state["member1_ss_claim_age"] = m1["ss_claim_age"]
    st.session_state["member1_ss_annual_benefit"] = m1["ss_annual_benefit"]
    if len(members) > 1:
        m2 = members[1]
        st.session_state["member2_person_name"] = m2["person_name"]
        st.session_state["member2_current_age"] = m2["current_age"]
        st.session_state["member2_ss_claim_age"] = m2["ss_claim_age"]
        st.session_state["member2_ss_annual_benefit"] = m2["ss_annual_benefit"]
    # 011-per-owner-accounts: match each account to a member row by
    # (account_type, owner) against the members just loaded above. An
    # account whose owner is None or doesn't match either member (a
    # multi-member scenario saved before this feature, or a stale
    # reference after a rename) is deliberately left out of every row --
    # its balance is not guessed into a row it may not belong to
    # (contracts/ui-pages.md's "Modified Load existing behavior"); the
    # scenario's own blocking flag (unaffected by this) still surfaces
    # normally on the next Save/Validate.
    member_names = [m["person_name"] for m in members]
    balances_by_owner: dict[tuple[str, str], float] = {}
    for account in scenario["accounts"]:
        owner = account.get("owner")
        if owner in member_names:
            balances_by_owner[(account["account_type"], owner)] = account["balance"]
    for index, person_name in enumerate(member_names, start=1):
        for account_type in ("traditional", "roth", "taxable"):
            st.session_state[f"member{index}_{account_type}_balance"] = balances_by_owner.get(
                (account_type, person_name), 0.0
            )
    st.session_state["annual_need_real"] = scenario["spending"]["annual_need_real"]
    st.session_state["state"] = scenario["state"]
    ma = scenario["market_assumptions"]
    for field in (
        "equity_allocation", "equity_return_mean_real", "equity_return_std_real",
        "bond_allocation", "bond_return_mean_real", "bond_return_std_real", "correlation",
    ):
        st.session_state[field] = ma[field]
    ss = scenario["simulation_settings"]
    st.session_state["n_paths"] = ss["n_paths"]
    st.session_state["seed"] = ss["seed"]
    st.session_state["plan_to_age"] = ss["plan_to_age"]
    rc = scenario.get("roth_conversion")
    st.session_state["include_roth_conversion"] = rc is not None
    if rc is not None:
        st.session_state["conversion_strategy"] = rc["strategy"]
        st.session_state["conversion_bracket_ceiling_or_amount"] = rc["bracket_ceiling_or_amount"]
        st.session_state["conversion_window_start"] = rc["window"][0]
        st.session_state["conversion_window_end"] = rc["window"][1]


def _render_flags(flags: list[dict]) -> None:
    """Inline validation feedback, distinguishing blocking from
    warning-only (Acceptance Scenario US1.2) -- never lets a blocking flag
    read the same as a warning."""
    if not flags:
        st.success("No validation issues -- this scenario is usable.")
        return
    for flag in flags:
        text = f"**{flag['field']}**: {flag['message']}"
        if flag.get("severity") == "blocking":
            st.error(text)
        else:
            st.warning(text)


# -- Load existing (must run before any other widget with these keys renders) --

st.subheader("Load an existing scenario")
try:
    existing_names = list_scenarios()
except RpUiError as err:
    st.error(str(err))
    st.stop()

load_col, delete_col = st.columns(2)
with load_col:
    selected_name = st.selectbox("Saved scenarios", options=[""] + existing_names, key="scenario_load_select")
    if st.button("Load", key="load_button") and selected_name:
        try:
            scenario = get_scenario(selected_name)
        except ScenarioNotFoundError:
            st.error("This scenario no longer exists -- it may have been removed elsewhere.")
        except BackendUnreachableError as err:
            st.error(str(err))
        else:
            _apply_scenario_to_form(scenario)
with delete_col:
    if st.button("Delete selected", key="delete_button") and selected_name:
        try:
            delete_scenario(selected_name)
        except ScenarioNotFoundError:
            st.error("This scenario no longer exists -- it may have been removed elsewhere.")
        except BackendUnreachableError as err:
            st.error(str(err))
        else:
            st.success(f"Deleted {selected_name!r}.")

for key, default in DEFAULTS.items():
    st.session_state.setdefault(key, default)

st.divider()

# -- Reference data needed by selectors below --

try:
    states = list_states()
    conversion_strategies = list_conversion_strategies()
except RpUiError as err:
    st.error(str(err))
    st.stop()

# -- Form -----------------------------------------------------------------

st.subheader("Scenario")
st.text_input("Scenario name", key="scenario_name")

st.subheader("Household")
st.selectbox("Filing status", options=["single", "married_filing_jointly"], key="filing_status")

st.markdown("**Member 1**")
c1, c2, c3, c4 = st.columns(4)
c1.text_input("Name", key="member1_person_name")
c2.number_input("Current age", min_value=0, step=1, key="member1_current_age")
c3.number_input("SS claim age", min_value=0, step=1, key="member1_ss_claim_age")
c4.number_input(
    "SS annual benefit ($)", min_value=0.0, step=100.0, key="member1_ss_annual_benefit"
)

if st.session_state["filing_status"] == "married_filing_jointly":
    st.markdown("**Member 2**")
    c1, c2, c3, c4 = st.columns(4)
    c1.text_input("Name", key="member2_person_name")
    c2.number_input("Current age", min_value=0, step=1, key="member2_current_age")
    c3.number_input("SS claim age", min_value=0, step=1, key="member2_ss_claim_age")
    c4.number_input(
        "SS annual benefit ($)", min_value=0.0, step=100.0, key="member2_ss_annual_benefit"
    )

st.subheader("Accounts")
# 011-per-owner-accounts: one row of account-type fields per household
# member -- owner is structural (module docstring), so member 2's row only
# renders when there is a member 2 to own it.
#
# Currency formatting note: st.number_input's `format` parameter can't
# carry a "$" (or any non-numeric character) in this Streamlit version --
# confirmed via StreamlitInvalidNumberFormatError, see rp_ui/formatting.py's
# module docstring -- so every dollar-amount field below signals its unit
# via a "($)" label suffix instead, the only mechanism that actually works
# for an editable field.
member1_label = st.session_state["member1_person_name"] or "Member 1"
st.markdown(f"**{member1_label}**")
a1, a2, a3 = st.columns(3)
a1.number_input("Traditional balance ($)", step=1000.0, key="member1_traditional_balance")
a2.number_input("Roth balance ($)", step=1000.0, key="member1_roth_balance")
a3.number_input("Taxable balance ($)", step=1000.0, key="member1_taxable_balance")

if st.session_state["filing_status"] == "married_filing_jointly":
    member2_label = st.session_state["member2_person_name"] or "Member 2"
    st.markdown(f"**{member2_label}**")
    a1, a2, a3 = st.columns(3)
    a1.number_input("Traditional balance ($)", step=1000.0, key="member2_traditional_balance")
    a2.number_input("Roth balance ($)", step=1000.0, key="member2_roth_balance")
    a3.number_input("Taxable balance ($)", step=1000.0, key="member2_taxable_balance")

st.subheader("Spending")
st.number_input(
    "Annual spending need ($, today's dollars)", step=1000.0, key="annual_need_real"
)

st.subheader("State")
state_options = [""] + states
current_state = st.session_state.get("state") or ""
state_index = state_options.index(current_state) if current_state in state_options else 0
st.selectbox("State", options=state_options, index=state_index, key="state")

st.subheader("Market assumptions")
m1, m2 = st.columns(2)
with m1:
    st.number_input("Equity allocation", min_value=0.0, max_value=1.0, key="equity_allocation")
    st.number_input("Equity return mean (real)", key="equity_return_mean_real")
    st.number_input("Equity return std (real)", key="equity_return_std_real")
    st.number_input("Correlation", min_value=-1.0, max_value=1.0, key="correlation")
with m2:
    st.number_input("Bond allocation", min_value=0.0, max_value=1.0, key="bond_allocation")
    st.number_input("Bond return mean (real)", key="bond_return_mean_real")
    st.number_input("Bond return std (real)", key="bond_return_std_real")

st.subheader("Simulation settings")
s1, s2, s3 = st.columns(3)
s1.number_input("Paths", min_value=1, step=100, key="n_paths")
s2.number_input("Seed", min_value=0, step=1, key="seed")
s3.number_input("Plan to age", min_value=1, step=1, key="plan_to_age")

st.subheader("Roth conversion (optional)")
st.checkbox("Include a Roth conversion strategy", key="include_roth_conversion")
if st.session_state["include_roth_conversion"]:
    strategy_options = [""] + conversion_strategies
    current_strategy = st.session_state.get("conversion_strategy") or ""
    strategy_index = strategy_options.index(current_strategy) if current_strategy in strategy_options else 0
    st.selectbox("Conversion strategy", options=strategy_options, index=strategy_index, key="conversion_strategy")
    st.number_input("Bracket ceiling or amount ($)", key="conversion_bracket_ceiling_or_amount")
    w1, w2 = st.columns(2)
    w1.number_input("Window start (plan year)", min_value=0, step=1, key="conversion_window_start")
    w2.number_input("Window end (plan year)", min_value=0, step=1, key="conversion_window_end")


def _build_body() -> dict:
    body = {
        "household": {
            "filing_status": st.session_state["filing_status"],
            "members": [
                {
                    "person_name": st.session_state["member1_person_name"],
                    "current_age": st.session_state["member1_current_age"],
                    "ss_claim_age": st.session_state["member1_ss_claim_age"],
                    "ss_annual_benefit": st.session_state["member1_ss_annual_benefit"],
                }
            ],
        },
        "accounts": [
            {
                "account_type": "traditional",
                "balance": st.session_state["member1_traditional_balance"],
                "owner": st.session_state["member1_person_name"],
            },
            {
                "account_type": "roth",
                "balance": st.session_state["member1_roth_balance"],
                "owner": st.session_state["member1_person_name"],
            },
            {
                "account_type": "taxable",
                "balance": st.session_state["member1_taxable_balance"],
                "owner": st.session_state["member1_person_name"],
            },
        ],
        "spending": {"annual_need_real": st.session_state["annual_need_real"]},
        "state": st.session_state["state"],
        "market_assumptions": {
            "equity_allocation": st.session_state["equity_allocation"],
            "equity_return_mean_real": st.session_state["equity_return_mean_real"],
            "equity_return_std_real": st.session_state["equity_return_std_real"],
            "bond_allocation": st.session_state["bond_allocation"],
            "bond_return_mean_real": st.session_state["bond_return_mean_real"],
            "bond_return_std_real": st.session_state["bond_return_std_real"],
            "correlation": st.session_state["correlation"],
        },
        "simulation_settings": {
            "n_paths": st.session_state["n_paths"],
            "seed": st.session_state["seed"],
            "plan_to_age": st.session_state["plan_to_age"],
        },
        "roth_conversion": None,
    }
    if st.session_state["filing_status"] == "married_filing_jointly":
        body["household"]["members"].append(
            {
                "person_name": st.session_state["member2_person_name"],
                "current_age": st.session_state["member2_current_age"],
                "ss_claim_age": st.session_state["member2_ss_claim_age"],
                "ss_annual_benefit": st.session_state["member2_ss_annual_benefit"],
            }
        )
        body["accounts"].extend(
            [
                {
                    "account_type": "traditional",
                    "balance": st.session_state["member2_traditional_balance"],
                    "owner": st.session_state["member2_person_name"],
                },
                {
                    "account_type": "roth",
                    "balance": st.session_state["member2_roth_balance"],
                    "owner": st.session_state["member2_person_name"],
                },
                {
                    "account_type": "taxable",
                    "balance": st.session_state["member2_taxable_balance"],
                    "owner": st.session_state["member2_person_name"],
                },
            ]
        )
    if st.session_state["include_roth_conversion"]:
        body["roth_conversion"] = {
            "strategy": st.session_state["conversion_strategy"],
            "bracket_ceiling_or_amount": st.session_state["conversion_bracket_ceiling_or_amount"],
            "window": [st.session_state["conversion_window_start"], st.session_state["conversion_window_end"]],
        }
    return body


st.divider()
save_col, validate_col = st.columns(2)

with save_col:
    if st.button("Save", key="save_button"):
        try:
            saved = put_scenario(st.session_state["scenario_name"], _build_body())
        except InvalidScenarioError as err:
            st.error(err.reason)
        except BackendUnreachableError as err:
            st.error(str(err))
        else:
            st.success(f"Saved {saved['name']!r}.")
            _render_flags(saved.get("validation_flags", []))

with validate_col:
    if st.button("Validate", key="validate_button"):
        try:
            result = validate_scenario(st.session_state["scenario_name"], _build_body())
        except InvalidScenarioError as err:
            st.error(err.reason)
        except BackendUnreachableError as err:
            st.error(str(err))
        else:
            _render_flags(result.get("validation_flags", []))
