"""Public API for the federal & state tax calculation engine.

See specs/002-tax-calculation-engine/contracts/tax-api.md for the locked
contract downstream features (account mechanics, simulation engine,
reporting) should code against, and
specs/010-advanced-tax-benefits/contracts/tax-api.md for the additive
IRMAA/NIIT extension.
"""

from .early_withdrawal_penalty import EARLY_WITHDRAWAL_PENALTY_RATE, compute_early_withdrawal_penalty
from .federal import compute_federal_tax
from .irmaa import compute_irmaa_surcharge
from .models import (
    BracketRow,
    BracketTable,
    EarlyWithdrawalPenaltyResult,
    FederalTaxResult,
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
    "EARLY_WITHDRAWAL_PENALTY_RATE",
    "STATE_MODULES",
    "BracketRow",
    "BracketTable",
    "EarlyWithdrawalPenaltyResult",
    "FederalTaxResult",
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
    "compute_early_withdrawal_penalty",
    "compute_federal_tax",
    "compute_irmaa_surcharge",
    "compute_niit",
    "compute_state_tax",
    "compute_taxable_social_security",
]
