"""Shared reporting data model.

These dataclasses are the locked public shape described in
specs/006-reporting-aggregation/contracts/reporting-api.md ("Data types"
section) and specs/006-reporting-aggregation/data-model.md. PercentileBand
is imported from retirement_planner.simulation rather than redefined,
continuing that feature's convention.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from retirement_planner.simulation import PercentileBand
from retirement_planner.tax import BracketContribution


@dataclass
class SummaryStatistics:
    """data-model.md § SummaryStatistics.

    success_rate/percentile_bands are None for a deterministic (004)
    candidate, which has no probability distribution to report either over
    (research.md §2) -- never a Monte-Carlo-shaped zero/empty standing in
    for "doesn't apply". median_depletion_age is None when nothing
    depleted (research.md §1). unverified_figure_names is always a list,
    possibly empty, never None -- "checked, none unverified" must stay
    distinguishable from "not checked" (FR-004).
    """

    candidate_label: str | None
    success_rate: float | None
    survival_adjusted_success_rate: float | None
    """rp-9vl (005-simulation-engine FR-017/FR-018): 1:1 pass-through of
    SimulationRun.survival_adjusted_success_rate -- None whenever that run
    was computed without survival_curves (every deterministic (004)
    candidate, and every Monte Carlo run that didn't opt in), never a
    Monte-Carlo-shaped zero standing in for "not requested" (same
    discipline as success_rate/percentile_bands above)."""
    ending_balance: float
    percentile_bands: list[PercentileBand] | None
    median_depletion_age: float | None
    median_lifetime_tax_paid: float
    median_lifetime_irmaa_paid: float
    """010-advanced-tax-benefits: same derivation as median_lifetime_tax_paid
    (median across Monte Carlo paths' PlanOutcome.cumulative_irmaa_paid;
    the single value for a deterministic candidate) -- a separate figure,
    never folded into median_lifetime_tax_paid, matching how PlanOutcome
    itself keeps cumulative_irmaa_paid distinct from cumulative_tax_paid."""
    median_lifetime_niit_paid: float
    """010-advanced-tax-benefits: same derivation, for cumulative_niit_paid."""
    median_lifetime_early_withdrawal_penalty_paid: float
    """020-early-withdrawal-penalty: same derivation, for
    cumulative_early_withdrawal_penalty_paid."""
    median_lifetime_fica_tax_paid: float
    """022-fica-payroll-tax: same derivation, for cumulative_fica_tax_paid."""
    unverified_figure_names: list[str] = field(default_factory=list)


@dataclass
class NarrativeEntry:
    """One detected driver within a single plan year's story
    (028-results-walkthrough data-model.md § NarrativeEntry). driver_key is
    a stable identifier (one of the closed v1 set, or "baseline") -- tests
    assert on it directly rather than string-matching prose. amounts is
    sourced only from figures already computed elsewhere in the tool
    (FR-004) -- this is rp-bm8.2's (P2, AI rewrite) only allowed source of
    numbers."""

    driver_key: str
    label: str
    explanation: str
    amounts: dict[str, float] = field(default_factory=dict)


@dataclass
class YearStory:
    """The full narrative for one plan year of the selected representative
    path (028-results-walkthrough data-model.md § YearStory). entries is
    never empty -- a year with no detected driver still gets exactly one
    driver_key="baseline" NarrativeEntry (FR-005). unverified_figure_names
    defaults to [] here and is populated by build_year_stories() once
    unverified_figure_names() (aggregation.py) is promoted to public
    (research.md §4) -- always a list, possibly empty, never None,
    mirroring SummaryStatistics' own convention."""

    plan_year: int
    tax_year: int
    member_ages: dict[str, int]
    detail: YearComputationDetail
    """rp-bm8.3: the full "how was this year's math computed" trace for
    this plan year (balance waterfall + income composition + federal/state
    tax breakdown) -- always populated by build_year_stories(), never
    partial (there is exactly one YearStory construction site)."""
    entries: list[NarrativeEntry] = field(default_factory=list)
    unverified_figure_names: list[str] = field(default_factory=list)


@dataclass
class RunNarrative:
    """The complete walkthrough for one simulation run
    (028-results-walkthrough data-model.md § RunNarrative). years spans
    every plan year of the selected path's projection, in ascending
    plan_year order (FR-002). Given identical scenario configuration and
    seed, selected_path_index and every YearStory/NarrativeEntry field in
    years MUST be byte-identical across repeated calls (FR-006/SC-002)."""

    selected_path_index: int
    years: list[YearStory] = field(default_factory=list)


@dataclass
class AccountTypeWaterfall:
    """rp-bm8.3: one account type's (traditional/roth/taxable) year-over-
    year balance walk for one plan year, entirely derived from already-
    computed PlanYearProjection checkpoint fields (year_detail.py) -- no
    new tax/mechanics/simulation computation. Every *_balance field below
    is a direct read of an existing checkpoint; rmd_drawn/
    spending_withdrawal/conversion_delta/tax_funding_withdrawal/growth are
    the deltas between two consecutive checkpoints."""

    account_type: Literal["traditional", "roth", "taxable"]
    starting_balance: float
    rmd_drawn: float
    """Traditional only; 0.0 for roth/taxable. From
    mechanics.withdrawal_plan.rmd_drawn -- RMDs only ever draw from
    traditional."""
    spending_withdrawal: float
    """This type's own amount from mechanics.withdrawal_plan.sequence_withdrawals
    (0.0 if this type wasn't drawn on this year)."""
    after_spending_withdrawal: float
    """Checkpoint: mechanics.withdrawal_plan.ending_balances.<type> -- post
    RMD + spending-need sequence withdrawal, pre-conversion."""
    conversion_delta: float
    """-amount_converted for traditional, +amount_converted for roth, 0.0
    for taxable (Roth conversions never touch the taxable account)."""
    after_conversion: float
    """Checkpoint: mechanics.ending_balances.<type> -- post conversion,
    pre-tax."""
    tax_funding_withdrawal: float
    """This type's own amount from tax_funding_withdrawal.sequence_withdrawals
    -- the second withdrawal pass that pays this year's tax bill."""
    after_tax_withdrawal: float
    """Checkpoint: tax_funding_withdrawal.ending_balances.<type> -- post
    tax-bill withdrawal, pre-growth."""
    growth: float
    """Derived: ending_balance - after_tax_withdrawal. Growth is applied
    last, once, to whatever remains after every withdrawal/conversion pass
    -- never stored directly anywhere (the return-path percentage is a
    projection.py-local variable), so this is the dollar amount it
    produced, read back out of two already-stored checkpoints."""
    growth_rate_pct: float | None
    """Derived: growth / after_tax_withdrawal, as a percentage. None when
    after_tax_withdrawal == 0.0 (no balance to apply a rate to -- avoids a
    division by zero rather than reporting a misleading 0%)."""
    ending_balance: float
    """Checkpoint: year.ending_balances.<type> -- final, post-growth."""


@dataclass
class BalanceWaterfall:
    """rp-bm8.3: the full account-balance walk for one plan year, across
    all three account types plus household totals."""

    traditional: AccountTypeWaterfall
    roth: AccountTypeWaterfall
    taxable: AccountTypeWaterfall
    total_starting_balance: float
    total_ending_balance: float
    total_tax_owed: float
    """federal_tax_owed + state_tax_owed + irmaa.surcharge_owed +
    niit.surtax_owed + early_withdrawal_penalty.penalty_owed +
    fica_tax.total_fica_tax -- the exact amount tax_funding_withdrawal was
    sized to cover (comparison/projection.py's own tax_owed local,
    reconstructed here from six already-stored fields, never itself a
    stored field)."""


@dataclass
class IncomeComposition:
    """rp-bm8.3: how this plan year's federal ordinary income
    (mechanics.ordinary_income) was assembled -- a pure read/sum of
    already-computed PlanYearProjection sub-fields, mirroring
    comparison/projection.py's/mechanics/plan_year.py's own
    ordinary_income_established + conversion.ordinary_income_added -
    hsa_contribution formula. Taxable Social Security is tracked
    separately (social_security_gross/taxable_social_security below) since
    it is NOT part of ordinary_income_total -- it's added in only at the
    federal tax computation step."""

    rmd_drawn: float
    traditional_sequence_withdrawal: float
    inherited_distribution: float
    income_streams: float
    """Summed member_income_stream_amounts (pensions, annuities, earned
    income) -- never Social Security, which is tracked separately below."""
    roth_conversion_added: float
    hsa_deduction: float
    ordinary_income_total: float
    """== mechanics.ordinary_income, retained here as a direct citation/
    sanity total for the components above (which sum to it, net of
    hsa_deduction)."""
    social_security_gross: float
    """Summed member_social_security_benefits -- gross Social Security
    received, not part of ordinary_income_total."""
    taxable_social_security: float
    """== federal_tax.taxable_social_security -- the portion of
    social_security_gross that becomes taxable (26 U.S.C. §86), added into
    taxable income only at the federal tax step, never into
    ordinary_income_total itself."""


@dataclass
class TaxComputationDetail:
    """rp-bm8.3: one jurisdiction's (federal or state) full tax
    computation for one plan year -- a pass-through of FederalTaxResult's/
    StateTaxResult's own newly-retained fields (tax/models.py), not
    recomputed here."""

    taxable_income: float
    deduction_or_exclusion_label: str
    """Reporting-layer-only human label for deduction_or_exclusion_amount
    -- "standard deduction" (federal), "age-65 exclusion" (SC), "age-60
    exclusion" (DE), "NC Bailey settlement exclusion" (NC), or "no state
    income tax" (FL). The tax module itself stays state-agnostic about
    presentation; this label is derived here from year.state_tax.state."""
    deduction_or_exclusion_amount: float
    bracket_breakdown: list[BracketContribution] = field(default_factory=list)
    tax_owed: float = 0.0


@dataclass
class InheritedAccountDetail:
    """rp-bm8.3: one inherited account's own distribution/ending balance
    for one plan year -- from the already-stored, independently-tracked
    inherited_account_distributions/inherited_account_balances dicts
    (012-inherited-ira-rmd; never pooled with the ordinary account-type
    waterfall above). Naturally absent for a household with no inherited
    accounts."""

    account_id: str
    distribution: float
    ending_balance: float


@dataclass
class YearComputationDetail:
    """rp-bm8.3: the full "how was this year's math computed" trace for
    one plan year -- YearStory.detail. Every field here is either a direct
    PlanYearProjection sub-field read or pure arithmetic over already-
    computed values (year_detail.py's own docstring); no new tax/
    mechanics/simulation computation (mirrors narrative.py's own
    FR-004/FR-014 discipline)."""

    balance_waterfall: BalanceWaterfall
    income_composition: IncomeComposition
    federal_tax_detail: TaxComputationDetail
    state_tax_detail: TaxComputationDetail
    inherited_accounts: list[InheritedAccountDetail] = field(default_factory=list)
