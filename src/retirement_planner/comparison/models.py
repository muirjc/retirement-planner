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
from retirement_planner.tax import (
    EarlyWithdrawalPenaltyResult,
    FederalTaxResult,
    FicaTaxResult,
    FigureUsage,
    IrmaaResult,
    NiitResult,
    StateTaxResult,
)


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
    conversion_window_mode: Literal["explicit", "auto_gap_year"] = "explicit"
    conversion_ceiling_mode: Literal["dollar_amount", "named_bracket"] = "dollar_amount"
    conversion_named_bracket_rate: float | None = None
    """rp-595: mirror run-time-configurable counterparts of
    RothConversionPlan's own window_mode/ceiling_mode/named_bracket_rate
    (scenario/models.py) -- when conversion_window_mode=="auto_gap_year"
    or conversion_ceiling_mode=="named_bracket", run_plan_projection()
    resolves conversion_window/conversion_bracket_ceiling_or_amount above
    itself each run/year rather than using them as given. Defaults
    reproduce every existing StrategyConfiguration construction's exact
    current behavior unmodified."""


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
    early_withdrawal_penalty: EarlyWithdrawalPenaltyResult
    """020-early-withdrawal-penalty: this plan year's own 10% penalty on
    the combined taxable early-distribution base (each under-59 household
    member's own share of that year's voluntary Traditional withdrawal,
    plus 019's own unseasoned_roth_withdrawal amount) -- required, no
    default, mirroring irmaa/niit's own precedent: always computed by
    run_plan_projection(), never opt-in (data-model.md)."""
    fica_tax: FicaTaxResult
    """022-fica-payroll-tax (rp-elp): this plan year's own employee-side
    FICA payroll tax on earned_income-type income-stream amounts only
    (021-pension-annuity-income) -- never pension/annuity. Required, no
    default, mirroring irmaa/niit/early_withdrawal_penalty's own
    precedent: always computed by run_plan_projection(), never opt-in."""
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
    member_income_stream_amounts: dict[str, float] = field(default_factory=dict)
    """021-pension-annuity-income (rp-pid): person_name -> that member's
    own summed gross income-stream amount this year, across every
    pension/annuity/earned-income stream that member has configured --
    0.0 for a member with none configured, or none active this year,
    never omitted. Mirrors member_social_security_benefits."""
    member_earned_income: dict[str, float] = field(default_factory=dict)
    """rp-bm8.4: person_name -> that member's own summed stream_type ==
    "earned_income" amount this year only (022-fica-payroll-tax's own
    _member_earned_income_amounts(), independently filtered/recomputed
    from member_income_stream_amounts above, not derived from it -- this
    is the exact dict that already feeds compute_fica_tax() and the SS
    earnings test, previously discarded afterward). 0.0 for a member with
    no earned_income stream active this year, never omitted. A subset of
    (never larger than) that member's own member_income_stream_amounts
    entry."""
    inherited_account_balances: dict[str, float] = field(default_factory=dict)
    """account_id -> that inherited account's own ending balance this
    year, snapshotted from InheritedAccountBalance.balance (012/013's own
    already-independently-tracked state)."""
    inherited_account_distributions: dict[str, float] = field(default_factory=dict)
    """account_id -> that inherited account's own distribution amount
    this year."""
    inherited_account_distribution_reason: dict[str, Literal["annual_rmd", "no_rmd_required_yet", "ten_year_rule_deadline"]] = field(
        default_factory=dict
    )
    """rp-bm8.4: account_id -> which branch of run_plan_projection()'s own
    inherited-account loop produced this year's distribution amount --
    "ten_year_rule_deadline" when tax_year >= depletion_deadline_year forced
    the entire remaining balance out; otherwise "annual_rmd" when
    compute_inherited_rmd() returned a positive required_amount, or
    "no_rmd_required_yet" when it returned 0.0 (the real
    owner_died_before_rbd / pre-RBD-spouse-EDB code paths in
    inherited_rmd.py). Present for every account_id that also has an entry
    in inherited_account_distributions this year -- previously computed by
    the existing branch, previously discarded once distribution was known."""
    inherited_account_rmd_divisor: dict[str, float] = field(default_factory=dict)
    """rp-bm8.4: account_id -> the divisor compute_inherited_rmd() actually
    used this year -- present only when
    inherited_account_distribution_reason[account_id] == "annual_rmd"."""
    inherited_account_depletion_deadline_year: dict[str, int] = field(default_factory=dict)
    """rp-bm8.4: account_id -> that account's own (already-stored, static)
    InheritedAccountBalance.depletion_deadline_year -- present for every
    account_id that also has an entry in inherited_account_distribution_reason,
    so a reader can see how close to (or how far past) the 10-year deadline
    this year's distribution is, whichever reason produced it."""
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
    unseasoned_roth_withdrawal: float = 0.0
    """019-roth-conversion-ladder: the portion of this year's Roth
    withdrawal, if any, sourced from a not-yet-seasoned (< 5 tax years
    since conversion) Roth conversion lot while at least one household
    member's translated age was 59 or younger (data-model.md) -- a flag,
    never a computed penalty dollar amount (FR-007). 0.0 for every plan
    year this feature doesn't flag, which is every plan year for a
    household with no Roth conversion configured at all. Always populated
    by run_plan_projection(); 0.0 only if some other caller constructs a
    PlanYearProjection directly without setting it."""
    member_ss_earnings_test_withheld: dict[str, float] = field(default_factory=dict)
    """025-ss-earnings-test (rp-acq) data-model.md: person_name -> that
    member's own SSA retirement-earnings-test withholding this year --
    already subtracted out of member_social_security_benefits above, not
    an additional deduction the caller must apply. 0.0 for a member the
    earnings test doesn't apply to this year (not yet claimed, no
    earned_income, earnings at/below the exempt threshold, or already
    past their FRA-attainment year), never omitted. Mirrors
    member_social_security_benefits' own "always present, 0.0 when
    inapplicable" convention. No lifetime cumulative field is added
    (PlanOutcome) -- unlike a tax, withheld Social Security is fully
    recovered via the FRA recredit, not a genuine lifetime cost."""


@dataclass
class PlanOutcome:
    """data-model.md § PlanOutcome."""

    ending_balance: float
    first_shortfall_plan_year: int | None
    cumulative_tax_paid: float
    cumulative_irmaa_paid: float  # 010-advanced-tax-benefits data-model.md § Projection extensions
    cumulative_niit_paid: float  # 010-advanced-tax-benefits data-model.md § Projection extensions
    cumulative_early_withdrawal_penalty_paid: float  # 020-early-withdrawal-penalty data-model.md
    cumulative_fica_tax_paid: float  # 022-fica-payroll-tax data-model.md


@dataclass
class PlanProjection:
    """data-model.md § PlanProjection.

    return_assumption (rp-cgj): typed ReturnSchedule, not the narrower
    DeterministicReturnAssumption this field's type annotation originally
    had (004-strategy-comparison-layer, before 005-simulation-engine's own
    ReturnSchedule seam existed) -- 005's data-model.md § path_results
    already documents the real, current behavior this corrects the type
    to match: for a Monte Carlo path, this field holds the specific
    ReturnPath that produced it, not a DeterministicReturnAssumption at
    all. run_plan_projection()'s own return_assumption parameter has
    already been ReturnSchedule since 012-inherited-ira-rmd; this field
    was simply never updated to match."""

    strategy: StrategyConfiguration
    return_assumption: ReturnSchedule
    years: list[PlanYearProjection]
    outcome: PlanOutcome
    resolved_conversion_window: tuple[int, int] | None = None
    """rp-595: the conversion window actually used for this whole run --
    equal to strategy.conversion_window unchanged when
    conversion_window_mode=="explicit"; the auto-derived
    (start_year, end_year) (or None, if no chronological gap exists for
    this household) when conversion_window_mode=="auto_gap_year". An
    informative addition, not a behavior change (mirrors
    PlanYearProjection.filing_status's own precedent) -- without this, an
    auto window collapsing to "no conversions ever" would be silently
    invisible to a caller/UI. Defaults to None, reproducing every existing
    PlanProjection construction's exact current behavior unmodified."""


ComparisonDimension = Literal["roth_conversion_strategy", "withdrawal_sequencing", "claiming_age_grid"]


@dataclass
class ComparisonResult:
    """data-model.md § ComparisonResult."""

    dimension: ComparisonDimension
    return_assumption: DeterministicReturnAssumption
    projections: list[PlanProjection]
