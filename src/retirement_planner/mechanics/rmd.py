"""Required Minimum Distribution calculation (FR-001–FR-003, FR-019).

Uses the IRS Uniform Lifetime Table by default, or the Joint Life and Last
Survivor Table when the household member's spouse is their sole named
beneficiary and more than 10 years younger — the source requirement
document's flagged gap in the prototype (which only ever implemented the
Uniform Lifetime Table).

RMD_START_AGE and UNIFORM_LIFETIME_TABLE have both been cross-checked
against their primary sources and ship verified=True
(014-figure-verification, rp-9wi.5/.7). JOINT_LIFE_TABLE remains an
illustrative placeholder figure (SourcedFigure, verified=False),
continuing 002's citation/verification convention (FR-019) -- it covers
only the age pairs this project's tests and quickstart.md exercise, and
neither its coverage nor its verification is in that feature's scope;
extending it to the full IRS Pub. 590-B Table II remains follow-on work.

Schedule note (added for 004-strategy-comparison-layer, updated by
014-figure-verification): RMD_START_AGE is scheduled to actually change
(73 -> 75 in 2033 under SECURE 2.0 Act §107, codified at 26 U.S.C.
§401(a)(9)(C)(v)) -- a real future caller must not assume it never will.
That step is now modeled directly: the schedule below returns 73 for
tax years before 2033 and 75 for 2033 onward. This is a tax-year-keyed
approximation of the statute's actual rule, which is keyed to the
account owner's *birth year* (age 73 applies to those born 1951-1959,
age 75 to those born 1960 or later — the 2033 tax-year cutoff is where
the birth-year cohorts' own RMD-triggering ages happen to cross that
line, not a literal restatement of the statute). Modeling the full
birth-year-cohort distinction would require threading the account
owner's birth year through compute_rmd()'s signature and every caller —
a materially larger change than this feature's other figure corrections
— and is deliberately left as separate follow-on work
(research.md §3, spec.md Assumptions). The divisor tables below are not
scheduled to change and keep the same flat-schedule shape.

See specs/003-retirement-account-mechanics/contracts/mechanics-api.md
("Operations (rmd)" section) for the locked public signature of
compute_rmd().
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from retirement_planner.tax import SourcedFigure

from .models import RmdResult

_DOCUMENTED_YEARS = range(2020, 2075)

RMD_START_AGE: SourcedFigure[int] = SourcedFigure(
    name="rmd_start_age",
    schedule={
        **{year: 73 for year in range(_DOCUMENTED_YEARS.start, 2033)},
        **{year: 75 for year in range(2033, _DOCUMENTED_YEARS.stop)},
    },
    citation=(
        "26 U.S.C. §401(a)(9)(C)(v), as amended by SECURE 2.0 Act (Pub. L. 117-328) §107 — "
        "applicable age 73 for individuals attaining age 72 after Dec. 31, 2022 and age 73 "
        "before Jan. 1, 2033; applicable age 75 for individuals attaining age 74 after "
        "Dec. 31, 2032. Modeled here as a tax-year step (73 before 2033, 75 from 2033 on) "
        "rather than the statute's own birth-year-cohort basis — see module docstring."
    ),
    last_verified=date(2026, 8, 30),
    verified=True,
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
    101: 6.0,
    102: 5.6,
    103: 5.2,
    104: 4.9,
    105: 4.6,
    106: 4.3,
    107: 4.1,
    108: 3.9,
    109: 3.7,
    110: 3.5,
    111: 3.4,
    112: 3.3,
    113: 3.1,
    114: 3.0,
    115: 2.9,
    116: 2.8,
    117: 2.7,
    118: 2.5,
    119: 2.3,
    120: 2.0,  # "120 and over" per the published table -- see compute_rmd()'s
    # own age lookup, which indexes this dict directly by member_age with no
    # clamping; an age above 120 still raises a plain KeyError (data-model.md).
}

UNIFORM_LIFETIME_TABLE: SourcedFigure[dict[int, float]] = SourcedFigure(
    name="uniform_lifetime_table",
    schedule={year: _UNIFORM_LIFETIME_DIVISORS for year in _DOCUMENTED_YEARS},
    citation="IRS Pub. 590-B (2025), Appendix B, Table III (Uniform Lifetime) — full published age range, 72 through 120 and over",
    last_verified=date(2026, 8, 30),
    verified=True,
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

    # rp-cgj: each branch keeps its own SourcedFigure reference (rather than
    # a shared `table_figure` name) since JOINT_LIFE_TABLE and
    # UNIFORM_LIFETIME_TABLE are differently-keyed
    # (SourcedFigure[dict[tuple[int, int], float]] vs.
    # SourcedFigure[dict[int, float]]) -- mypy correctly rejects reusing one
    # variable across both. table_used gets an explicit Literal annotation
    # so its two string-literal assignments narrow to RmdResult's own
    # Literal["uniform_lifetime", "joint_life"] field, not a widened str.
    table_used: Literal["uniform_lifetime", "joint_life"]
    if use_joint_life:
        # use_joint_life's own definition above already required
        # spouse_age is not None -- this assert documents that invariant
        # for mypy, which doesn't track it through the boolean flag.
        assert spouse_age is not None
        divisor = JOINT_LIFE_TABLE.value_for_year(tax_year)[(member_age, spouse_age)]
        table_used = "joint_life"
        figures_used = [RMD_START_AGE.usage_for_year(tax_year), JOINT_LIFE_TABLE.usage_for_year(tax_year)]
    else:
        divisor = UNIFORM_LIFETIME_TABLE.value_for_year(tax_year)[member_age]
        table_used = "uniform_lifetime"
        figures_used = [RMD_START_AGE.usage_for_year(tax_year), UNIFORM_LIFETIME_TABLE.usage_for_year(tax_year)]

    required_amount = traditional_balance / divisor

    return RmdResult(
        required_amount=required_amount,
        table_used=table_used,
        divisor=divisor,
        figures_used=figures_used,
    )
