# Contract: `retirement_planner.tax` public API (addendum to `002`, `010`)

Adds one new sibling module (`early_withdrawal_penalty.py`) and its result type. Every existing
`tax` operation and type — including `compute_niit()`, `compute_irmaa_surcharge()`,
`compute_federal_tax()`, `compute_state_tax()`, `compute_taxable_social_security()` — is
**unchanged in signature and behavior**.

## New data type (`models`)

```python
@dataclass
class EarlyWithdrawalPenaltyResult:
    taxable_early_distribution_base: float
    penalty_owed: float
    figures_used: list[FigureUsage] = field(default_factory=list)
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## New figure (`early_withdrawal_penalty`)

```python
EARLY_WITHDRAWAL_PENALTY_RATE: SourcedFigure[float] = SourcedFigure(
    name="early_withdrawal_penalty_rate",
    schedule={year: 0.10 for year in _DOCUMENTED_YEARS},
    citation="26 U.S.C. §72(t)(1) (10% additional tax); §72(t)(2)(A)(i) (age 59½ exception)",
    last_verified=<cross-checked at implementation time>,
    verified=True,
)
```

## New operation (`early_withdrawal_penalty`)

```python
# retirement_planner.tax.early_withdrawal_penalty:

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
    no schedule entry for tax_year."""
```

`retirement_planner.tax.__init__` re-exports `compute_early_withdrawal_penalty`,
`EarlyWithdrawalPenaltyResult`, and `EARLY_WITHDRAWAL_PENALTY_RATE` alongside the module's existing
exports.

## Consumption expectations for downstream features

- `retirement_planner.comparison.run_plan_projection()` is the only caller — see
  [comparison-api.md](./comparison-api.md) addendum for exactly how it computes
  `taxable_early_distribution_base` (per-member Traditional attribution via
  `traditional_ownership_shares`, plus `019`'s own `unseasoned_roth_withdrawal`) before calling this
  function.
- `retirement_planner.simulation` requires no direct change: every simulation path already calls
  `comparison.run_plan_projection()` internally, so every Monte Carlo path gets this feature's
  behavior transitively.
- Every figure returned in `figures_used` propagates through `PlanYearProjection.figures_used`
  exactly like every other cited figure already does — no new propagation mechanism.
