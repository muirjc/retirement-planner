"""Employee-side FICA payroll tax (022-fica-payroll-tax, rp-elp).

A flat-rate-plus-cap surtax on a caller-computed base -- mirrors
early_withdrawal_penalty.py's own shape exactly (a tax-liability concept,
reported on payroll/Form 8959, not an account-mechanics concept), extended
per-member for the two per-worker components (OASDI's wage-base cap is
inherently per-worker) plus one household-level component (the Additional
Medicare Tax threshold applies to a married-filing-jointly household's
*combined* wages, not each spouse individually -- 26 U.S.C. §3101(b)(2),
reconciled on IRS Form 8959).

What counts as "earned income" here -- which income streams are wages at
all -- is entirely the caller's own determination
(comparison/projection.py's _member_earned_income_amounts(), which sums
only stream_type == "earned_income" amounts, never pension/annuity); this
module has no opinion about that, only how the statutory rates apply to
whatever per-member totals it's given (research.md Decision 2, mirroring
compute_early_withdrawal_penalty()'s own "caller determines the base"
precedent).

OASDI_WAGE_BASE is pinned to its 2026 SSA-published value and held flat
across every documented year, mirroring tax/federal.py's own "real
dollars, no further indexing engine" convention -- the wage base is
nominal-dollar and genuinely grows year to year via national average wage
indexing (a different, faster-growing series than CPI), but this engine
has no wage-growth projection any more than it has a general inflation
one outside 021-pension-annuity-income's own INFLATION_RATE (which is
CPI-based and would be the WRONG figure to reuse here -- research.md
Decision 4). ADDITIONAL_MEDICARE_TAX_THRESHOLDS, by contrast, are
genuinely fixed by statute since the tax took effect in 2013, not merely
held flat by this engine's own convention.

Deliberately out of scope (spec.md Assumptions, disclosed in docs/BRD.md,
not silently absorbed): self-employment (SECA) tax -- this models only
the employee-side W-2 rates the originating issue names explicitly, not
the 15.3% combined self-employment rate a 1099/sole-proprietor household
member would actually owe.

See specs/022-fica-payroll-tax/contracts/tax-api.md for the locked public
signature of compute_fica_tax().
"""

from __future__ import annotations

from datetime import date

from .models import FicaTaxResult, FigureUsage, FilingStatus, SourcedFigure

_DOCUMENTED_YEARS = range(2020, 2075)

_SSA_COLA_FACT_SHEET_CITATION = (
    "SSA, \"2026 Cost-of-Living Adjustment (COLA) Fact Sheet\" "
    "(https://www.ssa.gov/news/en/cola/factsheets/2026.html): OASDI rate 6.2%, HI (Medicare) "
    "rate 1.45% (uncapped), 2026 taxable maximum (wage base) $184,500; cross-checked against "
    "SSA's own Contribution and Benefit Base page (https://www.ssa.gov/oact/cola/cbb.html)"
)

OASDI_RATE: SourcedFigure[float] = SourcedFigure(
    name="fica_oasdi_rate",
    schedule={year: 0.062 for year in _DOCUMENTED_YEARS},
    citation=_SSA_COLA_FACT_SHEET_CITATION,
    last_verified=date(2026, 9, 2),
    verified=True,
)

OASDI_WAGE_BASE: SourcedFigure[float] = SourcedFigure(
    name="fica_oasdi_wage_base",
    schedule={year: 184_500.0 for year in _DOCUMENTED_YEARS},
    citation=_SSA_COLA_FACT_SHEET_CITATION + " -- held flat across every documented year (module docstring)",
    last_verified=date(2026, 9, 2),
    verified=True,
)

MEDICARE_RATE: SourcedFigure[float] = SourcedFigure(
    name="fica_medicare_rate",
    schedule={year: 0.0145 for year in _DOCUMENTED_YEARS},
    citation=_SSA_COLA_FACT_SHEET_CITATION,
    last_verified=date(2026, 9, 2),
    verified=True,
)

_ADDITIONAL_MEDICARE_TAX_CITATION = (
    "26 U.S.C. §3101(b)(2) (added by the Affordable Care Act, effective 2013, fixed dollar "
    "thresholds -- not inflation-indexed); IRS, \"Questions and Answers for the Additional "
    "Medicare Tax\" (https://www.irs.gov/businesses/small-businesses-self-employed/"
    "questions-and-answers-for-the-additional-medicare-tax)"
)

ADDITIONAL_MEDICARE_TAX_RATE: SourcedFigure[float] = SourcedFigure(
    name="additional_medicare_tax_rate",
    schedule={year: 0.009 for year in _DOCUMENTED_YEARS},
    citation=_ADDITIONAL_MEDICARE_TAX_CITATION,
    last_verified=date(2026, 9, 2),
    verified=True,
)

ADDITIONAL_MEDICARE_TAX_THRESHOLDS: dict[FilingStatus, SourcedFigure[float]] = {
    "single": SourcedFigure(
        name="additional_medicare_tax_threshold_single",
        schedule={year: 200_000.0 for year in _DOCUMENTED_YEARS},
        citation=_ADDITIONAL_MEDICARE_TAX_CITATION,
        last_verified=date(2026, 9, 2),
        verified=True,
    ),
    "married_filing_jointly": SourcedFigure(
        name="additional_medicare_tax_threshold_mfj",
        schedule={year: 250_000.0 for year in _DOCUMENTED_YEARS},
        citation=_ADDITIONAL_MEDICARE_TAX_CITATION,
        last_verified=date(2026, 9, 2),
        verified=True,
    ),
}
"""dict[FilingStatus, SourcedFigure[float]] -- mirrors tax/federal.py's own
_FEDERAL_BRACKETS/_STANDARD_DEDUCTIONS shape (one SourcedFigure per filing
status, not one figure whose value is itself filing-status-keyed)."""


def compute_fica_tax(
    member_earned_income: dict[str, float],
    filing_status: FilingStatus,
    tax_year: int,
) -> FicaTaxResult:
    """OASDI and regular Medicare are computed per member (each worker's
    own wage-base cap applies to their own earnings only); the Additional
    Medicare Tax is computed once, against the household's *combined*
    earned income (research.md Decision 3) -- a married-filing-jointly
    household where each spouse earns under the threshold individually
    can still owe it if their combined earnings exceed the MFJ threshold
    (spec.md Edge Cases, Acceptance Scenario US3.2).

    member_earned_income is caller-computed and opaque to this function --
    it does not itself determine which income counts as "earned" (module
    docstring). figures_used always contains all five figures' usages for
    tax_year, even when every amount is 0.0.

    Raises UnsupportedTaxYearError if any figure has no schedule entry for
    tax_year.
    """
    oasdi_rate = OASDI_RATE.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    wage_base = OASDI_WAGE_BASE.value_for_year(tax_year)
    medicare_rate = MEDICARE_RATE.value_for_year(tax_year)
    additional_rate = ADDITIONAL_MEDICARE_TAX_RATE.value_for_year(tax_year)
    threshold = ADDITIONAL_MEDICARE_TAX_THRESHOLDS[filing_status].value_for_year(tax_year)

    member_oasdi_tax = {
        person_name: min(earned_income, wage_base) * oasdi_rate
        for person_name, earned_income in member_earned_income.items()
    }
    member_medicare_tax = {
        person_name: earned_income * medicare_rate for person_name, earned_income in member_earned_income.items()
    }
    combined_earned_income = sum(member_earned_income.values())
    additional_medicare_tax = max(0.0, combined_earned_income - threshold) * additional_rate

    total_fica_tax = sum(member_oasdi_tax.values()) + sum(member_medicare_tax.values()) + additional_medicare_tax

    figures_used: list[FigureUsage] = [
        OASDI_RATE.usage_for_year(tax_year),
        OASDI_WAGE_BASE.usage_for_year(tax_year),
        MEDICARE_RATE.usage_for_year(tax_year),
        ADDITIONAL_MEDICARE_TAX_RATE.usage_for_year(tax_year),
        ADDITIONAL_MEDICARE_TAX_THRESHOLDS[filing_status].usage_for_year(tax_year),
    ]

    return FicaTaxResult(
        member_oasdi_tax=member_oasdi_tax,
        member_medicare_tax=member_medicare_tax,
        additional_medicare_tax=additional_medicare_tax,
        total_fica_tax=total_fica_tax,
        figures_used=figures_used,
    )
