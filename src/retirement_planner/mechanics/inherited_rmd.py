"""Inherited-account distribution calculation (012-inherited-ira-rmd
FR-002, FR-003; extended by 013-inherited-ira-edge-cases).

Computes the annual required distribution for an inherited traditional or
Roth account, covering: the original-owner-died-on/after-RBD, non-eligible
designated beneficiary (10-year-rule) case (012's own original scope); the
original-owner-died-before-RBD case and Roth accounts, both of which never
require an annual distribution at all (013 research.md §1, §2); and the
eligible-designated-beneficiary (EDB) annual "stretch" case, for both a
spouse and a non-spouse beneficiary (013 research.md §3-§6). A trust/entity
beneficiary is still caught by scenario.validation's blocking flags before
ever reaching this module -- see 013's research.md §7/§8.

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
from .rmd import RMD_START_AGE

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
    account_type: Literal["traditional", "roth"] = "traditional",
    beneficiary_current_age: int | None = None,
    depletion_deadline_year: int | None = None,
) -> InheritedRmdResult:
    """Computes one inherited account's required distribution for
    tax_year (013-inherited-ira-edge-cases research.md §1-§6, extending
    012's own research.md §2, §3, §7).

    account_type (research.md §2): a "roth" account is always treated as
    though its original owner died before their Required Beginning Date
    (RBD), regardless of decedent_was_taking_rmds -- a Roth owner never
    truly "was taking RMDs" during their own lifetime under IRS rules, so
    that field's literal value is ignored for a Roth account rather than
    trusted. Defaults to "traditional", reproducing 012's own only-ever
    account type for every existing caller.

    beneficiary_current_age (research.md §3-§6; rp-kn5): the beneficiary's
    own age, translated to tax_year -- required (raises AssertionError if
    omitted) whenever a beneficiary's own divisor is actually needed to
    compute this year's amount: every eligible designated beneficiary
    (EDB) call, and also a non-EDB call when the owner died on/after RBD
    (rp-kn5 -- the "longer of" comparison now applies there too). Never
    consulted for a non-EDB call when the owner died before RBD or the
    account is a Roth (no annual amount is computed at all in that case).
    For a non-spouse EDB or a post-RBD non-EDB, looked up once at the
    initial divisor year (death_year + 1) then reduced by 1.0 each
    subsequent year, mirroring decedent_age_at_death's own existing
    "look up once, decrement" treatment -- so beneficiary_current_age
    must be given fresh, translated to *this* call's own tax_year, on
    every call (never just the initial year's value held fixed by the
    caller). For a spouse EDB, looked up fresh every single call instead
    (research.md §4 -- Pub. 590-B's own spousal recalculation rule).

    depletion_deadline_year (research.md §5, §6): the caller's own
    already-computed authoritative deadline (InheritedAccountBalance's
    own field of the same name) -- when given, used as-is; when omitted
    (None, the default), computed internally as death_year + 10,
    reproducing 012's own only-ever case for every existing caller. This
    function never itself enforces the forced full-depletion draw at
    that deadline (data-model.md § Consumption, unchanged from 012) --
    it only reports is_within_ten_year_window/depletion_deadline_year
    for the caller's own use.

    For beneficiary_classification="non_eligible_designated_beneficiary"
    when the owner died on/after RBD: required_amount is based on the
    "longer of" the beneficiary's own divisor or the decedent's own
    divisor (rp-kn5; IRS Pub. 590-B (2025) p.9's "longer of" rule for "a
    designated beneficiary" is not qualified to EDBs only -- 012's original
    decedent-only divisor here undercounted the shielding a beneficiary
    younger than the decedent is actually entitled to, overstating the
    required distribution in the common case). Returns required_amount=0.0,
    table_used=None, divisor=None for every year before the deadline when
    the owner died before RBD or account_type="roth" (research.md §1, §2
    -- no annual RMD required at all in that case, only the caller's own
    forced full-depletion draw at the deadline).

    For an EDB (spouse or other): required_amount is based on the same
    "longer of" comparison when the owner died on/after RBD (research.md
    §3, §4); the beneficiary's own divisor alone otherwise -- with a
    spouse EDB's distributions additionally delayed to (and
    required_amount=0.0 before) the year the owner would have reached
    their own RBD, when the owner died before RBD (research.md §4). A
    minor-child EDB uses exactly the non-spouse EDB divisor formula -- the
    majority-triggered conversion to the 10-year rule lives entirely in
    the caller's own depletion_deadline_year (research.md §5), never
    inside this function.

    Returns required_amount=0.0, table_used=None, divisor=None when
    inherited_balance <= 0. Raises UnsupportedTaxYearError if the Single
    Life Expectancy Table (or, for a pre-RBD spouse EDB, RMD_START_AGE)
    has no entry for a year this call needs.
    """
    if depletion_deadline_year is None:
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
    is_edb = beneficiary_classification != "non_eligible_designated_beneficiary"
    is_spouse = beneficiary_classification == "eligible_designated_beneficiary_spouse"
    owner_died_before_rbd = account_type == "roth" or not decedent_was_taking_rmds

    def _no_annual_rmd_required() -> InheritedRmdResult:
        """research.md §1, §2, §4: the 10-year-rule non-EDB case (pre-RBD
        or Roth) and a not-yet-required-to-start spouse EDB both return
        this -- no table consulted, since none was needed this year."""
        return InheritedRmdResult(
            required_amount=0.0,
            table_used=None,
            divisor=None,
            figures_used=[],
            depletion_deadline_year=depletion_deadline_year,
            is_within_ten_year_window=is_within_ten_year_window,
        )

    def _owner_divisor() -> float:
        """012's own existing formula, unchanged: the decedent's divisor,
        looked up once at decedent_age_at_death, reduced by 1.0/year."""
        initial = SINGLE_LIFE_EXPECTANCY_TABLE.value_for_year(initial_divisor_year)[decedent_age_at_death]
        return initial - (tax_year - initial_divisor_year)

    def _beneficiary_decrement_divisor() -> float:
        """research.md §3, §5; rp-kn5: non-spouse EDB divisor, and (since
        rp-kn5) a post-RBD non-EDB divisor's other "longer of" candidate --
        looked up once at the beneficiary's own age in the initial divisor
        year, then reduced by 1.0/year, mirroring _owner_divisor()'s own
        method."""
        assert beneficiary_current_age is not None, "beneficiary_current_age is required here"
        beneficiary_age_at_initial_year = beneficiary_current_age - (tax_year - initial_divisor_year)
        initial = SINGLE_LIFE_EXPECTANCY_TABLE.value_for_year(initial_divisor_year)[beneficiary_age_at_initial_year]
        return initial - (tax_year - initial_divisor_year)

    def _spouse_recalculated_divisor() -> float:
        """research.md §4: a spouse EDB's divisor is looked up fresh
        every year, at the spouse's own then-current age -- never
        decremented from an earlier lookup."""
        assert beneficiary_current_age is not None, "beneficiary_current_age is required here"
        return SINGLE_LIFE_EXPECTANCY_TABLE.value_for_year(tax_year)[beneficiary_current_age]

    if not is_edb:
        if owner_died_before_rbd:
            return _no_annual_rmd_required()
        # rp-kn5: same "longer of" comparison as the EDB branches below --
        # confirmed via 013 research.md §3's own primary-source reading
        # (Pub. 590-B p.9's "longer of" rule is not qualified to EDBs
        # only) plus independent cross-check against professional
        # secondary sources describing the post-2024-final-regulations
        # "at least as rapidly" requirement for any designated
        # beneficiary. 012's original decedent-only divisor here
        # overstated the required distribution whenever the beneficiary
        # is younger than the decedent (the common case).
        divisor = max(_beneficiary_decrement_divisor(), _owner_divisor())
        figure_years = [initial_divisor_year]
    elif is_spouse:
        if owner_died_before_rbd:
            decedent_rbd_age = RMD_START_AGE.value_for_year(initial_divisor_year)  # raises UnsupportedTaxYearError
            decedent_birth_year = death_year - decedent_age_at_death
            decedent_rbd_year = decedent_birth_year + decedent_rbd_age
            if tax_year < decedent_rbd_year:
                return _no_annual_rmd_required()
            divisor = _spouse_recalculated_divisor()
            figure_years = [tax_year]
        else:
            divisor = max(_spouse_recalculated_divisor(), _owner_divisor())
            figure_years = [tax_year, initial_divisor_year]
    else:  # non-spouse EDB (other_individual, or minor_child before majority -- research.md §5)
        if owner_died_before_rbd:
            divisor = _beneficiary_decrement_divisor()
            figure_years = [initial_divisor_year]
        else:
            divisor = max(_beneficiary_decrement_divisor(), _owner_divisor())
            figure_years = [initial_divisor_year]

    required_amount = inherited_balance / divisor
    figures_used = [SINGLE_LIFE_EXPECTANCY_TABLE.usage_for_year(year) for year in figure_years]
    if is_spouse and owner_died_before_rbd:
        figures_used.append(RMD_START_AGE.usage_for_year(initial_divisor_year))

    return InheritedRmdResult(
        required_amount=required_amount,
        table_used="single_life_expectancy",
        divisor=divisor,
        figures_used=figures_used,
        depletion_deadline_year=depletion_deadline_year,
        is_within_ten_year_window=is_within_ten_year_window,
    )
