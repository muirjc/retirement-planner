# Data Model: Advanced Tax & Benefits Modeling

Source: [spec.md](./spec.md) Key Entities, resolved against research.md's design decisions and the actual shape of `001`'s `Scenario`/`HouseholdMember`, `002`'s `SourcedFigure`/`FigureUsage`, `003`'s `PlanYearMechanicsResult`, and `004`'s `PlanYearProjection`/`PlanOutcome` (all read directly during planning). Every type below is either a small, additive extension of an already-locked type, or a new result type following an existing subpackage's own established shape.

## Scenario input extensions (`retirement_planner.scenario`)

```python
@dataclass
class HouseholdMember:
    person_name: str
    current_age: int
    ss_claim_age: int
    ss_annual_benefit: float
    hdhp_coverage: bool = False   # NEW -- whether this member is covered by a
                                  # qualifying high-deductible health plan (the
                                  # HSA-eligibility precondition), independent of
                                  # any other member's coverage or Medicare status

@dataclass
class HsaContributionPlan:        # NEW -- mirrors RothConversionPlan's own
                                   # optional-block shape exactly (001's own
                                   # precedent: an opaque block this feature owns
                                   # the interpretation of)
    annual_amount: float          # the household's intended combined annual
                                   # HSA contribution, in years any member is eligible

@dataclass
class Scenario:
    # ...every existing field unchanged...
    roth_conversion: RothConversionPlan | None = None
    hsa_contribution: HsaContributionPlan | None = None   # NEW, defaults to
                                                            # "not modeled"
    validation_flags: list[ValidationFlag] = field(default_factory=list)
```

Both new fields default to values that reproduce every existing scenario's current behavior exactly — no saved scenario or test fixture changes meaning.

## Tax result extensions (`retirement_planner.tax`)

```python
@dataclass
class IrmaaTierRow:
    magi_threshold: float              # lower bound, inclusive (research.md,
                                        # Edge Cases: at-or-above triggers the tier)
    annual_surcharge_per_person: float # combined Part B + Part D, already
                                        # annualized to match this engine's own
                                        # annual-dollar convention throughout

IrmaaTierTable = tuple[IrmaaTierRow, ...]  # ascending by magi_threshold; a MAGI
                                            # below every row's threshold means $0

@dataclass
class IrmaaResult:
    magi: float
    income_basis: Literal["two_year_lookback", "current_year_proxy"]  # research.md §3
    tier_crossed: float | None          # the magi_threshold of the tier applied,
                                         # or None if MAGI is below every tier
    enrolled_member_count: int          # how many household members' premiums
                                         # this surcharge reflects (FR-003)
    surcharge_owed: float               # annual_surcharge_per_person * enrolled_member_count
    figures_used: list[FigureUsage]

@dataclass
class NiitResult:
    magi: float
    investment_income: float            # research.md §1's taxable-withdrawal proxy
    threshold_exceeded: bool
    surtax_owed: float                  # 0.0 if not exceeded; otherwise rate *
                                         # min(investment_income, magi - threshold)
                                         # -- the lesser-of rule IRC §1411 actually uses
    figures_used: list[FigureUsage]
```

## Mechanics result extensions (`retirement_planner.mechanics`)

```python
@dataclass
class HsaEligibility:
    person_name: str
    age: int               # NEW, added during implementation (T022) --
                           # compute_hsa_contribution() needs each eligible
                           # member's age for 55+ catch-up determination and
                           # this is the only place that fits without a
                           # second, easy-to-desync parameter
    eligible: bool
    reason: str | None    # populated when eligible=False (no HDHP coverage /
                           # Medicare-enrolled), for a caller/report to explain why

@dataclass
class HsaContributionResult:
    eligible_members: list[HsaEligibility]   # every household member's
                                              # eligibility determination this year
    applicable_limit: float                  # self-only or family limit + any
                                              # 55+ catch-up, for this year's
                                              # eligible member count
    amount_contributed: float                # min(configured annual_amount,
                                              # applicable_limit), or 0.0
    rejected_reason: str | None              # populated when amount_contributed
                                              # is 0.0 or capped below the
                                              # configured amount (research.md §5)
    figures_used: list[FigureUsage]
```

## Projection extensions (`retirement_planner.comparison`)

```python
@dataclass
class StrategyConfiguration:
    # ...every existing field unchanged...
    claiming_ages: dict[str, int]
    hsa_contribution: HsaContributionPlan | None = None  # NEW -- the held-fixed
        # value every compare_*() function forces onto every candidate, the same
        # way withdrawal_strategy/claiming_ages already are (contracts/comparison-api.md)

@dataclass
class PlanYearProjection:
    # ...every existing field unchanged...
    irmaa: IrmaaResult              # NEW
    niit: NiitResult                # NEW
    hsa_contribution: HsaContributionResult  # NEW
    figures_used: list[FigureUsage] = field(default_factory=list)  # already
        # includes irmaa/niit/hsa_contribution's own figures_used, same
        # union pattern PlanYearProjection already uses for mechanics/federal_tax/state_tax

@dataclass
class PlanOutcome:
    ending_balance: float
    first_shortfall_plan_year: int | None
    cumulative_tax_paid: float           # UNCHANGED meaning -- federal + state
                                          # income tax only (research.md §6)
    cumulative_irmaa_paid: float         # NEW
    cumulative_niit_paid: float          # NEW
```

## New `SourcedFigure` schedules

Three new schedule-by-year figures, each following `federal.py`'s exact existing shape (illustrative placeholder values, `verified=False`, a citation naming the real primary source, `last_verified` set honestly to today):

| Figure | Shape | Citation target |
|---|---|---|
| IRMAA tier table, by filing status | `SourcedFigure[IrmaaTierTable]` | CMS.gov's published IRMAA premium tables |
| NIIT threshold, by filing status | `SourcedFigure[float]` | IRC §1411 |
| NIIT rate | `SourcedFigure[float]` (flat 3.8%, scheduled the same way for consistency even though it rarely changes) | IRC §1411 |
| HSA contribution limits (self-only, family, 55+ catch-up) | `SourcedFigure[HsaLimits]` (a small dataclass bundling the three amounts for one year) | IRS Rev. Proc. (annual HSA limits announcement) |

## Reporting extension (`retirement_planner.reporting`, T031)

`006-reporting-aggregation`'s `SummaryStatistics` gains two new fields, `median_lifetime_irmaa_paid: float` and `median_lifetime_niit_paid: float` — derived exactly the way `median_lifetime_tax_paid` already is (the median across a Monte Carlo run's paths' `PlanOutcome.cumulative_irmaa_paid`/`cumulative_niit_paid`, or the single value directly for a deterministic candidate), and exported as two additional CSV columns following the same pattern as every existing `SummaryStatistics` field. Found necessary during implementation (T031) once translating "these figures must be reported separately" (spec.md FR-002/FR-006) into an actual CSV column required a `SummaryStatistics` field to source it from, not just the raw `PlanOutcome` fields `004`'s projection already carries.

## Validation rules

- `hdhp_coverage` and `hsa_contribution` carry no `001`-level validation beyond shape (mirroring `roth_conversion`'s own precedent) — this feature's own compute functions are what interpret and reject/cap values at plan-year granularity (research.md §5), not `001`'s scenario-load-time `validate()`.
- An IRMAA tier boundary is inclusive at its lower bound: a MAGI exactly equal to `magi_threshold` triggers that tier (Edge Cases).
- `NiitResult.surtax_owed` is computed against the *lesser* of investment income and the amount MAGI exceeds the threshold by — never against the full investment income once any threshold is crossed, matching how the real surtax is actually bounded.
- `HsaContributionResult.applicable_limit` for a given plan year depends on how many household members have `hdhp_coverage=True` *and* are otherwise eligible that year (family limit if 2+, self-only if exactly 1, `0.0` if none), plus a per-eligible-member catch-up addition for members 55+.

## Relationships

- `run_plan_projection()` (`004`) computes `IrmaaResult`/`NiitResult` immediately after `federal_tax`/`state_tax` for a plan year, since both need that year's already-assembled income figures; it computes `HsaContributionResult` (from `strategy.hsa_contribution`, when not `None`) alongside `compute_plan_year_mechanics()`, since an HSA contribution reduces that same year's `ordinary_income` the same way a Roth conversion already does. `run_plan_projection()`'s own signature is unchanged — `hsa_contribution` arrives as a new field on the `strategy: StrategyConfiguration` parameter it already takes (contracts/comparison-api.md's correction note).
- `005-simulation-engine`'s public signatures need no change — `run_simulation()` and its own 4 `compare_*()` functions all pass `strategy`/`candidates: list[StrategyConfiguration]` straight through already. Each of `004`'s 3 and `005`'s 4 `compare_*()` functions needs one small *internal* addition: forcing `hsa_contribution` onto every candidate before running, the same way each already forces `withdrawal_strategy`/`claiming_ages` (contracts/comparison-api.md).
- `007-bff-api-service`'s JSON responses need no code change — `to_jsonable()` recurses generically over dataclass fields (confirmed directly from `serialization.py` during planning). Its *request* schema (`schemas.py`) needs the two new optional scenario input fields added, mirroring `scenario/models.py` exactly, and `resolve_run_context()` (`resolution.py`) needs to resolve `Scenario.hsa_contribution` into the `StrategyConfiguration` it already builds there — the same way it already resolves `Scenario.roth_conversion` into that object's conversion fields.
- `006-reporting-aggregation`'s CSV export functions gain additive columns for `cumulative_irmaa_paid`/`cumulative_niit_paid`, following the same column-per-`PlanOutcome`-field pattern already in place for `cumulative_tax_paid`.
- `apps/streamlit_ui` (`008`) needs no change for this feature's own functional requirements to be satisfied — the new figures are visible via CSV export and the JSON API's existing generic serialization. A dedicated UI display is an explicit follow-on, not part of this feature (plan.md's own Structure Decision).

## State transitions

None new. Every new result is a pure function of that plan year's already-assembled inputs (ages, income, filing status, HDHP coverage) plus, for IRMAA's look-back, two-years-prior data already present in the same projection's own accumulated `years` list — no new persisted state, no new cross-run memory.
