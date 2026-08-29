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
