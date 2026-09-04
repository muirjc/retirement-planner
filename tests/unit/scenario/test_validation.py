"""Unit tests for validate() (US3)."""

from retirement_planner.scenario import (
    Account,
    Household,
    HouseholdMember,
    IncomeStream,
    InheritedIraDetails,
    MarketAssumptions,
    RothConversionPlan,
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


def _member(
    name="you", age=60, claim_age=67, benefit=32_000.0, fra=None, predicted_death_age=None, income_streams=None
):
    return HouseholdMember(
        person_name=name,
        current_age=age,
        ss_claim_age=claim_age,
        ss_annual_benefit=benefit,
        full_retirement_age=fra,
        predicted_death_age=predicted_death_age,
        income_streams=income_streams or [],
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


def test_validate_flags_income_stream_end_age_before_start_age_as_blocking():
    scenario = _clean_scenario(
        household=Household(
            filing_status="single",
            members=[
                _member(
                    income_streams=[
                        IncomeStream(
                            label="Bad stream",
                            stream_type="pension",
                            start_age=70,
                            end_age=65,
                            annual_amount=10_000.0,
                            inflation_adjustment="cola_adjusted",
                        )
                    ]
                )
            ],
        )
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "household.members[0].income_streams[0].end_age"
    assert flags[0].severity == "blocking"


def test_validate_flags_negative_income_stream_annual_amount_as_blocking():
    scenario = _clean_scenario(
        household=Household(
            filing_status="single",
            members=[
                _member(
                    income_streams=[
                        IncomeStream(
                            label="Bad stream",
                            stream_type="pension",
                            start_age=65,
                            annual_amount=-1_000.0,
                            inflation_adjustment="cola_adjusted",
                        )
                    ]
                )
            ],
        )
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "household.members[0].income_streams[0].annual_amount"
    assert flags[0].severity == "blocking"


def test_validate_accepts_well_formed_income_stream():
    scenario = _clean_scenario(
        household=Household(
            filing_status="single",
            members=[
                _member(
                    income_streams=[
                        IncomeStream(
                            label="State Pension",
                            stream_type="pension",
                            start_age=62,
                            end_age=90,
                            annual_amount=18_000.0,
                            inflation_adjustment="cola_adjusted",
                        )
                    ]
                )
            ],
        )
    )
    assert validate(scenario) == []


def test_validate_accepts_income_stream_end_age_equal_to_start_age():
    scenario = _clean_scenario(
        household=Household(
            filing_status="single",
            members=[
                _member(
                    income_streams=[
                        IncomeStream(
                            label="One-year annuity",
                            stream_type="annuity",
                            start_age=70,
                            end_age=70,
                            annual_amount=5_000.0,
                            inflation_adjustment="fixed_nominal",
                        )
                    ]
                )
            ],
        )
    )
    assert validate(scenario) == []


def test_validate_accepts_full_retirement_age_inside_plausible_range():
    # 016-ss-claiming-age-actuarial-adjustment
    for fra in (65.0, 66.0, 67.0):
        scenario = _clean_scenario(
            household=Household(filing_status="single", members=[_member(fra=fra)])
        )
        assert validate(scenario) == []


def test_validate_flags_full_retirement_age_outside_plausible_range_as_warning():
    # 016-ss-claiming-age-actuarial-adjustment
    scenario = _clean_scenario(
        household=Household(filing_status="single", members=[_member(fra=64.0)])
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "household.members[0].full_retirement_age"
    assert flags[0].severity == "warning"

    scenario.validation_flags = flags
    assert scenario.is_usable is True


def test_validate_never_flags_full_retirement_age_when_none():
    # A HouseholdMember constructed directly (bypassing loader.parse_scenario(), which always
    # resolves a concrete float) still validates cleanly -- None is skipped, not treated as
    # implausible.
    scenario = _clean_scenario(
        household=Household(filing_status="single", members=[_member(fra=None)])
    )
    assert validate(scenario) == []


def test_validate_never_flags_predicted_death_age_when_none():
    # 017-ss-spousal-survivor-benefits: every existing scenario (which
    # never sets this field) validates cleanly -- None is skipped, not
    # treated as implausible or incoherent.
    scenario = _clean_scenario(
        household=Household(filing_status="single", members=[_member(predicted_death_age=None)])
    )
    assert validate(scenario) == []


def test_validate_accepts_predicted_death_age_inside_plausible_range():
    for death_age in (50, 85, 110):
        scenario = _clean_scenario(
            household=Household(filing_status="single", members=[_member(age=40, predicted_death_age=death_age)])
        )
        assert validate(scenario) == []


def test_validate_flags_predicted_death_age_outside_plausible_range_as_warning():
    # age=60 (matching _clean_scenario's own plan_to_age=60, so the
    # unrelated spending-vs-assets check stays quiet), predicted_death_age
    # =120: not blocking (120 >= 60), but still outside the [50, 110]
    # plausible range -- isolates the warning check from the blocking one
    # above.
    scenario = _clean_scenario(
        household=Household(filing_status="single", members=[_member(age=60, predicted_death_age=120)])
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "household.members[0].predicted_death_age"
    assert flags[0].severity == "warning"

    scenario.validation_flags = flags
    assert scenario.is_usable is True


def test_validate_flags_predicted_death_age_before_current_age_as_blocking():
    # A "prediction" of a death already in the past is incoherent, not
    # merely implausible -- distinct from the warning case above.
    scenario = _clean_scenario(
        household=Household(filing_status="single", members=[_member(age=60, predicted_death_age=59)])
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "household.members[0].predicted_death_age"
    assert flags[0].severity == "blocking"

    scenario.validation_flags = flags
    assert scenario.is_usable is False


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


# -- rp-595: auto Roth-conversion gap-window structural check --


def test_validate_flags_never_ending_wages_with_auto_gap_year_window_as_warning():
    scenario = _clean_scenario(
        household=Household(
            filing_status="single",
            members=[
                _member(
                    income_streams=[
                        IncomeStream(
                            label="Wages",
                            stream_type="earned_income",
                            start_age=60,
                            end_age=None,
                            annual_amount=80_000.0,
                            inflation_adjustment="cola_adjusted",
                        )
                    ]
                )
            ],
        ),
        roth_conversion=RothConversionPlan(strategy="fill_to_bracket", window_mode="auto_gap_year", ceiling_mode="named_bracket", named_bracket_rate=0.22),
    )
    flags = validate(scenario)
    assert len(flags) == 1
    assert flags[0].field == "roth_conversion.window_mode"
    assert flags[0].severity == "warning"
    assert "you" in flags[0].message


def test_validate_does_not_flag_auto_gap_year_window_when_wages_do_end():
    scenario = _clean_scenario(
        household=Household(
            filing_status="single",
            members=[
                _member(
                    income_streams=[
                        IncomeStream(
                            label="Wages",
                            stream_type="earned_income",
                            start_age=60,
                            end_age=65,
                            annual_amount=80_000.0,
                            inflation_adjustment="cola_adjusted",
                        )
                    ]
                )
            ],
        ),
        roth_conversion=RothConversionPlan(strategy="fill_to_bracket", window_mode="auto_gap_year", ceiling_mode="named_bracket", named_bracket_rate=0.22),
    )
    assert validate(scenario) == []


def test_validate_does_not_flag_never_ending_wages_when_window_mode_is_explicit():
    """The check only applies to window_mode=="auto_gap_year" -- the
    default/every-scenario-predating-rp-595 explicit mode is unaffected,
    even with a never-ending earned_income stream."""
    scenario = _clean_scenario(
        household=Household(
            filing_status="single",
            members=[
                _member(
                    income_streams=[
                        IncomeStream(
                            label="Wages",
                            stream_type="earned_income",
                            start_age=60,
                            end_age=None,
                            annual_amount=80_000.0,
                            inflation_adjustment="cola_adjusted",
                        )
                    ]
                )
            ],
        ),
        roth_conversion=RothConversionPlan(strategy="fill_to_bracket", window=(2026, 2030), bracket_ceiling_or_amount=200_000.0),
    )
    assert validate(scenario) == []


def test_validate_does_not_flag_auto_gap_year_window_with_no_roth_conversion_configured():
    scenario = _clean_scenario()  # roth_conversion defaults to None
    assert validate(scenario) == []
