"""North Carolina state income tax (FR-006) — a true flat-rate state, not a
graduated-bracket one.

North Carolina has taxed 100% of taxable income at a single statutory rate
since the 2013 tax reform (effective tax year 2014) -- there is no $0-rate
floor bracket like SC's and no higher bracket at any income level, unlike
SC's/DE's genuine multi-row tables. Represented here as a one-row
`BracketTable` per tax year (`BracketRow(rate=R, income_up_to=None)`) run
through the same `apply_progressive_brackets()` every other bracket-based
module uses -- it degenerates correctly for a single unbounded row, so no
separate flat-rate code path is needed (024-nc-state-tax research.md §1).

North Carolina does not tax Social Security benefits, so only
`ordinary_income` enters NC's taxable-income base (same shape as SC's/DE's
modules) -- this is not a SourcedFigure, it's simply never read.

Unlike SC's age-65 and DE's age-60 exclusion, this module defines **no**
age-based exclusion `SourcedFigure`. North Carolina has no general age-based
retirement-income exclusion at all. Its real-world analogue -- the Bailey
settlement (Bailey v. State of North Carolina, 1998; N.C. Gen. Stat.
§105-134.6 history) -- instead exempts retirement benefits from qualifying
government defined-benefit plans, but *only* for income identified by its
source (which pension plan it came from) and whether the retiree was
vested as of August 12, 1989. Approximating Bailey with an age threshold
(reusing SC's/DE's shape) was deliberately rejected: it would be actively
wrong in both directions (a 70-year-old NC retiree living on a private
401(k) owes full NC tax; a 55-year-old NC retiree drawing a pre-1989-vested
state pension owes none) -- see 024-nc-state-tax spec.md Assumptions /
research.md §3 for the full reasoning.

024-nc-state-tax shipped this module taxing 100% of `ordinary_income`,
honestly omitting Bailey rather than silently mismodeling it with an age
proxy, because `IncomeComponents` then carried no income-source breakdown.
027-nc-bailey-exclusion closes that gap: `IncomeComponents.
government_pension_income` (populated by `comparison/projection.py` from
each household member's `IncomeStream.bailey_qualifying`-flagged streams --
a household attestation, not something this module infers or verifies) is
now excluded from the taxable base before `apply_progressive_brackets()`
runs, in full (no partial exclusion, no phase-out) -- see
`compute_tax()` below. This is still not a `SourcedFigure`: Bailey is a
categorical, 100%-or-nothing legal exemption with no rate, threshold, or
dollar amount to schedule by tax year -- the same reason NC's
never-taxes-Social-Security fact (above) isn't one either. The citation
(N.C. Gen. Stat. §105-134.6 history; Bailey v. State of North Carolina,
1998) lives here, in this docstring and in test_state_nc.py, rather than in
a `SourcedFigure.citation` field, honestly reflecting that shape (research.md §4).
The separate, newer post-2021 NC military-retirement exemption
(S.L. 2021-180, no 1989 vesting cutoff) remains unmodeled -- a different
mechanism, out of scope for this feature too (027-nc-bailey-exclusion
spec.md Assumptions).

The flat-rate figure below is a real, confirmed figure, not a placeholder:
4.25% for tax year 2025 and 3.99% for tax year 2026 onward are both
legislated (N.C. Gen. Stat. §105-153.7, as amended by Session Law
2023-134) and were checked against NCDOR's own "Tax Rate Schedules" page
during 024-nc-state-tax's research -- shipped `verified=True`, unlike
SC's/DE's inherited unverified placeholders. NCDOR notes that further,
revenue-trigger-conditioned rate cuts may apply starting tax year 2027, but
those are not yet fixed, legislated numbers, so (matching every other
module's "hold the last documented figure flat" convention -- sc.py, de.py,
tax/federal.py, mechanics/rmd.py) the 3.99% rate is held flat through the
rest of the documented horizon rather than fabricating a further step.
"""

from __future__ import annotations

from datetime import date

from ..bracket_math import apply_progressive_brackets
from ..models import BracketRow, FilingStatus, IncomeComponents, SourcedFigure, StateTaxResult

# rp-5dn: matches every other module's _DOCUMENTED_YEARS convention
# (tax/federal.py, sc.py, de.py, mechanics/rmd.py, ...) -- covers any
# realistic plan horizon so a multi-year projection never hits
# UnsupportedTaxYearError.
_DOCUMENTED_YEARS = range(2020, 2075)

_2025_BRACKETS = (BracketRow(rate=0.0425, income_up_to=None),)
_2026_BRACKETS = (BracketRow(rate=0.0399, income_up_to=None),)

_NC_FLAT_RATE = SourcedFigure(
    name="nc_flat_rate",
    schedule={
        # Before 2026: the legislated 2025 rate. From 2026 on: the
        # legislated 2026 rate, held flat for the rest of the horizon --
        # the same "one step, then flat" shape sc.py's own 2026->2027
        # step (and rmd.py's 73->75 step) uses.
        **{year: _2025_BRACKETS for year in range(_DOCUMENTED_YEARS.start, 2026)},
        **{year: _2026_BRACKETS for year in range(2026, _DOCUMENTED_YEARS.stop)},
    },
    citation=(
        "N.C. Gen. Stat. §105-153.7, as amended by S.L. 2023-134; "
        "NCDOR Tax Rate Schedules (https://www.ncdor.gov/taxes-forms/"
        "individual-income-tax/tax-rate-schedules)"
    ),
    last_verified=date(2026, 9, 3),
    verified=True,
)


def compute_tax(
    income: IncomeComponents,
    filer_ages: list[int],
    filing_status: FilingStatus,
    tax_year: int,
) -> StateTaxResult:
    """North Carolina's compute_tax() — see
    specs/002-tax-calculation-engine/contracts/tax-api.md for the shape
    every state module conforms to (FR-005). `filer_ages` and
    `filing_status` are accepted (contract-required) but unused: NC's flat
    rate depends on neither age nor filing status, mirroring fl.py's own
    "accepts but ignores every parameter it doesn't need" precedent.

    027-nc-bailey-exclusion: `income.government_pension_income` (a
    household-attested subset of `income.ordinary_income` -- see this
    module's docstring) is excluded from the taxable base in full before
    the flat rate applies, floored at $0.0 like every other floor in this
    module (never negative)."""
    brackets = _NC_FLAT_RATE.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    figures_used = [_NC_FLAT_RATE.usage_for_year(tax_year)]

    taxable_income = max(0.0, income.ordinary_income - income.government_pension_income)

    return StateTaxResult(
        state="NC",
        state_tax_owed=apply_progressive_brackets(taxable_income, brackets),
        figures_used=figures_used,
    )
