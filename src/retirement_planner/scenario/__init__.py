"""Public API for the scenario configuration & validation layer.

See specs/001-scenario-config-management/contracts/scenario-api.md for the
locked contract downstream features (tax engine, strategy layer, simulation
engine, reporting) should code against.
"""

from .correlation import cholesky_lower
from .loader import ScenarioParseError, parse_scenario
from .store import delete_scenario, list_scenarios, load_scenario, save_scenario
from .models import (
    Account,
    AllocationPeriod,
    AllocationSchedule,
    AssetClass,
    ASSET_CLASSES,
    DEFAULT_MARKET_ASSUMPTIONS,
    AssetClassAssumptions,
    Contribution401kPlan,
    EmployerContributionPlan,
    Household,
    HouseholdMember,
    HsaContributionPlan,
    IncomeStream,
    InheritedIraDetails,
    MarketAssumptions,
    RothConversionPlan,
    Scenario,
    SimulationSettings,
    SpendingProfile,
    ValidationFlag,
)
from .validation import validate

__all__ = [
    "ASSET_CLASSES",
    "DEFAULT_MARKET_ASSUMPTIONS",
    "Account",
    "AllocationPeriod",
    "AllocationSchedule",
    "AssetClass",
    "AssetClassAssumptions",
    "Contribution401kPlan",
    "EmployerContributionPlan",
    "Household",
    "HouseholdMember",
    "HsaContributionPlan",
    "IncomeStream",
    "InheritedIraDetails",
    "MarketAssumptions",
    "RothConversionPlan",
    "Scenario",
    "ScenarioParseError",
    "SimulationSettings",
    "SpendingProfile",
    "ValidationFlag",
    "cholesky_lower",
    "delete_scenario",
    "list_scenarios",
    "load_scenario",
    "parse_scenario",
    "save_scenario",
    "validate",
]
