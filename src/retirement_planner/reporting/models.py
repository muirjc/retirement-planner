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
    unverified_figure_names: list[str] = field(default_factory=list)
