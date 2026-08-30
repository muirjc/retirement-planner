"""Unit tests for validate() (US3)."""

from retirement_planner.scenario import (
    Account,
    Household,
    HouseholdMember,
    InheritedIraDetails,
    MarketAssumptions,
    Scenario,
    SimulationSettings,
    SpendingProfile,
)
from retirement_planner.scenario.validation import validate


def _market_assumptions():
    return MarketAssumptions(
        equity_allocation=0.6,
        equity_return_mean_real=0.065,
        equity_return_std_real=0.17,
        bond_allocation=0.4,
        bond_return_mean_real=0.015,
        bond_return_std_real=0.06,
        correlation=-0.10,
    )


def _member(name="you", age=60, claim_age=67, benefit=32_000.0):
    return HouseholdMember(
        person_name=name, current_age=age, ss_claim_age=claim_age, ss_annual_benefit=benefit
    )


def _clean_scenario(**overrides):
    defaults = dict(
        name="clean",
        household=Household(filing_status="single", members=[_member()]),
        accounts=[Account(account_type="traditional", balance=1_000_000.0)],
        spending=SpendingProfile(annual_need_real=50_000.0),
        state="GA",
        market_assumptions=_market_assumptions(),
        # plan_to_age matches the default member's current_age (60) so the
        # spending-vs-assets plausibility check has a 0-year horizon and
        # never fires unless a test explicitly sets up a longer horizon.
        simulation_settings=SimulationSettings(n_paths=1000, seed=1, plan_to_age=60),
    )
    defaults.update(overrides)
    return Scenario(**defaults)


def test_validate_flags_negative_account_balance_as_blocking():
    scenario = _clean_scenario(
        accounts=[Account(account_type="traditional", balance=-1_000.0)]
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "accounts[traditional].balance"
    assert flags[0].severity == "blocking"


def test_validate_flags_ss_claim_age_out_of_range_as_blocking():
    scenario = _clean_scenario(
        household=Household(filing_status="single", members=[_member(claim_age=75)])
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "household.members[0].ss_claim_age"
    assert flags[0].severity == "blocking"


def test_validate_accepts_ss_claim_age_boundaries_62_and_70():
    for boundary_age in (62, 70):
        scenario = _clean_scenario(
            household=Household(filing_status="single", members=[_member(claim_age=boundary_age)])
        )
        assert validate(scenario) == []


def test_validate_flags_negative_ss_annual_benefit_as_blocking():
    scenario = _clean_scenario(
        household=Household(filing_status="single", members=[_member(benefit=-500.0)])
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "household.members[0].ss_annual_benefit"
    assert flags[0].severity == "blocking"


def test_validate_flags_negative_spending_as_blocking():
    scenario = _clean_scenario(spending=SpendingProfile(annual_need_real=-1.0))
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "spending.annual_need_real"
    assert flags[0].severity == "blocking"


def test_validate_accepts_zero_spending():
    scenario = _clean_scenario(spending=SpendingProfile(annual_need_real=0.0))
    assert validate(scenario) == []


def test_validate_flags_spending_vs_assets_plausibility_as_warning_and_stays_usable():
    scenario = _clean_scenario(
        accounts=[Account(account_type="traditional", balance=50_000.0)],
        spending=SpendingProfile(annual_need_real=110_000.0),
        simulation_settings=SimulationSettings(n_paths=1000, seed=1, plan_to_age=95),
        household=Household(filing_status="single", members=[_member(age=60)]),
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "spending.annual_need_real"
    assert flags[0].severity == "warning"

    scenario.validation_flags = flags
    assert scenario.is_usable is True


def test_validate_flags_missing_owner_as_blocking_for_multi_member_household():
    """011-per-owner-accounts: an account with no owner in a 2-member
    household is ambiguous -- validate() flags it itself (FR-006),
    regardless of whether the Scenario came through parse_scenario()."""
    scenario = _clean_scenario(
        household=Household(filing_status="married_filing_jointly", members=[_member("you"), _member("spouse")]),
        accounts=[Account(account_type="traditional", balance=1_000_000.0)],
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "accounts[0].owner"
    assert flags[0].severity == "blocking"


def test_validate_never_flags_missing_owner_for_single_member_household():
    """011-per-owner-accounts: a single-member household is unambiguous --
    validate() never flags a bare owner=None here, independent of whether
    parse_scenario()'s own auto-fill ran (FR-003)."""
    scenario = _clean_scenario(
        accounts=[Account(account_type="traditional", balance=1_000_000.0)]
    )
    assert validate(scenario) == []


def test_validate_flags_owner_not_matching_any_household_member_as_blocking():
    """011-per-owner-accounts: a stale or misspelled owner is flagged for
    any household size, including single-member (Edge Cases)."""
    scenario = _clean_scenario(
        accounts=[Account(account_type="traditional", balance=1_000_000.0, owner="nobody")]
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "accounts[0].owner"
    assert flags[0].severity == "blocking"
    assert "nobody" in flags[0].message


def test_validate_accepts_account_owner_matching_a_household_member():
    scenario = _clean_scenario(
        accounts=[Account(account_type="traditional", balance=1_000_000.0, owner="you")]
    )
    assert validate(scenario) == []


def test_validate_flags_owner_left_stale_after_a_member_rename():
    """011-per-owner-accounts Edge Cases: renaming a household member
    doesn't retroactively update accounts that already reference the old
    name -- the mismatch is flagged, never silently reattributed or
    dropped, for a 2-member household too (not just the single-member
    case test_validate_flags_owner_not_matching_any_household_member_as_blocking
    already covers)."""
    scenario = _clean_scenario(
        household=Household(filing_status="married_filing_jointly", members=[_member("you"), _member("spouse_v2")]),
        accounts=[
            Account(account_type="traditional", balance=900_000.0, owner="you"),
            # "spouse" was renamed to "spouse_v2" after this account was
            # saved -- its owner reference is now stale.
            Account(account_type="traditional", balance=300_000.0, owner="spouse"),
        ],
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "accounts[1].owner"
    assert flags[0].severity == "blocking"
    assert "spouse" in flags[0].message and "spouse_v2" in flags[0].message


def test_validate_returns_empty_list_for_clean_scenario():
    scenario = _clean_scenario()
    assert validate(scenario) == []
    scenario.validation_flags = validate(scenario)
    assert scenario.is_usable is True


# --- 012-inherited-ira-rmd / 013-inherited-ira-edge-cases: the two
# remaining blocking rules (data-model.md § Validation rules, 013
# research.md §8) ---


def _inherited_details(**overrides):
    base = dict(
        death_year=2023,
        decedent_age_at_death=80,
        decedent_was_taking_rmds=True,
        beneficiary_relationship="other_individual",
        beneficiary_classification="non_eligible_designated_beneficiary",
    )
    base.update(overrides)
    return InheritedIraDetails(**base)


def test_validate_accepts_a_fully_supported_inherited_account():
    scenario = _clean_scenario(
        accounts=[
            Account(
                account_type="traditional",
                balance=250_000.0,
                owner="you",
                inherited=_inherited_details(),
            )
        ]
    )
    assert validate(scenario) == []


def test_validate_accepts_pre_rbd_decedent():
    """013-inherited-ira-edge-cases research.md §1/§8: no longer
    blocking -- compute_inherited_rmd() now computes this case."""
    scenario = _clean_scenario(
        accounts=[
            Account(
                account_type="traditional",
                balance=250_000.0,
                owner="you",
                inherited=_inherited_details(decedent_was_taking_rmds=False),
            )
        ]
    )
    assert validate(scenario) == []


def test_validate_accepts_eligible_designated_beneficiary():
    """013 research.md §3-§6/§8: no longer blocking."""
    scenario = _clean_scenario(
        accounts=[
            Account(
                account_type="traditional",
                balance=250_000.0,
                owner="you",
                inherited=_inherited_details(
                    beneficiary_relationship="spouse",
                    beneficiary_classification="eligible_designated_beneficiary_spouse",
                ),
            )
        ]
    )
    assert validate(scenario) == []


def test_validate_accepts_roth_inherited_account():
    """013 research.md §2/§8: no longer blocking."""
    scenario = _clean_scenario(
        accounts=[
            Account(
                account_type="roth",
                balance=250_000.0,
                owner="you",
                inherited=_inherited_details(),
            )
        ]
    )
    assert validate(scenario) == []


def test_validate_flags_taxable_inherited_account_as_blocking():
    """013 research.md §8: account_type is narrowed to "not in
    (traditional, roth)" -- taxable stays blocked (012's own §10
    addendum rationale, unaffected by this pass)."""
    scenario = _clean_scenario(
        accounts=[
            Account(
                account_type="taxable",
                balance=250_000.0,
                owner="you",
                inherited=_inherited_details(),
            )
        ]
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "accounts[0].inherited"
    assert flags[0].severity == "blocking"


def test_validate_flags_trust_or_entity_beneficiary_as_blocking():
    """013 research.md §7: a new rule, closing a pre-existing gap --
    a trust/entity beneficiary must stay blocked even though
    beneficiary_classification's own blocking flag is gone."""
    scenario = _clean_scenario(
        accounts=[
            Account(
                account_type="traditional",
                balance=250_000.0,
                owner="you",
                inherited=_inherited_details(
                    beneficiary_relationship="trust_or_entity",
                    beneficiary_classification="non_eligible_designated_beneficiary",
                ),
            )
        ]
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "accounts[0].inherited"
    assert flags[0].severity == "blocking"


def test_validate_inherited_account_with_no_owner_still_produces_missing_owner_flag():
    """The existing owner check (011) applies unchanged to an inherited
    account -- it still needs a beneficiary owner."""
    scenario = _clean_scenario(
        household=Household(filing_status="married_filing_jointly", members=[_member("you"), _member("spouse")]),
        accounts=[
            Account(
                account_type="traditional",
                balance=250_000.0,
                owner=None,
                inherited=_inherited_details(),
            )
        ],
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "accounts[0].owner"
    assert flags[0].severity == "blocking"


def test_validate_reports_every_inherited_problem_at_once_not_just_the_first():
    """FR-006 (001): validate() always runs every rule to completion."""
    scenario = _clean_scenario(
        household=Household(filing_status="married_filing_jointly", members=[_member("you"), _member("spouse")]),
        accounts=[
            Account(
                account_type="taxable",  # wrong account_type
                balance=250_000.0,
                owner=None,  # missing owner
                inherited=_inherited_details(
                    beneficiary_relationship="trust_or_entity",  # unsupported beneficiary
                ),
            )
        ],
    )
    flags = validate(scenario)
    fields = {flag.field for flag in flags}
    assert fields == {"accounts[0].inherited", "accounts[0].owner"}
    # Two distinct "inherited" problems (wrong account_type +
    # trust/entity beneficiary) fire independently, not just the first
    # one found -- plus the separate missing-owner flag makes three
    # flags total.
    inherited_flags = [flag for flag in flags if flag.field == "accounts[0].inherited"]
    assert len(inherited_flags) == 2
    assert len(flags) == 3
