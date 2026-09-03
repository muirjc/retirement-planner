"""Shared reporting data model.

These dataclasses are the locked public shape described in
specs/006-reporting-aggregation/contracts/reporting-api.md ("Data types"
section) and specs/006-reporting-aggregation/data-model.md. PercentileBand
is imported from retirement_planner.simulation rather than redefined,
continuing that feature's convention.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from retirement_planner.simulation import PercentileBand


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
