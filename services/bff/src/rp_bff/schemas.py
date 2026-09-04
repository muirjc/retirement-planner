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


class IncomeStreamRequest(BaseModel):
    """Mirrors 021-pension-annuity-income's IncomeStream fields exactly."""

    label: str
    stream_type: Literal["pension", "annuity", "earned_income"]
    start_age: int
    annual_amount: float
    inflation_adjustment: Literal["cola_adjusted", "fixed_nominal"]
    end_age: int | None = None


class HouseholdMemberRequest(BaseModel):
    """Mirrors 001's HouseholdMember fields exactly."""

    person_name: str
    current_age: int
    ss_claim_age: int
    ss_annual_benefit: float
    full_retirement_age: float | None = None
    """016-ss-claiming-age-actuarial-adjustment: defaults to None, which
    parse_scenario() resolves to this member's own ss_claim_age (no
    adjustment) -- see scenario/loader.py."""
    hdhp_coverage: bool = False
    """010-advanced-tax-benefits."""
    predicted_death_age: int | None = None
    """017-ss-spousal-survivor-benefits: defaults to None (no hypothetical
    death configured). 018-survivor-scenario-projection now consumes this
    to switch a projection's mid-horizon filing status/Social Security
    income/spending need -- see scenario/models.py and
    comparison/projection.py."""
    income_streams: list[IncomeStreamRequest] = []
    """021-pension-annuity-income (rp-pid): defaults to [] (no streams
    configured), reproducing every existing request's exact current
    behavior. No resolution.py change needed -- routes/scenarios.py
    converts every ScenarioRequest to YAML via
    body.model_dump(mode="json") before calling parse_scenario(), so this
    field-name-matching addition round-trips automatically."""


class HouseholdRequest(BaseModel):
    """Mirrors 001's Household fields exactly."""

    filing_status: Literal["single", "married_filing_jointly"]
    members: list[HouseholdMemberRequest]
    survivor_spending_reduction_pct: float = 0.0
    """018-survivor-scenario-projection: defaults to 0.0 (no reduction --
    a true no-op). See scenario/models.py."""


class InheritedIraDetailsRequest(BaseModel):
    """Mirrors 012-inherited-ira-rmd's InheritedIraDetails fields exactly."""

    death_year: int
    decedent_age_at_death: int
    decedent_was_taking_rmds: bool
    beneficiary_relationship: Literal["spouse", "minor_child", "other_individual", "trust_or_entity"]
    beneficiary_classification: Literal[
        "eligible_designated_beneficiary_spouse",
        "eligible_designated_beneficiary_other",
        "non_eligible_designated_beneficiary",
    ]


class AccountRequest(BaseModel):
    """Mirrors 001's Account fields exactly."""

    account_type: Literal["traditional", "roth", "taxable"]
    balance: float
    owner: str | None = None
    """011-per-owner-accounts."""
    account_id: str | None = None
    """012-inherited-ira-rmd."""
    inherited: InheritedIraDetailsRequest | None = None
    """012-inherited-ira-rmd."""


class SpendingProfileRequest(BaseModel):
    """Mirrors 001's SpendingProfile fields exactly."""

    annual_need_real: float
    net_earned_income_against_spending: bool = False
    """rp-595: defaults to False, reproducing every existing request's
    exact current behavior. See scenario/models.py."""


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
    """Mirrors 001's RothConversionPlan fields exactly (rp-595 extends the
    original 3-field shape with window_mode/ceiling_mode/
    named_bracket_rate; window/bracket_ceiling_or_amount become optional,
    required only by their own mode -- see scenario/models.py's
    RothConversionPlan and scenario/loader.py's _build_roth_conversion()
    for exactly which field each mode requires. Pydantic-level shape
    validation only; resolution.py does the mode-vs-required-field cross-
    check (mirrors every other cross-field rule in this codebase, kept
    out of the request schema itself)."""

    strategy: str
    window_mode: Literal["explicit", "auto_gap_year"] = "explicit"
    window: tuple[int, int] | None = None
    ceiling_mode: Literal["dollar_amount", "named_bracket"] = "dollar_amount"
    bracket_ceiling_or_amount: float | None = None
    named_bracket_rate: float | None = None


class HsaContributionPlanRequest(BaseModel):
    """Mirrors 001's HsaContributionPlan fields exactly (010-advanced-tax-benefits)."""

    annual_amount: float


class StressScenarioRequest(BaseModel):
    """Mirrors 005-simulation-engine's StressScenario fields exactly (rp-2bn).
    Shared (unlike SimulationRequest/ComparisonRequest's own top-level
    fields, which are independently duplicated per route by this codebase's
    existing convention) because this nested shape is genuinely identical
    wherever it's used -- see routes/simulations.py and routes/comparisons.py,
    both of which nest this as an optional `stress_scenario` field, `None`
    (the default) meaning no stress overlay -- every existing request's exact
    current behavior (026-advanced-simulation-options data-model.md)."""

    magnitude: float
    duration_years: int
    start_plan_year: int


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
