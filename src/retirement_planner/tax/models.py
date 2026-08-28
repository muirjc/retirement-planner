"""Shared tax data model.

These types are the locked public shape described in
specs/002-tax-calculation-engine/contracts/tax-api.md ("Data types" section)
and specs/002-tax-calculation-engine/data-model.md. This module has no
dependency on retirement_planner.scenario — this feature is a pure
calculator that takes income components directly (see spec.md Assumptions).
"""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass
class BracketRow:
    """One row of a progressive bracket table. data-model.md § BracketTable."""

    rate: float
    income_up_to: float | None  # None = top bracket, "and above"


BracketTable = tuple[BracketRow, ...]
"""An ordered list of BracketRows, lowest bracket first."""


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


@dataclass
class StateTaxResult:
    """data-model.md § StateTaxResult."""

    state: str
    state_tax_owed: float
    figures_used: list[FigureUsage]
