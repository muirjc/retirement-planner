"""Required Minimum Distribution calculation (FR-001–FR-003, FR-019).

Uses the IRS Uniform Lifetime Table by default, or the Joint Life and Last
Survivor Table when the household member's spouse is their sole named
beneficiary and more than 10 years younger — the source requirement
document's flagged gap in the prototype (which only ever implemented the
Uniform Lifetime Table).

RMD_START_AGE, UNIFORM_LIFETIME_TABLE, and JOINT_LIFE_TABLE are illustrative
placeholder figures (SourcedFigure, verified=False), continuing 002's
citation/verification convention (FR-019) — see quickstart.md and plan.md's
Development Workflow gate. JOINT_LIFE_TABLE covers only the age pairs this
project's tests and quickstart.md exercise; extending coverage to the full
IRS Pub. 590-B Table II is follow-on work, not something this feature hides.

Schedule note (added for 004-strategy-comparison-layer): RMD_START_AGE is
scheduled to actually change (73 -> 75 in 2033 under SECURE 2.0) — a real
future caller must not assume it never will — but this project's own
documented figures don't yet model that second step, so the same value is
repeated across `_DOCUMENTED_YEARS` for now, same as the divisor tables
below (which are not scheduled to change). This keeps a multi-year caller
(a full-horizon projection) from hitting `UnsupportedTaxYearError` for
every year after 2026; modeling the 2033 step is follow-on work.

See specs/003-retirement-account-mechanics/contracts/mechanics-api.md
("Operations (rmd)" section) for the locked public signature of
compute_rmd().
"""

from __future__ import annotations

from datetime import date

from retirement_planner.tax import SourcedFigure

from .models import RmdResult

_DOCUMENTED_YEARS = range(2020, 2075)

RMD_START_AGE: SourcedFigure[int] = SourcedFigure(
    name="rmd_start_age",
    schedule={year: 73 for year in _DOCUMENTED_YEARS},
    citation="26 U.S.C. §401(a)(9)(C), as amended by SECURE 2.0 Act §107 (illustrative — pending verification)",
    last_verified=date(2026, 8, 28),
    verified=False,
)

_UNIFORM_LIFETIME_DIVISORS = {
    72: 27.4,
    73: 26.5,
    74: 25.5,
    75: 24.6,
    76: 23.7,
    77: 22.9,
    78: 22.0,
    79: 21.1,
    80: 20.2,
    81: 19.4,
    82: 18.5,
    83: 17.7,
    84: 16.8,
    85: 16.0,
    86: 15.2,
    87: 14.4,
    88: 13.7,
    89: 12.9,
    90: 12.2,
    91: 11.5,
    92: 10.8,
    93: 10.1,
    94: 9.5,
    95: 8.9,
    96: 8.4,
    97: 7.8,
    98: 7.3,
    99: 6.8,
    100: 6.4,
}

UNIFORM_LIFETIME_TABLE: SourcedFigure[dict[int, float]] = SourcedFigure(
    name="uniform_lifetime_table",
    schedule={year: _UNIFORM_LIFETIME_DIVISORS for year in _DOCUMENTED_YEARS},
    citation="IRS Pub. 590-B, Table III (Uniform Lifetime) (illustrative — pending verification)",
    last_verified=date(2026, 8, 28),
    verified=False,
)

_JOINT_LIFE_DIVISORS = {
    (75, 60): 35.2,
    (80, 65): 29.9,
    (90, 75): 18.4,
}

JOINT_LIFE_TABLE: SourcedFigure[dict[tuple[int, int], float]] = SourcedFigure(
    name="joint_life_and_last_survivor_table",
    schedule={year: _JOINT_LIFE_DIVISORS for year in _DOCUMENTED_YEARS},
    citation=(
        "IRS Pub. 590-B, Table II (Joint Life and Last Survivor) — "
        "partial coverage, illustrative — pending verification"
    ),
    last_verified=date(2026, 8, 28),
    verified=False,
)


def compute_rmd(
    traditional_balance: float,
    member_age: int,
    tax_year: int,
    spouse_age: int | None = None,
    spouse_is_sole_beneficiary: bool = False,
) -> RmdResult:
    """Computes one household member's RMD for tax_year (FR-001–FR-003).

    Uses the Joint Life and Last Survivor Table instead of the Uniform
    Lifetime Table when spouse_is_sole_beneficiary is True and
    member_age - spouse_age > 10 (FR-002). Returns required_amount=0,
    table_used=None when member_age is below that year's RMD-required
    starting age, or traditional_balance <= 0 (FR-003). Raises
    UnsupportedTaxYearError if the RMD-required starting age, or the
    divisor table actually needed, has no entry for tax_year.
    """
    start_age = RMD_START_AGE.value_for_year(tax_year)  # raises UnsupportedTaxYearError

    if member_age < start_age or traditional_balance <= 0:
        return RmdResult(required_amount=0.0, table_used=None, divisor=None, figures_used=[])

    use_joint_life = (
        spouse_is_sole_beneficiary and spouse_age is not None and (member_age - spouse_age) > 10
    )

    if use_joint_life:
        table_figure = JOINT_LIFE_TABLE
        divisor = table_figure.value_for_year(tax_year)[(member_age, spouse_age)]
        table_used = "joint_life"
    else:
        table_figure = UNIFORM_LIFETIME_TABLE
        divisor = table_figure.value_for_year(tax_year)[member_age]
        table_used = "uniform_lifetime"

    required_amount = traditional_balance / divisor
    figures_used = [RMD_START_AGE.usage_for_year(tax_year), table_figure.usage_for_year(tax_year)]

    return RmdResult(
        required_amount=required_amount,
        table_used=table_used,
        divisor=divisor,
        figures_used=figures_used,
    )
