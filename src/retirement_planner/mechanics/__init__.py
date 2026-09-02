"""Public API for retirement account mechanics: RMD, withdrawal sequencing,
and Roth conversion execution for one plan year.

See specs/003-retirement-account-mechanics/contracts/mechanics-api.md for
the locked contract downstream features (strategy comparison, simulation
engine, reporting) should code against, and
specs/010-advanced-tax-benefits/contracts/mechanics-api.md for the
additive HSA extension.
"""

from .hsa import compute_hsa_contribution, compute_hsa_eligibility
from .income_streams import INFLATION_RATE, compute_income_stream_amount
from .models import (
    AccountBalances,
    AccountType,
    ConversionResult,
    HsaContributionResult,
    HsaEligibility,
    IncomeStreamAmountResult,
    InheritedAccountBalance,
    InheritedRmdResult,
    PlanYearMechanicsResult,
    RmdResult,
    RothConversionLot,
    RothLadderConsumptionResult,
    SocialSecurityBenefitResult,
    SpousalBenefitResult,
    SurvivorBenefitResult,
    WithdrawalLineItem,
    WithdrawalPlan,
)
from .inherited_rmd import SINGLE_LIFE_EXPECTANCY_TABLE, compute_inherited_rmd
from .plan_year import compute_plan_year_mechanics
from .rmd import JOINT_LIFE_TABLE, RMD_START_AGE, UNIFORM_LIFETIME_TABLE, compute_rmd
from .roth_conversion import (
    CONVERSION_STRATEGIES,
    RothConversionFunction,
    compute_roth_conversion,
    fill_to_bracket_ceiling,
    fixed_dollar_amount,
)
from .roth_conversion_ladder import ROTH_CONVERSION_SEASONING_YEARS, compute_roth_ladder_consumption
from .social_security_benefit import (
    compute_social_security_benefit,
    compute_spousal_benefit_floor,
    compute_survivor_benefit,
)
from .withdrawal_sequencing import WITHDRAWAL_STRATEGIES, compute_withdrawal_plan

__all__ = [
    "AccountBalances",
    "AccountType",
    "CONVERSION_STRATEGIES",
    "ConversionResult",
    "HsaContributionResult",
    "HsaEligibility",
    "INFLATION_RATE",
    "IncomeStreamAmountResult",
    "InheritedAccountBalance",
    "InheritedRmdResult",
    "JOINT_LIFE_TABLE",
    "PlanYearMechanicsResult",
    "ROTH_CONVERSION_SEASONING_YEARS",
    "SINGLE_LIFE_EXPECTANCY_TABLE",
    "RMD_START_AGE",
    "RmdResult",
    "RothConversionFunction",
    "RothConversionLot",
    "RothLadderConsumptionResult",
    "SocialSecurityBenefitResult",
    "SpousalBenefitResult",
    "SurvivorBenefitResult",
    "UNIFORM_LIFETIME_TABLE",
    "WITHDRAWAL_STRATEGIES",
    "WithdrawalLineItem",
    "WithdrawalPlan",
    "compute_hsa_contribution",
    "compute_hsa_eligibility",
    "compute_income_stream_amount",
    "compute_inherited_rmd",
    "compute_plan_year_mechanics",
    "compute_rmd",
    "compute_roth_conversion",
    "compute_roth_ladder_consumption",
    "compute_social_security_benefit",
    "compute_spousal_benefit_floor",
    "compute_survivor_benefit",
    "compute_withdrawal_plan",
    "fill_to_bracket_ceiling",
    "fixed_dollar_amount",
]
