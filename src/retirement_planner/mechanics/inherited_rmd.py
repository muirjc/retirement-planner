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

SINGLE_LIFE_EXPECTANCY_TABLE is an illustrative placeholder figure
(SourcedFigure, verified=False), continuing 002's/003's citation/
verification convention -- see quickstart.md and plan.md's Development
Workflow gate. It covers only a partial age range, the same "partial
coverage, explicitly flagged" precedent rmd.py's own JOINT_LIFE_TABLE
already established; extending coverage to the full IRS Pub. 590-B Table I
is follow-on work, not something this feature hides.

See specs/012-inherited-ira-rmd/contracts/mechanics-api.md for the locked
public signature of compute_inherited_rmd().
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from retirement_planner.tax import SourcedFigure

from .models import InheritedRmdResult

_DOCUMENTED_YEARS = range(2000, 2075)

_SINGLE_LIFE_EXPECTANCY_DIVISORS = {
    50: 38.2,
    55: 33.8,
    60: 29.6,
    65: 25.5,
    70: 21.6,
    71: 20.8,
    72: 20.0,
    73: 19.2,
    74: 18.4,
    75: 17.6,
    76: 16.8,
    77: 16.0,
    78: 15.3,
    79: 14.6,
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
}

SINGLE_LIFE_EXPECTANCY_TABLE: SourcedFigure[dict[int, float]] = SourcedFigure(
    name="single_life_expectancy_table",
    schedule={year: _SINGLE_LIFE_EXPECTANCY_DIVISORS for year in _DOCUMENTED_YEARS},
    citation=(
        "IRS Pub. 590-B, Table I (Single Life Expectancy) -- "
        "partial coverage, illustrative -- pending verification"
    ),
    last_verified=date(2026, 8, 29),
    verified=False,
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
