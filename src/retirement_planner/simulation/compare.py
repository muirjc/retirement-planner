"""Paired-draw comparison functions (FR-007-FR-011, FR-016): thin loops
over run_simulation(), each varying exactly one dimension while holding
every other input -- including the shared return_paths list itself -- fixed
across every candidate (FR-009). Mirrors 004-strategy-comparison-layer's
compare.py candidate-forcing pattern, substituting Monte Carlo aggregation
for a single deterministic projection. See
specs/005-simulation-engine/research.md §2 and contracts/simulation-api.md.
"""

from __future__ import annotations

from dataclasses import replace

from retirement_planner.comparison import StrategyConfiguration
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HsaContributionPlan

from .models import ReturnPath, SimulationComparisonResult, SurvivalCurve
from .monte_carlo import run_simulation

_MIN_CLAIMING_AGE = 62
_MAX_CLAIMING_AGE = 70


def _validate_consistent_generation_mode(return_paths: list[ReturnPath]) -> None:
    """Raises ValueError if return_paths mixes generation_mode values
    (FR-011, US3 Acceptance Scenario 3, research.md §2's "structurally
    guaranteed... per candidate, checked once per shared list" note)."""
    modes = {path.generation_mode for path in return_paths}
    if len(modes) > 1:
        raise ValueError(f"return_paths mixes generation modes: {sorted(modes)}")


def compare_states(
    household: Household,
    accounts: AccountBalances,
    traditional_ownership_shares: dict[str, float],
    annual_spending_need: float,
    states: list[str],
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    strategy: StrategyConfiguration,
    return_paths: list[ReturnPath],
    survival_curves: dict[str, SurvivalCurve] | None = None,
) -> SimulationComparisonResult:
    """Runs run_simulation() once per entry in states, holding strategy,
    return_paths, and every other argument fixed -- only state differs
    (FR-007, FR-009, research.md §2). This is 005's own comparison axis;
    004 never built it, since state is a run_plan_projection() argument,
    not a StrategyConfiguration field.
    """
    _validate_consistent_generation_mode(return_paths)
    runs = [
        run_simulation(
            household=household,
            accounts=accounts,
            traditional_ownership_shares=traditional_ownership_shares,
            annual_spending_need=annual_spending_need,
            state=state,
            reference_tax_year=reference_tax_year,
            start_plan_year=start_plan_year,
            start_tax_year=start_tax_year,
            plan_to_age=plan_to_age,
            strategy=strategy,
            return_paths=return_paths,
            candidate_label=state,
            survival_curves=survival_curves,
        )
        for state in states
    ]
    return SimulationComparisonResult(axis="state", return_paths=return_paths, runs=runs)


def compare_roth_conversion_strategies(
    household: Household,
    accounts: AccountBalances,
    traditional_ownership_shares: dict[str, float],
    annual_spending_need: float,
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    withdrawal_strategy: str,
    claiming_ages: dict[str, int],
    return_paths: list[ReturnPath],
    candidates: list[StrategyConfiguration],
    survival_curves: dict[str, SurvivalCurve] | None = None,
    hsa_contribution: HsaContributionPlan | None = None,
) -> SimulationComparisonResult:
    """Runs run_simulation() once per entry in candidates, forcing this
    call's shared withdrawal_strategy/claiming_ages/hsa_contribution onto
    every candidate so only the conversion dimension varies (FR-005
    parity with 004, FR-009; hsa_contribution per
    010-advanced-tax-benefits contracts/comparison-api.md).
    Mirrors 004's compare_roth_conversion_strategies() exactly, substituting
    return_paths for return_assumption."""
    _validate_consistent_generation_mode(return_paths)
    runs = [
        run_simulation(
            household=household,
            accounts=accounts,
            traditional_ownership_shares=traditional_ownership_shares,
            annual_spending_need=annual_spending_need,
            state=state,
            reference_tax_year=reference_tax_year,
            start_plan_year=start_plan_year,
            start_tax_year=start_tax_year,
            plan_to_age=plan_to_age,
            strategy=replace(
                candidate,
                withdrawal_strategy=withdrawal_strategy,
                claiming_ages=claiming_ages,
                hsa_contribution=hsa_contribution,
            ),
            return_paths=return_paths,
            candidate_label=candidate.label,
            survival_curves=survival_curves,
        )
        for candidate in candidates
    ]
    return SimulationComparisonResult(axis="roth_conversion_strategy", return_paths=return_paths, runs=runs)


def compare_withdrawal_sequencing_strategies(
    household: Household,
    accounts: AccountBalances,
    traditional_ownership_shares: dict[str, float],
    annual_spending_need: float,
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    conversion_strategy: str | None,
    conversion_bracket_ceiling_or_amount: float | None,
    conversion_window: tuple[int, int] | None,
    claiming_ages: dict[str, int],
    return_paths: list[ReturnPath],
    candidates: list[StrategyConfiguration],
    survival_curves: dict[str, SurvivalCurve] | None = None,
    hsa_contribution: HsaContributionPlan | None = None,
) -> SimulationComparisonResult:
    """Runs run_simulation() once per entry in candidates, forcing this
    call's shared conversion_strategy/conversion_bracket_ceiling_or_amount/
    conversion_window/claiming_ages/hsa_contribution onto every candidate
    so only the withdrawal-sequencing dimension varies (FR-006 parity
    with 004, FR-009; hsa_contribution per
    010-advanced-tax-benefits contracts/comparison-api.md).
    Mirrors 004's compare_withdrawal_sequencing_strategies() exactly,
    substituting return_paths for return_assumption."""
    _validate_consistent_generation_mode(return_paths)
    runs = [
        run_simulation(
            household=household,
            accounts=accounts,
            traditional_ownership_shares=traditional_ownership_shares,
            annual_spending_need=annual_spending_need,
            state=state,
            reference_tax_year=reference_tax_year,
            start_plan_year=start_plan_year,
            start_tax_year=start_tax_year,
            plan_to_age=plan_to_age,
            strategy=replace(
                candidate,
                conversion_strategy=conversion_strategy,
                conversion_bracket_ceiling_or_amount=conversion_bracket_ceiling_or_amount,
                conversion_window=conversion_window,
                claiming_ages=claiming_ages,
                hsa_contribution=hsa_contribution,
            ),
            return_paths=return_paths,
            candidate_label=candidate.label,
            survival_curves=survival_curves,
        )
        for candidate in candidates
    ]
    return SimulationComparisonResult(axis="withdrawal_sequencing", return_paths=return_paths, runs=runs)


def compare_claiming_age_grid(
    household: Household,
    accounts: AccountBalances,
    traditional_ownership_shares: dict[str, float],
    annual_spending_need: float,
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    withdrawal_strategy: str,
    conversion_strategy: str | None,
    conversion_bracket_ceiling_or_amount: float | None,
    conversion_window: tuple[int, int] | None,
    return_paths: list[ReturnPath],
    claiming_age_grid: list[dict[str, int]],
    survival_curves: dict[str, SurvivalCurve] | None = None,
    hsa_contribution: HsaContributionPlan | None = None,
) -> SimulationComparisonResult:
    """Runs run_simulation() once per grid entry, forcing this call's
    shared withdrawal_strategy/conversion_strategy/
    conversion_bracket_ceiling_or_amount/conversion_window/
    hsa_contribution onto every entry so only the claiming-age dimension
    varies (FR-008 parity with 004, FR-009; hsa_contribution per
    010-advanced-tax-benefits contracts/comparison-api.md -- this
    function builds each StrategyConfiguration directly, like 004's own
    version, so needs an explicit parameter here). Raises ValueError if
    any grid entry names a claiming age outside 62-70 (FR-010). Mirrors
    004's compare_claiming_age_grid() exactly, substituting return_paths
    for return_assumption."""
    for entry in claiming_age_grid:
        for person_name, age in entry.items():
            if not (_MIN_CLAIMING_AGE <= age <= _MAX_CLAIMING_AGE):
                raise ValueError(
                    f"claiming age {age} for {person_name!r} is outside "
                    f"[{_MIN_CLAIMING_AGE}, {_MAX_CLAIMING_AGE}]"
                )

    _validate_consistent_generation_mode(return_paths)
    runs = [
        run_simulation(
            household=household,
            accounts=accounts,
            traditional_ownership_shares=traditional_ownership_shares,
            annual_spending_need=annual_spending_need,
            state=state,
            reference_tax_year=reference_tax_year,
            start_plan_year=start_plan_year,
            start_tax_year=start_tax_year,
            plan_to_age=plan_to_age,
            strategy=StrategyConfiguration(
                label=f"claiming_ages_{index}",
                withdrawal_strategy=withdrawal_strategy,
                conversion_strategy=conversion_strategy,
                conversion_bracket_ceiling_or_amount=conversion_bracket_ceiling_or_amount,
                conversion_window=conversion_window,
                claiming_ages=claiming_ages_entry,
                hsa_contribution=hsa_contribution,
            ),
            return_paths=return_paths,
            candidate_label=f"claiming_ages_{index}",
            survival_curves=survival_curves,
        )
        for index, claiming_ages_entry in enumerate(claiming_age_grid)
    ]
    return SimulationComparisonResult(axis="claiming_age_grid", return_paths=return_paths, runs=runs)
