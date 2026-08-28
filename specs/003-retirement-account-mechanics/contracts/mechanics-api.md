# Contract: `retirement_planner.mechanics` public API

This is a library, not a network service — the "contract" is the public Python interface this feature exposes for later features (the §3.4 strategy-comparison layer, the §3.5 simulation engine, §3.6 reporting) to import and build on. Anything not listed here is an internal implementation detail; anything listed here is what downstream features should code against.

> **Implementation note (added during `/speckit-implement`)**: two signatures below were corrected from this document's original draft because they could not otherwise produce fields this contract itself documents. `fill_to_bracket_ceiling()`, `fixed_dollar_amount()`, and `compute_roth_conversion()` gained an explicit `roth_balance: float` parameter — `ConversionResult.ending_roth_balance` (data-model.md) is "starting Roth balance + amount_converted," which is uncomputable without it. `compute_plan_year_mechanics()` gained an explicit `rmd_figures_used: list[FigureUsage] | None = None` parameter — `PlanYearMechanicsResult.figures_used` (data-model.md) is documented as the union of the RMD figures used and `conversion.figures_used`, but `rmd_amount` alone (a plain float) carries no figure provenance to union in. Both additions are backward-compatible in spirit (no existing field changed meaning) but do change these three functions' call signatures from the original draft below.

Module: `retirement_planner.mechanics` (re-exports from `models`, `rmd`, `withdrawal_sequencing`, `roth_conversion`, `plan_year` — see [plan.md](../plan.md) Project Structure).

## Data types (`models`)

```python
AccountType = Literal["traditional", "roth", "taxable"]

@dataclass
class AccountBalances:
    traditional: float
    roth: float
    taxable: float

@dataclass
class RmdResult:
    required_amount: float
    table_used: Literal["uniform_lifetime", "joint_life"] | None
    divisor: float | None
    figures_used: list[FigureUsage]   # FigureUsage from retirement_planner.tax.models

@dataclass
class WithdrawalLineItem:
    account_type: AccountType
    amount: float

@dataclass
class WithdrawalPlan:
    rmd_drawn: float
    sequence_withdrawals: list[WithdrawalLineItem]
    ending_balances: AccountBalances
    shortfall: float

@dataclass
class ConversionResult:
    amount_converted: float
    ordinary_income_added: float
    ending_traditional_balance: float
    ending_roth_balance: float
    figures_used: list[FigureUsage]

@dataclass
class PlanYearMechanicsResult:
    plan_year: int
    withdrawal_plan: WithdrawalPlan
    conversion: ConversionResult
    ending_balances: AccountBalances
    ordinary_income: float
    figures_used: list[FigureUsage]
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## Operations (`rmd`)

```python
def compute_rmd(
    traditional_balance: float,
    member_age: int,
    tax_year: int,
    spouse_age: int | None = None,
    spouse_is_sole_beneficiary: bool = False,
) -> RmdResult:
    """Computes one household member's RMD for tax_year (FR-001–FR-003).
    Uses the Joint Life and Last Survivor Table instead of the Uniform
    Lifetime Table when spouse_is_sole_beneficiary is True and
    member_age - spouse_age > 10 (FR-002). Returns required_amount=0,
    table_used=None when member_age is below that year's RMD-required
    starting age, or traditional_balance <= 0 (FR-003). Raises
    UnsupportedTaxYearError if the RMD-required starting age, or the
    divisor table actually needed, has no entry for tax_year."""
```

`RMD_START_AGE: SourcedFigure[int]`, `UNIFORM_LIFETIME_TABLE: SourcedFigure[dict[int, float]]`, and `JOINT_LIFE_TABLE: SourcedFigure[dict[tuple[int, int], float]]` are module-level constants in `rmd.py` — internal implementation detail, not part of this contract's call surface, but their citation/verification metadata is what populates `RmdResult.figures_used` (FR-019).

## Operations (`withdrawal_sequencing`)

```python
WITHDRAWAL_STRATEGIES: dict[str, tuple[AccountType, ...]]
"""Registry mapping a strategy name to the non-RMD account-type draw
order (FR-005). Currently populated: "rmd_taxable_traditional_roth" ->
("taxable", "traditional", "roth") — the shipped default. Adding a new
strategy means adding one tuple + one registry entry here — nothing
else in this package changes (SC-006)."""


def compute_withdrawal_plan(
    spending_need: float,
    rmd_amount: float,
    starting_balances: AccountBalances,
    strategy: str = "rmd_taxable_traditional_roth",
) -> WithdrawalPlan:
    """Draws rmd_amount from starting_balances.traditional first
    (FR-004), unconditionally — this leg is not part of the configured
    ordering. If spending_need is already met by rmd_amount, no further
    draws occur (Acceptance Scenario US2.2). Otherwise draws the
    remaining need from account types in the order WITHDRAWAL_STRATEGIES[strategy]
    specifies, never exceeding an account's available balance (FR-006);
    once an account type is exhausted, the unmet remainder moves to the
    next type in the sequence. If total available balance across all
    account types (including rmd_amount's traditional draw) is less
    than spending_need, the unmet amount is reported as shortfall and no
    balance goes negative (FR-007). Raises KeyError if strategy has no
    registered ordering."""
```

## Operations (`roth_conversion`)

```python
RothConversionFunction = Callable[
    [float, float, FilingStatus, int, float, float, float],  # (ordinary_income_established,
                                                               #  social_security_gross_benefit,
                                                               #  filing_status, tax_year,
                                                               #  traditional_balance, roth_balance,
                                                               #  bracket_ceiling_or_amount)
    ConversionResult,
]

CONVERSION_STRATEGIES: dict[str, RothConversionFunction]
"""Registry mapping a strategy name to that strategy's compute function
(FR-014). Currently populated: "fill_to_bracket" -> fill_to_bracket_ceiling,
"fixed_amount" -> fixed_dollar_amount. Adding a new strategy means adding
one function + one registry entry here — nothing else in this package
changes (SC-006)."""


def fill_to_bracket_ceiling(
    ordinary_income_established: float,
    social_security_gross_benefit: float,
    filing_status: FilingStatus,
    tax_year: int,
    traditional_balance: float,
    roth_balance: float,
    ceiling: float,
) -> ConversionResult:
    """Calls retirement_planner.tax.social_security.compute_taxable_social_security()
    (FR-015) to determine taxable Social Security given
    ordinary_income_established, then converts min(traditional_balance,
    max(0, ceiling - (ordinary_income_established + taxable_social_security)))
    (FR-009, Acceptance Scenario US3.5). figures_used carries the
    Social Security figures consulted. ending_roth_balance = roth_balance +
    amount_converted (roth_balance added during implementation — see the
    note at the top of this document)."""


def fixed_dollar_amount(
    ordinary_income_established: float,
    social_security_gross_benefit: float,
    filing_status: FilingStatus,
    tax_year: int,
    traditional_balance: float,
    roth_balance: float,
    fixed_amount: float,
) -> ConversionResult:
    """Converts min(traditional_balance, fixed_amount) (FR-010).
    Ignores ordinary_income_established, social_security_gross_benefit,
    filing_status, and tax_year — accepted only so every registered
    strategy shares an identical call signature. figures_used is always
    empty. ending_roth_balance = roth_balance + amount_converted."""


def compute_roth_conversion(
    plan_year: int,
    window: tuple[int, int] | None,
    strategy: str | None,
    bracket_ceiling_or_amount: float | None,
    ordinary_income_established: float,
    social_security_gross_benefit: float,
    filing_status: FilingStatus,
    tax_year: int,
    traditional_balance: float,
    roth_balance: float,
) -> ConversionResult:
    """Returns a zeroed ConversionResult (amount_converted=0,
    figures_used=[], ending_traditional_balance=traditional_balance,
    ending_roth_balance=roth_balance) without calling any strategy if
    window or strategy is None, or plan_year is outside [window[0],
    window[1]] inclusive (FR-008). Otherwise looks up
    CONVERSION_STRATEGIES[strategy] and calls it with roth_balance and
    bracket_ceiling_or_amount as the final positional arguments. Raises
    KeyError if strategy has no registered function."""
```

## Operations (`plan_year`)

```python
def compute_plan_year_mechanics(
    plan_year: int,
    tax_year: int,
    spending_need: float,
    starting_balances: AccountBalances,
    rmd_amount: float,
    social_security_gross_benefit: float,
    filing_status: FilingStatus,
    conversion_window: tuple[int, int] | None,
    conversion_strategy: str | None,
    conversion_bracket_ceiling_or_amount: float | None,
    withdrawal_strategy: str = "rmd_taxable_traditional_roth",
    rmd_figures_used: list[FigureUsage] | None = None,
) -> PlanYearMechanicsResult:
    """Orchestrates one plan year: calls compute_withdrawal_plan() first
    (rmd_amount is caller-supplied — typically the sum of one or more
    compute_rmd() calls, one per traditional-account-owning household
    member, since compute_rmd() is per-member while starting_balances is
    household-level; see data-model.md § AccountBalances), then, if
    conversion_window/conversion_strategy are not None, calls
    compute_roth_conversion() using the withdrawal plan's post-RMD
    ending traditional and Roth balances — never the pre-withdrawal
    balances — so RMD dollars are structurally excluded from conversion
    (FR-013, research.md §6). Returns None-conversion-plan callers a
    PlanYearMechanicsResult whose conversion field is a zeroed
    ConversionResult. figures_used = (rmd_figures_used or []) +
    conversion.figures_used — rmd_figures_used added during
    implementation so a caller with a compute_rmd() RmdResult in hand can
    pass its figures_used through (see the note at the top of this
    document)."""
```

## Consumption expectations for downstream features

- `compute_rmd()` does not read a `Scenario` (`001`) or attribute a household-level traditional balance to a specific member — a future integration feature is responsible for that attribution before calling `compute_rmd()` once per relevant household member (data-model.md § RmdResult, research.md §4).
- `compute_withdrawal_plan()` and `compute_roth_conversion()` accept `AccountBalances` and `RothConversionPlan`-shaped fields (`window`, `strategy`, `bracket_ceiling_or_amount`) that map directly onto `001`'s `Scenario.accounts` and `Scenario.roth_conversion` with no translation required — a caller with a loaded `Scenario` can pass those fields straight through (FR-016).
- `PlanYearMechanicsResult.ordinary_income` is the figure a caller should pass as `IncomeComponents.ordinary_income` into `002`'s `compute_federal_tax()`/`compute_state_tax()` for the same plan year — this feature does not call those itself (beyond the Social Security taxability call inside `fill_to_bracket_ceiling`), leaving full tax computation to the caller.
- A future strategy-comparison feature (§3.4) calling `compute_withdrawal_plan()` or `compute_roth_conversion()` repeatedly with different `strategy` values against the same starting inputs should expect fully independent, side-effect-free results each call (spec.md SC-003/SC-004) — neither function mutates its inputs or shares state across calls.
- `WITHDRAWAL_STRATEGIES` currently covers `"rmd_taxable_traditional_roth"` only (FR-005); `CONVERSION_STRATEGIES` currently covers `"fill_to_bracket"` and `"fixed_amount"` only (FR-008–FR-010). A downstream caller requesting any other strategy name should expect a lookup failure, not a silently-wrong result, until that strategy is added as follow-on work.
