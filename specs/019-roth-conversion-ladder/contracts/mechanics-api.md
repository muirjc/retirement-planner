# Contract: `retirement_planner.mechanics` public API (addendum to `003`, `010`, `012`)

Adds one new sibling module (`roth_conversion_ladder.py`) and its two new types. Every existing
`mechanics` operation and type — including `compute_roth_conversion()`, `fill_to_bracket_ceiling()`,
`fixed_dollar_amount()`, and `compute_withdrawal_plan()` — is **unchanged in signature and
behavior**.

## New data types (`models`)

```python
@dataclass
class RothConversionLot:
    conversion_tax_year: int
    balance: float


@dataclass
class RothLadderConsumptionResult:
    updated_lots: list[RothConversionLot]
    unseasoned_amount_flagged: float
    figures_used: list[FigureUsage] = field(default_factory=list)
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## New figure (`roth_conversion_ladder`)

```python
ROTH_CONVERSION_SEASONING_YEARS: SourcedFigure[int] = SourcedFigure(
    name="roth_conversion_seasoning_years",
    schedule={year: 5 for year in _DOCUMENTED_YEARS},
    citation="26 U.S.C. §408A(d)(3)(F); Treas. Reg. §1.408A-6, Q&A-5",
    last_verified=<cross-checked at implementation time>,
    verified=True,
)
```

## New operation (`roth_conversion_ladder`)

```python
# retirement_planner.mechanics.roth_conversion_ladder:

def compute_roth_ladder_consumption(
    lots: list[RothConversionLot],
    non_lot_roth_balance: float,
    roth_draw_amount: float,
    tax_year: int,
    age_condition_active: bool,
) -> RothLadderConsumptionResult:
    """Attributes roth_draw_amount across non_lot_roth_balance first (no
    limit beyond what's available there, never flagged), then across
    `lots` in order from the oldest conversion_tax_year to the newest,
    never drawing from a newer lot while an older one still has a
    positive balance (FR-004). A lot is "seasoned" once
    tax_year - lot.conversion_tax_year >=
    ROTH_CONVERSION_SEASONING_YEARS.value_for_year(tax_year) (FR-003).
    unseasoned_amount_flagged is the sum of every dollar drawn from a
    not-yet-seasoned lot this call, but ONLY when age_condition_active is
    True (FR-005/FR-006) -- otherwise 0.0 even if an unseasoned lot was
    drawn from. Pure: never mutates `lots` itself; updated_lots is a
    fresh list with each consumed lot's own balance reduced (research.md
    Decision 5). figures_used carries ROTH_CONVERSION_SEASONING_YEARS's
    usage whenever roth_draw_amount > non_lot_roth_balance (a lot's
    seasoning was actually consulted), regardless of the resulting flag
    (research.md Decision 4). Raises UnsupportedTaxYearError if
    ROTH_CONVERSION_SEASONING_YEARS has no schedule entry for tax_year.
    Does not itself validate that roth_draw_amount does not exceed
    non_lot_roth_balance plus the sum of every lot's balance -- callers
    are expected to pass a draw amount already bounded by
    compute_withdrawal_plan()'s own accounting."""
```

`retirement_planner.mechanics.__init__` re-exports `compute_roth_ladder_consumption`,
`RothConversionLot`, `RothLadderConsumptionResult`, and `ROTH_CONVERSION_SEASONING_YEARS` alongside
the module's existing exports.

## Consumption expectations for downstream features

- `retirement_planner.comparison.run_plan_projection()` is the only caller — see
  [comparison-api.md](./comparison-api.md) addendum for exactly where and how it calls this
  function each plan year, and how it maintains its own local `roth_conversion_lots` list (never a
  parameter to `run_plan_projection()` itself — research.md Decision 2).
- `retirement_planner.simulation` requires no direct change: every simulation path already calls
  `comparison.run_plan_projection()` internally, and this feature's lot-tracking state is entirely
  local to that one call (never shared, never threaded), so every Monte Carlo path gets this
  feature's behavior transitively with zero simulation-package changes.
- `services/bff` and `apps/streamlit_ui` require no changes at all — this feature introduces no new
  scenario-configurable input (plan.md Summary); `unseasoned_roth_withdrawal` is a projection
  *output* field only (see comparison-api.md addendum).
