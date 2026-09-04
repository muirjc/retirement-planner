"""Unit tests for rp_bff.resolution: the shared scenario/strategy
resolution helper User Stories 3-5 all build on (data-model.md § Run
Request/Response).
"""

import pytest

from retirement_planner.scenario import (
    Account,
    Household,
    HouseholdMember,
    InheritedIraDetails,
    MarketAssumptions,
    RothConversionPlan,
    Scenario,
    SimulationSettings,
    SpendingProfile,
    save_scenario,
)


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


def _scenario(name="base_case", roth_conversion=None, state="FL"):
    return Scenario(
        name=name,
        household=Household(
            filing_status="married_filing_jointly",
            members=[
                HouseholdMember(person_name="you", current_age=60, ss_claim_age=67, ss_annual_benefit=32_000),
                HouseholdMember(person_name="spouse", current_age=58, ss_claim_age=70, ss_annual_benefit=24_000),
            ],
        ),
        accounts=[
            Account(account_type="traditional", balance=1_000_000, owner="you"),
            Account(account_type="traditional", balance=500_000, owner="spouse"),
            Account(account_type="roth", balance=400_000, owner="you"),
            Account(account_type="taxable", balance=200_000, owner="you"),
        ],
        spending=SpendingProfile(annual_need_real=110_000),
        state=state,
        market_assumptions=_market_assumptions(),
        simulation_settings=SimulationSettings(n_paths=200, seed=42, plan_to_age=95),
        roth_conversion=roth_conversion,
    )


def test_strategy_configuration_claiming_ages_come_from_ss_claim_age(tmp_path):
    save_scenario(_scenario(), scenarios_dir=tmp_path)
    from rp_bff.resolution import resolve_run_context

    context = resolve_run_context(
        "base_case",
        withdrawal_strategy=None,
        state=None,
        plan_to_age=None,
        n_paths=None,
        seed=None,
        reference_tax_year=2026,
        scenarios_dir=tmp_path,
    )

    assert context.strategy.claiming_ages == {"you": 67, "spouse": 70}


def test_strategy_configuration_conversion_fields_come_from_roth_conversion_plan(tmp_path):
    plan = RothConversionPlan(strategy="fill_to_bracket", bracket_ceiling_or_amount=206_700, window=(2028, 2034))
    save_scenario(_scenario(roth_conversion=plan), scenarios_dir=tmp_path)
    from rp_bff.resolution import resolve_run_context

    context = resolve_run_context(
        "base_case",
        withdrawal_strategy=None,
        state=None,
        plan_to_age=None,
        n_paths=None,
        seed=None,
        reference_tax_year=2026,
        scenarios_dir=tmp_path,
    )

    assert context.strategy.conversion_strategy == "fill_to_bracket"
    assert context.strategy.conversion_bracket_ceiling_or_amount == 206_700
    assert context.strategy.conversion_window == (2028, 2034)


def test_no_roth_conversion_plan_yields_none_conversion_fields(tmp_path):
    save_scenario(_scenario(roth_conversion=None), scenarios_dir=tmp_path)
    from rp_bff.resolution import resolve_run_context

    context = resolve_run_context(
        "base_case",
        withdrawal_strategy=None,
        state=None,
        plan_to_age=None,
        n_paths=None,
        seed=None,
        reference_tax_year=2026,
        scenarios_dir=tmp_path,
    )

    assert context.strategy.conversion_strategy is None
    assert context.strategy.conversion_bracket_ceiling_or_amount is None
    assert context.strategy.conversion_window is None


# -- rp-1kz: auto conversion window / named-bracket ceiling / netting --


def test_strategy_configuration_auto_window_and_named_bracket_fields_come_from_roth_conversion_plan(tmp_path):
    plan = RothConversionPlan(
        strategy="fill_to_bracket", window_mode="auto_gap_year", ceiling_mode="named_bracket", named_bracket_rate=0.22,
    )
    save_scenario(_scenario(roth_conversion=plan), scenarios_dir=tmp_path)
    from rp_bff.resolution import resolve_run_context

    context = resolve_run_context(
        "base_case",
        withdrawal_strategy=None,
        state=None,
        plan_to_age=None,
        n_paths=None,
        seed=None,
        reference_tax_year=2026,
        scenarios_dir=tmp_path,
    )

    assert context.strategy.conversion_window_mode == "auto_gap_year"
    assert context.strategy.conversion_ceiling_mode == "named_bracket"
    assert context.strategy.conversion_named_bracket_rate == 0.22
    assert context.strategy.conversion_window is None
    assert context.strategy.conversion_bracket_ceiling_or_amount is None


def test_no_roth_conversion_plan_yields_default_mode_fields(tmp_path):
    save_scenario(_scenario(roth_conversion=None), scenarios_dir=tmp_path)
    from rp_bff.resolution import resolve_run_context

    context = resolve_run_context(
        "base_case",
        withdrawal_strategy=None,
        state=None,
        plan_to_age=None,
        n_paths=None,
        seed=None,
        reference_tax_year=2026,
        scenarios_dir=tmp_path,
    )

    assert context.strategy.conversion_window_mode == "explicit"
    assert context.strategy.conversion_ceiling_mode == "dollar_amount"
    assert context.strategy.conversion_named_bracket_rate is None


def test_unknown_named_bracket_rate_is_rejected(tmp_path):
    plan = RothConversionPlan(
        strategy="fill_to_bracket", window_mode="auto_gap_year", ceiling_mode="named_bracket", named_bracket_rate=0.23,
    )
    save_scenario(_scenario(roth_conversion=plan), scenarios_dir=tmp_path)
    from rp_bff.resolution import UnknownReferenceValueError, resolve_run_context

    with pytest.raises(UnknownReferenceValueError) as exc_info:
        resolve_run_context(
            "base_case",
            withdrawal_strategy=None,
            state=None,
            plan_to_age=None,
            n_paths=None,
            seed=None,
            reference_tax_year=2026,
            scenarios_dir=tmp_path,
        )
    assert exc_info.value.field == "conversion_named_bracket_rate"
    assert exc_info.value.value == "0.23"


def test_net_earned_income_against_spending_comes_from_scenario_spending(tmp_path):
    scenario = _scenario()
    scenario.spending.net_earned_income_against_spending = True
    save_scenario(scenario, scenarios_dir=tmp_path)
    from rp_bff.resolution import resolve_run_context

    context = resolve_run_context(
        "base_case",
        withdrawal_strategy=None,
        state=None,
        plan_to_age=None,
        n_paths=None,
        seed=None,
        reference_tax_year=2026,
        scenarios_dir=tmp_path,
    )

    assert context.net_earned_income_against_spending is True


def test_net_earned_income_against_spending_defaults_to_false(tmp_path):
    save_scenario(_scenario(), scenarios_dir=tmp_path)
    from rp_bff.resolution import resolve_run_context

    context = resolve_run_context(
        "base_case",
        withdrawal_strategy=None,
        state=None,
        plan_to_age=None,
        n_paths=None,
        seed=None,
        reference_tax_year=2026,
        scenarios_dir=tmp_path,
    )

    assert context.net_earned_income_against_spending is False


def test_accounts_are_summed_by_type(tmp_path):
    save_scenario(_scenario(), scenarios_dir=tmp_path)
    from rp_bff.resolution import resolve_run_context

    context = resolve_run_context(
        "base_case",
        withdrawal_strategy=None,
        state=None,
        plan_to_age=None,
        n_paths=None,
        seed=None,
        reference_tax_year=2026,
        scenarios_dir=tmp_path,
    )

    assert context.accounts.traditional == 1_500_000  # two traditional entries summed
    assert context.accounts.roth == 400_000
    assert context.accounts.taxable == 200_000


def test_inherited_account_excluded_from_pooled_accounts_and_ownership_shares(tmp_path):
    """012-inherited-ira-rmd (data-model.md § Exclusion from pooling): an
    inherited account contributes to neither the pooled AccountBalances
    total nor any member's traditional_ownership_shares numerator/
    denominator."""
    scenario = _scenario()
    scenario.accounts.append(
        Account(
            account_type="traditional",
            balance=250_000,
            owner="you",
            account_id="inherited-1",
            inherited=InheritedIraDetails(
                death_year=2023,
                decedent_age_at_death=80,
                decedent_was_taking_rmds=True,
                beneficiary_relationship="other_individual",
                beneficiary_classification="non_eligible_designated_beneficiary",
            ),
        )
    )
    save_scenario(scenario, scenarios_dir=tmp_path)
    from rp_bff.resolution import resolve_run_context

    context = resolve_run_context(
        "base_case",
        withdrawal_strategy=None,
        state=None,
        plan_to_age=None,
        n_paths=None,
        seed=None,
        reference_tax_year=2026,
        scenarios_dir=tmp_path,
    )

    # Unchanged from the non-inherited-only fixture above -- the $250k
    # inherited account is not part of this pooled total.
    assert context.accounts.traditional == 1_500_000
    assert context.traditional_ownership_shares["you"] + context.traditional_ownership_shares["spouse"] == pytest.approx(1.0)


def test_inherited_accounts_derived_with_stable_ids_and_deadline(tmp_path):
    scenario = _scenario()
    scenario.accounts.append(
        Account(
            account_type="traditional",
            balance=250_000,
            owner="you",
            account_id="inherited-1",
            inherited=InheritedIraDetails(
                death_year=2023,
                decedent_age_at_death=80,
                decedent_was_taking_rmds=True,
                beneficiary_relationship="other_individual",
                beneficiary_classification="non_eligible_designated_beneficiary",
            ),
        )
    )
    save_scenario(scenario, scenarios_dir=tmp_path)
    from rp_bff.resolution import resolve_run_context

    context = resolve_run_context(
        "base_case",
        withdrawal_strategy=None,
        state=None,
        plan_to_age=None,
        n_paths=None,
        seed=None,
        reference_tax_year=2026,
        scenarios_dir=tmp_path,
    )

    assert len(context.inherited_accounts) == 1
    inherited = context.inherited_accounts[0]
    assert inherited.account_id == "inherited-1"
    assert inherited.balance == 250_000
    assert inherited.death_year == 2023
    assert inherited.decedent_age_at_death == 80
    assert inherited.depletion_deadline_year == 2033


def test_inherited_account_pre_secure_act_death_has_no_forced_depletion_deadline(tmp_path):
    """rp-bdb: death_year < 2020 is grandfathered under the pre-Act rules
    -- no forced-depletion deadline at all, regardless of what
    beneficiary_classification the scenario recorded (here, still
    "non_eligible_designated_beneficiary", which post-Act would compute
    death_year + 10 = 2017, i.e. already years before this plan's own
    reference_tax_year=2026)."""
    scenario = _scenario()
    scenario.accounts.append(
        Account(
            account_type="traditional",
            balance=250_000,
            owner="you",
            account_id="inherited-1",
            inherited=InheritedIraDetails(
                death_year=2007,
                decedent_age_at_death=67,
                decedent_was_taking_rmds=True,
                beneficiary_relationship="other_individual",
                beneficiary_classification="non_eligible_designated_beneficiary",
            ),
        )
    )
    save_scenario(scenario, scenarios_dir=tmp_path)
    from rp_bff.resolution import resolve_run_context

    context = resolve_run_context(
        "base_case",
        withdrawal_strategy=None,
        state=None,
        plan_to_age=None,
        n_paths=None,
        seed=None,
        reference_tax_year=2026,
        scenarios_dir=tmp_path,
    )

    inherited = context.inherited_accounts[0]
    assert inherited.death_year == 2007
    assert inherited.depletion_deadline_year > 2100  # far-future sentinel, not death_year + 10 (2017)


def test_no_inherited_accounts_yields_empty_list(tmp_path):
    save_scenario(_scenario(), scenarios_dir=tmp_path)
    from rp_bff.resolution import resolve_run_context

    context = resolve_run_context(
        "base_case",
        withdrawal_strategy=None,
        state=None,
        plan_to_age=None,
        n_paths=None,
        seed=None,
        reference_tax_year=2026,
        scenarios_dir=tmp_path,
    )

    assert context.inherited_accounts == []


def test_omitted_optional_fields_default_from_scenario_simulation_settings(tmp_path):
    save_scenario(_scenario(), scenarios_dir=tmp_path)
    from rp_bff.resolution import resolve_run_context

    context = resolve_run_context(
        "base_case",
        withdrawal_strategy=None,
        state=None,
        plan_to_age=None,
        n_paths=None,
        seed=None,
        reference_tax_year=2026,
        scenarios_dir=tmp_path,
    )

    assert context.plan_to_age == 95
    assert context.n_paths == 200
    assert context.seed == 42
    assert context.state == "FL"


def test_explicit_overrides_win_over_scenario_defaults(tmp_path):
    save_scenario(_scenario(), scenarios_dir=tmp_path)
    from rp_bff.resolution import resolve_run_context

    context = resolve_run_context(
        "base_case",
        withdrawal_strategy=None,
        state="SC",
        plan_to_age=80,
        n_paths=50,
        seed=7,
        reference_tax_year=2026,
        scenarios_dir=tmp_path,
    )

    assert context.plan_to_age == 80
    assert context.n_paths == 50
    assert context.seed == 7
    assert context.state == "SC"


# --- 026-advanced-simulation-options: generate_configured_return_paths() ---


def _resolved_context(tmp_path, n_paths=20, seed=42, plan_to_age=95):
    save_scenario(_scenario(), scenarios_dir=tmp_path)
    from rp_bff.resolution import resolve_run_context

    return resolve_run_context(
        "base_case",
        withdrawal_strategy=None,
        state=None,
        plan_to_age=plan_to_age,
        n_paths=n_paths,
        seed=seed,
        reference_tax_year=2026,
        scenarios_dir=tmp_path,
    )


def test_default_generation_mode_matches_generate_return_paths_directly(tmp_path):
    from retirement_planner.simulation import generate_return_paths
    from rp_bff.resolution import generate_configured_return_paths

    context = _resolved_context(tmp_path)

    configured = generate_configured_return_paths(
        context,
        horizon_years=10,
        start_plan_year=1,
        generation_mode="parametric",
        historical_block_length=10,
        stress_scenario=None,
    )
    direct = generate_return_paths(
        market_assumptions=context.scenario.market_assumptions,
        path_count=context.n_paths,
        horizon_years=10,
        start_plan_year=1,
        seed=context.seed,
    )

    assert configured == direct


def test_path_count_and_seed_overrides_default_to_context_values_when_omitted(tmp_path):
    """rp-9hl: omitting path_count/seed reproduces every existing caller's
    exact prior behavior (context.n_paths/context.seed) unchanged."""
    from rp_bff.resolution import generate_configured_return_paths

    context = _resolved_context(tmp_path, n_paths=20, seed=42)

    without_override = generate_configured_return_paths(
        context, horizon_years=10, start_plan_year=1, generation_mode="parametric", historical_block_length=10, stress_scenario=None,
    )
    with_explicit_matching_values = generate_configured_return_paths(
        context, horizon_years=10, start_plan_year=1, generation_mode="parametric", historical_block_length=10, stress_scenario=None,
        path_count=20, seed=42,
    )

    assert without_override == with_explicit_matching_values


def test_path_count_override_changes_the_number_of_paths_generated(tmp_path):
    """rp-9hl: the sustainable-spending search's own reason for this
    override -- a reduced path count independent of context.n_paths."""
    from rp_bff.resolution import generate_configured_return_paths

    context = _resolved_context(tmp_path, n_paths=20, seed=42)

    reduced = generate_configured_return_paths(
        context, horizon_years=10, start_plan_year=1, generation_mode="parametric", historical_block_length=10, stress_scenario=None,
        path_count=5,
    )

    assert len(reduced) == 5


def test_historical_bootstrap_mode_returns_paths_citing_historical_returns(tmp_path):
    from rp_bff.resolution import generate_configured_return_paths

    context = _resolved_context(tmp_path)

    paths = generate_configured_return_paths(
        context,
        horizon_years=10,
        start_plan_year=1,
        generation_mode="historical_bootstrap",
        historical_block_length=10,
        stress_scenario=None,
    )

    assert all(path.generation_mode == "historical_bootstrap" for path in paths)
    assert all(any(figure.name == "historical_annual_real_returns" for figure in path.figures_used) for path in paths)
    assert all(figure.verified is False for path in paths for figure in path.figures_used)


def test_stress_scenario_overrides_the_configured_window_regardless_of_mode(tmp_path):
    from retirement_planner.simulation import StressScenario
    from rp_bff.resolution import generate_configured_return_paths

    context = _resolved_context(tmp_path)
    stress = StressScenario(magnitude=-0.5, duration_years=2, start_plan_year=1)

    paths = generate_configured_return_paths(
        context,
        horizon_years=10,
        start_plan_year=1,
        generation_mode="parametric",
        historical_block_length=10,
        stress_scenario=stress,
    )

    for path in paths:
        assert path.annual_returns[0] == pytest.approx(-0.5)
        assert path.annual_returns[1] == pytest.approx(-0.5)


def test_none_stress_scenario_leaves_paths_unmodified(tmp_path):
    from retirement_planner.simulation import generate_return_paths
    from rp_bff.resolution import generate_configured_return_paths

    context = _resolved_context(tmp_path)

    configured = generate_configured_return_paths(
        context,
        horizon_years=10,
        start_plan_year=1,
        generation_mode="parametric",
        historical_block_length=10,
        stress_scenario=None,
    )
    direct = generate_return_paths(
        market_assumptions=context.scenario.market_assumptions,
        path_count=context.n_paths,
        horizon_years=10,
        start_plan_year=1,
        seed=context.seed,
    )

    assert configured == direct


def test_invalid_block_length_raises_value_error(tmp_path):
    from rp_bff.resolution import generate_configured_return_paths

    context = _resolved_context(tmp_path)

    with pytest.raises(ValueError):
        generate_configured_return_paths(
            context,
            horizon_years=10,
            start_plan_year=1,
            generation_mode="historical_bootstrap",
            historical_block_length=0,
            stress_scenario=None,
        )


def test_stress_window_past_horizon_raises_value_error(tmp_path):
    from retirement_planner.simulation import StressScenario
    from rp_bff.resolution import generate_configured_return_paths

    context = _resolved_context(tmp_path)
    stress = StressScenario(magnitude=-0.3, duration_years=5, start_plan_year=10)

    with pytest.raises(ValueError):
        generate_configured_return_paths(
            context,
            horizon_years=10,
            start_plan_year=1,
            generation_mode="parametric",
            historical_block_length=10,
            stress_scenario=stress,
        )


def test_invalid_simulation_options_error_shape():
    from rp_bff.resolution import invalid_simulation_options_error

    http_exc = invalid_simulation_options_error(ValueError("block_length must be positive, got 0"))

    assert http_exc.status_code == 422
    assert http_exc.detail == {"error": "invalid_simulation_options", "detail": "block_length must be positive, got 0"}


def test_unknown_state_is_rejected(tmp_path):
    save_scenario(_scenario(), scenarios_dir=tmp_path)
    from rp_bff.resolution import UnknownReferenceValueError, resolve_run_context

    with pytest.raises(UnknownReferenceValueError) as exc_info:
        resolve_run_context(
            "base_case",
            withdrawal_strategy=None,
            state="ZZ",
            plan_to_age=None,
            n_paths=None,
            seed=None,
            reference_tax_year=2026,
            scenarios_dir=tmp_path,
        )
    assert exc_info.value.field == "state"
    assert exc_info.value.value == "ZZ"


def test_unknown_withdrawal_strategy_is_rejected(tmp_path):
    save_scenario(_scenario(), scenarios_dir=tmp_path)
    from rp_bff.resolution import UnknownReferenceValueError, resolve_run_context

    with pytest.raises(UnknownReferenceValueError) as exc_info:
        resolve_run_context(
            "base_case",
            withdrawal_strategy="not_a_real_strategy",
            state=None,
            plan_to_age=None,
            n_paths=None,
            seed=None,
            reference_tax_year=2026,
            scenarios_dir=tmp_path,
        )
    assert exc_info.value.field == "withdrawal_strategy"


def test_scenario_with_blocking_flags_is_rejected(tmp_path):
    invalid = _scenario()
    invalid.accounts = [Account(account_type="traditional", balance=-100)]
    save_scenario(invalid, scenarios_dir=tmp_path)
    from rp_bff.resolution import BlockingValidationFlagsError, resolve_run_context

    with pytest.raises(BlockingValidationFlagsError) as exc_info:
        resolve_run_context(
            "base_case",
            withdrawal_strategy=None,
            state=None,
            plan_to_age=None,
            n_paths=None,
            seed=None,
            reference_tax_year=2026,
            scenarios_dir=tmp_path,
        )
    assert any(flag.severity == "blocking" for flag in exc_info.value.flags)
