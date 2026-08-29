"""Public API for the federal & state tax calculation engine.

See specs/002-tax-calculation-engine/contracts/tax-api.md for the locked
contract downstream features (account mechanics, simulation engine,
reporting) should code against, and
specs/010-advanced-tax-benefits/contracts/tax-api.md for the additive
IRMAA/NIIT extension.
"""

from .federal import compute_federal_tax
from .irmaa import compute_irmaa_surcharge
from .models import (
    BracketRow,
    BracketTable,
    FederalTaxResult,
    FigureUsage,
    FilingStatus,
    IncomeComponents,
    IrmaaResult,
    IrmaaTierRow,
    IrmaaTierTable,
    NiitResult,
    SourcedFigure,
    StateTaxResult,
    UnsupportedTaxYearError,
)
from .niit import compute_niit
from .social_security import compute_taxable_social_security
from .state import STATE_MODULES, compute_state_tax

__all__ = [
    "STATE_MODULES",
    "BracketRow",
    "BracketTable",
    "FederalTaxResult",
    "FigureUsage",
    "FilingStatus",
    "IncomeComponents",
    "IrmaaResult",
    "IrmaaTierRow",
    "IrmaaTierTable",
    "NiitResult",
    "SourcedFigure",
    "StateTaxResult",
    "UnsupportedTaxYearError",
    "compute_federal_tax",
    "compute_irmaa_surcharge",
    "compute_niit",
    "compute_state_tax",
    "compute_taxable_social_security",
]
