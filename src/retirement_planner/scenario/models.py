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
    """016-ss-claiming-age-actuarial-adjustment: this member's Primary
    Insurance Amount (PIA) -- the Social Security benefit payable if
    claimed exactly at full_retirement_age -- not the amount actually
    paid at ss_claim_age. The amount actually paid is derived by
    retirement_planner.mechanics.compute_social_security_benefit() from
    this PIA, full_retirement_age, and ss_claim_age together
    (contracts/mechanics-api.md)."""
    full_retirement_age: float | None = None
    """016-ss-claiming-age-actuarial-adjustment: this member's Social
    Security full retirement age, in years (fractional allowed, e.g.
    66.8333 for 66 years 10 months). None (the YAML-omitted case) is
    resolved by scenario.loader.parse_scenario() to this member's own
    ss_claim_age -- i.e., assume no adjustment -- so every scenario that
    predates this feature keeps producing exactly its current output
    unless it explicitly opts in with a real FRA (data-model.md,
    research.md Decision 3). Every HouseholdMember that has passed
    through parse_scenario() carries a concrete float here, never None."""
    hdhp_coverage: bool = False
    """Whether this member is covered by a qualifying high-deductible
    health plan -- the HSA-eligibility precondition
    (010-advanced-tax-benefits contracts/scenario-api.md). Per-member,
    since coverage is inherently individual, independent of any other
    member's coverage or Medicare status. Defaults to False, reproducing
    every existing scenario's exact current behavior."""
    predicted_death_age: int | None = None
    """017-ss-spousal-survivor-benefits (rp-52n): this member's
    hypothetical age at death, for planning purposes only -- a "what if"
    input, not a record of a past, certain event (contrast `012`'s
    InheritedIraDetails.death_year, research.md Decision 6). None (the
    default, and every scenario predating this feature) means no
    hypothetical death is configured; nothing in this feature's own
    computations consults this field -- it exists purely as the
    data-model home a future feature (rp-g8y) will need, once mortality
    is wired into a running projection."""


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
class InheritedIraDetails:
    """Decedent and beneficiary facts for an inherited traditional account
    already in RMD status -- covers only the case the original owner died
    on or after their Required Beginning Date (012-inherited-ira-rmd
    research.md §2). Attached to an Account via Account.inherited.
    data-model.md § InheritedIraDetails."""

    death_year: int
    decedent_age_at_death: int
    decedent_was_taking_rmds: bool
    beneficiary_relationship: Literal["spouse", "minor_child", "other_individual", "trust_or_entity"]
    beneficiary_classification: Literal[
        "eligible_designated_beneficiary_spouse",
        "eligible_designated_beneficiary_other",
        "non_eligible_designated_beneficiary",
    ]


@dataclass
class Account:
    """A single balance bucket. data-model.md § Account."""

    account_type: Literal["traditional", "roth", "taxable"]
    balance: float
    owner: str | None = None
    """011-per-owner-accounts: references a household.members[*].person_name.
    None only ever appears transiently -- before validate() runs, or for a
    Scenario built directly rather than via parse_scenario() -- a Scenario
    that has passed validation with is_usable=True never has an owner=None
    account in a household with more than one member (see validation.py)."""
    account_id: str | None = None
    """012-inherited-ira-rmd: a stable per-account handle, used only to key
    an inherited account's independently-tracked runtime state through a
    projection (research.md §8). parse_scenario() auto-fills it
    deterministically (f"{account_type}-{index}") when the YAML omits it
    -- every parsed Account has a non-None account_id, whether or not it
    is inherited."""
    inherited: InheritedIraDetails | None = None
    """012-inherited-ira-rmd: None for an ordinary, owner-held account
    (every account before this feature). Present only for an account
    whose original owner has died and whose current owner is the
    beneficiary (research.md §4)."""


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
