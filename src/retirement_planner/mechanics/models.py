"""Shared account-mechanics data model.

These dataclasses are the locked public shape described in
specs/003-retirement-account-mechanics/contracts/mechanics-api.md ("Data
types" section) and specs/003-retirement-account-mechanics/data-model.md.
FigureUsage is imported from retirement_planner.tax rather than redefined,
continuing that feature's auditability convention (FR-019).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from retirement_planner.tax import FigureUsage

AccountType = Literal["traditional", "roth", "taxable"]


@dataclass
class AccountBalances:
    """Household-level balances for the three account types. data-model.md
    § AccountBalances.
    """

    traditional: float
    roth: float
    taxable: float


@dataclass
class RmdResult:
    """data-model.md § RmdResult."""

    required_amount: float
    table_used: Literal["uniform_lifetime", "joint_life"] | None
    divisor: float | None
    figures_used: list[FigureUsage] = field(default_factory=list)


@dataclass
class WithdrawalLineItem:
    """data-model.md § WithdrawalLineItem."""

    account_type: AccountType
    amount: float


@dataclass
class WithdrawalPlan:
    """data-model.md § WithdrawalPlan."""

    rmd_drawn: float
    sequence_withdrawals: list[WithdrawalLineItem]
    ending_balances: AccountBalances
    shortfall: float
    inherited_distribution_drawn: float = 0.0
    """012-inherited-ira-rmd: an amount already distributed this plan year
    from one or more inherited accounts, tracked entirely outside
    ending_balances (research.md §10, §5) -- set by compute_withdrawal_plan()
    to exactly whatever inherited_distribution_amount it was called with,
    never capped here. Defaults to 0.0, reproducing every existing caller's
    exact prior behavior."""


@dataclass
class InheritedRmdResult:
    """One inherited traditional account's required distribution for one
    tax year, computed by compute_inherited_rmd() (mechanics/inherited_rmd.py).
    data-model.md § derived InheritedAccountBalance's sibling result type;
    contracts/mechanics-api.md (012-inherited-ira-rmd, addendum to 003)."""

    required_amount: float
    table_used: Literal["single_life_expectancy"] | None
    divisor: float | None
    figures_used: list[FigureUsage] = field(default_factory=list)
    depletion_deadline_year: int | None = None
    is_within_ten_year_window: bool = True


@dataclass
class InheritedAccountBalance:
    """One inherited account's independently-tracked runtime state,
    threaded through a multi-year projection (research.md §5, §8; the
    account_type/decedent_was_taking_rmds/beneficiary_classification/
    beneficiary_person_name fields added by 013-inherited-ira-edge-cases,
    research.md § Handoff). Never pooled with AccountBalances.traditional
    -- mutated in place by run_plan_projection() as distributions are
    taken and growth applied. data-model.md § Derived: InheritedAccountBalance."""

    account_id: str
    balance: float
    death_year: int
    decedent_age_at_death: int
    depletion_deadline_year: int
    """013-inherited-ira-edge-cases research.md §5/§6: computed once at
    resolution time, same as 012's own death_year + 10 -- death_year + 10
    for a non-eligible designated beneficiary (unchanged from 012);
    majority_year + 10 for a minor-child EDB; a far-future sentinel
    (effectively never) for any other EDB, who has no 10-year deadline of
    their own under the annual "stretch" they're taking instead."""
    account_type: Literal["traditional", "roth"] = "traditional"
    """013-inherited-ira-edge-cases research.md §2: a Roth account is
    always treated as pre-RBD by compute_inherited_rmd(), regardless of
    decedent_was_taking_rmds below."""
    decedent_was_taking_rmds: bool = True
    """013-inherited-ira-edge-cases research.md §1: defaults to True,
    reproducing 012's own only-supported case (the deterministic
    post-RBD, non-EDB divisor logic) for every existing caller that
    doesn't set this explicitly."""
    beneficiary_classification: Literal[
        "eligible_designated_beneficiary_spouse",
        "eligible_designated_beneficiary_other",
        "non_eligible_designated_beneficiary",
    ] = "non_eligible_designated_beneficiary"
    """013-inherited-ira-edge-cases research.md §3-§6: defaults to
    012's own only-supported classification, for the same reason."""
    beneficiary_person_name: str | None = None
    """013-inherited-ira-edge-cases research.md §3-§6, extended by rp-kn5:
    the beneficiary's own household_member.person_name, used to look up
    their current age each plan year for the beneficiary's own
    life-expectancy divisor. None is only a safe default when no annual
    divisor is ever computed for this account at all -- account_type=
    "roth", or decedent_was_taking_rmds=False (owner died before RBD):
    every other case, including beneficiary_classification=
    "non_eligible_designated_beneficiary" since rp-kn5's "longer of" fix,
    now consults this every year an annual amount is due, and
    compute_inherited_rmd() raises AssertionError if the resulting
    beneficiary_current_age comes back None when it's needed. The real
    resolution path (services/bff/src/rp_bff/resolution.py) always sets
    this to the account's owner, so this only bites a caller that builds
    an InheritedAccountBalance directly and omits it."""


@dataclass
class ConversionResult:
    """data-model.md § ConversionResult."""

    amount_converted: float
    ordinary_income_added: float
    ending_traditional_balance: float
    ending_roth_balance: float
    figures_used: list[FigureUsage] = field(default_factory=list)


@dataclass
class RothConversionLot:
    """One Roth conversion actually executed during a projection --
    tracked independently of the household's pooled AccountBalances.roth
    total, never folded into that pooled arithmetic itself.
    compute_roth_ladder_consumption() (roth_conversion_ladder.py, pure)
    never mutates an instance of this type -- it returns a fresh, updated
    list; run_plan_projection() (comparison package) reassigns its own
    local list to that result, mirroring how compute_inherited_rmd()
    never mutates InheritedAccountBalance.balance itself either (012
    contracts/mechanics-api.md's package-wide purity guarantee).
    019-roth-conversion-ladder data-model.md § RothConversionLot."""

    conversion_tax_year: int
    balance: float


@dataclass
class RothLadderConsumptionResult:
    """One plan year's attribution of a Roth withdrawal across the
    assumed-already-seasoned portion and any tracked conversion lots --
    a pure function's result; compute_roth_ladder_consumption() itself
    never mutates the lots list it was called with.
    019-roth-conversion-ladder data-model.md § RothLadderConsumptionResult."""

    updated_lots: list[RothConversionLot]
    unseasoned_amount_flagged: float
    figures_used: list[FigureUsage] = field(default_factory=list)


@dataclass
class HsaEligibility:
    """010-advanced-tax-benefits data-model.md § Mechanics result
    extensions.

    Correction found during implementation (T022): `age` was added so
    compute_hsa_contribution() can determine 55+ catch-up eligibility per
    member without a second parameter carrying ages separately -- the
    original contracts/mechanics-api.md draft omitted it. See
    contracts/mechanics-api.md's own correction note.
    """

    person_name: str
    age: int
    eligible: bool
    reason: str | None


@dataclass
class HsaContributionResult:
    """010-advanced-tax-benefits data-model.md § Mechanics result
    extensions."""

    eligible_members: list[HsaEligibility]
    applicable_limit: float
    amount_contributed: float
    rejected_reason: str | None
    figures_used: list[FigureUsage] = field(default_factory=list)


@dataclass
class PlanYearMechanicsResult:
    """data-model.md § PlanYearMechanicsResult."""

    plan_year: int
    withdrawal_plan: WithdrawalPlan
    conversion: ConversionResult
    ending_balances: AccountBalances
    ordinary_income: float
    figures_used: list[FigureUsage] = field(default_factory=list)


@dataclass
class SocialSecurityBenefitResult:
    """016-ss-claiming-age-actuarial-adjustment data-model.md §
    SocialSecurityBenefitResult. One household member's actual annual
    Social Security benefit, adjusted for how their claiming age compares
    to their full retirement age (FRA) -- mirrors RmdResult's own shape
    (a derived dollar amount, a derived descriptor, figures_used)."""

    annual_benefit: float
    """The member's PIA, reduced for early claiming or increased for
    delayed claiming -- equals primary_insurance_amount exactly when
    claiming_age == full_retirement_age."""
    adjustment_factor: float
    """annual_benefit / primary_insurance_amount, e.g. ~0.70 at 62 against
    a 67 FRA, 1.0 at FRA, ~1.24 at 70 against a 67 FRA -- surfaced
    separately from annual_benefit so a caller/report can show "70% of
    PIA" without re-deriving it from two floats."""
    figures_used: list[FigureUsage] = field(default_factory=list)


@dataclass
class SpousalBenefitResult:
    """017-ss-spousal-survivor-benefits data-model.md § SpousalBenefitResult.
    One member's spousal-derived Social Security amount -- up to 50% of
    their spouse's PIA, adjusted for the claiming member's own claiming
    age relative to their own FRA (never the spouse's FRA)."""

    spousal_amount: float
    """0.5 * other_member_pia, reduced for the claiming member's own
    early claiming via the SSA's spousal-specific reduction rate; never
    increased for delayed claiming -- capped at exactly
    0.5 * other_member_pia for claiming at or after the claiming
    member's own FRA (no delayed-retirement credit on a spousal amount,
    research.md Decision 2)."""
    adjustment_factor: float
    """spousal_amount / (0.5 * other_member_pia), e.g. ~0.65 at 62
    against a 67 FRA (25% + 10% reduction), 1.0 at or after FRA -- never
    > 1.0, unlike SocialSecurityBenefitResult.adjustment_factor which can
    exceed 1.0 for delayed claiming."""
    figures_used: list[FigureUsage] = field(default_factory=list)


@dataclass
class SurvivorBenefitResult:
    """017-ss-spousal-survivor-benefits data-model.md § SurvivorBenefitResult.
    The surviving member's ongoing Social Security benefit after one
    member has died -- the higher of the two members' own currently-
    claimed benefit amounts (research.md Decision 4)."""

    survivor_benefit: float
    """max(member_a_benefit, member_b_benefit)."""
    figures_used: list[FigureUsage] = field(default_factory=list)


@dataclass
class IncomeStreamAmountResult:
    """021-pension-annuity-income (rp-pid) data-model.md §
    IncomeStreamAmountResult. One IncomeStream's own gross amount for one
    plan year -- mirrors SocialSecurityBenefitResult's own shape (a
    derived dollar amount plus figures_used)."""

    amount: float
    """0.0 when member_age_this_year falls outside the stream's active
    window. Otherwise the stream's annual_amount unchanged (cola_adjusted)
    or eroded against mechanics.income_streams.INFLATION_RATE
    (fixed_nominal)."""
    figures_used: list[FigureUsage] = field(default_factory=list)
    """Empty for cola_adjusted (a flat pass-through cites nothing) or an
    inactive year; carries exactly [INFLATION_RATE.usage_for_year(tax_year)]
    for an active fixed_nominal stream."""
