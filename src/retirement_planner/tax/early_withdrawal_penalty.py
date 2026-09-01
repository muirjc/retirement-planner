"""Early-withdrawal penalty (10%, pre-59.5) calculation
(020-early-withdrawal-penalty, rp-8z0).

A flat-rate additional tax applied to a household's combined taxable
early-distribution amount for a plan year -- mirrors tax/niit.py's own
shape exactly (a flat-rate surtax on a caller-computed base), since this
is a tax-liability concept (reported on IRS Form 5329, added to the
taxpayer's total tax), not an account-mechanics concept.

The 10% rate is fixed directly by 26 U.S.C. §72(t)(1) -- not inflation-
indexed, so the same rate applies to every documented year -- and has
been cross-checked against that statute's text directly
(020-early-withdrawal-penalty, implementation-time verification).
`verified=True` reflects that.

What counts as the "taxable early-distribution base" here -- which
dollars are early, whose age matters, and which statutory exceptions
apply -- is entirely this feature's own caller-computed determination
(research.md Decision 2: comparison/projection.py, using the engine's
existing traditional_ownership_shares per-member attribution and
019-roth-conversion-ladder's own unseasoned_roth_withdrawal flag); this
module has no opinion about how that base was derived, only how the flat
rate applies to it once given.

Deliberately out of scope (spec.md Assumptions, disclosed in docs/BRD.md,
not silently absorbed): 72(t)/SEPP substantially-equal-periodic-payment
modeling, and every real IRC §72(t)(2) exception beyond age 59½
(disability, medical expenses, higher education, first-time homebuyer,
health insurance while unemployed, IRS levy, qualified reservist
distributions, birth/adoption, terminal illness, disaster relief, and
others).

See specs/020-early-withdrawal-penalty/contracts/tax-api.md for the
locked public signature of compute_early_withdrawal_penalty().
"""

from __future__ import annotations

from datetime import date

from .models import EarlyWithdrawalPenaltyResult, FigureUsage, SourcedFigure

_DOCUMENTED_YEARS = range(2020, 2075)

EARLY_WITHDRAWAL_PENALTY_RATE: SourcedFigure[float] = SourcedFigure(
    name="early_withdrawal_penalty_rate",
    schedule={year: 0.10 for year in _DOCUMENTED_YEARS},
    citation=(
        "26 U.S.C. §72(t)(1) (10% additional tax on early distributions from a qualified "
        "retirement plan); §72(t)(2)(A)(i) (exception once the distributee has attained age 59½)"
    ),
    last_verified=date(2026, 9, 1),
    verified=True,
)


def compute_early_withdrawal_penalty(
    taxable_early_distribution_base: float,
    tax_year: int,
) -> EarlyWithdrawalPenaltyResult:
    """Returns penalty_owed = taxable_early_distribution_base *
    EARLY_WITHDRAWAL_PENALTY_RATE.value_for_year(tax_year) (FR-006).
    taxable_early_distribution_base is caller-computed and opaque to this
    function -- it does not itself determine which dollars are early,
    whose age matters, or whether an exception applies (research.md
    Decision 2); it only applies the flat rate to whatever base it's
    given. figures_used always includes EARLY_WITHDRAWAL_PENALTY_RATE's
    usage, even when taxable_early_distribution_base is 0.0 (research.md
    Decision 5, mirroring compute_niit()'s own "always cited" precedent).
    Raises UnsupportedTaxYearError if EARLY_WITHDRAWAL_PENALTY_RATE has
    no schedule entry for tax_year.
    """
    rate = EARLY_WITHDRAWAL_PENALTY_RATE.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    figures_used: list[FigureUsage] = [EARLY_WITHDRAWAL_PENALTY_RATE.usage_for_year(tax_year)]

    return EarlyWithdrawalPenaltyResult(
        taxable_early_distribution_base=taxable_early_distribution_base,
        penalty_owed=taxable_early_distribution_base * rate,
        figures_used=figures_used,
    )
