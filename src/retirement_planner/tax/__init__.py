"""Public API for the federal & state tax calculation engine.

See specs/002-tax-calculation-engine/contracts/tax-api.md for the locked
contract downstream features (account mechanics, simulation engine,
reporting) should code against.
"""

from .federal import compute_federal_tax
from .models import (
    BracketRow,
    BracketTable,
    FederalTaxResult,
    FigureUsage,
    FilingStatus,
    IncomeComponents,
    SourcedFigure,
    StateTaxResult,
    UnsupportedTaxYearError,
)
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
    "SourcedFigure",
    "StateTaxResult",
    "UnsupportedTaxYearError",
    "compute_federal_tax",
    "compute_state_tax",
    "compute_taxable_social_security",
]
