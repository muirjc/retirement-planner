"""Unit tests for retirement_planner.simulation.compare: paired-draw
comparison across the state axis (US2, new relative to 004) and the
strategy/order/claiming-age axes (US2, mirroring 004 with Monte Carlo
paths), plus the historical-bootstrap mode-mismatch guard (US3) and the
stress-scenario uniform-application guarantee (US4).
"""

import pytest

from retirement_planner.comparison import StrategyConfiguration
from retirement_planner.mechanics import AccountBalances, InheritedAccountBalance
from retirement_planner.scenario import Household, HouseholdMember
from retirement_planner.simulation.models import ReturnPath

_HOUSEHOLD = Household(
    filing_status="single",
    members=[HouseholdMember(person_name="you", current_age=90, ss_claim_age=99, ss_annual_benefit=0)],
)
_ZERO_INCOME_ACCOUNTS = AccountBalances(traditional=0, roth=0, taxable=100)
_STRATEGY = StrategyConfiguration(
    label="test",
    withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy=None,
    conversion_bracket_ceiling_or_amount=None,
    conversion_window=None,
    claiming_ages={"you": 99},
)
_COMMON_KWARGS = dict(
    household=_HOUSEHOLD,
    accounts=_ZERO_INCOME_ACCOUNTS,
    traditional_ownership_shares={"you": 1.0},
    annual_spending_need=50,
    reference_tax_year=2026,
    start_plan_year=1,
    start_tax_year=2026,
    plan_to_age=91,
)
_RETURN_PATHS = [
    ReturnPath(start_plan_year=1, annual_returns=[0.0, 0.0], generation_mode="parametric", figures_used=[]),
    ReturnPath(start_plan_year=1, annual_returns=[-0.5, 0.0], generation_mode="parametric", figures_used=[]),
]


# --- compare_states() (US2, new state axis) ---


def test_compare_states_reuses_the_identical_return_paths_object_per_candidate():
    from retirement_planner.simulation.compare import compare_states

    comparison = compare_states(
        **_COMMON_KWARGS, states=["FL", "SC"], strategy=_STRATEGY, return_paths=_RETURN_PATHS,
    )

    assert comparison.axis == "state"
    assert len(comparison.runs) == 2
    for run in comparison.runs:
        assert run.path_results[0].return_assumption is _RETURN_PATHS[0]
        assert run.path_results[1].return_assumption is _RETURN_PATHS[1]


def test_compare_states_produces_equal_outcomes_when_financially_identical():
    from retirement_planner.simulation.compare import compare_states

    # Zero ordinary_income (no RMD, no conversion, no SS) => $0 tax under
    # every state module regardless of bracket/exclusion structure -- these
    # three candidates are financially identical for this fixture scenario
    # (Acceptance Scenario US2.4). A single-plan-year horizon (tax_year
    # 2026 only) keeps this within every state module's documented years --
    # DE's bracket table currently only documents 2026 (002's own scope).
    single_year_kwargs = {**_COMMON_KWARGS, "plan_to_age": 90}
    comparison = compare_states(
        **single_year_kwargs, states=["FL", "SC", "DE"], strategy=_STRATEGY, return_paths=_RETURN_PATHS,
    )

    success_rates = {run.success_rate for run in comparison.runs}
    assert len(success_rates) == 1
    percentile_bands = {tuple((b.plan_year, tuple(sorted(b.percentiles.items()))) for b in run.percentile_bands) for run in comparison.runs}
    assert len(percentile_bands) == 1


# --- other axes (US2, mirroring 004 with Monte Carlo paths) ---


def test_compare_roth_conversion_strategies_reuses_the_identical_return_paths_object():
    from retirement_planner.simulation.compare import compare_roth_conversion_strategies

    candidates = [
        StrategyConfiguration(
            label="no_conversion", withdrawal_strategy="rmd_taxable_traditional_roth",
            conversion_strategy=None, conversion_bracket_ceiling_or_amount=None,
            conversion_window=None, claiming_ages={"you": 99},
        ),
    ]

    comparison = compare_roth_conversion_strategies(
        **_COMMON_KWARGS, state="FL", withdrawal_strategy="rmd_taxable_traditional_roth",
        claiming_ages={"you": 99}, return_paths=_RETURN_PATHS, candidates=candidates,
    )

    assert comparison.axis == "roth_conversion_strategy"
    assert comparison.runs[0].path_results[0].return_assumption is _RETURN_PATHS[0]


def test_compare_roth_conversion_strategies_no_cross_candidate_leakage_in_inherited_distributions():
    """012-inherited-ira-rmd rp-mt7: mirrors comparison/compare.py's own
    test_no_cross_candidate_leakage_in_inherited_distributions -- each
    candidate's run_simulation() call must see the identical, unmutated
    starting inherited balance, not another candidate's already-decremented
    one (monte_carlo.py's own module docstring)."""
    from retirement_planner.simulation.compare import compare_roth_conversion_strategies

    candidates = [
        StrategyConfiguration(
            label="fill_to_bracket", withdrawal_strategy="ignored",
            conversion_strategy="fill_to_bracket", conversion_bracket_ceiling_or_amount=206_000,
            conversion_window=(2026, 2030), claiming_ages={"ignored": 0},
        ),
        StrategyConfiguration(
            label="no_conversion", withdrawal_strategy="ignored",
            conversion_strategy=None, conversion_bracket_ceiling_or_amount=None,
            conversion_window=None, claiming_ages={"ignored": 0},
        ),
    ]
    inherited_accounts = [
        InheritedAccountBalance(
            account_id="traditional-1", balance=250_000.0, death_year=2023,
            decedent_age_at_death=80, depletion_deadline_year=2033, beneficiary_person_name="you",
        )
    ]

    comparison = compare_roth_conversion_strategies(
        **_COMMON_KWARGS, state="FL", withdrawal_strategy="rmd_taxable_traditional_roth",
        claiming_ages={"you": 99}, return_paths=_RETURN_PATHS, candidates=candidates,
        inherited_accounts=inherited_accounts,
    )

    first_path_first_year_distributions = {
        run.path_results[0].years[0].mechanics.withdrawal_plan.inherited_distribution_drawn
        for run in comparison.runs
    }
    assert len(first_path_first_year_distributions) == 1
    assert first_path_first_year_distributions.pop() > 0
    assert inherited_accounts[0].balance == 250_000.0


def test_compare_withdrawal_sequencing_strategies_reuses_the_identical_return_paths_object():
    from retirement_planner.simulation.compare import compare_withdrawal_sequencing_strategies

    comparison = compare_withdrawal_sequencing_strategies(
        **_COMMON_KWARGS, state="FL", conversion_strategy=None, conversion_bracket_ceiling_or_amount=None,
        conversion_window=None, claiming_ages={"you": 99}, return_paths=_RETURN_PATHS, candidates=[_STRATEGY],
    )

    assert comparison.axis == "withdrawal_sequencing"
    assert comparison.runs[0].path_results[0].return_assumption is _RETURN_PATHS[0]


def test_compare_claiming_age_grid_reuses_the_identical_return_paths_object():
    from retirement_planner.simulation.compare import compare_claiming_age_grid

    comparison = compare_claiming_age_grid(
        **_COMMON_KWARGS, state="FL", withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
        return_paths=_RETURN_PATHS, claiming_age_grid=[{"you": 67}],
    )

    assert comparison.axis == "claiming_age_grid"
    assert comparison.runs[0].path_results[0].return_assumption is _RETURN_PATHS[0]


def test_compare_claiming_age_grid_entry_missing_a_household_member_raises_value_error():
    """Regression for rp-dd9: a married household's grid entry omitting
    one member previously reached run_plan_projection()'s own
    claiming_ages[member.person_name] lookup as an uncaught KeyError
    (found via e2e testing) instead of this function's own validation."""
    from retirement_planner.simulation.compare import compare_claiming_age_grid

    married_household = Household(
        filing_status="married_filing_jointly",
        members=[
            HouseholdMember(person_name="you", current_age=90, ss_claim_age=99, ss_annual_benefit=0),
            HouseholdMember(person_name="spouse", current_age=88, ss_claim_age=99, ss_annual_benefit=0),
        ],
    )
    kwargs = {**_COMMON_KWARGS, "household": married_household}

    with pytest.raises(ValueError):
        compare_claiming_age_grid(
            **kwargs, state="FL", withdrawal_strategy="rmd_taxable_traditional_roth",
            conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
            return_paths=_RETURN_PATHS, claiming_age_grid=[{"you": 67}],  # missing "spouse"
        )


# --- single-candidate validity (US2, Acceptance Scenario US2.5, FR-010) ---


# --- generation-mode mismatch guard (US3, FR-011) ---


def test_compare_states_rejects_return_paths_mixing_generation_modes():
    from retirement_planner.simulation.compare import compare_states

    mixed_paths = [
        ReturnPath(start_plan_year=1, annual_returns=[0.0, 0.0], generation_mode="parametric", figures_used=[]),
        ReturnPath(start_plan_year=1, annual_returns=[-0.5, 0.0], generation_mode="historical_bootstrap", figures_used=[]),
    ]

    with pytest.raises(ValueError):
        compare_states(**_COMMON_KWARGS, states=["FL", "SC"], strategy=_STRATEGY, return_paths=mixed_paths)


# --- stress-scenario uniform application across candidates (US4, FR-016) ---


def test_stress_tested_return_paths_apply_the_identical_shock_to_every_candidate():
    from retirement_planner.simulation.compare import compare_states
    from retirement_planner.simulation.models import StressScenario
    from retirement_planner.simulation.returns import apply_stress_scenario

    stress = StressScenario(magnitude=-0.90, duration_years=1, start_plan_year=1)
    stressed_paths = apply_stress_scenario(_RETURN_PATHS, stress, horizon_last_plan_year=2)

    comparison = compare_states(
        **_COMMON_KWARGS, states=["FL", "SC"], strategy=_STRATEGY, return_paths=stressed_paths,
    )

    # Every candidate's paths carry the identical forced first-year shock --
    # the stress override lives in the shared return_paths list, not in
    # anything compare_states() varies per candidate.
    for run in comparison.runs:
        assert run.path_results[0].return_assumption.annual_returns[0] == -0.90
        assert run.path_results[1].return_assumption.annual_returns[0] == -0.90


def test_all_four_compare_functions_accept_a_single_candidate():
    from retirement_planner.simulation.compare import (
        compare_claiming_age_grid,
        compare_roth_conversion_strategies,
        compare_states,
        compare_withdrawal_sequencing_strategies,
    )

    state_result = compare_states(
        **_COMMON_KWARGS, states=["FL"], strategy=_STRATEGY, return_paths=_RETURN_PATHS,
    )
    assert len(state_result.runs) == 1

    conversion_result = compare_roth_conversion_strategies(
        **_COMMON_KWARGS, state="FL", withdrawal_strategy="rmd_taxable_traditional_roth",
        claiming_ages={"you": 99}, return_paths=_RETURN_PATHS, candidates=[_STRATEGY],
    )
    assert len(conversion_result.runs) == 1

    order_result = compare_withdrawal_sequencing_strategies(
        **_COMMON_KWARGS, state="FL", conversion_strategy=None, conversion_bracket_ceiling_or_amount=None,
        conversion_window=None, claiming_ages={"you": 99}, return_paths=_RETURN_PATHS, candidates=[_STRATEGY],
    )
    assert len(order_result.runs) == 1

    grid_result = compare_claiming_age_grid(
        **_COMMON_KWARGS, state="FL", withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
        return_paths=_RETURN_PATHS, claiming_age_grid=[{"you": 67}],
    )
    assert len(grid_result.runs) == 1
