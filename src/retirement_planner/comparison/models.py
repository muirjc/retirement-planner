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
    # 015-per-account-projection-detail (data-model.md § PlanYearProjection
    # extension): four additive fields, each retaining a figure the engine
    # already computes correctly this year but previously discarded before
    # returning -- no existing field's value changes, every existing
    # construction call site is unaffected by these defaults.
    member_rmd_amounts: dict[str, float] = field(default_factory=dict)
    """person_name -> that member's own exact RMD required_amount this
    year (pre-cap), 011-per-owner-accounts' own already-correct per-member
    figure, retained instead of being summed away."""
    member_social_security_benefits: dict[str, float] = field(default_factory=dict)
    """person_name -> that member's own gross Social Security benefit
    received this year -- 0.0 before that member's own claiming age, never
    omitted."""
    inherited_account_balances: dict[str, float] = field(default_factory=dict)
    """account_id -> that inherited account's own ending balance this
    year, snapshotted from InheritedAccountBalance.balance (012/013's own
    already-independently-tracked state)."""
    inherited_account_distributions: dict[str, float] = field(default_factory=dict)
    """account_id -> that inherited account's own distribution amount
    this year."""
    filing_status: Literal["single", "married_filing_jointly"] | None = None
    """018-survivor-scenario-projection: the EFFECTIVE filing status this
    year's federal_tax/state_tax/irmaa/niit were actually computed with --
    household.filing_status unchanged through a configured death year
    (inclusive) and every year before it; forced to "single" for every plan
    year after (data-model.md). Always populated by run_plan_projection();
    None only if some other caller constructs a PlanYearProjection directly
    without setting it. For a household with no configured death, every
    year's value equals household.filing_status unchanged -- an informative
    addition, not a behavior change."""
    effective_spending_need: float = 0.0
    """018-survivor-scenario-projection: the actual spending_need value
    passed into compute_plan_year_mechanics() this year --
    annual_spending_need unchanged through a configured death year
    (inclusive) and every year before it; annual_spending_need * (1 -
    household.survivor_spending_reduction_pct) for every plan year after
    (data-model.md). No existing mechanics-package result type echoes back
    its own spending_need input, so this is recorded here instead. Always
    populated by run_plan_projection(); 0.0 only if some other caller
    constructs a PlanYearProjection directly without setting it."""


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
