# Contract: `retirement_planner.mechanics` public API (addendum to `003`, `010`)

Extends `specs/003-retirement-account-mechanics/contracts/mechanics-api.md` with one new module (`inherited_rmd`), two new data types, one modified data type, and additive optional parameters on two existing functions. `compute_rmd()` (`rmd.py`) is untouched — its locked signature and behavior carry forward exactly as `003` defined them.

## New data types (`models`)

```python
@dataclass
class InheritedRmdResult:
    required_amount: float
    table_used: Literal["single_life_expectancy"] | None
    divisor: float | None
    figures_used: list[FigureUsage] = field(default_factory=list)
    depletion_deadline_year: int | None = None
    is_within_ten_year_window: bool = True

@dataclass
class InheritedAccountBalance:
    account_id: str
    balance: float
    death_year: int
    decedent_age_at_death: int
    depletion_deadline_year: int
```

## Modified data type (`models`)

```python
@dataclass
class WithdrawalPlan:
    rmd_drawn: float
    sequence_withdrawals: list[WithdrawalLineItem]
    ending_balances: AccountBalances
    shortfall: float
    inherited_distribution_drawn: float = 0.0   # NEW — see data-model.md / research.md §10
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## New operations (`inherited_rmd`)

```python
def compute_inherited_rmd(
    inherited_balance: float,
    tax_year: int,
    death_year: int,
    decedent_age_at_death: int,
    decedent_was_taking_rmds: bool,
    beneficiary_classification: Literal[
        "eligible_designated_beneficiary_spouse",
        "eligible_designated_beneficiary_other",
        "non_eligible_designated_beneficiary",
    ],
) -> InheritedRmdResult:
    """Computes one inherited traditional account's required distribution
    for tax_year, for the case decedent_was_taking_rmds=True and
    beneficiary_classification="non_eligible_designated_beneficiary"
    (research.md §2, §3) — the only case this function actually computes;
    callers are responsible for not invoking it for any other combination
    (guaranteed by scenario.validation's blocking flags before this is
    ever reached from run_plan_projection()). Looks up the decedent's
    Single Life Expectancy divisor at decedent_age_at_death for
    death_year + 1, then reduces it by exactly 1.0 for each subsequent
    tax_year (research.md §7) — never a fresh table lookup keyed by a
    later year. required_amount = inherited_balance / divisor.
    depletion_deadline_year = death_year + 10;
    is_within_ten_year_window = tax_year <= depletion_deadline_year.
    Returns required_amount=0.0, table_used=None, divisor=None when
    inherited_balance <= 0. Raises UnsupportedTaxYearError if the
    Single Life Expectancy Table has no entry for the divisor year
    needed. This function does not itself enforce the 10-year forced
    full-depletion draw — that is the caller's responsibility
    (data-model.md § Consumption); it only reports
    is_within_ten_year_window/depletion_deadline_year for the caller's
    own use."""
```

`SINGLE_LIFE_EXPECTANCY_TABLE: SourcedFigure[dict[int, float]]` is a module-level constant in `inherited_rmd.py` (IRS Pub. 590-B Table I, partial/illustrative coverage, `verified=False`) — internal implementation detail, not part of this contract's call surface, but its citation/verification metadata is what populates `InheritedRmdResult.figures_used`.

## Modified operations (`withdrawal_sequencing`)

```python
def compute_withdrawal_plan(
    spending_need: float,
    rmd_amount: float,
    starting_balances: AccountBalances,
    strategy: str = "rmd_taxable_traditional_roth",
    inherited_distribution_amount: float = 0.0,   # NEW
) -> WithdrawalPlan:
    """Unchanged behavior for rmd_amount/starting_balances/strategy
    (003's contract). inherited_distribution_amount (research.md §10):
    an amount already distributed from one or more inherited accounts
    this same plan year, tracked entirely outside starting_balances —
    reduces remaining_need exactly like rmd_drawn already does
    (remaining_need = spending_need - rmd_drawn - inherited_distribution_amount)
    but is never subtracted from starting_balances.traditional (it was
    never part of that pooled balance). Returned WithdrawalPlan's
    inherited_distribution_drawn field is set to exactly
    inherited_distribution_amount (never capped — the caller has
    already confirmed it does not exceed the source inherited
    account's own balance before calling this function). Defaults to
    0.0, reproducing every existing caller's exact current behavior."""
```

## Modified operations (`plan_year`)

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
    hsa_contribution: HsaContributionResult | None = None,
    inherited_distribution_amount: float = 0.0,             # NEW
    inherited_rmd_figures_used: list[FigureUsage] | None = None,  # NEW
) -> PlanYearMechanicsResult:
    """Unchanged behavior for every existing parameter (003's contract,
    010's hsa_contribution addition). inherited_distribution_amount/
    inherited_rmd_figures_used (research.md §10): passed straight
    through to compute_withdrawal_plan() as its own new parameter of the
    same name; ordinary_income_established becomes
    withdrawal_plan.rmd_drawn + traditional_draws +
    withdrawal_plan.inherited_distribution_drawn (was: the first two
    terms only). figures_used gains
    (inherited_rmd_figures_used or []) as a fourth unioned source,
    alongside rmd_figures_used, conversion.figures_used, and
    hsa_contribution's figures_used. Both new parameters default such
    that omitting them reproduces this function's exact prior behavior
    unchanged."""
```

## Consumption expectations for downstream features

- `compute_inherited_rmd()` does not read a `Scenario` (`001`) or an `Account` — a caller (`004`'s `run_plan_projection()`) is responsible for building one `InheritedAccountBalance` per inherited account and calling this function once per such account per plan year (data-model.md § Consumption).
- `InheritedAccountBalance.balance` is mutable runtime state a caller updates in place (distribution subtracted, then growth applied) across plan years — this package does not persist or mutate it itself; every function in this package remains a pure, side-effect-free computation over its explicit arguments, matching every existing function's own discipline (`003`'s spec.md SC-003/SC-004).
- A future comparison/simulation feature repeatedly calling `compute_withdrawal_plan()`/`compute_plan_year_mechanics()` with different `inherited_distribution_amount` values across otherwise-identical inputs should expect fully independent, side-effect-free results each call — neither function mutates its inputs or shares state across calls, unchanged from `003`'s original guarantee.
