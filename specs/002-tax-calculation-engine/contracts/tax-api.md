# Contract: `retirement_planner.tax` public API

This is a library, not a network service — the "contract" is the public Python interface this feature exposes for later features (account mechanics, simulation engine, reporting) to import and build on. Anything not listed here is an internal implementation detail; anything listed here is what downstream features should code against.

Module: `retirement_planner.tax` (re-exports from `models`, `social_security`, `federal`, `state` — see [plan.md](../plan.md) Project Structure).

## Data types (`models`)

```python
FilingStatus = Literal["single", "married_filing_jointly"]

@dataclass
class IncomeComponents:
    ordinary_income: float
    social_security_gross_benefit: float

# FilerAges: list[int] — length 1 for "single", 2 for "married_filing_jointly"

@dataclass
class StandardDeductionAmounts:
    base: float
    additional_per_filer_65_plus: float  # added once per filer_ages entry >= 65

@dataclass
class BracketRow:
    rate: float
    income_up_to: float | None  # None = top bracket, "and above"

BracketTable = tuple[BracketRow, ...]

@dataclass
class SourcedFigure(Generic[T]):
    schedule: dict[int, T]          # tax_year -> value in effect that year
    citation: str
    last_verified: date
    verified: bool

    def value_for_year(self, tax_year: int) -> T:
        """Returns schedule[tax_year]. Raises UnsupportedTaxYearError if
        tax_year is not a key in schedule — never falls back or interpolates."""

@dataclass
class FigureUsage:
    name: str
    citation: str
    last_verified: date
    verified: bool

@dataclass
class FederalTaxResult:
    federal_tax_owed: float
    taxable_social_security: float
    figures_used: list[FigureUsage]

@dataclass
class StateTaxResult:
    state: str
    state_tax_owed: float
    figures_used: list[FigureUsage]

class UnsupportedTaxYearError(Exception):
    def __init__(self, figure_name: str, requested_year: int, available_years: list[int]): ...
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## Operations (`social_security`, `federal`, `state`)

```python
def compute_taxable_social_security(
    income: IncomeComponents,
    filing_status: FilingStatus,
    tax_year: int,
) -> tuple[float, list[FigureUsage]]:
    """Returns (taxable_social_security, figures_used) per the federal
    provisional-income rule (FR-002): 0%, up to 50%, or up to 85% of
    social_security_gross_benefit included in taxable income depending on
    provisional income vs. the tax year's thresholds. Raises
    UnsupportedTaxYearError if the threshold figures have no entry for
    tax_year."""


def compute_federal_tax(
    income: IncomeComponents,
    filer_ages: list[int],
    filing_status: FilingStatus,
    tax_year: int,
) -> FederalTaxResult:
    """Computes federal tax via compute_taxable_social_security() + the
    standard deduction (rp-7me; base amount plus the age-65 addition per
    filer_ages entry >= 65) + genuine progressive bracket math against
    tax_year's federal brackets (FR-001). Raises UnsupportedTaxYearError if
    any figure needed (SS thresholds, federal brackets, or the standard
    deduction) has no entry for tax_year."""


# retirement_planner.tax.state:

STATE_MODULES: dict[str, Callable[[IncomeComponents, list[int], FilingStatus, int], StateTaxResult]]
"""Registry mapping a two-letter state code to that state's compute_tax
function (FR-005). Currently populated: "SC", "DE", "FL" (FR-017).
Adding a new state means adding one module + one registry entry here —
nothing else in this package changes (SC-006)."""


def compute_state_tax(
    state: str,
    income: IncomeComponents,
    filer_ages: list[int],
    filing_status: FilingStatus,
    tax_year: int,
) -> StateTaxResult:
    """Looks up STATE_MODULES[state] and calls it. Raises KeyError (or a
    dedicated UnsupportedStateError — implementation's choice, not locked
    by this contract) if `state` has no registered module. Raises
    UnsupportedTaxYearError if a figure the state's module needs has no
    entry for tax_year."""
```

Every state module registered in `STATE_MODULES` (e.g., `retirement_planner.tax.state.sc.compute_tax`) has the identical signature `(income: IncomeComponents, filer_ages: list[int], filing_status: FilingStatus, tax_year: int) -> StateTaxResult` — this is what "pluggable" (FR-005) means concretely: `compute_state_tax()` never branches on which state it's calling, it only looks the function up and calls it.

## Consumption expectations for downstream features

- A future feature deriving `IncomeComponents` from a `Scenario` (`001`) and its account-withdrawal activity is responsible for excluding Roth withdrawals from `ordinary_income` before calling this engine — this engine does not know which account a dollar came from, only the pre-classified totals.
- `FederalTaxResult.figures_used` and `StateTaxResult.figures_used` are the single place downstream reporting features (§3.6, not yet spec'd) should look to render "needs verification" flags — they should not need to reach into `SourcedFigure` internals or re-derive verification status themselves.
- A caller needing tax years beyond what a figure's `schedule` documents (e.g., a 35-year simulation horizon outliving GA/NC/MS's documented 2028–2029 schedule) must not expect this engine to extrapolate (FR-016) — that caller is responsible for supplying an extended schedule with its own documented assumption, or catching `UnsupportedTaxYearError` and deciding what to do.
- `STATE_MODULES` currently covers `"SC"`, `"DE"`, `"FL"` only (FR-017) — a downstream feature calling `compute_state_tax()` for any other state code should expect a lookup failure, not a silently-wrong result, until that state's module is added as follow-on work.
