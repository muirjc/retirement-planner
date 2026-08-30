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
    """013-inherited-ira-edge-cases research.md §3-§6: the beneficiary's
    own household_member.person_name, used to look up their current age
    each plan year for an EDB's own life-expectancy divisor -- never
    consulted for beneficiary_classification="non_eligible_designated_beneficiary"
    (012's existing, decedent-only divisor logic), so None is a safe
    default for every existing caller."""


@dataclass
class ConversionResult:
    """data-model.md § ConversionResult."""

    amount_converted: float
    ordinary_income_added: float
    ending_traditional_balance: float
    ending_roth_balance: float
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
