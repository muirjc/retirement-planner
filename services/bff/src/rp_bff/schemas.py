"""Pydantic request models (research.md §3): request bodies get real
validation via Pydantic; response bodies are plain to_jsonable() output,
not hand-mirrored response models (see serialization.py and this
module's own docstrings for why). ScenarioRequest mirrors 001's Scenario
fields exactly, minus `name` -- the scenario name always comes from the
URL path parameter and is passed to parse_scenario(yaml_text, name=...),
never duplicated in the request body (data-model.md § Scenario Resource).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HouseholdMemberRequest(BaseModel):
    """Mirrors 001's HouseholdMember fields exactly."""

    person_name: str
    current_age: int
    ss_claim_age: int
    ss_annual_benefit: float
    hdhp_coverage: bool = False
    """010-advanced-tax-benefits."""


class HouseholdRequest(BaseModel):
    """Mirrors 001's Household fields exactly."""

    filing_status: Literal["single", "married_filing_jointly"]
    members: list[HouseholdMemberRequest]


class AccountRequest(BaseModel):
    """Mirrors 001's Account fields exactly."""

    account_type: Literal["traditional", "roth", "taxable"]
    balance: float
    owner: str | None = None
    """011-per-owner-accounts."""


class SpendingProfileRequest(BaseModel):
    """Mirrors 001's SpendingProfile fields exactly."""

    annual_need_real: float


class MarketAssumptionsRequest(BaseModel):
    """Mirrors 001's MarketAssumptions fields exactly."""

    equity_allocation: float
    equity_return_mean_real: float
    equity_return_std_real: float
    bond_allocation: float
    bond_return_mean_real: float
    bond_return_std_real: float
    correlation: float


class SimulationSettingsRequest(BaseModel):
    """Mirrors 001's SimulationSettings fields exactly."""

    n_paths: int
    seed: int
    plan_to_age: int


class RothConversionPlanRequest(BaseModel):
    """Mirrors 001's RothConversionPlan fields exactly."""

    strategy: str
    bracket_ceiling_or_amount: float
    window: tuple[int, int]


class HsaContributionPlanRequest(BaseModel):
    """Mirrors 001's HsaContributionPlan fields exactly (010-advanced-tax-benefits)."""

    annual_amount: float


class ScenarioRequest(BaseModel):
    """The PUT /scenarios/{name} and POST /scenarios/{name}/validate
    request body -- see data-model.md § Scenario Resource and
    contracts/bff-api.md § Scenarios."""

    household: HouseholdRequest
    accounts: list[AccountRequest]
    spending: SpendingProfileRequest
    state: str
    market_assumptions: MarketAssumptionsRequest
    simulation_settings: SimulationSettingsRequest
    roth_conversion: RothConversionPlanRequest | None = None
    hsa_contribution: HsaContributionPlanRequest | None = None
    """010-advanced-tax-benefits."""
