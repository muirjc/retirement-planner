"""Shared strategy-comparison data model.

These dataclasses are the locked public shape described in
specs/004-strategy-comparison-layer/contracts/comparison-api.md ("Data
types" section) and specs/004-strategy-comparison-layer/data-model.md.
Types are imported from retirement_planner.mechanics and
retirement_planner.tax rather than redefined, continuing those features'
conventions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from retirement_planner.mechanics import AccountBalances, HsaContributionResult, PlanYearMechanicsResult, WithdrawalPlan
from retirement_planner.scenario import HsaContributionPlan
from retirement_planner.tax import FederalTaxResult, FigureUsage, IrmaaResult, NiitResult, StateTaxResult


class ReturnSchedule(Protocol):
    """The seam 005-simulation-engine's research.md §1 adds: anything
    run_plan_projection() can use for its per-plan-year growth factor.
    DeterministicReturnAssumption (below) and 005's ReturnPath both satisfy
    this by implementing return_for_plan_year(). See
    specs/005-simulation-engine/contracts/simulation-api.md.
    """

    def return_for_plan_year(self, plan_year: int) -> float: ...


@dataclass
class DeterministicReturnAssumption:
    """data-model.md § DeterministicReturnAssumption."""

    annual_real_return: float

    def return_for_plan_year(self, plan_year: int) -> float:
        """Satisfies ReturnSchedule: ignores plan_year, always returns
        annual_real_return (005-simulation-engine research.md §1)."""
        return self.annual_real_return


@dataclass
class StrategyConfiguration:
    """data-model.md § StrategyConfiguration."""

    label: str
    withdrawal_strategy: str
    conversion_strategy: str | None
    conversion_bracket_ceiling_or_amount: float | None
    conversion_window: tuple[int, int] | None
    claiming_ages: dict[str, int]
    hsa_contribution: HsaContributionPlan | None = None
    """010-advanced-tax-benefits contracts/comparison-api.md's correction:
    the held-fixed value every compare_*() function forces onto every
    candidate, the same way withdrawal_strategy/claiming_ages already
    are. Defaults to None, reproducing every existing StrategyConfiguration
    construction's exact current behavior unmodified."""


@dataclass
class PlanYearProjection:
    """data-model.md § PlanYearProjection."""

    plan_year: int
    tax_year: int
    mechanics: PlanYearMechanicsResult
    federal_tax: FederalTaxResult
    state_tax: StateTaxResult
    tax_funding_withdrawal: WithdrawalPlan
    starting_balances: AccountBalances
    ending_balances: AccountBalances
    shortfall: float
    irmaa: IrmaaResult  # 010-advanced-tax-benefits data-model.md § Projection extensions
    niit: NiitResult  # 010-advanced-tax-benefits data-model.md § Projection extensions
    hsa_contribution: HsaContributionResult  # 010-advanced-tax-benefits data-model.md § Projection extensions
    figures_used: list[FigureUsage] = field(default_factory=list)


@dataclass
class PlanOutcome:
    """data-model.md § PlanOutcome."""

    ending_balance: float
    first_shortfall_plan_year: int | None
    cumulative_tax_paid: float
    cumulative_irmaa_paid: float  # 010-advanced-tax-benefits data-model.md § Projection extensions
    cumulative_niit_paid: float  # 010-advanced-tax-benefits data-model.md § Projection extensions


@dataclass
class PlanProjection:
    """data-model.md § PlanProjection."""

    strategy: StrategyConfiguration
    return_assumption: DeterministicReturnAssumption
    years: list[PlanYearProjection]
    outcome: PlanOutcome


ComparisonDimension = Literal["roth_conversion_strategy", "withdrawal_sequencing", "claiming_age_grid"]


@dataclass
class ComparisonResult:
    """data-model.md § ComparisonResult."""

    dimension: ComparisonDimension
    return_assumption: DeterministicReturnAssumption
    projections: list[PlanProjection]
