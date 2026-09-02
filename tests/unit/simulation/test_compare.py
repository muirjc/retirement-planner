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


# --- death_year_draws (023-probabilistic-death-draws rp-vgv, User Story 2) ---


def test_compare_states_reuses_the_identical_death_year_draws_across_every_candidate():
    """Acceptance Scenario 3, SC-004: every candidate's path i must
    reflect the identical drawn death year(s) as every other candidate's
    path i -- confirmed structurally, by comparing each candidate's own
    per-path filing-status sequence (018's own per-year audit field)
    rather than merely by coincidentally-equal aggregate outcomes."""
    from datetime import date

    from retirement_planner.simulation.compare import compare_states
    from retirement_planner.simulation.models import SurvivalCurve

    household = Household(
        filing_status="married_filing_jointly",
        members=[
            HouseholdMember(person_name="you", current_age=67, ss_claim_age=67, ss_annual_benefit=30_000),
            HouseholdMember(person_name="spouse", current_age=65, ss_claim_age=67, ss_annual_benefit=20_000),
        ],
    )
    accounts = AccountBalances(traditional=800_000, roth=0, taxable=0)
    strategy = StrategyConfiguration(
        label="test", withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
        claiming_ages={"you": 67, "spouse": 67},
    )
    # 2-year horizon (tax years 2026-2027 only) -- stays within SC's own
    # currently-documented bracket-table years (002's own scope), unlike
    # the longer horizons other fixtures in this file use for FL (which
    # has no bracket table to run out of years on).
    return_paths = [
        ReturnPath(start_plan_year=1, annual_returns=[0.0, 0.0], generation_mode="parametric", figures_used=[]),
        ReturnPath(start_plan_year=1, annual_returns=[0.0, 0.0], generation_mode="parametric", figures_used=[]),
    ]
    # One path with no death, one with "spouse" drawn to die at exactly
    # their own current_age (65) -- 2026 (the death year itself) stays
    # MFJ, 2027 switches to single (018's own "death year itself is still
    # MFJ" convention). A hand-crafted draw set (not
    # generate_death_age_draws()'s own output) is enough to isolate
    # compare_states()'s own passthrough behavior.
    death_year_draws = [{"you": None, "spouse": None}, {"you": None, "spouse": 65}]
    always_alive_curve = SurvivalCurve(
        person_name="placeholder", probabilities_by_age={age: 1.0 for age in range(50, 111)},
        citation="test fixture", last_verified=date(2026, 8, 28), verified=False,
    )
    survival_curves = {"you": always_alive_curve, "spouse": always_alive_curve}

    comparison = compare_states(
        household=household, accounts=accounts, traditional_ownership_shares={"you": 1.0, "spouse": 0.0},
        annual_spending_need=60_000, states=["FL", "SC"],
        reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=68,
        strategy=strategy, return_paths=return_paths,
        survival_curves=survival_curves, death_year_draws=death_year_draws,
    )

    fl_run, sc_run = comparison.runs
    for path_index in range(2):
        fl_statuses = [year.filing_status for year in fl_run.path_results[path_index].years]
        sc_statuses = [year.filing_status for year in sc_run.path_results[path_index].years]
        assert fl_statuses == sc_statuses
    # Sanity: the two paths actually differ from each other (the draws
    # varied path to path, not just candidate to candidate).
    assert [year.filing_status for year in fl_run.path_results[0].years] != [
        year.filing_status for year in fl_run.path_results[1].years
    ]
