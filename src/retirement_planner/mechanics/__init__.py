"""Public API for retirement account mechanics: RMD, withdrawal sequencing,
and Roth conversion execution for one plan year.

See specs/003-retirement-account-mechanics/contracts/mechanics-api.md for
the locked contract downstream features (strategy comparison, simulation
engine, reporting) should code against, and
specs/010-advanced-tax-benefits/contracts/mechanics-api.md for the
additive HSA extension.
"""

from .hsa import compute_hsa_contribution, compute_hsa_eligibility
from .models import (
    AccountBalances,
    AccountType,
    ConversionResult,
    HsaContributionResult,
    HsaEligibility,
    PlanYearMechanicsResult,
    RmdResult,
    WithdrawalLineItem,
    WithdrawalPlan,
)
from .plan_year import compute_plan_year_mechanics
from .rmd import JOINT_LIFE_TABLE, RMD_START_AGE, UNIFORM_LIFETIME_TABLE, compute_rmd
from .roth_conversion import (
    CONVERSION_STRATEGIES,
    RothConversionFunction,
    compute_roth_conversion,
    fill_to_bracket_ceiling,
    fixed_dollar_amount,
)
from .withdrawal_sequencing import WITHDRAWAL_STRATEGIES, compute_withdrawal_plan

__all__ = [
    "AccountBalances",
    "AccountType",
    "CONVERSION_STRATEGIES",
    "ConversionResult",
    "HsaContributionResult",
    "HsaEligibility",
    "JOINT_LIFE_TABLE",
    "PlanYearMechanicsResult",
    "RMD_START_AGE",
    "RmdResult",
    "RothConversionFunction",
    "UNIFORM_LIFETIME_TABLE",
    "WITHDRAWAL_STRATEGIES",
    "WithdrawalLineItem",
    "WithdrawalPlan",
    "compute_hsa_contribution",
    "compute_hsa_eligibility",
    "compute_plan_year_mechanics",
    "compute_rmd",
    "compute_roth_conversion",
    "compute_withdrawal_plan",
    "fill_to_bracket_ceiling",
    "fixed_dollar_amount",
]
