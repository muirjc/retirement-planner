"""Pension/annuity/phased-retirement income-stream amount derivation
(021-pension-annuity-income, rp-pid).

Derives one IncomeStream's own gross amount for one plan year, given the
member's age that year. This engine already works entirely in real,
inflation-adjusted dollars, with no separate nominal-dollar projection
(tax/federal.py's own "real dollars, no further indexing engine"
convention, restated in docs/BRD.md §5.2) -- so a cost-of-living-adjusted
income source, translated into that convention, is simply flat:
`cola_adjusted` pays exactly its configured annual_amount every active
year, the same treatment ss_annual_benefit already gets. A *non*-COLA'd
(`fixed_nominal`) source is the opposite -- its purchasing power genuinely
erodes every year -- and this engine has no existing nominal-dollar
inflation schedule to derive that erosion from, because nothing before
this feature needed one. INFLATION_RATE below is that engine's first
inflation-rate figure (specs/021-pension-annuity-income/research.md §1).

See specs/021-pension-annuity-income/contracts/mechanics-api.md ("New
operations (income_streams)" section) for the locked public signature of
compute_income_stream_amount().
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from retirement_planner.tax import SourcedFigure

from .models import IncomeStreamAmountResult

_DOCUMENTED_YEARS = range(2020, 2075)

INFLATION_RATE: SourcedFigure[float] = SourcedFigure(
    name="income_stream_fixed_nominal_erosion_rate",
    schedule={year: 0.024 for year in _DOCUMENTED_YEARS},
    citation=(
        "The 2025 Annual Report of the Boards of Trustees of the OASI and DI Trust Funds, "
        "\"Long-Range Economic Assumptions\" (intermediate assumption, ultimate annual CPI "
        "increase): 2.40%/year -- the same inflation index the Social Security Administration "
        "itself uses to project future Social Security COLAs, chosen here specifically because "
        "it is the natural pairing for eroding a NON-COLA'd income stream against. "
        "https://www.ssa.gov/oact/TR/2025/2025_Long-Range_Economic_Assumptions.pdf"
    ),
    last_verified=date(2026, 9, 2),
    verified=True,
)
"""A planning assumption, not government-published tax law -- unlike most
other SourcedFigures in this codebase, this rate is never going to be
"the" legally correct number, only a documented, cited, defensible one
(constitution Principle I). Fixed across every documented year, mirroring
tax/social_security.py's own "fixed since 1983" precedent and
mechanics/social_security_benefit.py's SS_CLAIMING_AGE_ADJUSTMENT -- not
because this rate is fixed by law, but because this engine has no
per-year-varying inflation forecast to plug in instead; a single flat
rate is the documented simplification (research.md §1)."""


def compute_income_stream_amount(
    annual_amount: float,
    inflation_adjustment: Literal["cola_adjusted", "fixed_nominal"],
    start_age: int,
    end_age: int | None,
    member_age_this_year: int,
    tax_year: int,
    reference_tax_year: int,
) -> IncomeStreamAmountResult:
    """Takes an IncomeStream's fields as plain values rather than a
    scenario.IncomeStream instance -- this package is a pure calculator
    over explicit inputs, the same convention 003's own data-model.md
    states ("does not read a Scenario object directly") and every other
    mechanics function already follows (e.g.
    compute_social_security_benefit() takes a raw PIA/FRA/claiming_age,
    never a HouseholdMember).

    Returns amount=0.0, figures_used=[] when member_age_this_year falls
    outside [start_age, end_age or +inf] (data-model.md §
    IncomeStreamAmountResult). Otherwise: amount=annual_amount,
    figures_used=[] for a cola_adjusted stream (flat pass-through, no
    figure to cite); amount=annual_amount eroded against INFLATION_RATE,
    compounded from reference_tax_year (not from start_age -- a stream
    that hasn't started paying yet still loses the same real value while
    waiting, research.md §1's Assumptions),
    figures_used=[INFLATION_RATE.usage_for_year(tax_year)] for a
    fixed_nominal stream. Pure function -- no dependency on any other
    stream, member, or account state.
    """
    if member_age_this_year < start_age:
        return IncomeStreamAmountResult(amount=0.0, figures_used=[])
    if end_age is not None and member_age_this_year > end_age:
        return IncomeStreamAmountResult(amount=0.0, figures_used=[])

    if inflation_adjustment == "cola_adjusted":
        return IncomeStreamAmountResult(amount=annual_amount, figures_used=[])

    rate = INFLATION_RATE.value_for_year(tax_year)
    years_elapsed = tax_year - reference_tax_year
    amount = annual_amount / ((1.0 + rate) ** years_elapsed)
    return IncomeStreamAmountResult(
        amount=amount, figures_used=[INFLATION_RATE.usage_for_year(tax_year)]
    )
