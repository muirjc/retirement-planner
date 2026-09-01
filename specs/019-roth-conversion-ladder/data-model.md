# Data Model: Roth Conversion Ladder (Five-Year Rule) Tracking

## New: `RothConversionLot` (`retirement_planner.mechanics`)

```python
@dataclass
class RothConversionLot:
    """One Roth conversion actually executed during a projection --
    tracked independently of the household's pooled AccountBalances.roth
    total, never folded into that pooled arithmetic itself.
    compute_roth_ladder_consumption() (mechanics, pure) never mutates an
    instance of this type -- it returns a fresh, updated list;
    run_plan_projection() (comparison) reassigns its own local list to
    that result, mirroring how compute_inherited_rmd() never mutates
    InheritedAccountBalance.balance itself either (012 contracts/
    mechanics-api.md's package-wide purity guarantee). 019-roth-
    conversion-ladder data-model.md § RothConversionLot."""

    conversion_tax_year: int
    balance: float
```

- `conversion_tax_year`: the tax year `compute_roth_conversion()` actually executed this
  conversion — immutable once created. Used by `compute_roth_ladder_consumption()` to determine
  whether 5 full tax years have elapsed (`ROTH_CONVERSION_SEASONING_YEARS`).
- `balance`: this lot's own remaining (not-yet-drawn) amount, starting at the full amount converted
  and decremented (in a fresh returned instance, research.md Decision 5) as
  `run_plan_projection()`'s per-year attribution consumes it. A lot whose `balance` reaches `0.0`
  is simply skipped by future attribution (Edge Cases) — never removed from the list (mirrors
  `InheritedAccountBalance`'s own "depleted but still present" precedent, `012` data-model.md), so
  a caller inspecting the full lot history mid-projection still sees it.
- Created only by `run_plan_projection()` itself, immediately after a plan year's own
  `compute_roth_conversion()` call reports `amount_converted > 0` (research.md Decision 3, step 5)
  — never constructed from a scenario input (there is no such input; FR-002).

## New: `RothLadderConsumptionResult` (`retirement_planner.mechanics`)

```python
@dataclass
class RothLadderConsumptionResult:
    """One plan year's attribution of a Roth withdrawal across the
    assumed-already-seasoned portion and any tracked conversion lots --
    a pure function's result; compute_roth_ladder_consumption() itself
    never mutates the lots list it was called with (research.md Decision
    5). 019-roth-conversion-ladder data-model.md §
    RothLadderConsumptionResult."""

    updated_lots: list[RothConversionLot]
    unseasoned_amount_flagged: float
    figures_used: list[FigureUsage] = field(default_factory=list)
```

- `updated_lots`: a fresh list, structurally the same length and order as the `lots` argument
  passed in, with each consumed lot's own `balance` reduced by whatever this plan year's draw
  attributed to it (an untouched lot's own instance may be reused unchanged). The caller
  (`run_plan_projection()`) reassigns its own local `roth_conversion_lots` to this value.
- `unseasoned_amount_flagged`: the portion of this plan year's Roth draw that was sourced from a
  not-yet-seasoned lot while the age condition (FR-005/FR-006) was active — `0.0` whenever no such
  draw occurred, the draw stayed within the non-lot/already-seasoned amount, every touched lot was
  already seasoned, or every household member had cleared the age condition. Never a computed
  penalty — a plain dollar amount describing *what was touched*, not *what it costs* (FR-007).
- `figures_used`: carries `ROTH_CONVERSION_SEASONING_YEARS`'s usage whenever a lot's seasoning was
  actually consulted this year (research.md Decision 4), independent of whether a flag actually
  resulted.

## New: `ROTH_CONVERSION_SEASONING_YEARS` (`retirement_planner.mechanics.roth_conversion_ladder`)

A `SourcedFigure[int]`, mirroring `RMD_START_AGE`'s own shape — `schedule` maps every documented
tax year to `5` (26 U.S.C. §408A(d)(3)(F); Treas. Reg. §1.408A-6, Q&A-5 — the number of tax years
that must elapse from a conversion's own tax year before that conversion's principal is treated as
if it had always been a regular contribution for early-withdrawal-penalty purposes). Cross-checked
against the primary source at implementation time before `verified=True` is set, per the
constitution's verified-figure gate.

## Modified: `PlanYearProjection` (`retirement_planner.comparison`)

```python
@dataclass
class PlanYearProjection:
    # ... every existing field, unchanged ...
    unseasoned_roth_withdrawal: float = 0.0   # NEW
```

- `unseasoned_roth_withdrawal`: this plan year's own `RothLadderConsumptionResult.unseasoned_amount_flagged`
  (data-model.md above) — `0.0` for every plan year this feature doesn't flag, which is every plan
  year for a household with no Roth conversion configured at all (FR-008) and every plan year
  before a flag-worthy draw occurs. Always populated by `run_plan_projection()`; the `0.0` default
  only matters if some other caller constructs a `PlanYearProjection` directly without setting it
  (mirrors every other additive `PlanYearProjection` field's own default-value precedent, e.g.
  `018`'s `effective_spending_need`).

## Derived (computed by `run_plan_projection()`, not stored on any dataclass)

- **`roth_conversion_lots`**: a `list[RothConversionLot]`, local to one `run_plan_projection()`
  call — never a parameter, never returned, never shared across calls (research.md Decision 2).
  Starts empty at the top of every call; grows by one entry per plan year with a positive
  conversion (appended directly); reassigned wholesale to `compute_roth_ladder_consumption()`'s own
  `updated_lots` result every plan year a draw occurs (research.md Decision 5) — each entry's own
  `balance` only ever decreases across that sequence of reassignments.
- **`non_lot_roth_balance`** (one plan year): `current_balances.roth` (that year's starting pooled
  Roth balance) minus the sum of every open lot's own `balance`, clamped to `>= 0.0`. Represents
  the assumed-already-seasoned, freely-accessible portion (FR-002) — the household's original
  pre-existing balance plus, implicitly, whatever a since-seasoned lot's balance effectively
  behaves like once fully consumed by this feature's own oldest-first attribution (a seasoned lot's
  balance is still tracked as its own lot, not folded back into "non-lot," but it is simply never
  flagged once seasoned — see `compute_roth_ladder_consumption()`'s own seasoning check per lot,
  not a one-time reclassification).
- **`age_condition_active`** (one plan year): `True` whenever any household member's translated age
  that plan year is 59 or younger (spec.md Edge Cases); the feature's own FR-005/FR-006 gate.

## Relationships

- `RothConversionLot` instances are created from, and only from,
  `PlanYearMechanicsResult.conversion.amount_converted` (an existing field, unmodified) — this
  feature reads that value, it does not change how it's computed.
- `PlanYearProjection.unseasoned_roth_withdrawal` and `PlanYearProjection.member_social_security_benefits`
  (from `018`) are independent — a household can be flagged by this feature while completely
  unaffected by `018`'s survivor-scenario switch, and vice versa; nothing here reads or writes
  `018`'s own fields.
