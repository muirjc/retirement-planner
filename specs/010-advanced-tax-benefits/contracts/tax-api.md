# Contract: `retirement_planner.tax` public API (addendum to `002`)

Extends `specs/002-tax-calculation-engine/contracts/tax-api.md` with the two new modules this feature adds (`irmaa`, `niit`). Everything else in that contract is unchanged — `compute_federal_tax()`, `compute_state_tax()`, `compute_taxable_social_security()`, and every existing type keep their exact locked shape.

## New data types (`models`)

```python
@dataclass
class IrmaaTierRow:
    magi_threshold: float
    annual_surcharge_per_person: float

IrmaaTierTable = tuple[IrmaaTierRow, ...]

@dataclass
class IrmaaResult:
    magi: float
    income_basis: Literal["two_year_lookback", "current_year_proxy"]
    tier_crossed: float | None
    enrolled_member_count: int
    surcharge_owed: float
    figures_used: list[FigureUsage]

@dataclass
class NiitResult:
    magi: float
    investment_income: float
    threshold_exceeded: bool
    surtax_owed: float
    figures_used: list[FigureUsage]
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## New operations (`irmaa`, `niit`)

```python
# retirement_planner.tax.irmaa:

def compute_irmaa_surcharge(
    magi: float,
    income_basis: Literal["two_year_lookback", "current_year_proxy"],
    filing_status: FilingStatus,
    tax_year: int,
    enrolled_member_count: int,
) -> IrmaaResult:
    """Looks up tax_year's IRMAA tier table for filing_status, finds the
    tier magi falls into (inclusive lower bound -- research.md §3, data-
    model.md Validation rules), and returns the resulting surcharge as
    annual_surcharge_per_person * enrolled_member_count (FR-001-FR-004).
    Returns tier_crossed=None and surcharge_owed=0.0 when magi is below
    every documented tier and when enrolled_member_count is 0 (FR-004) --
    never raises for "no surcharge applies," only for an undocumented
    tax_year. Raises UnsupportedTaxYearError if the tier table has no
    entry for tax_year."""


# retirement_planner.tax.niit:

def compute_niit(
    magi: float,
    investment_income: float,
    filing_status: FilingStatus,
    tax_year: int,
) -> NiitResult:
    """Looks up tax_year's NIIT threshold and rate for filing_status,
    and applies the surtax to min(investment_income, magi - threshold)
    when magi exceeds the threshold (FR-005-FR-007, data-model.md
    Validation rules) -- never to the full investment_income once any
    threshold is crossed. Returns threshold_exceeded=False and
    surtax_owed=0.0 when magi does not exceed the threshold. Raises
    UnsupportedTaxYearError if the threshold or rate figure has no entry
    for tax_year."""
```

## Consumption expectations for downstream features

- `004-strategy-comparison-layer`'s `run_plan_projection()` is the only caller expected to invoke these two functions — it already assembles `magi` (via research.md §2's `ordinary_income + taxable_social_security` proxy) and `income_basis`/two-year look-back data from its own accumulated `years` list (research.md §3); no other feature should call these directly against ad hoc income figures.
- Every figure returned in `figures_used` MUST propagate through `PlanYearProjection.figures_used` and onward into `unverified_figure_names`, the same union pattern `002`'s own `federal_tax`/`state_tax` figures already follow — this feature introduces no new propagation mechanism.
