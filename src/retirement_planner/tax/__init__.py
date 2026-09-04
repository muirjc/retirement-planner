"""Public API for the federal & state tax calculation engine.

See specs/002-tax-calculation-engine/contracts/tax-api.md for the locked
contract downstream features (account mechanics, simulation engine,
reporting) should code against, and
specs/010-advanced-tax-benefits/contracts/tax-api.md for the additive
IRMAA/NIIT extension.
"""

from .early_withdrawal_penalty import EARLY_WITHDRAWAL_PENALTY_RATE, compute_early_withdrawal_penalty
from .federal import available_bracket_ceiling_rates, bracket_ceiling_for_rate, compute_federal_tax
from .fica import (
    ADDITIONAL_MEDICARE_TAX_RATE,
    ADDITIONAL_MEDICARE_TAX_THRESHOLDS,
    MEDICARE_RATE,
    OASDI_RATE,
    OASDI_WAGE_BASE,
    compute_fica_tax,
)
from .irmaa import compute_irmaa_surcharge
from .models import (
    BracketContribution,
    BracketRow,
    BracketTable,
    EarlyWithdrawalPenaltyResult,
    FederalTaxResult,
    FicaTaxResult,
    FigureUsage,
    FilingStatus,
    IncomeComponents,
    IrmaaResult,
    IrmaaTierRow,
    IrmaaTierTable,
    NiitResult,
    SourcedFigure,
    StandardDeductionAmounts,
    StateTaxResult,
    UnsupportedTaxYearError,
)
from .niit import compute_niit
from .social_security import compute_taxable_social_security
from .state import STATE_MODULES, compute_state_tax

__all__ = [
    "ADDITIONAL_MEDICARE_TAX_RATE",
    "ADDITIONAL_MEDICARE_TAX_THRESHOLDS",
    "EARLY_WITHDRAWAL_PENALTY_RATE",
    "MEDICARE_RATE",
    "OASDI_RATE",
    "OASDI_WAGE_BASE",
    "STATE_MODULES",
    "BracketContribution",
    "BracketRow",
    "BracketTable",
    "EarlyWithdrawalPenaltyResult",
    "FederalTaxResult",
    "FicaTaxResult",
    "FigureUsage",
    "FilingStatus",
    "IncomeComponents",
    "IrmaaResult",
    "IrmaaTierRow",
    "IrmaaTierTable",
    "NiitResult",
    "SourcedFigure",
    "StandardDeductionAmounts",
    "StateTaxResult",
    "UnsupportedTaxYearError",
    "available_bracket_ceiling_rates",
    "bracket_ceiling_for_rate",
    "compute_early_withdrawal_penalty",
    "compute_federal_tax",
    "compute_fica_tax",
    "compute_irmaa_surcharge",
    "compute_niit",
    "compute_state_tax",
    "compute_taxable_social_security",
]
