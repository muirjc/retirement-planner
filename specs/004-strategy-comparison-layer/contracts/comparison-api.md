# Contract: `retirement_planner.comparison` public API

This is a library, not a network service — the "contract" is the public Python interface this feature exposes for later features (§3.5 Simulation Engine, §3.6 Reporting) to import and build on. Anything not listed here is an internal implementation detail; anything listed here is what downstream features should code against.

Module: `retirement_planner.comparison` (re-exports from `models`, `returns`, `projection`, `compare` — see [plan.md](../plan.md) Project Structure).

## Data types (`models`)

```python
@dataclass
class DeterministicReturnAssumption:
    annual_real_return: float

@dataclass
class StrategyConfiguration:
    label: str
    withdrawal_strategy: str
    conversion_strategy: str | None
    conversion_bracket_ceiling_or_amount: float | None
    conversion_window: tuple[int, int] | None
    claiming_ages: dict[str, int]   # person_name -> claiming age

@dataclass
class PlanYearProjection:
    plan_year: int
    tax_year: int
    mechanics: PlanYearMechanicsResult   # from retirement_planner.mechanics
    federal_tax: FederalTaxResult         # from retirement_planner.tax
    state_tax: StateTaxResult
    tax_funding_withdrawal: WithdrawalPlan  # from retirement_planner.mechanics
    starting_balances: AccountBalances
    ending_balances: AccountBalances
    shortfall: float
    figures_used: list[FigureUsage]

@dataclass
class PlanOutcome:
    ending_balance: float
    first_shortfall_plan_year: int | None
    cumulative_tax_paid: float

@dataclass
class PlanProjection:
    strategy: StrategyConfiguration
    return_assumption: DeterministicReturnAssumption
    years: list[PlanYearProjection]
    outcome: PlanOutcome

ComparisonDimension = Literal["roth_conversion_strategy", "withdrawal_sequencing", "claiming_age_grid"]

@dataclass
class ComparisonResult:
    dimension: ComparisonDimension
    return_assumption: DeterministicReturnAssumption
    projections: list[PlanProjection]
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## Operations (`returns`)

```python
def derive_deterministic_return(
    market_assumptions: MarketAssumptions,  # from retirement_planner.scenario
) -> DeterministicReturnAssumption:
    """Returns the allocation-weighted blend of equity_return_mean_real
    and bond_return_mean_real (FR-003, research.md §1). Ignores both
    std_real fields and correlation entirely — this is a fixed value,
    not a distribution to sample from."""
```

## Operations (`projection`)

```python
def run_plan_projection(
    household: Household,                    # from retirement_planner.scenario
    accounts: AccountBalances,                # from retirement_planner.mechanics
    annual_spending_need: float,
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    strategy: StrategyConfiguration,
    return_assumption: DeterministicReturnAssumption,
) -> PlanProjection:
    """Runs one full-horizon projection, one plan year at a time, from
    start_plan_year through the plan year in which the older household
    member reaches plan_to_age (inclusive) (FR-001, FR-002). Each plan
    year:
      1. Translates every household member's age for this tax_year from
         reference_tax_year (research.md §2).
      2. Computes the household's total gross Social Security benefit
         for this year from each member's ss_annual_benefit and this
         strategy's claiming_ages (research.md, data-model.md § Relationships).
      3. Calls retirement_planner.mechanics.compute_rmd() once, against
         the older member's translated age and the current traditional
         balance, with spouse_is_sole_beneficiary=False always
         (research.md §3-4) -- the deemed sole owner for RMD purposes.
      4. Calls retirement_planner.mechanics.compute_plan_year_mechanics()
         with that rmd_amount, annual_spending_need, the year's starting
         balances, and this strategy's withdrawal_strategy/
         conversion_strategy/conversion_window/
         conversion_bracket_ceiling_or_amount -- passing tax_year (the
         calendar year) as compute_plan_year_mechanics()'s own `plan_year`
         argument, since conversion_window is calendar-year-based (001's
         Scenario.roth_conversion.window) and compute_roth_conversion()
         checks window membership against that argument, not against this
         function's own sequential plan_year counter (implementation
         note, added during /speckit-implement).
      5. Calls retirement_planner.tax.compute_federal_tax() and
         compute_state_tax() with IncomeComponents(ordinary_income=
         mechanics_result.ordinary_income, social_security_gross_benefit=
         <step 2's total>) for this tax_year (FR-001).
      6. Calls compute_withdrawal_plan() a second time -- spending_need=
         federal_tax_owed + state_tax_owed, rmd_amount=0, starting_balances=
         mechanics_result.ending_balances, strategy=strategy.withdrawal_strategy
         -- to fund the year's tax bill (research.md §5).
      7. Applies return_assumption.annual_real_return to every account
         type in the tax-funding withdrawal's ending_balances to produce
         next year's starting_balances (research.md §6); a shortfall in
         either draw floors the affected account type at 0, never negative
         (research.md §7), and the year's shortfall is recorded regardless
         of whether the projection continues.
    Returns a PlanProjection whose outcome is derived from the assembled
    years list. Raises KeyError if strategy.withdrawal_strategy or
    strategy.conversion_strategy names an unregistered strategy (per
    003's compute_withdrawal_plan()/compute_roth_conversion() contracts).
    Raises UnsupportedTaxYearError if any tax_year in the horizon has no
    entry for a figure 002 or 003 needs (per those contracts)."""
```

## Operations (`compare`)

```python
def compare_roth_conversion_strategies(
    household: Household,
    accounts: AccountBalances,
    annual_spending_need: float,
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    withdrawal_strategy: str,
    claiming_ages: dict[str, int],
    return_assumption: DeterministicReturnAssumption,
    candidates: list[StrategyConfiguration],
) -> ComparisonResult:
    """Calls run_plan_projection() once per entry in candidates, holding
    every argument above (withdrawal_strategy, claiming_ages,
    return_assumption, and every other scenario input) fixed across all
    of them -- only each candidate's conversion_strategy/
    conversion_bracket_ceiling_or_amount/conversion_window differs
    (FR-005, FR-009). Returns a ComparisonResult with
    dimension="roth_conversion_strategy". Every candidate's
    withdrawal_strategy and claiming_ages fields are overwritten with
    this call's withdrawal_strategy/claiming_ages before running, so a
    caller cannot accidentally vary more than the conversion dimension
    within one call."""


def compare_withdrawal_sequencing_strategies(
    household: Household,
    accounts: AccountBalances,
    annual_spending_need: float,
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    conversion_strategy: str | None,
    conversion_bracket_ceiling_or_amount: float | None,
    conversion_window: tuple[int, int] | None,
    claiming_ages: dict[str, int],
    return_assumption: DeterministicReturnAssumption,
    candidates: list[StrategyConfiguration],
) -> ComparisonResult:
    """Calls run_plan_projection() once per entry in candidates, holding
    every argument above fixed -- only each candidate's
    withdrawal_strategy differs (FR-006, FR-009). Requires len(candidates)
    to name at least one withdrawal_strategy beyond 003's shipped default
    for the comparison to be meaningful (FR-007); does not enforce this
    itself -- a single-candidate call still returns a valid
    ComparisonResult per FR-011. Returns a ComparisonResult with
    dimension="withdrawal_sequencing"."""


def compare_claiming_age_grid(
    household: Household,
    accounts: AccountBalances,
    annual_spending_need: float,
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    withdrawal_strategy: str,
    conversion_strategy: str | None,
    conversion_bracket_ceiling_or_amount: float | None,
    conversion_window: tuple[int, int] | None,
    return_assumption: DeterministicReturnAssumption,
    claiming_age_grid: list[dict[str, int]],
) -> ComparisonResult:
    """Calls run_plan_projection() once per entry in claiming_age_grid,
    holding every argument above fixed -- only each entry's per-member
    claiming ages differ (FR-008, FR-009). Raises ValueError if any
    claiming age in any grid entry falls outside the household-configured
    claiming-age bounds (62-70 inclusive, per 001's validation bounds)
    (FR-010, Edge Cases). Returns a ComparisonResult with
    dimension="claiming_age_grid"."""
```

## Consumption expectations for downstream features

- `run_plan_projection()` is the single entry point a future Simulation Engine feature (§3.5) will call once per Monte Carlo path per candidate, substituting a randomly-drawn per-year return sequence for `return_assumption` — this contract's per-year steps (RMD → mechanics → tax → tax-funding withdrawal → growth) do not change shape when that happens, only where `return_assumption` comes from (research.md §1).
- `ComparisonResult.projections` preserves the order `candidates` (or `claiming_age_grid`) were supplied in — a downstream reporting feature (§3.6) rendering a table or chart should not need to re-sort or re-match candidates by inspecting their `StrategyConfiguration` fields.
- `PlanYearProjection.figures_used` is the single place a downstream reporting feature should look to render "needs verification" flags for a projected year, mirroring `002`'s and `003`'s existing `figures_used` convention (FR-013) — it is a union, not a fresh derivation, so it never drops a flag either of those features already raised.
- A caller needing a withdrawal-sequencing or Roth-conversion strategy this feature and `003` don't already register should expect a `KeyError`, not a silently-wrong result, until that strategy is added as follow-on work (mirrors `003`'s own consumption note).
- `compare_claiming_age_grid()`'s `claiming_age_grid` parameter is caller-constructed — this module does not itself enumerate the full 62-70 x 62-70 combination set; a caller wanting the full grid (spec.md US4) builds it via `itertools.product(range(62, 71), range(62, 71))` and maps each pair onto `{person_name: age, ...}` before calling.
