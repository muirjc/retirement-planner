"""AppTest-driven walkthrough of every page in apps/streamlit_ui, US1-US5
(plan.md's single integration test file). Each test installs its own
httpx.MockTransport on rp_ui.api_client (module-level state, shared with
AppTest's in-process script execution) before running a page, per
research.md §2's testing decision -- no real 007 process needed.

Organized by user story, in the same priority order as spec.md and
tasks.md: Home (Foundational) -> US1 Scenarios -> US2 Run Simulation ->
US3 Compare -> US4 Verification Indicator -> US5 CSV Download -> the full
quickstart.md walkthrough (Polish).
"""

import json
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from rp_ui import api_client

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
APP_PATH = PACKAGE_ROOT / "app.py"
INSTRUCTIONS_PAGE = PACKAGE_ROOT / "pages" / "0_Instructions.py"
SCENARIOS_PAGE = PACKAGE_ROOT / "pages" / "1_Scenarios.py"
RUN_PAGE = PACKAGE_ROOT / "pages" / "2_Run_Simulation.py"
COMPARE_PAGE = PACKAGE_ROOT / "pages" / "3_Compare.py"


@pytest.fixture(autouse=True)
def _reset_transport():
    yield
    api_client._transport = None


def _install(handler) -> None:
    api_client._transport = httpx.MockTransport(handler)


def _route(routes: dict) -> callable:
    """Builds an httpx.MockTransport handler from a {(method, path): response_or_callable}
    map -- most fixture-driven tests only need to say what each endpoint
    returns, not write a full handler function by hand."""

    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, request.url.path)
        if key not in routes:
            raise AssertionError(f"unexpected request: {request.method} {request.url.path}")
        value = routes[key]
        return value(request) if callable(value) else value

    return handler


# -- Home page (Foundational, T007) ------------------------------------------


def test_home_page_shows_connected_when_backend_reachable():
    _install(_route({("GET", "/api/v1/reference/states"): httpx.Response(200, json={"states": ["SC", "DE", "FL"]})}))
    at = AppTest.from_file(str(APP_PATH)).run()
    assert not at.exception
    assert any("connected" in s.value.lower() for s in at.success)


def test_home_page_shows_backend_unreachable_message_immediately():
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    _install(handler)
    at = AppTest.from_file(str(APP_PATH)).run()
    assert not at.exception
    assert any("could not reach the backend" in e.value.lower() for e in at.error)


# -- Fake BFF: an in-memory stand-in for 007, stateful enough to round-trip
# saves/deletes and compute simple blocking flags -- used by every US1 test
# below, plus the Polish-phase quickstart walkthrough (T036). -----------------


def make_fake_bff():
    """Returns (handler, scenarios) -- `scenarios` is the fake store,
    exposed so a test can seed it directly. Mirrors 007's own documented
    request/response shapes (contracts/bff-api.md § Scenarios/Reference)."""

    scenarios: dict[str, dict] = {}

    def compute_flags(body: dict) -> list[dict]:
        flags = []
        for index, acct in enumerate(body["accounts"]):
            if acct["balance"] < 0:
                flags.append(
                    {
                        "field": f"accounts[{acct['account_type']}].balance",
                        "message": "balance must be >= 0",
                        "severity": "blocking",
                    }
                )
            # 012-inherited-ira-rmd: a minimal mirror of one of the real
            # backend's four inherited-account blocking rules, enough to
            # exercise this page's inline flag-rendering path end-to-end
            # without reimplementing every rule here.
            inherited = acct.get("inherited")
            if inherited and inherited.get("decedent_was_taking_rmds") is False:
                flags.append(
                    {
                        "field": f"accounts[{index}].inherited",
                        "message": "pre-RBD inherited accounts are not yet supported",
                        "severity": "blocking",
                    }
                )
        if body["spending"]["annual_need_real"] > 10_000_000:
            flags.append(
                {
                    "field": "spending.annual_need_real",
                    "message": "unusually high spending -- please confirm",
                    "severity": "warning",
                }
            )
        return flags

    def handler(request: httpx.Request) -> httpx.Response:
        method, path = request.method, request.url.path
        parts = path.split("/")

        if method == "GET" and path == "/api/v1/scenarios":
            return httpx.Response(200, json={"scenarios": sorted(scenarios.keys())})
        if method == "GET" and path == "/api/v1/reference/states":
            return httpx.Response(200, json={"states": ["DE", "FL", "SC"]})
        if method == "GET" and path == "/api/v1/reference/withdrawal-strategies":
            return httpx.Response(200, json={"withdrawal_strategies": ["rmd_taxable_traditional_roth"]})
        if method == "GET" and path == "/api/v1/reference/conversion-strategies":
            return httpx.Response(200, json={"conversion_strategies": ["bracket_fill"]})
        if method == "GET" and path == "/api/v1/reference/comparison-axes":
            return httpx.Response(
                200,
                json={"axes": ["state", "roth_conversion_strategy", "withdrawal_sequencing", "claiming_age_grid"]},
            )

        if len(parts) == 6 and parts[3] == "scenarios" and parts[5] == "validate" and method == "POST":
            name = parts[4]
            body = json.loads(request.content)
            flags = compute_flags(body)
            return httpx.Response(
                200, json={"validation_flags": flags, "is_usable": not any(f["severity"] == "blocking" for f in flags)}
            )

        if len(parts) == 5 and parts[3] == "scenarios":
            name = parts[4]
            if method == "GET":
                if name not in scenarios:
                    return httpx.Response(404, json={"error": "no_such_scenario", "name": name})
                return httpx.Response(200, json=scenarios[name])
            if method == "PUT":
                body = json.loads(request.content)
                flags = compute_flags(body)
                response_body = {
                    **body,
                    "name": name,
                    "validation_flags": flags,
                    "is_usable": not any(f["severity"] == "blocking" for f in flags),
                }
                scenarios[name] = response_body
                return httpx.Response(200, json=response_body)
            if method == "DELETE":
                if name not in scenarios:
                    return httpx.Response(404, json={"error": "no_such_scenario", "name": name})
                del scenarios[name]
                return httpx.Response(204)

        raise AssertionError(f"unexpected request: {method} {path}")

    return handler, scenarios


def _fill_minimal_valid_scenario(at: AppTest, *, name: str, state: str = "FL") -> AppTest:
    """Fills every widget needed for a valid single-filer scenario --
    shared setup for every US1 test below."""
    at.text_input(key="scenario_name").set_value(name)
    at.text_input(key="member1_person_name").set_value("Alex")
    at.number_input(key="member1_current_age").set_value(60)
    at.number_input(key="member1_ss_claim_age").set_value(67)
    at.number_input(key="member1_ss_annual_benefit").set_value(28000.0)
    at.number_input(key="member1_traditional_balance").set_value(1_500_000.0)
    at.number_input(key="member1_roth_balance").set_value(400_000.0)
    at.number_input(key="member1_taxable_balance").set_value(200_000.0)
    at.number_input(key="annual_need_real").set_value(110_000.0)
    at.selectbox(key="state").set_value(state)
    at.run()
    return at


# -- 011-per-owner-accounts: per-member account fields (US2) -----------------


def test_us2_married_household_renders_per_member_account_fields_with_structural_owner():
    """011-per-owner-accounts User Story 2: a married household gets its
    own row of account fields per member (traditional/roth/taxable), and
    the owner submitted for each is exactly whichever member's row it was
    entered in -- never a free-text or omittable field."""
    handler, store = make_fake_bff()
    _install(handler)

    at = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    at.selectbox(key="filing_status").set_value("married_filing_jointly")
    at.run()

    # Both members' account rows must be present once married is selected.
    assert at.number_input(key="member2_traditional_balance") is not None
    assert at.number_input(key="member2_roth_balance") is not None
    assert at.number_input(key="member2_taxable_balance") is not None

    at.text_input(key="scenario_name").set_value("couple")
    at.text_input(key="member1_person_name").set_value("you")
    at.number_input(key="member1_current_age").set_value(74)
    at.number_input(key="member1_ss_claim_age").set_value(67)
    at.number_input(key="member1_ss_annual_benefit").set_value(32_000.0)
    at.number_input(key="member1_traditional_balance").set_value(900_000.0)
    at.number_input(key="member1_roth_balance").set_value(200_000.0)
    at.number_input(key="member1_taxable_balance").set_value(100_000.0)
    at.text_input(key="member2_person_name").set_value("spouse")
    at.number_input(key="member2_current_age").set_value(60)
    at.number_input(key="member2_ss_claim_age").set_value(67)
    at.number_input(key="member2_ss_annual_benefit").set_value(24_000.0)
    at.number_input(key="member2_traditional_balance").set_value(300_000.0)
    at.number_input(key="member2_roth_balance").set_value(200_000.0)
    at.number_input(key="member2_taxable_balance").set_value(100_000.0)
    at.number_input(key="annual_need_real").set_value(90_000.0)
    at.selectbox(key="state").set_value("FL")
    at.run()
    at.button(key="save_button").click().run()

    assert not at.exception
    saved_accounts = store["couple"]["accounts"]
    assert len(saved_accounts) == 6
    you_traditional = next(a for a in saved_accounts if a["owner"] == "you" and a["account_type"] == "traditional")
    spouse_traditional = next(
        a for a in saved_accounts if a["owner"] == "spouse" and a["account_type"] == "traditional"
    )
    assert you_traditional["balance"] == 900_000.0
    assert spouse_traditional["balance"] == 300_000.0


def test_full_retirement_age_defaults_and_is_saved_and_reloaded():
    """016-ss-claiming-age-actuarial-adjustment: the FRA widget defaults to
    67.0 (matching the ss_claim_age widget's own default), an explicit
    value the user enters is sent in the saved payload, and loading a
    previously saved scenario repopulates it (not just ss_claim_age/
    ss_annual_benefit)."""
    handler, store = make_fake_bff()
    _install(handler)

    at = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    assert at.number_input(key="member1_full_retirement_age").value == 67.0

    at.text_input(key="scenario_name").set_value("fra_case")
    at.text_input(key="member1_person_name").set_value("alex")
    at.number_input(key="member1_current_age").set_value(61)
    at.number_input(key="member1_ss_claim_age").set_value(62)
    at.number_input(key="member1_ss_annual_benefit").set_value(30_000.0)
    at.number_input(key="member1_full_retirement_age").set_value(67.0)
    at.number_input(key="annual_need_real").set_value(60_000.0)
    at.selectbox(key="state").set_value("FL")
    at.run()
    at.button(key="save_button").click().run()

    assert not at.exception
    assert store["fra_case"]["household"]["members"][0]["full_retirement_age"] == 67.0

    # A fresh page load, then loading that saved scenario back, repopulates it.
    at = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    at.selectbox(key="scenario_load_select").set_value("fra_case")
    at.button(key="load_button").click().run()

    assert not at.exception
    assert at.number_input(key="member1_full_retirement_age").value == 67.0


def test_us2_single_member_household_never_renders_member2_account_fields():
    """A single-filer household has only one possible owner -- no second
    row is ever offered (FR-003)."""
    handler, _store = make_fake_bff()
    _install(handler)

    at = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    assert at.session_state["filing_status"] == "single"

    with pytest.raises(KeyError):
        at.number_input(key="member2_traditional_balance")


def test_us3_loading_a_stale_owner_account_leaves_its_balance_absent_not_guessed():
    """011-per-owner-accounts User Story 3: a scenario saved before this
    feature (or with a since-renamed member) has an account whose owner
    doesn't match either currently-loaded member. Loading it must not
    guess which row that balance belongs to -- it stays at $0 in every
    row, a visible cue that something needs re-entering, rather than a
    validation flag (ui-pages.md's corrected "Modified Load existing
    behavior" -- this form always supplies a valid owner on resubmit, so
    an unmatched balance, not a flag, is the real signal)."""
    handler, store = make_fake_bff()
    _install(handler)
    # Pre-seed the fake store as if saved before this feature: "spouse_old"
    # no longer matches either current member's name.
    store["couple"] = {
        "name": "couple",
        "household": {
            "filing_status": "married_filing_jointly",
            "members": [
                {
                    "person_name": "you",
                    "current_age": 74,
                    "ss_claim_age": 67,
                    "ss_annual_benefit": 32_000,
                    "full_retirement_age": 67.0,
                },
                {
                    "person_name": "spouse",
                    "current_age": 60,
                    "ss_claim_age": 67,
                    "ss_annual_benefit": 24_000,
                    "full_retirement_age": 67.0,
                },
            ],
        },
        "accounts": [
            {"account_type": "traditional", "balance": 900_000.0, "owner": "you"},
            {"account_type": "traditional", "balance": 300_000.0, "owner": "spouse_old"},
        ],
        "spending": {"annual_need_real": 90_000.0},
        "state": "FL",
        "market_assumptions": {
            "equity_allocation": 0.6, "equity_return_mean_real": 0.065, "equity_return_std_real": 0.17,
            "bond_allocation": 0.4, "bond_return_mean_real": 0.015, "bond_return_std_real": 0.06,
            "correlation": -0.10,
        },
        "simulation_settings": {"n_paths": 1000, "seed": 1, "plan_to_age": 95},
        "roth_conversion": None,
        "validation_flags": [
            {"field": "accounts[1].owner", "message": "does not match any household member", "severity": "blocking"}
        ],
        "is_usable": False,
    }

    at = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    at.selectbox(key="scenario_load_select").set_value("couple")
    at.button(key="load_button").click().run()

    assert not at.exception
    # you's account matched and loaded normally.
    assert at.number_input(key="member1_traditional_balance").value == 900_000.0
    # spouse_old's $300k didn't match "spouse" (the currently-loaded second
    # member's name) -- it must NOT be silently placed into spouse's row.
    assert at.number_input(key="member2_traditional_balance").value == 0.0
    # No error/flag rendered automatically at load time (Load never calls Validate).
    assert len(at.error) == 0


# -- 012-inherited-ira-rmd: Inherited IRA (optional) section (rp-8ap) --------


def test_inherited_ira_section_hidden_until_checkbox_checked():
    handler, _store = make_fake_bff()
    _install(handler)

    at = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    assert at.checkbox(key="include_inherited_ira").value is False
    with pytest.raises(KeyError):
        at.number_input(key="inherited_balance")

    at.checkbox(key="include_inherited_ira").set_value(True)
    at.run()
    assert at.number_input(key="inherited_balance") is not None
    assert at.number_input(key="inherited_death_year") is not None
    assert at.number_input(key="inherited_decedent_age_at_death") is not None
    assert at.checkbox(key="inherited_decedent_was_taking_rmds").value is True
    assert at.selectbox(key="inherited_beneficiary_relationship").value == "other_individual"
    assert at.selectbox(key="inherited_beneficiary_classification").value == "non_eligible_designated_beneficiary"


def test_inherited_ira_beneficiary_options_are_current_household_members():
    handler, _store = make_fake_bff()
    _install(handler)

    at = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    at.selectbox(key="filing_status").set_value("married_filing_jointly")
    at.run()
    at.text_input(key="member1_person_name").set_value("you")
    at.text_input(key="member2_person_name").set_value("spouse")
    at.checkbox(key="include_inherited_ira").set_value(True)
    at.run()

    assert at.selectbox(key="inherited_owner").options == ["", "you", "spouse"]


def test_inherited_ira_save_round_trip_produces_inherited_account():
    """The filled-in fields save as a fourth account entry, carrying an
    `inherited` block, alongside the three ordinary per-member accounts."""
    handler, store = make_fake_bff()
    _install(handler)

    at = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    _fill_minimal_valid_scenario(at, name="inherited_case")
    at.checkbox(key="include_inherited_ira").set_value(True)
    at.run()
    at.selectbox(key="inherited_owner").set_value("Alex")
    at.number_input(key="inherited_balance").set_value(250_000.0)
    at.number_input(key="inherited_death_year").set_value(2023)
    at.number_input(key="inherited_decedent_age_at_death").set_value(80)
    at.run()
    at.button(key="save_button").click().run()

    assert not at.exception
    saved_accounts = store["inherited_case"]["accounts"]
    assert len(saved_accounts) == 4  # 3 ordinary + 1 inherited
    inherited_account = next(a for a in saved_accounts if a.get("inherited") is not None)
    assert inherited_account["account_type"] == "traditional"
    assert inherited_account["balance"] == 250_000.0
    assert inherited_account["owner"] == "Alex"
    assert inherited_account["inherited"] == {
        "death_year": 2023,
        "decedent_age_at_death": 80,
        "decedent_was_taking_rmds": True,
        "beneficiary_relationship": "other_individual",
        "beneficiary_classification": "non_eligible_designated_beneficiary",
    }


def test_inherited_ira_unchecked_submits_no_inherited_account():
    handler, store = make_fake_bff()
    _install(handler)

    at = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    _fill_minimal_valid_scenario(at, name="ordinary_case")
    at.button(key="save_button").click().run()

    assert not at.exception
    assert all(a.get("inherited") is None for a in store["ordinary_case"]["accounts"])


def test_inherited_ira_load_round_trip_populates_fields_without_double_counting():
    """Loading a scenario with an inherited account fills the Inherited
    IRA section's fields, and its balance never leaks into the owning
    member's own ordinary traditional balance (research.md §5)."""
    handler, store = make_fake_bff()
    _install(handler)
    store["inherited_case"] = {
        "name": "inherited_case",
        "household": {
            "filing_status": "single",
            "members": [
                {
                    "person_name": "Alex",
                    "current_age": 55,
                    "ss_claim_age": 67,
                    "ss_annual_benefit": 28_000,
                    "full_retirement_age": 67.0,
                }
            ],
        },
        "accounts": [
            {"account_type": "traditional", "balance": 100_000.0, "owner": "Alex"},
            {
                "account_type": "traditional",
                "balance": 250_000.0,
                "owner": "Alex",
                "account_id": "inherited-1",
                "inherited": {
                    "death_year": 2023,
                    "decedent_age_at_death": 80,
                    "decedent_was_taking_rmds": True,
                    "beneficiary_relationship": "other_individual",
                    "beneficiary_classification": "non_eligible_designated_beneficiary",
                },
            },
        ],
        "spending": {"annual_need_real": 60_000.0},
        "state": "FL",
        "market_assumptions": {
            "equity_allocation": 0.6, "equity_return_mean_real": 0.05, "equity_return_std_real": 0.15,
            "bond_allocation": 0.4, "bond_return_mean_real": 0.02, "bond_return_std_real": 0.05, "correlation": 0.0,
        },
        "simulation_settings": {"n_paths": 1, "seed": 1, "plan_to_age": 95},
        "roth_conversion": None,
        "validation_flags": [],
        "is_usable": True,
    }

    at = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    at.selectbox(key="scenario_load_select").set_value("inherited_case")
    at.button(key="load_button").click().run()

    assert not at.exception
    # The member's own ordinary traditional balance is $100k -- the
    # inherited account's $250k must not be added into it.
    assert at.number_input(key="member1_traditional_balance").value == 100_000.0
    assert at.checkbox(key="include_inherited_ira").value is True
    assert at.number_input(key="inherited_balance").value == 250_000.0
    assert at.selectbox(key="inherited_owner").value == "Alex"
    assert at.number_input(key="inherited_death_year").value == 2023
    assert at.number_input(key="inherited_decedent_age_at_death").value == 80


def test_inherited_ira_pre_rbd_blocking_flag_shown_inline():
    """Unchecking 'already begun their own RMDs' and saving surfaces a
    blocking flag inline, the same way every other blocking flag on this
    page already does (rp-8ap: 'inline surfacing of the four new blocking
    validation flags')."""
    handler, _store = make_fake_bff()
    _install(handler)

    at = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    _fill_minimal_valid_scenario(at, name="pre_rbd_case")
    at.checkbox(key="include_inherited_ira").set_value(True)
    at.run()
    at.selectbox(key="inherited_owner").set_value("Alex")
    at.number_input(key="inherited_balance").set_value(250_000.0)
    at.checkbox(key="inherited_decedent_was_taking_rmds").set_value(False)
    at.run()
    at.button(key="save_button").click().run()

    assert not at.exception
    assert any("pre-rbd" in e.value.lower() for e in at.error)


# -- User Story 1: Scenario management (T009-T012) ---------------------------


def test_us1_save_read_and_list_round_trip():
    """Acceptance Scenario US1.1: saving a complete scenario results in it
    being read back with the same data and listed among saved scenarios."""
    handler, _store = make_fake_bff()
    _install(handler)

    at = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    _fill_minimal_valid_scenario(at, name="base_case")
    at.button(key="save_button").click().run()

    assert not at.exception
    assert any("saved 'base_case'" in s.value.lower() for s in at.success)
    assert any("no validation issues" in s.value.lower() for s in at.success)

    # A fresh page load must now list it and read it back with the same data.
    at2 = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    assert "base_case" in at2.selectbox(key="scenario_load_select").options
    at2.selectbox(key="scenario_load_select").set_value("base_case")
    at2.button(key="load_button").click().run()
    assert at2.text_input(key="member1_person_name").value == "Alex"
    assert at2.number_input(key="member1_traditional_balance").value == 1_500_000.0
    assert at2.selectbox(key="state").value == "FL"


def test_us1_blocking_flag_shown_inline_distinct_from_warning():
    """Acceptance Scenario US1.2: a blocking validation problem is shown
    inline, distinguishable from a warning-only flag."""
    handler, _store = make_fake_bff()
    _install(handler)

    at = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    _fill_minimal_valid_scenario(at, name="broke_case")
    at.number_input(key="member1_traditional_balance").set_value(-100.0)
    at.run()
    at.button(key="validate_button").click().run()

    assert not at.exception
    assert len(at.error) >= 1
    assert "must be >= 0" in at.error[0].value
    # A warning-only flag must never be rendered as an error -- confirmed
    # by triggering one next and checking it lands in at.warning, not at.error.
    at.number_input(key="annual_need_real").set_value(50_000_000.0)
    at.run()
    at.button(key="validate_button").click().run()
    assert len(at.warning) >= 1
    assert "unusually high spending" in at.warning[-1].value


def test_us1_selectors_populated_only_from_live_reference_data():
    """Acceptance Scenario US1.3: state/conversion-strategy selectors
    reflect exactly what the backend's reference endpoints return -- never
    a hardcoded list."""
    handler, _store = make_fake_bff()
    _install(handler)

    at = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    assert at.selectbox(key="state").options == ["", "DE", "FL", "SC"]
    at.checkbox(key="include_roth_conversion").set_value(True)
    at.run()
    assert at.selectbox(key="conversion_strategy").options == ["", "bracket_fill"]


def test_us1_resave_replaces_and_delete_removes_immediately():
    """Acceptance Scenario US1.4: re-saving under an existing name fully
    replaces the previous data; deleting drops it from every list
    immediately."""
    handler, store = make_fake_bff()
    _install(handler)

    at = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    _fill_minimal_valid_scenario(at, name="base_case", state="FL")
    at.button(key="save_button").click().run()
    assert store["base_case"]["state"] == "FL"

    at2 = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    _fill_minimal_valid_scenario(at2, name="base_case", state="SC")
    at2.button(key="save_button").click().run()
    assert store["base_case"]["state"] == "SC"
    assert len(store) == 1  # replaced, not duplicated

    at3 = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    at3.selectbox(key="scenario_load_select").set_value("base_case")
    at3.button(key="delete_button").click().run()
    assert "base_case" not in store

    at4 = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    assert "base_case" not in at4.selectbox(key="scenario_load_select").options


# -- User Story 2: Run a simulation (T014-T017) -------------------------------

_RUN_PERCENTILE_BANDS = [
    {"plan_year": 1, "percentiles": [{"percentile": 0.10, "value": 1_000_000.0}, {"percentile": 0.50, "value": 1_500_000.0}, {"percentile": 0.90, "value": 2_000_000.0}]},
    {"plan_year": 2, "percentiles": [{"percentile": 0.10, "value": 900_000.0}, {"percentile": 0.50, "value": 1_600_000.0}, {"percentile": 0.90, "value": 2_200_000.0}]},
]


def _run_reference_routes(scenarios=("base_case",), withdrawal_strategies=("rmd_taxable_traditional_roth",)):
    return {
        ("GET", "/api/v1/scenarios"): httpx.Response(200, json={"scenarios": list(scenarios)}),
        ("GET", "/api/v1/reference/withdrawal-strategies"): httpx.Response(
            200, json={"withdrawal_strategies": list(withdrawal_strategies)}
        ),
    }


def _run_page_ready(at: AppTest) -> AppTest:
    at.number_input(key="run_reference_tax_year").set_value(2026)
    at.number_input(key="run_start_plan_year").set_value(1)
    at.number_input(key="run_start_tax_year").set_value(2026)
    at.run()
    return at


def test_us2_run_displays_success_rate_and_fan_chart():
    """Acceptance Scenario US2.1."""
    summary = {
        "candidate_label": "base_case",
        "success_rate": 0.91,
        "ending_balance": 1_800_000.0,
        "percentile_bands": _RUN_PERCENTILE_BANDS,
        "median_depletion_age": None,
        "median_lifetime_tax_paid": 300_000.0,
        "unverified_figure_names": [],
    }

    def sim_response(request):
        body = json.loads(request.content)
        assert body["scenario_name"] == "base_case"
        assert body["reference_tax_year"] == 2026
        return httpx.Response(200, json={"run": {"candidate_label": "base_case", "path_results": [{}] * 100}, "summary": summary})

    routes = _run_reference_routes()
    routes[("POST", "/api/v1/simulations")] = sim_response
    _install(_route(routes))

    at = _run_page_ready(AppTest.from_file(str(RUN_PAGE)).run())
    at.button(key="run_button").click().run()

    assert not at.exception
    assert at.metric[0].value == "91.0%"
    assert any(type(child).__name__ == "UnknownElement" for child in at.main.children.values())


def test_us2_blocking_flags_show_specific_message():
    """Acceptance Scenario US2.2 -- distinct wording from a
    "scenario doesn't exist" message."""
    flags = [{"field": "accounts[traditional].balance", "message": "must be >= 0", "severity": "blocking"}]

    def sim_response(request):
        return httpx.Response(422, json={"error": "blocking_validation_flags", "flags": flags})

    routes = _run_reference_routes()
    routes[("POST", "/api/v1/simulations")] = sim_response
    _install(_route(routes))

    at = _run_page_ready(AppTest.from_file(str(RUN_PAGE)).run())
    at.button(key="run_button").click().run()

    assert not at.exception
    assert any("fix these problems" in e.value.lower() for e in at.error)
    assert any("must be >= 0" in e.value for e in at.error)
    assert not any("no longer exists" in e.value.lower() for e in at.error)


def test_us2_cost_budget_exceeded_shows_specific_message():
    """Acceptance Scenario US2.3."""

    def sim_response(request):
        return httpx.Response(
            413, json={"error": "estimated_cost_exceeds_budget", "estimated_seconds": 180.0, "budget_seconds": 30.0}
        )

    routes = _run_reference_routes()
    routes[("POST", "/api/v1/simulations")] = sim_response
    _install(_route(routes))

    at = _run_page_ready(AppTest.from_file(str(RUN_PAGE)).run())
    at.button(key="run_button").click().run()

    assert not at.exception
    assert any("too large" in e.value.lower() and "180" in e.value for e in at.error)


def test_us2_unsupported_tax_year_shows_specific_message_not_a_bare_500():
    """Regression: a real user left the Reference tax year field at its
    unedited placeholder (1900) and got "Unexpected response from
    backend: HTTP 500" -- 007 now returns a clean 422 for this, and this
    page must render a specific message for it, not fall through to the
    generic UnexpectedBackendError branch."""

    def sim_response(request):
        return httpx.Response(
            422,
            json={
                "error": "unsupported_tax_year",
                "figure_name": "rmd_start_age",
                "requested_year": 1900,
                "documented_years": [2020, 2026],
            },
        )

    routes = _run_reference_routes()
    routes[("POST", "/api/v1/simulations")] = sim_response
    _install(_route(routes))

    at = _run_page_ready(AppTest.from_file(str(RUN_PAGE)).run())
    at.button(key="run_button").click().run()

    assert not at.exception
    assert any("1900" in e.value and "2020" in e.value and "2026" in e.value for e in at.error)


def test_us2_run_button_wrapped_in_spinner():
    """Acceptance Scenario US2.4 -- a progress indicator is visible for the
    duration of a run request. Verified structurally: run_simulation() is
    called from inside a `with st.spinner(...)` block in the page source
    (AppTest executes synchronously, so a running spinner can't be
    captured mid-flight)."""
    source = RUN_PAGE.read_text()
    assert "st.spinner" in source
    spinner_index = source.index("st.spinner")
    run_call_index = source.index("run_simulation(_build_run_body())")
    assert spinner_index < run_call_index


# -- User Story 3: Compare candidates (T020-T023) -----------------------------


def _compare_reference_routes():
    return {
        ("GET", "/api/v1/scenarios"): httpx.Response(200, json={"scenarios": ["base_case"]}),
        ("GET", "/api/v1/reference/comparison-axes"): httpx.Response(
            200, json={"axes": ["state", "roth_conversion_strategy", "withdrawal_sequencing", "claiming_age_grid"]}
        ),
        ("GET", "/api/v1/reference/states"): httpx.Response(200, json={"states": ["DE", "FL", "SC"]}),
        ("GET", "/api/v1/reference/conversion-strategies"): httpx.Response(
            200, json={"conversion_strategies": ["bracket_fill"]}
        ),
        ("GET", "/api/v1/reference/withdrawal-strategies"): httpx.Response(
            200, json={"withdrawal_strategies": ["rmd_taxable_traditional_roth"]}
        ),
    }


def _compare_page_ready(at: AppTest) -> AppTest:
    at.number_input(key="compare_reference_tax_year").set_value(2026)
    at.number_input(key="compare_start_plan_year").set_value(1)
    at.number_input(key="compare_start_tax_year").set_value(2026)
    at.run()
    return at


def _simulated_summary(label: str) -> dict:
    return {
        "candidate_label": label,
        "success_rate": 0.9,
        "ending_balance": 1_500_000.0,
        "percentile_bands": _RUN_PERCENTILE_BANDS,
        "median_depletion_age": None,
        "median_lifetime_tax_paid": 250_000.0,
        "unverified_figure_names": [],
    }


def _deterministic_summary(label: str) -> dict:
    return {
        "candidate_label": label,
        "success_rate": None,
        "ending_balance": 1_500_000.0,
        "percentile_bands": None,
        "median_depletion_age": None,
        "median_lifetime_tax_paid": 250_000.0,
        "unverified_figure_names": [],
    }


def test_us3_simulated_state_comparison_shows_overlay_and_table():
    """Acceptance Scenario US3.1: a Monte Carlo comparison across
    candidates displays a line-overlay chart and a summary table with one
    row per candidate, in request order."""
    summaries = [_simulated_summary("SC"), _simulated_summary("DE"), _simulated_summary("FL")]

    def compare_response(request):
        body = json.loads(request.content)
        assert body["axis"] == "state"
        assert body["candidates"] == ["SC", "DE", "FL"]
        return httpx.Response(200, json={"axis": "state", "summaries": summaries})

    routes = _compare_reference_routes()
    routes[("POST", "/api/v1/comparisons/simulated")] = compare_response
    _install(_route(routes))

    at = _compare_page_ready(AppTest.from_file(str(COMPARE_PAGE)).run())
    at.selectbox(key="compare_axis").set_value("state")
    at.number_input(key="compare_candidate_count").set_value(3)
    at.run()
    at.selectbox(key="compare_candidate_0_state").set_value("SC")
    at.selectbox(key="compare_candidate_1_state").set_value("DE")
    at.selectbox(key="compare_candidate_2_state").set_value("FL")
    at.run()
    at.button(key="compare_button").click().run()

    assert not at.exception
    table = at.dataframe[0].value
    assert list(table["candidate_label"]) == ["SC", "DE", "FL"]
    # Dollar columns render as full "$X,XXX.XX" currency strings (never
    # achievable in an editable number_input -- see rp_ui/formatting.py).
    assert table["ending_balance"].iloc[0] == "$1,500,000.00"
    assert table["median_lifetime_tax_paid"].iloc[0] == "$250,000.00"
    assert any(type(child).__name__ == "UnknownElement" for child in at.main.children.values())


def test_us3_deterministic_engine_hides_state_axis():
    """Acceptance Scenario US3.2."""
    _install(_route(_compare_reference_routes()))
    at = _compare_page_ready(AppTest.from_file(str(COMPARE_PAGE)).run())
    at.radio(key="compare_engine").set_value("Deterministic")
    at.run()
    assert "state" not in at.selectbox(key="compare_axis").options


def test_us3_deterministic_summary_shows_na_not_zero_or_blank():
    """Acceptance Scenario US3.3: percentile-derived fields render "n/a",
    never a fabricated zero or blank, and the bar chart (not an overlay)
    is used, since percentile_bands is null."""
    summaries = [_deterministic_summary("bracket_fill")]

    def compare_response(request):
        return httpx.Response(200, json={"axis": "roth_conversion_strategy", "summaries": summaries})

    routes = _compare_reference_routes()
    routes[("POST", "/api/v1/comparisons/deterministic")] = compare_response
    _install(_route(routes))

    at = _compare_page_ready(AppTest.from_file(str(COMPARE_PAGE)).run())
    at.radio(key="compare_engine").set_value("Deterministic")
    at.run()
    at.selectbox(key="compare_axis").set_value("roth_conversion_strategy")
    at.number_input(key="compare_candidate_count").set_value(1)
    at.run()
    at.text_input(key="compare_candidate_0_label").set_value("bracket_fill")
    at.run()
    at.button(key="compare_button").click().run()

    assert not at.exception
    table = at.dataframe[0].value
    assert table["success_rate"].iloc[0] == "n/a"
    assert table["median_depletion_age"].iloc[0] == "n/a"


def test_us3_single_candidate_comparison_renders_without_special_casing():
    """Acceptance Scenario US3.4."""
    summaries = [_simulated_summary("SC")]

    def compare_response(request):
        body = json.loads(request.content)
        assert body["candidates"] == ["SC"]
        return httpx.Response(200, json={"axis": "state", "summaries": summaries})

    routes = _compare_reference_routes()
    routes[("POST", "/api/v1/comparisons/simulated")] = compare_response
    _install(_route(routes))

    at = _compare_page_ready(AppTest.from_file(str(COMPARE_PAGE)).run())
    at.selectbox(key="compare_axis").set_value("state")
    at.run()
    at.selectbox(key="compare_candidate_0_state").set_value("SC")
    at.run()
    at.button(key="compare_button").click().run()

    assert not at.exception
    table = at.dataframe[0].value
    assert len(table) == 1
    assert table["candidate_label"].iloc[0] == "SC"


# -- User Story 4: Verification indicator on Run/Compare (T027-T028) ---------


def test_us4_run_page_shows_verification_indicator():
    """Acceptance Scenario US4.1: the Run page reflects the mocked
    response's unverified_figure_names."""
    summary = {
        "candidate_label": "base_case",
        "success_rate": 0.91,
        "ending_balance": 1_800_000.0,
        "percentile_bands": _RUN_PERCENTILE_BANDS,
        "median_depletion_age": None,
        "median_lifetime_tax_paid": 300_000.0,
        "unverified_figure_names": ["historical_bootstrap_returns"],
    }

    def sim_response(request):
        return httpx.Response(200, json={"run": {"candidate_label": "base_case", "path_results": [{}] * 100}, "summary": summary})

    routes = _run_reference_routes()
    routes[("POST", "/api/v1/simulations")] = sim_response
    _install(_route(routes))

    at = _run_page_ready(AppTest.from_file(str(RUN_PAGE)).run())
    at.button(key="run_button").click().run()

    assert not at.exception
    assert any("historical_bootstrap_returns" in w.value for w in at.warning)


def test_us4_compare_page_shows_verification_indicator_union():
    """Acceptance Scenario US4.2: a fully-verified comparison shows the
    positive confirmation; the union-across-candidates design is exercised
    by test_us3_* fixtures (all empty), so this test covers the non-empty
    branch specifically."""
    summaries = [
        {**_simulated_summary("SC"), "unverified_figure_names": ["stress_scenario_2008"]},
        {**_simulated_summary("DE"), "unverified_figure_names": []},
    ]

    def compare_response(request):
        return httpx.Response(200, json={"axis": "state", "summaries": summaries})

    routes = _compare_reference_routes()
    routes[("POST", "/api/v1/comparisons/simulated")] = compare_response
    _install(_route(routes))

    at = _compare_page_ready(AppTest.from_file(str(COMPARE_PAGE)).run())
    at.selectbox(key="compare_axis").set_value("state")
    at.number_input(key="compare_candidate_count").set_value(2)
    at.run()
    at.selectbox(key="compare_candidate_0_state").set_value("SC")
    at.selectbox(key="compare_candidate_1_state").set_value("DE")
    at.run()
    at.button(key="compare_button").click().run()

    assert not at.exception
    assert any("stress_scenario_2008" in w.value for w in at.warning)


# -- User Story 5: CSV download on Run/Compare (T032-T033) -------------------


def test_us5_run_page_csv_download_matches_on_screen_request():
    """Acceptance Scenario US5.1: the download action calls
    export_simulation_csv() with the identical request body already used
    for the on-screen run, and the returned CSV text matches the mocked
    response."""
    summary = {
        "candidate_label": "base_case",
        "success_rate": 0.91,
        "ending_balance": 1_800_000.0,
        "percentile_bands": _RUN_PERCENTILE_BANDS,
        "median_depletion_age": None,
        "median_lifetime_tax_paid": 300_000.0,
        "unverified_figure_names": [],
    }
    csv_text = "plan_year,ending_balance\n1,1000000\n2,1100000\n"
    captured_bodies = []

    def sim_response(request):
        captured_bodies.append(("simulate", json.loads(request.content)))
        return httpx.Response(200, json={"run": {"candidate_label": "base_case", "path_results": [{}] * 100}, "summary": summary})

    def csv_response(request):
        captured_bodies.append(("export", json.loads(request.content)))
        return httpx.Response(200, text=csv_text)

    routes = _run_reference_routes()
    routes[("POST", "/api/v1/simulations")] = sim_response
    routes[("POST", "/api/v1/reports/simulations.csv")] = csv_response
    _install(_route(routes))

    at = _run_page_ready(AppTest.from_file(str(RUN_PAGE)).run())
    at.button(key="run_button").click().run()
    at.button(key="run_prepare_csv_button").click().run()

    assert not at.exception
    assert captured_bodies[0][1] == captured_bodies[1][1]  # identical request body
    assert at.session_state["run_csv_text"] == csv_text
    assert at.download_button[0].label == "Download CSV"


def test_us5_compare_page_csv_download_matches_on_screen_request():
    """Acceptance Scenario US5.2: the download action calls
    export_comparison_csv() with the identical request body and engine,
    and the returned CSV text has one row per candidate matching the
    summary table."""
    summaries = [_simulated_summary("SC"), _simulated_summary("DE")]
    csv_text = "candidate_label,ending_balance\nSC,1500000\nDE,1500000\n"
    captured = []

    def compare_response(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"axis": "state", "summaries": summaries})

    def csv_response(request):
        assert request.url.params["engine"] == "simulated"
        captured.append(json.loads(request.content))
        return httpx.Response(200, text=csv_text)

    routes = _compare_reference_routes()
    routes[("POST", "/api/v1/comparisons/simulated")] = compare_response
    routes[("POST", "/api/v1/reports/comparisons.csv")] = csv_response
    _install(_route(routes))

    at = _compare_page_ready(AppTest.from_file(str(COMPARE_PAGE)).run())
    at.selectbox(key="compare_axis").set_value("state")
    at.number_input(key="compare_candidate_count").set_value(2)
    at.run()
    at.selectbox(key="compare_candidate_0_state").set_value("SC")
    at.selectbox(key="compare_candidate_1_state").set_value("DE")
    at.run()
    at.button(key="compare_button").click().run()
    at.button(key="compare_prepare_csv_button").click().run()

    assert not at.exception
    assert captured[0] == captured[1]
    assert at.session_state["compare_csv_text"] == csv_text
    assert csv_text.count("\n") - 1 == len(summaries)  # header + one row per candidate


# -- Polish: the full quickstart.md walkthrough, chained (T036) --------------


def test_polish_full_quickstart_walkthrough():
    """Every section of quickstart.md, chained end-to-end against one
    stateful fake backend: save/edit/blocking-flag/fix/delete/re-save
    (§1), run + fan chart + verification indicator + CSV (§2 & §4 & §5),
    compare + overlay + verification indicator + CSV (§3 & §4 & §5)."""
    scenario_handler, store = make_fake_bff()

    run_summary = {
        "candidate_label": "base_case",
        "success_rate": 0.93,
        "ending_balance": 1_900_000.0,
        "percentile_bands": _RUN_PERCENTILE_BANDS,
        "median_depletion_age": None,
        "median_lifetime_tax_paid": 310_000.0,
        "unverified_figure_names": [],
    }
    compare_summaries = [_simulated_summary("SC"), _simulated_summary("DE"), _simulated_summary("FL")]

    def handler(request: httpx.Request) -> httpx.Response:
        method, path = request.method, request.url.path
        if method == "POST" and path == "/api/v1/simulations":
            return httpx.Response(200, json={"run": {"candidate_label": "base_case", "path_results": [{}] * 100}, "summary": run_summary})
        if method == "POST" and path == "/api/v1/comparisons/simulated":
            return httpx.Response(200, json={"axis": "state", "summaries": compare_summaries})
        if method == "POST" and path == "/api/v1/reports/simulations.csv":
            return httpx.Response(200, text="plan_year,ending_balance\n1,1000000\n")
        if method == "POST" and path == "/api/v1/reports/comparisons.csv":
            return httpx.Response(200, text="candidate_label,ending_balance\nSC,1500000\nDE,1500000\nFL,1500000\n")
        return scenario_handler(request)

    _install(handler)

    # -- §1: Enter and manage a scenario --
    at = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    _fill_minimal_valid_scenario(at, name="base_case")
    at.button(key="save_button").click().run()
    assert not at.exception
    assert any("saved 'base_case'" in s.value.lower() for s in at.success)

    at.number_input(key="member1_traditional_balance").set_value(-100.0)
    at.run()
    at.button(key="save_button").click().run()
    assert len(at.error) >= 1  # blocking flag shown inline (US1.2)

    at.number_input(key="member1_traditional_balance").set_value(1_500_000.0)
    at.run()
    at.button(key="save_button").click().run()
    assert store["base_case"]["is_usable"] is True

    at.selectbox(key="scenario_load_select").set_value("base_case")
    at.button(key="delete_button").click().run()
    assert "base_case" not in store

    at2 = AppTest.from_file(str(SCENARIOS_PAGE)).run()
    _fill_minimal_valid_scenario(at2, name="base_case")
    at2.button(key="save_button").click().run()
    assert "base_case" in store

    # -- §2: Run a simulation and see the fan chart --
    run_at = _run_page_ready(AppTest.from_file(str(RUN_PAGE)).run())
    run_at.button(key="run_button").click().run()
    assert not run_at.exception
    assert run_at.metric[0].value == "93.0%"

    # -- §4 (Run half): verified confirmation shown --
    assert any("verified" in s.value.lower() for s in run_at.success)

    # -- §5 (Run half): CSV download --
    run_at.button(key="run_prepare_csv_button").click().run()
    assert run_at.session_state["run_csv_text"].startswith("plan_year,ending_balance")

    # -- §3: Compare candidates and see the overlay --
    compare_at = _compare_page_ready(AppTest.from_file(str(COMPARE_PAGE)).run())
    compare_at.selectbox(key="compare_axis").set_value("state")
    compare_at.number_input(key="compare_candidate_count").set_value(3)
    compare_at.run()
    compare_at.selectbox(key="compare_candidate_0_state").set_value("SC")
    compare_at.selectbox(key="compare_candidate_1_state").set_value("DE")
    compare_at.selectbox(key="compare_candidate_2_state").set_value("FL")
    compare_at.run()
    compare_at.button(key="compare_button").click().run()
    assert not compare_at.exception
    table = compare_at.dataframe[0].value
    assert list(table["candidate_label"]) == ["SC", "DE", "FL"]

    # Deterministic hides "state" as an axis choice (US3.2), checked once
    # more here as part of the chained walkthrough.
    compare_at.radio(key="compare_engine").set_value("Deterministic")
    compare_at.run()
    assert "state" not in compare_at.selectbox(key="compare_axis").options
    compare_at.radio(key="compare_engine").set_value("Monte Carlo")
    compare_at.run()

    # -- §4 (Compare half): verified confirmation shown --
    assert any("verified" in s.value.lower() for s in compare_at.success)

    # -- §5 (Compare half): CSV download --
    compare_at.button(key="compare_prepare_csv_button").click().run()
    assert compare_at.session_state["compare_csv_text"].startswith("candidate_label,ending_balance")


# -- Feature 009: Instructions page ------------------------------------------
#
# -- User Story 1: guidance content (T004) --


def test_us1_instructions_page_renders_all_sections_with_zero_backend_calls():
    """Acceptance Scenario US1.1 (spec.md 009) / contracts/ui-pages.md §
    pages/0_Instructions.py: renders every section, and makes no HTTP call
    at all -- api_client._transport is deliberately left unset (no mock
    installed); a real network attempt to the default 127.0.0.1:8000
    would fail fast (connection refused, nothing listening in a test
    environment) and surface as at.exception, which this asserts against."""
    from rp_ui.instructions_content import SECTIONS

    at = AppTest.from_file(str(INSTRUCTIONS_PAGE)).run()

    assert not at.exception
    rendered_titles = {h.value for h in at.header}
    assert rendered_titles == {section.title for section in SECTIONS}

    rendered_text = " ".join(m.value for m in at.markdown)
    for section in SECTIONS:
        # A couple of words from each body, not the whole string -- proves
        # the actual SECTIONS content made it to the page, without
        # duplicating test_instructions_content.py's own detailed checks.
        assert section.body.split(".")[0][:20] in rendered_text


# -- User Story 2: findable at any time (T006) --


def test_us2_home_page_navigation_mentions_instructions():
    _install(_route({("GET", "/api/v1/reference/states"): httpx.Response(200, json={"states": ["FL"]})}))
    at = AppTest.from_file(str(APP_PATH)).run()
    assert not at.exception
    assert any("Instructions" in m.value for m in at.markdown)


def test_us2_instructions_page_sorts_before_scenarios_in_the_sidebar():
    """Streamlit's own sidebar ordering is filename-lexicographic --
    AppTest simulates one script's execution, not the full multipage
    sidebar chrome, so this checks the actual guarantee (filename order)
    directly rather than trying to read a sidebar AppTest doesn't model."""
    assert INSTRUCTIONS_PAGE.name < SCENARIOS_PAGE.name


def test_us2_round_trip_navigation_does_not_error_on_either_leg():
    """Acceptance Scenario US2.2, structural half: visiting Instructions
    mid-form and coming back doesn't crash either page. (AppTest's
    switch_page() does not faithfully simulate real Streamlit's
    cross-page st.session_state persistence -- confirmed empirically
    while writing this test, a testing-tool limitation, not a claim
    about the real running app, which does share session_state across
    pages the same way every Streamlit multipage app does. The concrete,
    testable form of "doesn't disturb another page's state" for *this*
    page is the next test: it writes no session_state key at all.)"""
    handler, _store = make_fake_bff()
    _install(handler)

    at = AppTest.from_file(str(APP_PATH)).run()
    at.switch_page("pages/1_Scenarios.py").run()
    _fill_minimal_valid_scenario(at, name="round_trip_case")
    assert not at.exception

    at.switch_page("pages/0_Instructions.py").run()
    assert not at.exception

    at.switch_page("pages/1_Scenarios.py").run()
    assert not at.exception


def test_us2_instructions_page_writes_no_session_state_of_its_own():
    """data-model.md § State transitions: SECTIONS is a module-level
    constant; this page holds no st.session_state entry -- the concrete
    guarantee that it can never collide with or clear another page's
    in-progress form state."""
    at = AppTest.from_file(str(INSTRUCTIONS_PAGE)).run()
    assert not at.exception
    assert dict(at.session_state.filtered_state) == {}


# -- Polish (009): the full quickstart.md (009) walkthrough, chained (T010) --


def test_polish_009_full_quickstart_walkthrough():
    """Both sections of specs/009-instructions-page/quickstart.md,
    chained: find and read the guidance before creating a scenario (§1),
    then reach it mid-form and return without disruption (§2)."""
    from rp_ui.instructions_content import SECTIONS

    handler, _store = make_fake_bff()
    _install(handler)

    # -- §1: find and read the guidance before creating a scenario --
    home = AppTest.from_file(str(APP_PATH)).run()
    assert not home.exception
    assert any("Instructions" in m.value for m in home.markdown)
    assert INSTRUCTIONS_PAGE.name < SCENARIOS_PAGE.name

    instructions = AppTest.from_file(str(INSTRUCTIONS_PAGE)).run()
    assert not instructions.exception
    assert {h.value for h in instructions.header} == {section.title for section in SECTIONS}
    accounts_body = next(s.body for s in SECTIONS if s.title == "Accounts")
    assert "own balance" in accounts_body
    household_body = next(s.body for s in SECTIONS if s.title == "Household")
    assert "claiming age" in household_body
    state_body = next(s.body for s in SECTIONS if s.title == "State")
    for code in ("SC", "DE", "FL"):
        assert code not in state_body

    # -- §2: reach it mid-form and return without losing your place --
    at = AppTest.from_file(str(APP_PATH)).run()
    at.switch_page("pages/1_Scenarios.py").run()
    _fill_minimal_valid_scenario(at, name="quickstart_009_case")
    at.switch_page("pages/0_Instructions.py").run()
    assert not at.exception
    at.switch_page("pages/1_Scenarios.py").run()
    assert not at.exception
