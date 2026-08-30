"""HSA contribution eligibility and limit calculation
(010-advanced-tax-benefits FR-008-FR-012).

compute_hsa_eligibility() determines each household member's eligibility
independently (FR-010): eligible iff covered by a qualifying HDHP and not
Medicare-enrolled -- one member's result never depends on another
member's coverage or enrollment status. compute_hsa_contribution() then
looks up the applicable IRS contribution limit for the number of
eligible members this plan year (self-only vs. family, plus a per-
eligible-member 55+ catch-up) and caps the household's configured intent
at that limit, never raising for the ordinary "not eligible this year" or
"configured above the limit" cases (research.md §5) -- only for an
undocumented tax_year's limit figure.

The dollar limits below are IRS Rev. Proc. 2025-19's actual tax year 2026
figures (self-only/family under IRC §223(b); the $1,000 catch-up is
itself a fixed statutory amount, not inflation-indexed), cross-checked
directly against that Revenue Procedure and the statute
(014-figure-verification, rp-9wi.2) — pinned to the same tax year 2026
basis as federal.py's/irmaa.py's own real-dollar figures, per this
project's "real dollars, no further indexing engine" convention.

See specs/010-advanced-tax-benefits/contracts/mechanics-api.md for the
locked public signatures of compute_hsa_eligibility()/compute_hsa_contribution().
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from retirement_planner.tax import FigureUsage, SourcedFigure

from .models import HsaContributionResult, HsaEligibility

_DOCUMENTED_YEARS = range(2020, 2075)

_CATCH_UP_ELIGIBLE_AGE = 55


@dataclass
class _HsaLimits:
    self_only: float
    family: float
    catch_up: float


_HSA_LIMITS: SourcedFigure[_HsaLimits] = SourcedFigure(
    name="hsa_contribution_limits",
    schedule={
        year: _HsaLimits(self_only=4_400.0, family=8_750.0, catch_up=1_000.0) for year in _DOCUMENTED_YEARS
    },
    citation="IRS Rev. Proc. 2025-19, tax year 2026 HSA contribution limits (IRC §223(b); $1,000 catch-up per IRC §223(b)(3), fixed by statute)",
    last_verified=date(2026, 8, 30),
    verified=True,
)


def compute_hsa_eligibility(
    members: list[tuple[str, int, bool]],
    medicare_enrolled: dict[str, bool],
) -> list[HsaEligibility]:
    """members is a list of (person_name, age_this_year, hdhp_coverage).
    A member is eligible iff hdhp_coverage is True and
    medicare_enrolled[person_name] is False (FR-008-FR-010) -- computed
    per member, independent of every other member's own values. Each
    result carries that member's age (for compute_hsa_contribution()'s
    own 55+ catch-up determination, contracts/mechanics-api.md's
    correction note)."""
    results = []
    for person_name, age, hdhp_coverage in members:
        if medicare_enrolled.get(person_name, False):
            results.append(
                HsaEligibility(person_name=person_name, age=age, eligible=False, reason="enrolled in Medicare")
            )
        elif not hdhp_coverage:
            results.append(
                HsaEligibility(
                    person_name=person_name, age=age, eligible=False, reason="not covered by a qualifying HDHP"
                )
            )
        else:
            results.append(HsaEligibility(person_name=person_name, age=age, eligible=True, reason=None))
    return results


def compute_hsa_contribution(
    eligibility: list[HsaEligibility],
    configured_annual_amount: float,
    tax_year: int,
) -> HsaContributionResult:
    """Looks up tax_year's HSA contribution limits, determines the
    applicable_limit from how many members in eligibility are eligible
    (0 -> 0.0; 1 -> self_only; 2+ -> family), plus catch_up once per
    eligible member 55+, and sets amount_contributed to
    min(configured_annual_amount, applicable_limit) (FR-011). Sets
    rejected_reason when amount_contributed is 0.0 (no eligible member)
    or capped below configured_annual_amount (research.md §5) -- never
    raises for either case. Raises UnsupportedTaxYearError if the limit
    figure has no entry for tax_year.
    """
    limits_figure = _HSA_LIMITS
    limits = limits_figure.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    figures_used: list[FigureUsage] = [limits_figure.usage_for_year(tax_year)]

    eligible = [e for e in eligibility if e.eligible]

    if not eligible:
        return HsaContributionResult(
            eligible_members=eligibility,
            applicable_limit=0.0,
            amount_contributed=0.0,
            rejected_reason="no eligible household member this plan year",
            figures_used=figures_used,
        )

    base_limit = limits.self_only if len(eligible) == 1 else limits.family
    applicable_limit = base_limit + limits.catch_up * sum(
        1 for e in eligible if e.age >= _CATCH_UP_ELIGIBLE_AGE
    )

    if configured_annual_amount <= applicable_limit:
        return HsaContributionResult(
            eligible_members=eligibility,
            applicable_limit=applicable_limit,
            amount_contributed=configured_annual_amount,
            rejected_reason=None,
            figures_used=figures_used,
        )

    return HsaContributionResult(
        eligible_members=eligibility,
        applicable_limit=applicable_limit,
        amount_contributed=applicable_limit,
        rejected_reason=(
            f"configured annual_amount {configured_annual_amount:.2f} exceeds the "
            f"applicable limit {applicable_limit:.2f} for {tax_year} -- capped"
        ),
        figures_used=figures_used,
    )
