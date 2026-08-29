"""Scenario data model.

These dataclasses are the locked public shape described in
specs/001-scenario-config-management/contracts/scenario-api.md ("Data types"
section) and specs/001-scenario-config-management/data-model.md.
Field-level validation rules live in validation.py, not here — this module
only defines shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class HouseholdMember:
    """One person in the household. data-model.md § HouseholdMember."""

    person_name: str
    current_age: int
    ss_claim_age: int
    ss_annual_benefit: float
    hdhp_coverage: bool = False
    """Whether this member is covered by a qualifying high-deductible
    health plan -- the HSA-eligibility precondition
    (010-advanced-tax-benefits contracts/scenario-api.md). Per-member,
    since coverage is inherently individual, independent of any other
    member's coverage or Medicare status. Defaults to False, reproducing
    every existing scenario's exact current behavior."""


@dataclass
class Household:
    """A single filer or a married-filing-jointly couple. data-model.md § Household.

    `members` MUST have exactly 1 entry for `"single"` or exactly 2 for
    `"married_filing_jointly"` (FR-013) — enforced by loader.parse_scenario(),
    not here.
    """

    filing_status: Literal["single", "married_filing_jointly"]
    members: list[HouseholdMember]


@dataclass
class Account:
    """A single balance bucket. data-model.md § Account."""

    account_type: Literal["traditional", "roth", "taxable"]
    balance: float


@dataclass
class SpendingProfile:
    """The household's planned annual spending need, in today's dollars.
    data-model.md § SpendingProfile.
    """

    annual_need_real: float


@dataclass
class RothConversionPlan:
    """An opaque reference for a future strategy-layer feature to interpret —
    this feature stores it as-is and does not validate its contents beyond
    shape. data-model.md § RothConversionPlan.
    """

    strategy: str
    bracket_ceiling_or_amount: float
    window: tuple[int, int]


@dataclass
class HsaContributionPlan:
    """The household's intended annual HSA contribution, in years any
    member is eligible -- mirrors RothConversionPlan's own optional-block
    shape exactly: an opaque value this feature owns the interpretation
    of, not validated here beyond shape
    (010-advanced-tax-benefits contracts/scenario-api.md, data-model.md).
    """

    annual_amount: float


@dataclass
class MarketAssumptions:
    """Return/allocation inputs consumed by the future simulation-engine
    feature. data-model.md § MarketAssumptions.
    """

    equity_allocation: float
    equity_return_mean_real: float
    equity_return_std_real: float
    bond_allocation: float
    bond_return_mean_real: float
    bond_return_std_real: float
    correlation: float


@dataclass
class SimulationSettings:
    """Simulation-run inputs consumed by the future simulation-engine
    feature. `plan_to_age` also drives this feature's spending-vs-assets
    plausibility check (data-model.md § SpendingProfile). data-model.md §
    SimulationSettings.
    """

    n_paths: int
    seed: int
    plan_to_age: int


@dataclass
class ValidationFlag:
    """One problem found by validation.validate(). data-model.md §
    ValidationFlag. `severity="blocking"` means the owning Scenario is not
    usable downstream (Scenario.is_usable is False); `severity="warning"`
    means it's a plausibility concern only (FR-014).
    """

    field: str
    message: str
    severity: Literal["blocking", "warning"]


@dataclass
class Scenario:
    """The top-level, named unit of scenario input data — one YAML file =
    one Scenario. data-model.md § Scenario. See
    contracts/scenario-api.md for the full public API built around this
    type (parse_scenario, validate, save_scenario, list_scenarios,
    load_scenario).
    """

    name: str
    household: Household
    accounts: list[Account]
    spending: SpendingProfile
    state: str
    market_assumptions: MarketAssumptions
    simulation_settings: SimulationSettings
    roth_conversion: RothConversionPlan | None = None
    hsa_contribution: HsaContributionPlan | None = None
    """010-advanced-tax-benefits contracts/scenario-api.md. Defaults to
    None ("not modeled"), reproducing every existing scenario's exact
    current behavior."""
    validation_flags: list[ValidationFlag] = field(default_factory=list)

    @property
    def is_usable(self) -> bool:
        """True iff no `blocking` flag is present (`warning`-only or empty is usable)."""
        return all(flag.severity != "blocking" for flag in self.validation_flags)
