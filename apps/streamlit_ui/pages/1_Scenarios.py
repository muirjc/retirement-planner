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
    "member1_full_retirement_age": 67.0,
    "member2_person_name": "",
    "member2_current_age": 60,
    "member2_ss_claim_age": 67,
    "member2_ss_annual_benefit": 0.0,
    "member2_full_retirement_age": 67.0,
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
    "include_inherited_ira": False,
    "inherited_account_type": "traditional",
    "inherited_owner": None,
    "inherited_account_id": "",
    "inherited_balance": 0.0,
    "inherited_death_year": 2020,
    "inherited_decedent_age_at_death": 75,
    "inherited_decedent_was_taking_rmds": True,
    "inherited_beneficiary_relationship": "other_individual",
    "inherited_beneficiary_classification": "non_eligible_designated_beneficiary",
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
    # 016-ss-claiming-age-actuarial-adjustment: a scenario saved before this
    # feature (or via a non-UI client that omitted it) still resolves to a
    # concrete float server-side (parse_scenario()'s own default), so this
    # key is never missing from a get_scenario()-shaped response -- no
    # `.get(..., fallback)` needed, unlike a field this UI predates entirely.
    st.session_state["member1_full_retirement_age"] = m1["full_retirement_age"]
    if len(members) > 1:
        m2 = members[1]
        st.session_state["member2_person_name"] = m2["person_name"]
        st.session_state["member2_current_age"] = m2["current_age"]
        st.session_state["member2_ss_claim_age"] = m2["ss_claim_age"]
        st.session_state["member2_ss_annual_benefit"] = m2["ss_annual_benefit"]
        st.session_state["member2_full_retirement_age"] = m2["full_retirement_age"]
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
        if account.get("inherited"):
            continue  # 012-inherited-ira-rmd: handled separately below, never
            # folded into a member's own ordinary balance -- an inherited
            # account is never legally commingled with the beneficiary's own
            # account (research.md §5), so it must not double-count here.
        owner = account.get("owner")
        if owner in member_names:
            balances_by_owner[(account["account_type"], owner)] = account["balance"]
    for index, person_name in enumerate(member_names, start=1):
        for account_type in ("traditional", "roth", "taxable"):
            st.session_state[f"member{index}_{account_type}_balance"] = balances_by_owner.get(
                (account_type, person_name), 0.0
            )

    # 012-inherited-ira-rmd: this form supports at most one inherited
    # account (mirrors this page's other fixed-shape conventions -- see
    # module docstring); the first account carrying an `inherited` block
    # is the one shown here.
    inherited_account = next((a for a in scenario["accounts"] if a.get("inherited")), None)
    st.session_state["include_inherited_ira"] = inherited_account is not None
    if inherited_account is not None:
        st.session_state["inherited_account_type"] = inherited_account["account_type"]
        st.session_state["inherited_owner"] = inherited_account.get("owner") or ""
        st.session_state["inherited_account_id"] = inherited_account.get("account_id") or ""
        st.session_state["inherited_balance"] = inherited_account["balance"]
        inherited = inherited_account["inherited"]
        st.session_state["inherited_death_year"] = inherited["death_year"]
        st.session_state["inherited_decedent_age_at_death"] = inherited["decedent_age_at_death"]
        st.session_state["inherited_decedent_was_taking_rmds"] = inherited["decedent_was_taking_rmds"]
        st.session_state["inherited_beneficiary_relationship"] = inherited["beneficiary_relationship"]
        st.session_state["inherited_beneficiary_classification"] = inherited["beneficiary_classification"]
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
    selected_name = st.selectbox(
        "Saved scenarios",
        options=[""] + existing_names,
        key="scenario_load_select",
        help="Pick a previously saved scenario, then Load to populate the form below with its data, or Delete to remove it.",
    )
    if st.button(
        "Load", key="load_button", help="Replaces everything in the form below with the selected scenario's saved data."
    ) and selected_name:
        try:
            scenario = get_scenario(selected_name)
        except ScenarioNotFoundError:
            st.error("This scenario no longer exists -- it may have been removed elsewhere.")
        except BackendUnreachableError as err:
            st.error(str(err))
        else:
            _apply_scenario_to_form(scenario)
with delete_col:
    if st.button(
        "Delete selected",
        key="delete_button",
        help="Permanently removes the selected saved scenario. Doesn't affect the form below.",
    ) and selected_name:
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
st.text_input(
    "Scenario name",
    key="scenario_name",
    help="A short name to save this scenario under. Saving again under the same name completely overwrites it.",
)

st.subheader("Household")
st.selectbox(
    "Filing status",
    options=["single", "married_filing_jointly"],
    key="filing_status",
    help=(
        "`single` -- one person, only Member 1 below. "
        "`married_filing_jointly` -- two people; Member 2's fields and account balances appear "
        "below once selected. See the Instructions page's Household section for more."
    ),
)

_NAME_HELP = "This person's name or a short label -- used to identify them elsewhere (account owner, Roth conversion candidate, inherited-IRA beneficiary)."
_CURRENT_AGE_HELP = "Their age today, as of right now -- not a future planning age."
_SS_CLAIM_AGE_HELP = "The age they plan to start claiming Social Security, between 62 and 70."
_SS_BENEFIT_HELP = (
    "Their Primary Insurance Amount (PIA) -- the annual Social Security benefit payable **at full "
    "retirement age**, not the (possibly reduced or increased) amount actually paid at the claim age "
    "entered here. See the Instructions page's Household section."
)
_FRA_HELP = (
    "Their Social Security full retirement age (FRA) -- typically 66-67 depending on birth year. "
    "Claiming before this reduces the benefit below the PIA; claiming after it (up to 70) increases "
    "the benefit above the PIA."
)

st.markdown("**Member 1**")
c1, c2, c3, c4, c5 = st.columns(5)
c1.text_input("Name", key="member1_person_name", help=_NAME_HELP)
c2.number_input("Current age", min_value=0, step=1, key="member1_current_age", help=_CURRENT_AGE_HELP)
c3.number_input("SS claim age", min_value=0, step=1, key="member1_ss_claim_age", help=_SS_CLAIM_AGE_HELP)
c4.number_input(
    "SS benefit at FRA ($)", min_value=0.0, step=100.0, key="member1_ss_annual_benefit", help=_SS_BENEFIT_HELP
)
c5.number_input(
    "Full retirement age", min_value=0.0, step=1.0, key="member1_full_retirement_age", help=_FRA_HELP
)

if st.session_state["filing_status"] == "married_filing_jointly":
    st.markdown("**Member 2**")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.text_input("Name", key="member2_person_name", help=_NAME_HELP)
    c2.number_input("Current age", min_value=0, step=1, key="member2_current_age", help=_CURRENT_AGE_HELP)
    c3.number_input("SS claim age", min_value=0, step=1, key="member2_ss_claim_age", help=_SS_CLAIM_AGE_HELP)
    c4.number_input(
        "SS benefit at FRA ($)", min_value=0.0, step=100.0, key="member2_ss_annual_benefit", help=_SS_BENEFIT_HELP
    )
    c5.number_input(
        "Full retirement age", min_value=0.0, step=1.0, key="member2_full_retirement_age", help=_FRA_HELP
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
_TRADITIONAL_HELP = "This person's own pre-tax IRA/401(k) balance. Entered per person, never combined with a spouse's."
_ROTH_HELP = "This person's own Roth IRA/401(k) balance."
_TAXABLE_HELP = "This person's own ordinary (non-retirement) brokerage or savings balance."

member1_label = st.session_state["member1_person_name"] or "Member 1"
st.markdown(f"**{member1_label}**")
a1, a2, a3 = st.columns(3)
a1.number_input("Traditional balance ($)", step=1000.0, key="member1_traditional_balance", help=_TRADITIONAL_HELP)
a2.number_input("Roth balance ($)", step=1000.0, key="member1_roth_balance", help=_ROTH_HELP)
a3.number_input("Taxable balance ($)", step=1000.0, key="member1_taxable_balance", help=_TAXABLE_HELP)

if st.session_state["filing_status"] == "married_filing_jointly":
    member2_label = st.session_state["member2_person_name"] or "Member 2"
    st.markdown(f"**{member2_label}**")
    a1, a2, a3 = st.columns(3)
    a1.number_input("Traditional balance ($)", step=1000.0, key="member2_traditional_balance", help=_TRADITIONAL_HELP)
    a2.number_input("Roth balance ($)", step=1000.0, key="member2_roth_balance", help=_ROTH_HELP)
    a3.number_input("Taxable balance ($)", step=1000.0, key="member2_taxable_balance", help=_TAXABLE_HELP)

st.subheader("Inherited IRA (optional)")
# 012-inherited-ira-rmd: a separate, always-independent account from the
# ordinary per-member balances above (never pooled with them -- see
# module docstring's equivalent note in _apply_scenario_to_form()).
# This form supports at most one inherited account, mirroring every
# other optional block on this page (Roth conversion below) -- a
# beneficiary with more than one inherited account still needs to edit
# the scenario's YAML/API directly for the second one.
def _seed_inherited_ira_defaults() -> None:
    """Streamlit gotcha workaround: a widget that's *conditionally
    revealed for the first time on the same rerun that flips its gating
    checkbox* does not reliably pick up a value pre-seeded via a plain
    st.session_state.setdefault() earlier in the script -- it silently
    falls back to its own constructor default (False / first option)
    instead, even when an explicit value=/index= is also passed. A
    value written from an on_change callback (which runs before the
    main script body, in the phase Streamlit's widget machinery expects
    state mutations to happen in) is honored correctly. Only forces
    fresh defaults on the check transition -- unchecking then
    re-checking intentionally resets the sub-fields rather than trying
    to preserve a half-entered, hidden state."""
    if st.session_state["include_inherited_ira"]:
        st.session_state["inherited_account_type"] = "traditional"
        st.session_state["inherited_owner"] = ""  # blank placeholder -- see selectbox's own comment below
        st.session_state["inherited_account_id"] = ""
        st.session_state["inherited_balance"] = 0.0
        st.session_state["inherited_death_year"] = 2020
        st.session_state["inherited_decedent_age_at_death"] = 75
        st.session_state["inherited_decedent_was_taking_rmds"] = True
        st.session_state["inherited_beneficiary_relationship"] = "other_individual"
        st.session_state["inherited_beneficiary_classification"] = "non_eligible_designated_beneficiary"


st.checkbox(
    "Include an inherited IRA",
    key="include_inherited_ira",
    on_change=_seed_inherited_ira_defaults,
    help=(
        "A traditional or Roth account inherited from an original owner is computed by this "
        "tool -- covering the owner-died-on/after-RBD case, the owner-died-before-RBD case, "
        "and both non-eligible and eligible designated beneficiaries. See the Instructions "
        "page's Inherited IRA section for what each field below means and the one case still "
        "not supported (a trust or entity beneficiary)."
    ),
)
if st.session_state["include_inherited_ira"]:
    # Explicit blank placeholder, matching State/Conversion strategy's
    # own established convention -- forces an active choice (important
    # for who a beneficiary is) rather than trying to pre-select a
    # "likely" member, which also sidesteps a Streamlit quirk where a
    # freshly-revealed selectbox's session_state-seeded value doesn't
    # reliably resolve against an explicit index= (see
    # _seed_inherited_ira_defaults()'s docstring for the general issue).
    inherited_owner_options = [""] + [st.session_state["member1_person_name"]]
    if st.session_state["filing_status"] == "married_filing_jointly":
        inherited_owner_options.append(st.session_state["member2_person_name"])

    i0, i1, i2 = st.columns(3)
    i0.selectbox(
        "Account type",
        options=["traditional", "roth"],
        key="inherited_account_type",
        help=(
            "A Roth account's original owner is always treated as having died before their "
            "own Required Beginning Date (RBD), regardless of the checkbox below -- Roth "
            "owners never have RMDs during their own lifetime."
        ),
    )
    i1.selectbox(
        "Beneficiary",
        options=inherited_owner_options,
        key="inherited_owner",
        help="Which household member inherited this account -- they're the one it's taxed to.",
    )
    i2.number_input(
        "Balance ($)",
        step=1000.0,
        key="inherited_balance",
        help="The inherited account's own balance -- tracked entirely separately from this person's ordinary Traditional balance above.",
    )

    i3, i4 = st.columns(2)
    i3.number_input(
        "Decedent's death year",
        min_value=1900,
        step=1,
        key="inherited_death_year",
        help="The calendar year the original account owner died.",
    )
    i4.number_input(
        "Decedent's age at death",
        min_value=0,
        step=1,
        key="inherited_decedent_age_at_death",
        help="Their age in the death year above -- drives the required-distribution divisor.",
    )

    st.checkbox(
        "Original owner had already begun their own RMDs before death",
        key="inherited_decedent_was_taking_rmds",
        help=(
            "Ignored entirely for a Roth account above (always treated as unchecked -- see "
            "its own help text). For a traditional account: checked means the owner was "
            "already in RMD status (\"post-RBD\") -- an eligible designated beneficiary's "
            "annual amount is then based on the longer of their own or the owner's "
            "remaining life expectancy. Unchecked (\"pre-RBD\") means no annual distribution "
            "is required at all for a non-eligible designated beneficiary (only a year-10 "
            "full-depletion deadline), and an eligible designated beneficiary's own annual "
            "amount is based on their life expectancy alone."
        ),
    )

    i5, i6 = st.columns(2)
    i5.selectbox(
        "Beneficiary relationship",
        options=["spouse", "minor_child", "other_individual", "trust_or_entity"],
        key="inherited_beneficiary_relationship",
        help=(
            "`trust_or_entity` blocks the scenario -- not yet supported. `minor_child` "
            "(alongside classification `eligible_designated_beneficiary_other`) converts to "
            "the 10-year rule once the beneficiary turns 21, using a fresh 10-year clock from "
            "that year -- otherwise, only used to enforce that combination."
        ),
    )
    i6.selectbox(
        "Beneficiary classification",
        options=[
            "non_eligible_designated_beneficiary",
            "eligible_designated_beneficiary_spouse",
            "eligible_designated_beneficiary_other",
        ],
        key="inherited_beneficiary_classification",
        help=(
            "`non_eligible_designated_beneficiary` -- the SECURE 2.0 10-year rule (most "
            "non-spouse beneficiaries). `eligible_designated_beneficiary_spouse` / `_other` -- "
            "an annual life-expectancy \"stretch\" instead (spouse, minor child, disabled/"
            "chronically ill, or someone not more than 10 years younger than the owner); a "
            "spouse's own amount is recalculated fresh every year, a non-spouse's is reduced "
            "by 1.0 each year from an initial lookup. See the Instructions page for the full "
            "explanation of each case."
        ),
    )

st.subheader("Spending")
st.number_input(
    "Annual spending need ($, today's dollars)",
    step=1000.0,
    key="annual_need_real",
    help="Your planned annual spending in today's dollars, before taxes. See the Instructions page's Spending section.",
)

st.subheader("State")
state_options = [""] + states
current_state = st.session_state.get("state") or ""
state_index = state_options.index(current_state) if current_state in state_options else 0
st.selectbox(
    "State",
    options=state_options,
    index=state_index,
    key="state",
    help=(
        "The state you plan to reside in for tax purposes. States differ in whether they tax "
        "income at all, flat vs. graduated brackets, and whether retirees get an age-based "
        "exclusion -- see the Instructions page's State section for details."
    ),
)

st.subheader("Market assumptions")
# These are your own forward-looking planning inputs, not something the
# tool looks up (see the Instructions page's Market Assumptions section)
# -- every help text below explains what the number means, not what
# value to use.
m1, m2 = st.columns(2)
with m1:
    st.number_input(
        "Equity allocation",
        min_value=0.0,
        max_value=1.0,
        key="equity_allocation",
        help="Fraction of the portfolio in equities, 0 to 1 (e.g. 0.6 = 60% stocks). Together with Bond allocation, should sum to 1.",
    )
    st.number_input(
        "Equity return mean (real)",
        key="equity_return_mean_real",
        help="Expected average annual equity return, inflation-adjusted (real), as a decimal (e.g. 0.05 = 5%).",
    )
    st.number_input(
        "Equity return std (real)",
        key="equity_return_std_real",
        help="Expected annual volatility (standard deviation) of equity returns, inflation-adjusted.",
    )
    st.number_input(
        "Correlation",
        min_value=-1.0,
        max_value=1.0,
        key="correlation",
        help="Correlation between equity and bond returns, -1 to 1. 0 means uncorrelated.",
    )
with m2:
    st.number_input(
        "Bond allocation",
        min_value=0.0,
        max_value=1.0,
        key="bond_allocation",
        help="Fraction of the portfolio in bonds, 0 to 1. Together with Equity allocation, should sum to 1.",
    )
    st.number_input(
        "Bond return mean (real)",
        key="bond_return_mean_real",
        help="Expected average annual bond return, inflation-adjusted (real), as a decimal.",
    )
    st.number_input(
        "Bond return std (real)",
        key="bond_return_std_real",
        help="Expected annual volatility (standard deviation) of bond returns, inflation-adjusted.",
    )

st.subheader("Simulation settings")
s1, s2, s3 = st.columns(3)
s1.number_input(
    "Paths",
    min_value=1,
    step=100,
    key="n_paths",
    help="How many randomized future paths to simulate by default. More paths give a smoother, more stable success-rate estimate at the cost of a slower run.",
)
s2.number_input(
    "Seed",
    min_value=0,
    step=1,
    key="seed",
    help="Fixes the randomness so re-running with the same inputs reproduces the same result.",
)
s3.number_input(
    "Plan to age",
    min_value=1,
    step=1,
    key="plan_to_age",
    help="The horizon this scenario's simulations run until by default -- not a prediction of how long you'll live.",
)

st.subheader("Roth conversion (optional)")
st.checkbox(
    "Include a Roth conversion strategy",
    key="include_roth_conversion",
    help="Leave unchecked if you don't plan to convert traditional balances to Roth. See the Instructions page's Roth Conversion section.",
)
if st.session_state["include_roth_conversion"]:
    strategy_options = [""] + conversion_strategies
    current_strategy = st.session_state.get("conversion_strategy") or ""
    strategy_index = strategy_options.index(current_strategy) if current_strategy in strategy_options else 0
    st.selectbox(
        "Conversion strategy",
        options=strategy_options,
        index=strategy_index,
        key="conversion_strategy",
        help=(
            "`fill_to_bracket` -- converts just enough each year to reach the income ceiling "
            "you set below, without going over. `fixed_amount` -- converts that same flat "
            "dollar amount every year, regardless of income. See the Instructions page's Roth "
            "Conversion section for the full explanation."
        ),
    )
    st.number_input(
        "Bracket ceiling or amount ($)",
        key="conversion_bracket_ceiling_or_amount",
        help=(
            "For `fill_to_bracket`: the income ceiling in dollars to fill up to. "
            "For `fixed_amount`: the flat dollar amount to convert each year."
        ),
    )
    w1, w2 = st.columns(2)
    _WINDOW_HELP = (
        "The plan years (1 = the scenario's first plan year) during which this conversion "
        "strategy is active -- outside this window, no conversions happen, regardless of strategy."
    )
    w1.number_input("Window start (plan year)", min_value=0, step=1, key="conversion_window_start", help=_WINDOW_HELP)
    w2.number_input("Window end (plan year)", min_value=0, step=1, key="conversion_window_end", help=_WINDOW_HELP)


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
                    "full_retirement_age": st.session_state["member1_full_retirement_age"],
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
                "full_retirement_age": st.session_state["member2_full_retirement_age"],
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
    if st.session_state["include_inherited_ira"]:
        inherited_account = {
            "account_type": st.session_state["inherited_account_type"],
            "balance": st.session_state["inherited_balance"],
            "owner": st.session_state["inherited_owner"],
            "inherited": {
                "death_year": st.session_state["inherited_death_year"],
                "decedent_age_at_death": st.session_state["inherited_decedent_age_at_death"],
                "decedent_was_taking_rmds": st.session_state["inherited_decedent_was_taking_rmds"],
                "beneficiary_relationship": st.session_state["inherited_beneficiary_relationship"],
                "beneficiary_classification": st.session_state["inherited_beneficiary_classification"],
            },
        }
        if st.session_state["inherited_account_id"]:
            inherited_account["account_id"] = st.session_state["inherited_account_id"]
        body["accounts"].append(inherited_account)
    return body


st.divider()
save_col, validate_col = st.columns(2)

with save_col:
    if st.button(
        "Save", key="save_button", help="Saves the form above under Scenario name, overwriting any existing scenario with that name."
    ):
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
    if st.button(
        "Validate", key="validate_button", help="Checks the form above for problems without saving it."
    ):
        try:
            result = validate_scenario(st.session_state["scenario_name"], _build_body())
        except InvalidScenarioError as err:
            st.error(err.reason)
        except BackendUnreachableError as err:
            st.error(str(err))
        else:
            _render_flags(result.get("validation_flags", []))
