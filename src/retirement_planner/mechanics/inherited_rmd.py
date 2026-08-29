"""Inherited-account (already-in-RMD-status) distribution calculation
(012-inherited-ira-rmd FR-002, FR-003).

Computes the annual required distribution for an inherited traditional
account whose original owner died on or after their own Required Beginning
Date (RBD) and whose beneficiary is a non-eligible designated beneficiary --
the SECURE Act 2.0 10-year-rule case, the only case this module computes
(research.md §2, §3). Every other inherited-account case (owner died before
their RBD, an eligible-designated-beneficiary, a non-traditional account) is
caught by scenario.validation's blocking flags before ever reaching this
module -- see specs/012-inherited-ira-rmd/data-model.md § Validation rules.

Deliberately a sibling module to rmd.py, not a branch inside compute_rmd()
-- compute_rmd()'s signature is a locked contract (003's
contracts/mechanics-api.md) already consumed by every RMD call site; a
decedent's account's forced depletion schedule is a conceptually and
legally distinct computation from a living owner's own RMD (research.md §7).

SINGLE_LIFE_EXPECTANCY_TABLE is a SourcedFigure (verified=True), cross-checked
against IRS Pub. 590-B (2025), Appendix B, Table I (Single Life Expectancy)
-- https://www.irs.gov/pub/irs-pdf/p590b.pdf, pp. 50-51 -- covering every
published age, 0 through 120+ (rp-6c5). This is the current table, unchanged
since the IRS's 2021 mortality-table update took effect for 2022
distributions; previously it shipped as an unverified placeholder covering
only a partial age range, following rmd.py's own JOINT_LIFE_TABLE precedent.

See specs/012-inherited-ira-rmd/contracts/mechanics-api.md for the locked
public signature of compute_inherited_rmd().
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from retirement_planner.tax import SourcedFigure

from .models import InheritedRmdResult

_DOCUMENTED_YEARS = range(2000, 2075)

# Every age 0-120 (120 representing the IRS's "120+" terminal row) from IRS
# Pub. 590-B (2025), Appendix B, Table I (Single Life Expectancy), p. 50-51
# (https://www.irs.gov/pub/irs-pdf/p590b.pdf) -- verified against that
# primary source 2026-08-29 (rp-6c5). This table has been unchanged since
# the IRS's 2021 mortality-table update took effect for 2022 distributions.
_SINGLE_LIFE_EXPECTANCY_DIVISORS = {
    0: 84.6,
    1: 83.7,
    2: 82.8,
    3: 81.8,
    4: 80.8,
    5: 79.8,
    6: 78.8,
    7: 77.9,
    8: 76.9,
    9: 75.9,
    10: 74.9,
    11: 73.9,
    12: 72.9,
    13: 71.9,
    14: 70.9,
    15: 69.9,
    16: 69.0,
    17: 68.0,
    18: 67.0,
    19: 66.0,
    20: 65.0,
    21: 64.1,
    22: 63.1,
    23: 62.1,
    24: 61.1,
    25: 60.2,
    26: 59.2,
    27: 58.2,
    28: 57.3,
    29: 56.3,
    30: 55.3,
    31: 54.4,
    32: 53.4,
    33: 52.5,
    34: 51.5,
    35: 50.5,
    36: 49.6,
    37: 48.6,
    38: 47.7,
    39: 46.7,
    40: 45.7,
    41: 44.8,
    42: 43.8,
    43: 42.9,
    44: 41.9,
    45: 41.0,
    46: 40.0,
    47: 39.0,
    48: 38.1,
    49: 37.1,
    50: 36.2,
    51: 35.3,
    52: 34.3,
    53: 33.4,
    54: 32.5,
    55: 31.6,
    56: 30.6,
    57: 29.8,
    58: 28.9,
    59: 28.0,
    60: 27.1,
    61: 26.2,
    62: 25.4,
    63: 24.5,
    64: 23.7,
    65: 22.9,
    66: 22.0,
    67: 21.2,
    68: 20.4,
    69: 19.6,
    70: 18.8,
    71: 18.0,
    72: 17.2,
    73: 16.4,
    74: 15.6,
    75: 14.8,
    76: 14.1,
    77: 13.3,
    78: 12.6,
    79: 11.9,
    80: 11.2,
    81: 10.5,
    82: 9.9,
    83: 9.3,
    84: 8.7,
    85: 8.1,
    86: 7.6,
    87: 7.1,
    88: 6.6,
    89: 6.1,
    90: 5.7,
    91: 5.3,
    92: 4.9,
    93: 4.6,
    94: 4.3,
    95: 4.0,
    96: 3.7,
    97: 3.4,
    98: 3.2,
    99: 3.0,
    100: 2.8,
    101: 2.6,
    102: 2.5,
    103: 2.3,
    104: 2.2,
    105: 2.1,
    106: 2.1,
    107: 2.1,
    108: 2.0,
    109: 2.0,
    110: 2.0,
    111: 2.0,
    112: 2.0,
    113: 1.9,
    114: 1.9,
    115: 1.8,
    116: 1.8,
    117: 1.6,
    118: 1.4,
    119: 1.1,
    120: 1.0,
}

SINGLE_LIFE_EXPECTANCY_TABLE: SourcedFigure[dict[int, float]] = SourcedFigure(
    name="single_life_expectancy_table",
    schedule={year: _SINGLE_LIFE_EXPECTANCY_DIVISORS for year in _DOCUMENTED_YEARS},
    citation="IRS Pub. 590-B (2025), Appendix B, Table I (Single Life Expectancy), pp. 50-51",
    last_verified=date(2026, 8, 29),
    verified=True,
)


def compute_inherited_rmd(
    inherited_balance: float,
    tax_year: int,
    death_year: int,
    decedent_age_at_death: int,
    decedent_was_taking_rmds: bool,
    beneficiary_classification: Literal[
        "eligible_designated_beneficiary_spouse",
        "eligible_designated_beneficiary_other",
        "non_eligible_designated_beneficiary",
    ],
) -> InheritedRmdResult:
    """Computes one inherited traditional account's required distribution
    for tax_year (research.md §2, §3, §7) -- the only case this function
    actually computes is decedent_was_taking_rmds=True and
    beneficiary_classification="non_eligible_designated_beneficiary";
    callers are responsible for not invoking it for any other combination
    (guaranteed by scenario.validation's blocking flags before this is
    ever reached from run_plan_projection() -- decedent_was_taking_rmds
    and beneficiary_classification are still accepted as explicit
    parameters, mirroring compute_rmd()'s own
    spouse_is_sole_beneficiary parameter, rather than assumed silently).

    Looks up the decedent's Single Life Expectancy divisor at
    decedent_age_at_death for death_year + 1, then reduces it by exactly
    1.0 for each subsequent tax_year (research.md §7) -- never a fresh
    table lookup keyed by a later year. required_amount =
    inherited_balance / divisor. depletion_deadline_year = death_year + 10;
    is_within_ten_year_window = tax_year <= depletion_deadline_year.

    Returns required_amount=0.0, table_used=None, divisor=None when
    inherited_balance <= 0. Raises UnsupportedTaxYearError if the Single
    Life Expectancy Table has no entry for the divisor year needed
    (death_year + 1). This function does not itself enforce the 10-year
    forced full-depletion draw -- that is the caller's responsibility
    (data-model.md § Consumption); it only reports
    is_within_ten_year_window/depletion_deadline_year for the caller's
    own use.
    """
    depletion_deadline_year = death_year + 10
    is_within_ten_year_window = tax_year <= depletion_deadline_year

    if inherited_balance <= 0:
        return InheritedRmdResult(
            required_amount=0.0,
            table_used=None,
            divisor=None,
            figures_used=[],
            depletion_deadline_year=depletion_deadline_year,
            is_within_ten_year_window=is_within_ten_year_window,
        )

    initial_divisor_year = death_year + 1
    initial_divisor = SINGLE_LIFE_EXPECTANCY_TABLE.value_for_year(initial_divisor_year)[  # raises UnsupportedTaxYearError
        decedent_age_at_death
    ]
    divisor = initial_divisor - (tax_year - initial_divisor_year)

    required_amount = inherited_balance / divisor
    figures_used = [SINGLE_LIFE_EXPECTANCY_TABLE.usage_for_year(initial_divisor_year)]

    return InheritedRmdResult(
        required_amount=required_amount,
        table_used="single_life_expectancy",
        divisor=divisor,
        figures_used=figures_used,
        depletion_deadline_year=depletion_deadline_year,
        is_within_ten_year_window=is_within_ten_year_window,
    )
