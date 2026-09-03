"""Shared tax data model.

These types are the locked public shape described in
specs/002-tax-calculation-engine/contracts/tax-api.md ("Data types" section)
and specs/002-tax-calculation-engine/data-model.md. This module has no
dependency on retirement_planner.scenario — this feature is a pure
calculator that takes income components directly (see spec.md Assumptions).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Generic, Literal, TypeVar

FilingStatus = Literal["single", "married_filing_jointly"]

T = TypeVar("T")


class UnsupportedTaxYearError(Exception):
    """Raised when a SourcedFigure has no schedule entry for the requested
    tax year (FR-016). Never falls back to the nearest documented year or
    otherwise extrapolates — see data-model.md § SourcedFigure.
    """

    def __init__(self, figure_name: str, requested_year: int, available_years: list[int]) -> None:
        self.figure_name = figure_name
        self.requested_year = requested_year
        self.available_years = sorted(available_years)
        super().__init__(
            f"{figure_name}: no figure documented for tax year {requested_year} "
            f"(documented years: {self.available_years})"
        )

    def __reduce__(self):
        """Makes this exception picklable with its actual __init__ signature
        (figure_name, requested_year, available_years) rather than the
        single formatted message BaseException.__reduce__ would otherwise
        try to replay -- needed for this exception to survive crossing a
        process boundary, e.g. when raised inside a
        005-simulation-engine ProcessPoolExecutor worker
        (specs/005-simulation-engine/research.md §7)."""
        return (self.__class__, (self.figure_name, self.requested_year, self.available_years))


@dataclass
class IncomeComponents:
    """Household-level income for one tax year. data-model.md § IncomeComponents.

    No sign/range validation is performed here — this feature is a pure
    calculator, not a validator (see spec.md Assumptions).
    """

    ordinary_income: float
    social_security_gross_benefit: float
    government_pension_income: float = 0.0
    """027-nc-bailey-exclusion: the subset (never an addition) of
    ordinary_income sourced from IncomeStreams the household has attested
    are source-and-vesting-date-qualifying government/military retirement
    income -- today, only tax.state.nc.compute_tax() reads this field, to
    apply North Carolina's Bailey settlement exclusion. Defaults to 0.0,
    which reproduces every existing state module's original behavior
    exactly (max(0.0, ordinary_income - 0.0) == ordinary_income) -- SC,
    DE, and FL never read this field at all. Federal tax, FICA, IRMAA, and
    NIIT all continue to consume ordinary_income (which still includes
    this income in full) unchanged -- this is a NC-state-only side
    channel, not a reduction to the household's real income (data-model.md
    § IncomeComponents)."""


@dataclass
class StandardDeductionAmounts:
    """One filing status's standard deduction figure for a tax year:
    the base amount plus the additional amount added *per filer* who has
    reached age 65 (26 U.S.C. §63(c)(2), (f)) -- rp-7me. Grouped as one
    dataclass (rather than two separate SourcedFigures) because both
    numbers come from the same citable publication for a given filing
    status, matching SourcedFigure's "one figure = one citation"
    convention (see SourcedFigure docstring)."""

    base: float
    additional_per_filer_65_plus: float


@dataclass
class BracketRow:
    """One row of a progressive bracket table. data-model.md § BracketTable."""

    rate: float
    income_up_to: float | None  # None = top bracket, "and above"


BracketTable = tuple[BracketRow, ...]
"""An ordered list of BracketRows, lowest bracket first."""


@dataclass
class BracketContribution:
    """One bracket's contribution to a progressive-tax computation (rp-bm8.3):
    retains what apply_progressive_brackets_detailed() (bracket_math.py)
    already computes internally -- a dollar-for-dollar breakdown of how a
    taxable-income figure became a tax-owed figure, previously discarded
    after being summed. Never changes the computed total; a pure retention
    of an already-verified computation's own intermediate values."""

    rate: float
    income_in_bracket: float
    tax_in_bracket: float


@dataclass
class FigureUsage:
    """A snapshot of one SourcedFigure's citation metadata for the year
    actually used in a computation — one entry in a result's provenance
    trail (FR-010, FR-011). data-model.md § FigureUsage.
    """

    name: str
    citation: str
    last_verified: date
    verified: bool


@dataclass
class SourcedFigure(Generic[T]):
    """The auditability primitive (FR-009). One SourcedFigure corresponds to
    one real-world citation — a state's whole bracket table for a year is
    one citable publication, not one citation per row. data-model.md §
    SourcedFigure.
    """

    name: str
    schedule: dict[int, T]
    citation: str
    last_verified: date
    verified: bool

    def value_for_year(self, tax_year: int) -> T:
        """Returns schedule[tax_year]. Raises UnsupportedTaxYearError if
        tax_year is not a key in schedule — never falls back or interpolates.
        """
        if tax_year not in self.schedule:
            raise UnsupportedTaxYearError(
                figure_name=self.name,
                requested_year=tax_year,
                available_years=list(self.schedule.keys()),
            )
        return self.schedule[tax_year]

    def usage_for_year(self, tax_year: int) -> FigureUsage:
        """Validates tax_year is documented (raises UnsupportedTaxYearError
        if not) and returns the FigureUsage snapshot for it. A convenience
        so every caller doesn't hand-build a FigureUsage at each call site.
        """
        self.value_for_year(tax_year)
        return FigureUsage(
            name=self.name,
            citation=self.citation,
            last_verified=self.last_verified,
            verified=self.verified,
        )


@dataclass
class FederalTaxResult:
    """data-model.md § FederalTaxResult."""

    federal_tax_owed: float
    taxable_social_security: float
    figures_used: list[FigureUsage]
    taxable_income: float = 0.0
    """rp-bm8.3: ordinary_income + taxable_social_security - standard_deduction_used,
    floored at $0 -- compute_federal_tax()'s own already-computed local
    variable, simply no longer discarded after producing federal_tax_owed.
    Defaults to 0.0 so the one existing direct construction site
    (tests/unit/comparison/test_projection.py) is unaffected."""
    standard_deduction_used: float = 0.0
    """rp-bm8.3: the actual dollar amount subtracted this year (base +
    age-65 addition per qualifying filer) -- same retention discipline as
    taxable_income above."""
    bracket_breakdown: list[BracketContribution] = field(default_factory=list)
    """rp-bm8.3: apply_progressive_brackets_detailed()'s own per-row
    output for this computation -- sums to federal_tax_owed exactly."""


@dataclass
class StateTaxResult:
    """data-model.md § StateTaxResult."""

    state: str
    state_tax_owed: float
    figures_used: list[FigureUsage]
    taxable_income: float = 0.0
    """rp-bm8.3: same retention discipline as FederalTaxResult.taxable_income
    -- each state module's own already-computed local, no longer discarded.
    0.0 for FL (no state income tax, no taxable base)."""
    exclusion_applied: float = 0.0
    """rp-bm8.3: the total dollar amount excluded from ordinary_income before
    bracket math -- SC/DE's age-65/60 exclusion, NC's Bailey exclusion
    (income.government_pension_income), or 0.0 (FL, or no exclusion
    applicable this year)."""
    bracket_breakdown: list[BracketContribution] = field(default_factory=list)
    """rp-bm8.3: same as FederalTaxResult.bracket_breakdown. Empty for FL
    (no bracket math runs at all)."""


@dataclass
class IrmaaTierRow:
    """One IRMAA premium-surcharge tier. 010-advanced-tax-benefits
    data-model.md § Tax result extensions. `magi_threshold` is the
    inclusive lower bound of this tier (Edge Cases: at-or-above
    triggers it, never strictly-above)."""

    magi_threshold: float
    annual_surcharge_per_person: float


IrmaaTierTable = tuple[IrmaaTierRow, ...]
"""Ascending by magi_threshold. A MAGI below every row's threshold means
$0 -- there is no explicit "no surcharge" row."""


@dataclass
class IrmaaResult:
    """010-advanced-tax-benefits data-model.md § Tax result extensions."""

    magi: float
    income_basis: Literal["two_year_lookback", "current_year_proxy"]
    tier_crossed: float | None
    enrolled_member_count: int
    surcharge_owed: float
    figures_used: list[FigureUsage]


@dataclass
class NiitResult:
    """010-advanced-tax-benefits data-model.md § Tax result extensions."""

    magi: float
    investment_income: float
    threshold_exceeded: bool
    surtax_owed: float
    figures_used: list[FigureUsage]


@dataclass
class EarlyWithdrawalPenaltyResult:
    """020-early-withdrawal-penalty data-model.md § EarlyWithdrawalPenaltyResult.
    One plan year's 10% early-withdrawal penalty (26 U.S.C. §72(t)(1)),
    applied to a combined taxable early-distribution base the caller
    (comparison.run_plan_projection()) has already computed -- this
    module has no opinion about how that base was derived, only how the
    flat rate applies to it once given (mirrors NiitResult's own
    caller-computed-base precedent)."""

    taxable_early_distribution_base: float
    penalty_owed: float
    figures_used: list[FigureUsage]


@dataclass
class FicaTaxResult:
    """022-fica-payroll-tax (rp-elp) data-model.md § FicaTaxResult. One
    plan year's employee-side FICA payroll tax on earned_income-type
    income streams (021-pension-annuity-income) -- never pension/annuity
    amounts, which are not wages. Mirrors EarlyWithdrawalPenaltyResult's
    own shape (a derived amount plus figures_used), extended per-member
    for the two per-worker components."""

    member_oasdi_tax: dict[str, float]
    """person_name -> that member's own 6.2% Social Security (OASDI) tax,
    computed on that member's own combined earned_income amount for the
    year, capped at OASDI_WAGE_BASE. 0.0 for a member with no earned
    income this year, never omitted."""
    member_medicare_tax: dict[str, float]
    """person_name -> that member's own 1.45% regular Medicare (HI) tax,
    uncapped."""
    additional_medicare_tax: float
    """0.9% of the household's combined earned income (summed across
    every member) that exceeds the filing-status threshold -- computed
    once per household, never per member (research.md §3)."""
    total_fica_tax: float
    """sum(member_oasdi_tax.values()) + sum(member_medicare_tax.values())
    + additional_medicare_tax."""
    figures_used: list[FigureUsage]
    """Always carries all five figures' usages for the tax year, even
    when total_fica_tax == 0.0 (mirrors compute_niit()'s/
    compute_early_withdrawal_penalty()'s own "always cited" precedent)."""
